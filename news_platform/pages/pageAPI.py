# -*- coding: utf-8 -*-
"""Get article data for all views"""

import datetime
import functools
import urllib
import operator

from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Q
from django.forms.models import model_to_dict
from django.http import HttpResponse
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from news_platform.celery import app
from articles.models import Article
from feed_scraper.http_utils import fetch_json_limited, head_status
from feeds.models import Publisher
from preferences.models import url_parm_encode


def __convert_type(n):
    """convert string to float, int, or bool if possible"""
    try:
        return int(n)
    except ValueError:
        try:
            return float(n)
        except ValueError:
            if n.lower() == "true":
                return True
            elif n.lower() == "false":
                return False
            elif n.lower() == "none" or n.lower() == "null":
                return None
            else:
                return n


# Rehydrating more ids than this in one query would build an IN clause big
# enough to hit SQLite's variable limit, so the lookup is chunked.
ARTICLE_FETCH_CHUNK_SIZE = 500


def _load_articles(pks):
    """Turn a list of cached article ids back into model instances.

    The two large text columns are deferred. `full_text_text` and `ai_summary`
    are never touched by the list templates, and `full_text_html` is only
    rendered for `content_type='group'` rows (home.html) - so instead of letting
    the template trigger one deferred load per group row, it is back-filled for
    exactly those rows in a single extra query.

    Loading a page of 72 articles with their full bodies is several MB; deferring
    them makes it a few hundred KB.
    """
    if not pks:
        return []

    base_queryset = (
        Article.objects.select_related("publisher", "article_group")
        # select_related is the correct tool for a forward FK - prefetch_related
        # issued a second query per page and cached the result on the instances.
        .defer("full_text_html", "full_text_text", "ai_summary")
    )

    articles_by_pk = {}
    unique_pks = list(dict.fromkeys(pks))
    for start in range(0, len(unique_pks), ARTICLE_FETCH_CHUNK_SIZE):
        articles_by_pk.update(base_queryset.in_bulk(unique_pks[start : start + ARTICLE_FETCH_CHUNK_SIZE]))

    group_pks = [pk for pk, article in articles_by_pk.items() if article.content_type == "group"]
    if group_pks:
        for pk, full_text_html in Article.objects.filter(pk__in=group_pks).values_list("pk", "full_text_html"):
            # Assigning over a deferred field just populates the instance dict,
            # which is what the descriptor reads from - no extra query later.
            articles_by_pk[pk].full_text_html = full_text_html

    # Rebuilt in the original order, keeping any duplicates the joins produced.
    return [articles_by_pk[pk] for pk in pks if pk in articles_by_pk]


def get_articles(max_length=72, force_recache=False, grouped_articles=True, hydrate=True, **kwargs):
    """Gets article request by user either from database or from cache

    The cache holds article *ids*, not pickled model instances. Every distinct
    set of url parameters gets its own 48h cache entry and `refresh_all_pages()`
    rewrites all of them twice per refresh cycle - storing whole `Article`
    objects meant every one of those entries carried the full text of ~72
    articles, in redis and in the worker that pickled them.

    Pass `hydrate=False` when only the caching side effect is wanted; the second
    return value is then the list of ids rather than model instances.
    """
    kwargs_hash, kwargs = url_parm_encode(**kwargs)
    page_num = max(int(kwargs.pop("page", ["1"])[0]), 1) - 1

    article_pks = cache.get(kwargs_hash)
    if article_pks is not None and not all(isinstance(pk, int) for pk in article_pks):
        # Entry written by an older version of this function, which cached model
        # instances. Drop it rather than trying to interpret it.
        article_pks = None

    cached_views_lst = cache.get("cached_views_lst")
    if cached_views_lst is None:
        cache.set("cached_views_lst", {kwargs_hash: kwargs}, 60 * 60 * 48)
    elif kwargs_hash not in cached_views_lst:
        cache.set(
            "cached_views_lst",
            {**cached_views_lst, **{kwargs_hash: kwargs}},
            60 * 60 * 48,
        )

    if article_pks is None or force_recache:
        conditions = Q()
        special_filters = kwargs["special"] if "special" in kwargs else None
        exclude_sidebar = True
        has_language_filters = False
        has_read_later = False
        for field, condition_lst in kwargs.items():
            sub_conditions = Q()
            for condition in condition_lst:
                if field.lower() == "special":
                    if condition.lower() == "free-only":
                        sub_conditions &= Q(
                            Q(Q(has_full_text=True) | Q(publisher__paywall="N")) & Q(categories__icontains="frontpage")
                        )
                    elif condition.lower() == "sidebar":
                        sub_conditions &= Q(categories__icontains="SIDEBAR")
                        exclude_sidebar = False
                else:
                    condition = __convert_type(condition)
                    if isinstance(condition, str):
                        sub_conditions |= Q(**{f"{field}__icontains": condition})
                    else:
                        sub_conditions |= Q(**{f"{field}": condition})
                    exclude_sidebar = False
            if field == "language":
                has_language_filters = True
            if field == "read_later":
                has_read_later = True
            try:
                # .exists() stops at the first matching row. `len(queryset)`
                # loaded every matching Article - including its full text - into
                # memory, once per filter field, purely to test for emptiness.
                condition_has_matches = Article.objects.filter(sub_conditions).exists()
            except Exception:
                condition_has_matches = False
            if condition_has_matches:
                conditions &= sub_conditions
        if grouped_articles:
            conditions &= Q(article_group__isnull=True)
        else:
            conditions &= Q(articlegroup__isnull=True)
            conditions &= ~Q(content_type="group")
        # Only ids are pulled from the database here - the model instances are
        # built once, at the end, by _load_articles().
        articles = Article.objects.filter(conditions)
        articles = articles.order_by(
            F("min_article_relevance").asc(nulls_last=True),
            "-pub_date__date",
            "-max_importance",
            "-last_updated_date",
        )
        if has_read_later:
            articles = articles.order_by("-last_updated_date")
            has_language_filters = True
        if exclude_sidebar:
            articles = articles.exclude(categories__icontains="SIDEBAR")
        if special_filters is not None and "sidebar" in special_filters:
            articles = articles.order_by("-added_date", "-pub_date", "min_article_relevance").exclude(
                pub_date__lte=settings.TIME_ZONE_OBJ.localize(datetime.datetime.now() - datetime.timedelta(days=5))
            )
        if has_language_filters is False and "*" not in settings.ALLOWED_LANGUAGES:
            articles = articles.filter(
                functools.reduce(
                    operator.or_,
                    (Q(language__icontains=x) for x in settings.ALLOWED_LANGUAGES.split(",")),
                )
            )
        # Slicing the id queryset rather than the model queryset. The old
        # `min(..., len(articles))` upper bound evaluated the *entire* result set
        # just to compute a number that LIMIT/OFFSET already handles.
        article_pk_queryset = articles.values_list("pk", flat=True)
        if max_length is not None:
            lower_bound = page_num * max_length
            article_pk_queryset = article_pk_queryset[lower_bound : lower_bound + max_length]
        article_pks = list(article_pk_queryset)

        if grouped_articles:
            cache.set(kwargs_hash, article_pks, 60 * 60 * 48 if page_num == 0 else 10 * 60)
        print(f"Got {kwargs_hash} from database" + (" and cached it" if grouped_articles else ""))

    if not hydrate:
        return kwargs_hash, article_pks, page_num + 1

    return kwargs_hash, _load_articles(article_pks), page_num + 1


class RestArticleAPIView(APIView):
    """RestAPI view to get article data via /api/article/<int:pk>/"""

    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, format=None):
        """get method for Django"""
        try:
            return Response(model_to_dict(Article.objects.get(pk=pk)))
        except Exception as e:
            return Response(data=dict(error=e.__str__()), status=status.HTTP_400_BAD_REQUEST)


class RestPublisherAPIView(APIView):
    """RestAPI view to get publisher data via /api/publisher/<int:pk>/"""

    authentication_classes = []  # type: ignore
    permission_classes = []  # type: ignore

    def get(self, request, pk, format=None):
        """get method for Django"""
        try:
            return Response(model_to_dict(Publisher.objects.get(pk=pk)))
        except Exception as e:
            return Response(data=dict(error=e.__str__()), status=status.HTTP_400_BAD_REQUEST)


class RestLastRefeshAPIView(APIView):
    """RestAPI view to check when articles were last refreshed"""

    authentication_classes = []  # type: ignore
    permission_classes = []  # type: ignore

    def get(self, request, format=None):
        """get method for Django"""
        return Response(
            dict(
                lastRefreshed=cache.get("lastRefreshed"),
                currentlyRefreshing=cache.get("currentlyRefreshing", False),
                videoRefreshCycleCount=cache.get("videoRefreshCycleCount", 8),
                notifications_display=cache.get("notifications_display", []),
            )
        )


def ReadLaterView(request, action, pk):
    try:
        requested_article = Article.objects.get(pk=pk)
        setattr(requested_article, "read_later", action == "add")
        requested_article.save()

        cached_views_lst = cache.get("cached_views_lst")
        for kwargs_hash, kwargs in [].items() if cached_views_lst is None else cached_views_lst.items():
            if "read_later" in kwargs_hash:
                _, _, _ = get_articles(force_recache=True, **kwargs)

        return redirect("/")

    except Exception:
        return HttpResponse(
            "Error! Maybe the article was not found or other unknown error.",
            content_type="text/plain",
        )


def ArchiveView(request, action, pk):
    try:
        requested_article = Article.objects.get(pk=pk)
        setattr(requested_article, "archive", action == "add")
        if requested_article.read_later and action == "add":
            setattr(requested_article, "read_later", False)
        requested_article.save()

        cached_views_lst = cache.get("cached_views_lst")
        for kwargs_hash, kwargs in [].items() if cached_views_lst is None else cached_views_lst.items():
            if "archive" in kwargs_hash or "read_later" in kwargs_hash:
                _, _, _ = get_articles(force_recache=True, **kwargs)

        return redirect("/")

    except Exception:
        return HttpResponse(
            "Error! Maybe the article was not found or other unknown error.",
            content_type="text/plain",
        )


@app.task(bind=True, time_limit=60 * 3, max_retries=0, ignore_result=True)  # 3 min time limit
def refetch_image_article(self, pk):
    """Main function to refetching article image if loading error detected by JS"""
    print(f"Article {pk} image refetching started")

    if settings.FULL_TEXT_URL is None:
        result = "No FULL_TEXT_URL defined for image refetch"
    else:
        # fetch full-text data
        try:
            result = "Error checking current image"
            requested_article = Article.objects.get(pk=int(pk))
            # Only the status code matters here. The previous `requests.get()` had
            # no timeout at all and downloaded the whole body, so one slow or
            # oversized image could pin a worker child for the full 3 min time
            # limit while holding the entire response in memory.
            status_code, is_ok = head_status(requested_article.link)
            if is_ok is False and status_code in [400, 404]:
                result = f"Image does not work ({status_code}) - error fetching new image"
                full_text_request_url = (
                    f"{settings.FULL_TEXT_URL}extract.php?url={urllib.parse.quote(requested_article.link, safe='')}"
                )
                full_text_response = fetch_json_limited(full_text_request_url, timeout=(3.05, 5))
                if full_text_response.status_code == 200:
                    full_text_json = full_text_response.json()
                    setattr(requested_article, "image_url", full_text_json.get("image", full_text_json.get("og_image")))
                    requested_article.save()
                    result = f"Image does not work ({status_code}) - success fetching new image"
            else:
                result = f"Image works ({status_code}) - refetching not required"

        except Exception as e:
            print(f'Error fetching image for article "{pk}": {e}')
            result += ": " + str(e)

    print(f"Article {pk} image refetching finished")
    return result


def ImageErrorView(request, article):
    """view to trigger article image refetching if JS detects loading error"""
    article = int(article)
    lastImageRefetched = cache.get(f"lastImageRefetched-{article}", False)

    if lastImageRefetched:
        print(f"Image issue was already received for article {article}. No new task")

    else:
        task = refetch_image_article.delay(article)
        cache.set(f"lastImageRefetched-{article}", True, 60 * 60 * 2)
        print(f"Image issue received for article {article}. Task Id: {task.task_id}")

    return HttpResponse("RECEIVED")
