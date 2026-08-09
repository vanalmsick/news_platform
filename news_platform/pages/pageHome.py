# -*- coding: utf-8 -*-
"""Responaible for home view at base url /"""

import datetime
import traceback
import urllib.parse

from celery import chain
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Min
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template.defaulttags import register
from rest_framework.response import Response
from rest_framework.views import APIView

from articles.models import Article
from feed_scraper.article_scraper import find_grouped_articles, update_feeds
from feed_scraper.video_scraper import update_videos
from markets.scrape import scrape_market_data
from news_platform.celery import app
from preferences.models import Page, get_page_lst, url_parm_encode
from webpush.models import SubscriptionInfo

from .pageAPI import get_articles

# Key of the redis lock that serialises the refresh pipeline. `cache.add()` maps
# onto redis SETNX, so acquiring it is atomic across workers - unlike the old
# `inspect().active()` broadcast, which could not see a *chained* step running
# and silently failed open when no worker replied in time.
REFRESH_LOCK_KEY = "refresh_feeds_lock"
# The lock expires on its own so a hard-killed worker (OOM, SIGKILL) cannot wedge
# refreshing forever; it only has to outlive one full pipeline run.
REFRESH_LOCK_TIMEOUT = 60 * 60 * 3


@app.task(bind=True, time_limit=60 * 10, max_retries=5, ignore_result=True)  # 10 min time limit
def cleanup_webpush_subscriptions(self):
    """Cleanup multiple webpush subscriptions for same device"""
    # Step 1: Annotate each WebpushSubscriptionInfo with the minimum id for each group of auth and p256dh.
    duplicates = (
        SubscriptionInfo.objects.values("auth", "p256dh")
        .annotate(min_id=Min("id"), count_id=Count("id"))
        .filter(count_id__gt=1)
    )
    # Step 2: Collect the IDs of the entries with the lowest id in each group.
    min_ids_to_delete = [entry["min_id"] for entry in duplicates]
    # Step 3: Delete these entries.
    SubscriptionInfo.objects.filter(id__in=min_ids_to_delete).delete()

    return (
        "No duplicate webpush subscriptions"
        if len(min_ids_to_delete) == 0
        else f"Deleted these {len(min_ids_to_delete)} duplicate webpush subscriptions: {min_ids_to_delete}"
    )


@register.filter(name="split")
def split(value, key):
    """Django filter 'split'"""
    value.split("key")
    return value.split(key)


def refresh_all_pages():
    """reshresh all cached pages with force_recache=True"""
    cached_views_dict = cache.get("cached_views_lst", {})
    for k, v in get_page_lst().items():
        if k not in cached_views_dict:
            cached_views_dict[k] = v

    for view_hash, view_kwargs in cached_views_dict.items():
        # hydrate=False recomputes and re-caches the article ids without building
        # the model instances. Nothing here looks at the articles, and this runs
        # over every cached page twice per refresh cycle - previously that meant
        # loading (and pickling) thousands of full article rows for nothing.
        _, _, _ = get_articles(**view_kwargs, force_recache=True, hydrate=False)


def get_stats():
    """Get stats about number of articles/videos per publisher for relevance ranking"""
    added_date__lte_2d = settings.TIME_ZONE_OBJ.localize(datetime.datetime.now() - datetime.timedelta(days=2))
    added_date__lte_30d = settings.TIME_ZONE_OBJ.localize(datetime.datetime.now() - datetime.timedelta(days=30))

    all_articles = Article.objects.exclude(content_type="video").filter(pub_date__gte=added_date__lte_2d)
    all_videos = Article.objects.filter(content_type="video").filter(pub_date__gte=added_date__lte_30d)

    for content_type, query in [("art", all_articles), ("vid", all_videos)]:
        summary = (
            query.exclude(feedposition=None).values("feedposition__feed__publisher__pk").annotate(count=Count("pk"))
        )
        for i in summary:
            cache.set(
                f'feed_publisher_{content_type}_cnt_{i["feedposition__feed__publisher__pk"]}',
                i["count"],
                60 * 60 * 24,
            )
            print(
                f'There are currently {i["count"]} active {content_type}s from '
                f'feed__publisher__pk {i["feedposition__feed__publisher__pk"]}'
            )


def _set_currently_refreshing(state):
    """Publish the refresh state that the frontend polls via /api/last-refresh/"""
    cache.set("currentlyRefreshing", state, 60 * 60 * 2 + 300)


def _release_refresh_lock():
    """Drop the pipeline lock and mark refreshing as finished."""
    cache.delete(REFRESH_LOCK_KEY)
    _set_currently_refreshing(False)


# ---------------------------------------------------------------------------
# The refresh pipeline
#
# This used to be a single 3-hour task that scraped feeds, scraped videos,
# scraped market data, ran a sentence-transformer clustering pass and called the
# OpenAI API. Peak RSS was therefore the *union* of all of those - torch stayed
# resident alongside the scraped page buffers - and neither
# --max-tasks-per-child nor worker_max_memory_per_child can help with that,
# because both only act *between* tasks.
#
# Splitting it into a chain means each step runs in its own forked child, so the
# memory a step allocates is handed back to the OS before the next one starts,
# and the (by far heaviest) clustering step can be recycled on its own.
# ---------------------------------------------------------------------------


@app.task(bind=True, time_limit=60 * 60, max_retries=3)  # 1 hour time limit
def scrape_articles(self):
    """Pipeline step 1: refresh publisher stats, page caches and article feeds."""
    try:
        get_stats()
        # Caching articles before updating
        refresh_all_pages()
        added_articles = update_feeds()
        return f"articles refreshed successfully ({added_articles} added)"
    except Exception as e:
        print(traceback.format_exc())
        raise self.retry(countdown=60, exc=e)


@app.task(bind=True, time_limit=60 * 60, max_retries=3)  # 1 hour time limit
def scrape_videos(self):
    """Pipeline step 2: refresh video feeds, but only every 9th cycle."""
    video_refresh_cycle_count = cache.get("videoRefreshCycleCount")
    if video_refresh_cycle_count:
        print(f"Refreshing videos in {video_refresh_cycle_count - 1} cycles")
        cache.set("videoRefreshCycleCount", video_refresh_cycle_count - 1, 60 * 60 * 24)
        return "video refresh not required"

    try:
        update_videos()
        cache.set("videoRefreshCycleCount", 8, 60 * 60 * 24)
        return "videos refreshed successfully"
    except Exception as e:
        print(traceback.format_exc())
        raise self.retry(countdown=60, exc=e)


@app.task(bind=True, time_limit=60 * 20, max_retries=3)  # 20 min time limit
def scrape_markets(self):
    """Pipeline step 3: refresh stock/FX/commodity data (pulls in pandas)."""
    try:
        scrape_market_data()
        return "market data refreshed successfully"
    except Exception as e:
        print(traceback.format_exc())
        raise self.retry(countdown=60, exc=e)


@app.task(bind=True, time_limit=60 * 60, max_retries=1)  # 1 hour time limit
def group_articles(self):
    """Pipeline step 4: cluster articles about the same topic.

    Routed to the 'ml' queue (see celery.py) because this is the only task that
    imports torch/sentence-transformers. Isolating it keeps several hundred MB of
    model and framework RSS out of every other step.
    """
    try:
        find_grouped_articles()
        return "article groups refreshed successfully"
    except Exception as e:
        print(traceback.format_exc())
        raise self.retry(countdown=60, exc=e)


@app.task(bind=True, time_limit=60 * 20, max_retries=1)  # 20 min time limit
def finalise_refresh(self):
    """Pipeline step 5: re-cache every page and release the lock."""
    try:
        refresh_all_pages()
        now = settings.TIME_ZONE_OBJ.localize(datetime.datetime.now())
        cache.set("lastRefreshed", str(now.isoformat()), 60 * 60 * 48)
        print("refreshing finished")
        return "DONE"
    finally:
        # Runs even if re-caching blows up: the lock must never outlive the run.
        _release_refresh_lock()


@app.task(bind=True, ignore_result=True)
def refresh_failed(self, request, exc, traceback_str):
    """link_error handler - releases the lock when any pipeline step gives up."""
    failed_task = getattr(request, "task", "unknown task")
    print(f"Refresh pipeline step '{failed_task}' failed and will not be retried: {exc}")
    _release_refresh_lock()
    return f"ERROR: {exc}"


# @postpone
@app.task(bind=True, time_limit=60 * 5, max_retries=0, ignore_result=True)  # 5 min time limit
def refresh_feeds(self):
    """Entry point: dispatch the refresh pipeline if it is not already running.

    This task no longer does the work itself - it only takes the lock and queues
    the chain, so it returns in milliseconds instead of holding a worker child
    (and everything that child allocated) for up to three hours.
    """
    print("refreshing started")

    if not cache.add(REFRESH_LOCK_KEY, self.request.id or "manual", REFRESH_LOCK_TIMEOUT):
        print("Already other task that is refreshing articles")
        return "ALREADY RUNNING"

    _set_currently_refreshing(True)

    on_error = refresh_failed.s()
    # Immutable signatures (.si) - no step needs the previous step's return value,
    # and this keeps result payloads out of the broker.
    steps = [
        scrape_articles.si(),
        scrape_videos.si(),
        scrape_markets.si(),
        group_articles.si(),
        finalise_refresh.si(),
    ]
    # link_error has to be attached per signature: a chain only propagates an
    # errback attached to the chain itself to its first member.
    for step in steps:
        step.link_error(on_error)

    chain(*steps).apply_async()

    return "DISPATCHED"


def homeView(request, article=None):
    """Return django view of home page"""
    # update_feeds()
    # refresh_all_pages()
    # scrape_market_data()

    # Get Articles
    kwargs_hash, articles, page_num = (
        get_articles(categories="frontpage") if len(request.GET) == 0 else get_articles(**request.GET)
    )
    _, sidebar, _ = get_articles(special="sidebar", max_length=100, grouped_articles=False)

    # Get page infos
    _, url_kwargs = url_parm_encode(**request.GET)
    page_num = max(int(url_kwargs.pop("page", ["1"])[0]), 1)
    page_pagination = []
    for i in range(max(1, page_num - 1), max(1, page_num - 1) + 3):
        url_kwargs["page"] = [f"{i}"]
        page_pagination.append(
            dict(
                i=i,
                css_class="active" if i == page_num else ("disabled" if len(articles) < 72 and i > page_num else ""),
                url="/?" + urllib.parse.urlencode({k: ",".join(v) for k, v in url_kwargs.items()}),
            )
        )

    # Get additional infos
    lastRefreshed = cache.get("lastRefreshed")
    latestMarketData = cache.get("latestMarketData")

    return render(
        request,
        "home.html",
        {
            "articles": articles,
            "sidebar": sidebar,
            "marketData": latestMarketData,
            "debug": "debug" in request.GET and request.GET["debug"].lower() == "true",
            "authenticated": request.user.is_authenticated,
            "platform_name": settings.CUSTOM_PLATFORM_NAME,
            "webpush": {"group": "no" if settings.WEBPUSH_SETTINGS["VAPID_PRIVATE_KEY"] is None else "all"},
            "page_pagination": page_pagination,
            "lastRefreshed": lastRefreshed,
            "navbar": Page.objects.all().order_by("position_index"),
            "selected_page": kwargs_hash,
            "sidebar_title": settings.SIDEBAR_TITLE,
            "meta": (
                f"<title>{settings.CUSTOM_PLATFORM_NAME}</title><meta"
                ' name="description" content="Personal news platform aggregating news'
                " articles from several RSS feeds and videos from different YouTube"
                ' channels.">'
            ),
            "sentry_sdk": settings.SENTRY_SCRIPT_HEAD,
        },
    )


class RestHomeView(APIView):
    """View for url request to home view"""

    authentication_classes = []  # type: ignore
    permission_classes = []  # type: ignore

    def get(self, request, format=None):
        """get method for Django"""
        _, articles, _ = get_articles(categories="frontpage") if len(request.GET) == 0 else get_articles(**request.GET)

        articles = [
            dict(
                id=i.pk,
                title=i.title,
                publisher=i.publisher.name,
                summary=i.extract,
                image_url=i.image_url,
                has_full_text=i.has_full_text,
                has_paywall=i.publisher.paywall == "Y",
                is_breaking_news=i.importance_type == "breaking",
                content_type=i.content_type,
                external_link=i.link,
                internal_link=f"{settings.MAIN_HOST}/view/{i.pk}/",
                pub_date=i.pub_date,
                added_date=i.added_date,
                categories=str(i.categories).split(";"),
                language=i.language,
            )
            for i in articles
        ]

        return Response(articles)


def RedirectView(request, article):
    """view to redirect users to external article source url"""
    try:
        requested_article = Article.objects.get(pk=int(article))
        return HttpResponseRedirect(requested_article.link)
    except Exception:
        return HttpResponseRedirect("/")


def TriggerManualRefreshView(request):
    """view to trigger manual news refresh"""
    task = refresh_feeds.delay()

    HTML_RESPONSE = f"""
    <html>
        <head>
            <meta http-equiv="refresh" content="5;url=/" />
        </head>
        <body>
            <h1>Successfully triggered manual news refresh. ID: {task.task_id}</h1>
            <p><i>Redirecting in 5 seconds...</i></p>
        </body>
    </html>
    """

    print(f"Manual news refresh triggered. Id: {task.task_id}")
    return HttpResponse(HTML_RESPONSE)
