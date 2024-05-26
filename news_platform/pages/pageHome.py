# -*- coding: utf-8 -*-
"""Responaible for home view at base url / """
import datetime
import traceback
import urllib.parse

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template.defaulttags import register
from rest_framework.response import Response
from rest_framework.views import APIView

from articles.models import Article
from feed_scraper.feed_scraper import update_feeds
from feed_scraper.video_scraper import update_videos
from markets.scrape import scrape_market_data
from news_platform.celery import app
from preferences.models import Page, get_page_lst, url_parm_encode

from .pageAPI import get_articles


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
        _, _, _ = get_articles(**view_kwargs, force_recache=True)


def get_stats():
    """Get stats about number of artciles/videos per publisher for relevance ranking"""
    added_date__lte_2d = settings.TIME_ZONE_OBJ.localize(
        datetime.datetime.now() - datetime.timedelta(days=2)
    )
    added_date__lte_30d = settings.TIME_ZONE_OBJ.localize(
        datetime.datetime.now() - datetime.timedelta(days=30)
    )

    all_articles = Article.objects.exclude(content_type="video").filter(
        pub_date__gte=added_date__lte_2d
    )
    all_videos = Article.objects.filter(content_type="video").filter(
        pub_date__gte=added_date__lte_30d
    )

    for content_type, query in [("art", all_articles), ("vid", all_videos)]:
        summary = (
            query.exclude(feedposition=None)
            .values("feedposition__feed__publisher__pk")
            .annotate(count=Count("pk"))
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


# @postpone
@app.task(bind=True, time_limit=60 * 60 * 3, max_retries=5)  # 3 hour time limit
def refresh_feeds(self):
    """Main function to refresh all articles and videos"""
    print("refreshing started")

    currentlyRefreshing = cache.get("currentlyRefreshing")
    if currentlyRefreshing:
        print("Already other task that is refreshing articles")
        return "ALREADY RUNNING"

    response = ""
    try:
        cache.set("currentlyRefreshing", True, 60 * 60 * 2 + 300)
        videoRefreshCycleCount = cache.get("videoRefreshCycleCount")

        get_stats()

        # Caching artciles before updaing
        refresh_all_pages()

        update_feeds()
        response += "articles refreshed successfully; "
        if videoRefreshCycleCount is None or videoRefreshCycleCount == 0:
            update_videos()
            cache.set("videoRefreshCycleCount", 8, 60 * 60 * 24)
            response += "videos refreshed successfully; "
        else:
            print(f"Refeshing videos in {videoRefreshCycleCount - 1} cycles")
            cache.set(
                "videoRefreshCycleCount", videoRefreshCycleCount - 1, 60 * 60 * 24
            )
            response += "video refresh not required; "

        refresh_all_pages()

        # Update marekt data
        scrape_market_data()
        response += "market data refreshed successfully; "

        now = settings.TIME_ZONE_OBJ.localize(datetime.datetime.now())
        cache.set("lastRefreshed", now, 60 * 60 * 48)

        response += "DONE"
        cache.set("currentlyRefreshing", False, 60 * 60 * 2)
        print("refreshing finished")

    except Exception as e:
        response += f"ERROR: {e}"
        cache.set("currentlyRefreshing", False, 60 * 60 * 2)
        print(traceback.format_exc())
        raise self.retry(countdown=30, exc=e)

    finally:
        return response


def homeView(request, article=None):
    """Return django view of home page"""
    # refresh_feeds()
    # update_feeds()
    # refresh_all_pages()

    # Get Articles
    kwargs_hash, articles, page_num = (
        get_articles(categories="frontpage")
        if len(request.GET) == 0
        else get_articles(**request.GET)
    )
    _, sidebar, _ = get_articles(special="sidebar", max_length=100)

    # Get page infos
    _, url_kwargs = url_parm_encode(**request.GET)
    page_num = max(int(url_kwargs.pop("page", ["1"])[0]), 1)
    page_pagination = []
    for i in range(max(1, page_num - 1), max(1, page_num - 1) + 3):
        url_kwargs["page"] = [f"{i}"]
        page_pagination.append(
            dict(
                i=i,
                css_class="active"
                if i == page_num
                else ("disabled" if len(articles) < 72 and i > page_num else ""),
                url="/?"
                + urllib.parse.urlencode(
                    {k: ",".join(v) for k, v in url_kwargs.items()}
                ),
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
            "webpush": {"group": "all"},
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
        _, articles, _ = (
            get_articles(categories="frontpage")
            if len(request.GET) == 0
            else get_articles(**request.GET)
        )

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
    """view to tigger manual news refresh"""
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
