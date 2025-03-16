# -*- coding: utf-8 -*-
"""This file is doing the article scraping"""

import datetime
import html
import math
import os
import random
import threading
import time
import urllib

import feedparser
import ratelimit
import requests  # type: ignore
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, F, Q
from openai import OpenAI
from webpush import send_group_notification
from itertools import groupby
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from django.db.models import Max, Min

from articles.models import Article, ArticleGroup, FeedPosition
from feeds.models import Feed, Publisher
from preferences.models import Page

from .article_scraper_class import ScrapedArticle
from news_platform.pages.pageAPI import get_articles


def postpone(function):
    """
    Reusable decorator function to run any function async to Django User request - i.e. that the user does not
    have to wait for completion of function to get the requested view
    """

    def decorator(*args, **kwargs):
        t = threading.Thread(target=function, args=args, kwargs=kwargs)
        t.daemon = True
        t.start()

    return decorator


def find_grouped_articles():
    """Finds articles about the same topic and adds ArticleGroup objects"""
    print("Finding article groups...")
    pages_kwargs = Page.objects.all().order_by("-position_index").values_list("url_parameters_json", flat=True)
    model = SentenceTransformer("all-MiniLM-L6-v2")
    new_article_groups = 0

    for page_kwargs in pages_kwargs:
        _, articles, _ = get_articles(grouped_articles=False, force_recache=True, **page_kwargs)
        articles_query = [
            {"id": i.id, "title": i.title, "summary": i.extract, "article_group": i.article_group} for i in articles
        ]

        articles_text = [f"{i['title']}.\n{i['summary']}" for i in articles_query]
        embeddings = model.encode(articles_text)

        clustering = AgglomerativeClustering(n_clusters=None, distance_threshold=1.0, linkage="ward")
        hierarchical_labels = clustering.fit_predict(embeddings)

        article_groups = {
            i: cat
            for i, cat in zip(range(len(hierarchical_labels)), hierarchical_labels)
            if {i: hierarchical_labels.tolist().count(i) for i in range(max(hierarchical_labels) + 1)}[cat] > 1
        }
        sorted_article_groups = sorted(article_groups.items(), key=lambda item: item[1])
        grouped_article_groups = {
            k: [i[0] for i in g] for k, g in groupby(sorted_article_groups, key=lambda item: item[1])
        }

        for _, article_pos in grouped_article_groups.items():
            if len(article_pos) < 10:  # ensure not insane large article groups - probably incorrect group then
                new_article_groups += 1
                existing_article_groups = [articles_query[i]["article_group"] for i in article_pos]
                article_ids = [articles_query[i]["id"] for i in article_pos]
                common_article_group = max([-1] + [x.id for x in existing_article_groups if x is not None])
                all_same_groups = all([i is None or i.id == common_article_group for i in existing_article_groups])

                # if different existing article groups - delete existing grouped articles
                if all_same_groups is False:
                    for i in existing_article_groups:
                        if i is not None:
                            i.delete()

                # get existing ArticleGroup
                if common_article_group != -1 and all_same_groups:
                    article_group = ArticleGroup.objects.filter(id=common_article_group)
                    if len(article_group) > 0:
                        article_group = article_group[0]
                    else:
                        article_group = ArticleGroup()
                        article_group.save()

                # create new ArticleGroup
                else:
                    article_group = ArticleGroup()
                    article_group.save()

                # add ArticleGroup to articles
                for article_id in article_ids:
                    article = Article.objects.get(id=article_id)
                    setattr(article, "article_group", article_group)
                    article.save()

                articles = Article.objects.filter(article_group__id=article_group.id).order_by("min_article_relevance")

                categories = ";".join(set(";".join(i.categories for i in articles).split(";")))
                extract_html_rows = [
                    f'<tr class="context-card border-top border-bottom" article_id="{i.pk}" article_target="{"view" if i.has_full_text else "redirect"}"><td>{i.title}<br><span class="text-muted">{i.publisher.name} - <script>document.write(createDateStr("{i.pub_date.isoformat()}", "{i.added_date.isoformat()}", "medium"));</script></span></td></tr>'
                    for i in articles[1:]
                ]
                extract_html_rows = "\n".join(extract_html_rows[: min(3, len(extract_html_rows))])
                extract_html = f"\n<tbody>\n{extract_html_rows}\n</tbody>\n"

                combined_article = Article(
                    title=articles[0].title,
                    publisher=articles[0].publisher,
                    link=articles[0].link,
                    image_url=articles[0].image_url,
                    language=articles[0].language,
                    mailto_link=articles[0].mailto_link,
                    content_type="group",
                    pub_date=articles.aggregate(Max("pub_date"))["pub_date__max"],
                    added_date=articles.aggregate(Max("added_date"))["added_date__max"],
                    last_updated_date=articles.aggregate(Max("last_updated_date"))["last_updated_date__max"],
                    publisher_article_position=articles.aggregate(Min("publisher_article_position"))[
                        "publisher_article_position__min"
                    ],
                    min_feed_position=articles.aggregate(Min("min_feed_position"))["min_feed_position__min"],
                    min_article_relevance=articles.aggregate(Min("min_article_relevance"))[
                        "min_article_relevance__min"
                    ],
                    max_importance=articles.aggregate(Max("max_importance"))["max_importance__max"],
                    extract=articles[0].extract,
                    categories=categories,
                    full_text_html=extract_html,
                    full_text_text=articles[0].full_text_text,
                    has_full_text=False,
                    ai_summary=articles[0].ai_summary,
                    hash="group_" + str(random.randint(1, 1_000_000_000_000_000)),
                )
                combined_article.save()

                setattr(article_group, "combined_article", combined_article)
                article_group.save()

    # Delete old article groups
    ArticleGroup.objects.filter(article=None).delete()
    Article.objects.filter(content_type="group", articlegroup__isnull=True).delete()

    # Update not new article group's relevance
    all_aticle_groups = ArticleGroup.objects.all()
    for article_group in all_aticle_groups:
        articles = Article.objects.filter(article_group__id=article_group.id)
        combined_article = article_group.combined_article

        setattr(
            combined_article,
            "publisher_article_position",
            articles.aggregate(Min("publisher_article_position"))["publisher_article_position__min"],
        )
        setattr(
            combined_article,
            "min_feed_position",
            articles.aggregate(Min("min_feed_position"))["min_feed_position__min"],
        )
        setattr(
            combined_article,
            "min_article_relevance",
            articles.aggregate(Min("min_article_relevance"))["min_article_relevance__min"],
        )
        setattr(combined_article, "max_importance", articles.aggregate(Max("max_importance"))["max_importance__max"])

        combined_article.save()

    print(f"Found {new_article_groups} article groups.")


def update_feeds():
    """Main function that refreshes/scrapes articles from article feed sources."""
    start_time = time.time()

    # delete feed positions of inactive feeds
    inactive_feeds = Feed.objects.filter(~Q(active=True))
    for feed in inactive_feeds:
        delete_feed_positions(feed=feed)

    # get active feeds
    feeds = Feed.objects.filter(active=True, feed_type="rss")
    if settings.TESTING:
        # when testing is turned on only fetch 10% of feeds to not having to wait too long
        feeds = [feeds[i] for i in range(0, len(feeds), len(feeds) // (len(feeds) // 10))]
    force_refetch = os.getenv("FORCE_REFETCH", "False").lower() == "true"

    added_articles = 0
    for feed in feeds:
        add_articles, feed__last_fetched = fetch_feed(feed, force_refetch)
        added_articles += add_articles
        setattr(feed, "last_fetched", feed__last_fetched)
        feed.save()

    # apply publisher feed position
    publishers = Publisher.objects.all()
    for publisher in publishers:
        articles = (
            Article.objects.filter(feedposition__feed__publisher__pk=publisher.pk)
            .exclude(min_feed_position__isnull=True)
            .exclude(min_article_relevance__isnull=True)
            .exclude(content_type="video")
            .annotate(feed_count=Count("feedposition"))
            .annotate(calc_rel_feed_pos=F("min_feed_position") * 1000 / (F("max_importance") + 4))
            .order_by(
                "-calc_rel_feed_pos",
                "feed_count",
            )
        )
        len_articles = len(articles)
        for i, article in enumerate(articles):
            setattr(article, "publisher_article_position", int(len_articles - i))
            setattr(
                article,
                "min_article_relevance",
                min(
                    float(
                        round(
                            (len_articles - i) * float(getattr(article, "min_article_relevance")),
                            6,
                        )
                    ),
                    10_000,
                ),
            )
            article.save()

    # refresh next refresh time
    end_time = time.time()

    now = datetime.datetime.now()
    if now.hour >= 18 or now.hour < 6 or now.weekday() in [5, 6]:
        print(
            "No AI summaries are generated during non-business "
            "hours (i.e. between 18:00-6:00 and on Saturdays and Sundays)"
        )
    else:
        min_article_relevance = (
            Article.objects.filter(categories__icontains="FRONTPAGE", min_article_relevance__isnull=False)
            .order_by("min_article_relevance")[20]
            .min_article_relevance
        )

        articles_add_ai_summary = Article.objects.filter(
            has_full_text=True,
            ai_summary__isnull=True,
            min_article_relevance__isnull=False,
            content_type="article",
        ).filter(
            Q(Q(categories__icontains="FRONTPAGE") & Q(min_article_relevance__lte=min_article_relevance))
            | Q(
                Q(categories__icontains="SIDEBAR")
                & Q(publisher__renowned__gte=2)
                & Q(pub_date__gte=settings.TIME_ZONE_OBJ.localize(datetime.datetime.now() - datetime.timedelta(days=2)))
            )
        )

        add_ai_summary(article_obj_lst=articles_add_ai_summary)

    old_articles = (
        Article.objects.filter(
            min_article_relevance__isnull=True,
            feedposition=None,
            added_date__lte=settings.TIME_ZONE_OBJ.localize(datetime.datetime.now() - datetime.timedelta(days=21)),
        )
        .exclude(read_later=True)
        .exclude(archive=True)
    )
    if len(old_articles) > 0:
        print(f"Delete {len(old_articles)} old articles")
        old_articles.delete()
    else:
        print("No old articles to delete")

    find_grouped_articles()

    print(f"Refreshed articles and added {added_articles} articles in" f" {int(end_time - start_time)} seconds")

    # connection.close()


def calcualte_relevance(publisher, feed, feed_position, hash, pub_date, article_type):
    """
    This function calsucates the relvanec score for all articles and videos depensing on user
    settings and article positions
    """
    random.seed(hash)

    random_int = random.randrange(0, 9) / 10000
    feed__importance = feed.importance  # 0-4
    feed__ordering = feed.feed_ordering  # r or d
    publisher__renowned = publisher.renowned  # -3-3
    # content_type = "art" if feed.feed_type == "rss" else "vid"
    # publisher_article_count = cache.get(
    #    f"feed_publisher_{content_type}_cnt_{feed.publisher.pk}"
    # )
    if pub_date is None:
        article_age = 3
    else:
        article_age = abs((settings.TIME_ZONE_OBJ.localize(datetime.datetime.now()) - pub_date).total_seconds() / 3600)

    factor_publisher__renowned = {
        3: 2 / 9,  # Top Publisher = 4.5x
        2: 4 / 6,  # Highly Renowned Publisher = 1.5x
        1: 5 / 6,  # Renowned Publisher = 1.2x
        0: 6 / 6,  # Regular Publisher = 1x
        -1: 8 / 6,  # Lesser-known Publisher = 0.75x
        -2: 10 / 6,  # Unknown Publisher = 0.6x
        -3: 12 / 6,  # Inaccurate Publisher = 0.5x
    }[publisher__renowned]

    # Publisher article ccount normalization
    # factor_article_normalization = max(min(100 / publisher_article_count, 3), 0.5)
    factor_article_normalization = 1

    factor_feed__importance = {
        4: 1 / 4,  # Lead Articles News: 4x
        3: 2 / 4,  # Breaking & Top News: 2x
        2: 3 / 4,  # Frontpage News: 1.3x
        1: 4 / 4,  # Latest News: 1x
        0: 5 / 4,  # Normal: 0.8x
    }[feed__importance]

    # age factor
    if feed.feed_type != "rss":  # videos
        factor_age = 10 / (1 + math.exp(-0.01 * article_age + 4)) + 1
    elif feed__ordering == "r":
        factor_age = 3 / (1 + math.exp(-0.25 * article_age + 4)) + 1
    else:  # d
        factor_age = 4 / (1 + math.exp(-0.25 * article_age + 4)) + 1

    article_relevance = round(
        factor_publisher__renowned
        * (feed_position if article_type == "video" else 1)
        * factor_article_normalization
        * factor_feed__importance
        * factor_age
        * (0.5 if article_type == "ticker" else 1.0)
        * (0.25 if article_type == "briefing" and article_age < 10 else 1.0)
        + random_int,
        6,
    )
    article_relevance = min(float(article_relevance), 999999.0)

    return int(feed__importance), float(article_relevance)


def delete_feed_positions(feed):
    """Deletes all feed positions of a respective feed"""
    all_feedpositions = feed.feedposition_set.all()
    all_feedpositions.delete()


@ratelimit.sleep_and_retry
@ratelimit.limits(calls=30, period=60)
def check_limit_openai():
    """Empty function just to check for calls to API"""
    # limit of 90k tokens per minute = 90k / 3k per requests = 30 requests
    # limit of 3500 requests per minute
    # min(3.5k, 30) = 30 requests per minute
    return


def add_ai_summary(article_obj_lst):
    """Use OpenAI's ChatGPT API to get article summaries"""
    if settings.OPENAI_API_KEY is None:
        print("Not Requesting AI article summaries as OPENAI_API_KEY not set.")
    else:
        print(f"Requesting AI article summaries for {len(article_obj_lst)} articles.")

        # openai.api_key = settings.OPENAI_API_KEY
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        TOTAL_API_COST = float(cache.get("OPENAI_API_COST_LAUNCH", 0.0))
        COST_TOKEN_INPUT = 0.0005
        COST_TOKEN_OUTPUT = 0.0015
        NET_USD_TO_GROSS_GBP = 1.2 * 0.785
        THIS_RUN_API_COST = 0
        articles_summarized = 0

        for article_obj in article_obj_lst:
            logging = [
                str(datetime.datetime.now().isoformat()),
                str(article_obj.pk),
                str(article_obj.publisher.name),
                f'"{article_obj.title}"',
                str(article_obj.pub_date.isoformat()),
                str(article_obj.min_article_relevance),
                f'"{article_obj.categories}"',
            ]
            try:
                soup = BeautifulSoup(article_obj.full_text_html, "html5lib")
                article_text = " ".join(html.unescape(soup.text).split())
                # article_text = re.sub(r'\n+', '\n', article_text).strip()
                if len(article_text) > 3000 * 5:
                    article_text = article_text[: 3000 * 5]
                if len(article_text) / 5 < 500:
                    continue
                elif len(article_text) / 5 < 1000:
                    bullets = 2
                elif len(article_text) / 5 < 2000:
                    bullets = 3
                else:
                    bullets = 4
                check_limit_openai()
                completion = client.chat.completions.create(
                    # completion = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": f"Summarize this article in {bullets} bulletpoints",
                        },
                        {
                            "role": "user",
                            "content": article_text,
                        },
                    ],
                )
                article_summary = completion.choices[0].message.content
                article_summary = article_summary.replace("- ", "<li>").replace("\n", "</li>\n")
                article_summary = "<ul>\n" + article_summary + "</li>\n</ul>"
                this_article_cost = round(
                    float(
                        (
                            (completion.usage.prompt_tokens * COST_TOKEN_INPUT)
                            + (completion.usage.completion_tokens * COST_TOKEN_OUTPUT)
                        )
                        / 1000
                        * NET_USD_TO_GROSS_GBP
                    ),
                    8,
                )
                THIS_RUN_API_COST += this_article_cost
                setattr(article_obj, "ai_summary", article_summary)
                article_obj.save()
                articles_summarized += 1
                logging.extend(["SUCCESS", str(this_article_cost)])
            except Exception as e:
                print(f"Error getting AI article summary for {article_obj}:", e)
                logging.extend(["ERROR", str(0)])

            with open(str(settings.BASE_DIR) + "/data/ai_summaries.csv", "a+") as myfile:
                myfile.write(";".join(logging) + "\n")

        TOTAL_API_COST += THIS_RUN_API_COST
        cache.set("OPENAI_API_COST_LAUNCH", TOTAL_API_COST, 3600 * 1000)
        print(
            f"Summarized {articles_summarized} articles costing"
            f" {THIS_RUN_API_COST} GBP. Total API cost since container launch"
            f" {TOTAL_API_COST} GBP."
        )


def fetch_feed(feed, force_refetch):
    """Fetch/update/scrape all articles for a specific source feed"""
    added_articles = 0
    updated_articles = 0
    no_change_articles = 0

    feed_url = feed.url
    if "http://FEED-CREATOR.local" in feed_url:
        feed_url = feed_url.replace("http://FEED-CREATOR.local", settings.FEED_CREATOR_URL)

    fetched_feed = feedparser.parse(feed_url)
    fetched_feed__last_updated = []
    if hasattr(fetched_feed.feed, "updated_parsed"):
        fetched_feed__last_updated.append(
            datetime.datetime.fromtimestamp(time.mktime(fetched_feed.feed.updated_parsed))
        )
    if hasattr(fetched_feed.feed, "published_parsed"):
        fetched_feed__last_updated.append(
            datetime.datetime.fromtimestamp(time.mktime(fetched_feed.feed.published_parsed))
        )
    if len(fetched_feed__last_updated) == 0:
        fetched_feed__last_updated.append(datetime.datetime.now())
    fetched_feed__last_updated = settings.TIME_ZONE_OBJ.localize(max(fetched_feed__last_updated))

    if feed.last_fetched is not None and feed.last_fetched >= fetched_feed__last_updated and force_refetch is False:
        fetched_feed.entries = []
        print(
            f"Feed '{feed}' does not require refreshing - already up-to-date "
            f"(latest change at {fetched_feed__last_updated})"
        )

    if len(fetched_feed.entries) > 0:
        delete_feed_positions(feed)

    for article_feed_position, feed_article in enumerate(fetched_feed.entries, 1):
        scraped_article = ScrapedArticle(feed_model=feed)
        scraped_article.add_feed_attrs(feed_obj=fetched_feed.feed, article_obj=feed_article)

        scraped_article__url = scraped_article.article_link__final
        scraped_article__hash = scraped_article.article_hash__final
        scraped_article__guid = scraped_article.article_id__final
        scraped_article__last_updated = scraped_article.article_last_updated__final

        # check if article already exists
        matches = Article.objects.filter(
            guid=scraped_article__guid[:95]
            if isinstance(scraped_article__guid, str) and len(scraped_article__guid) > 95
            else scraped_article__guid
        )
        if len(matches) == 0:
            matches = Article.objects.filter(
                hash=scraped_article__hash[:100]
                if isinstance(scraped_article__hash, str) and len(scraped_article__hash) > 100
                else scraped_article__hash
            )

        # check if additional data fetching required
        fetch = False
        full_text_scraping = feed.full_text_fetch == "Y"
        if len(matches) > 0:
            article_obj = matches[0]
            scraped_article.current_categories = article_obj.categories
            # if article was updated or
            # article is missing image or extract and was published in the last 4 hours try getting content or
            # is ticker content type
            if (
                (
                    scraped_article__last_updated is not None
                    and article_obj.last_updated_date < scraped_article__last_updated
                )
                or (article_obj.content_type == "ticker")
                or (
                    (
                        (
                            settings.TIME_ZONE_OBJ.localize(datetime.datetime.now()) - article_obj.pub_date
                        ).total_seconds()
                        / (60 * 60)
                        < 4
                    )
                    and (
                        article_obj.image_url is None
                        or article_obj.image_url == ""
                        or article_obj.extract is None
                        or article_obj.extract == ""
                    )
                )
            ):
                fetch = True
        else:
            fetch = True

        if fetch:
            # fetch <meta> data
            try:
                article_html_response = requests.get(scraped_article__url, timeout=5)
                scraped_article.parse_meta_attrs(response_obj=article_html_response)
            except Exception as e:
                print(f'Error fetching meta for "{scraped_article.article_title__final}": {e}')
            if full_text_scraping and settings.FULL_TEXT_URL is not None:
                # fetch full-text data
                try:
                    full_text_request_url = (
                        f"{settings.FULL_TEXT_URL}extract.php?"
                        f'url={urllib.parse.quote(scraped_article__url, safe="")}'
                    )
                    full_text_response = requests.get(full_text_request_url, timeout=5)
                    if full_text_response.status_code == 200:
                        full_text_json = full_text_response.json()
                        scraped_article.parse_scrape_attrs(json_dict=full_text_json)
                except Exception as e:
                    print(f'Error fetching full-text for "{scraped_article.article_title__final}": {e}')

        # create new entry
        if len(matches) == 0:
            article_kwargs = scraped_article.get_final_attrs()
            # if feed is news aggregator - find correct article publisher
            if isinstance((publisher := article_kwargs["publisher"]), dict):
                if "link" in publisher:
                    url = ".".join(publisher["link"].split(".")[-2:])
                    matching_publishers = Publisher.objects.filter(link__icontains=url)
                    # existing matching publisher found
                    if len(matching_publishers) > 0:
                        article_kwargs["publisher"] = matching_publishers[0]
                    # no existing found - create new
                    else:
                        publisher_obj = Publisher(**article_kwargs["publisher"], renowned=-2)
                        publisher_obj.save()
                        article_kwargs["publisher"] = publisher_obj
                else:
                    article_kwargs["publisher"] = feed.publisher
            # create article
            article_obj = Article(**article_kwargs)
            article_obj.save()
            added_articles += 1

        # update entry
        elif fetch and len(matches) > 0:
            article_kwargs = scraped_article.get_final_attrs()
            _ = article_kwargs.pop("publisher")
            for prop, new_value in article_kwargs.items():
                if new_value is not None and new_value != "":
                    setattr(article_obj, prop, new_value)
            article_obj.save()
            updated_articles += 1

        # don't update entire entry - just categories
        else:
            curr_categories = getattr(article_obj, "categories", None)
            updated_categories = scraped_article.article_tags__final
            if updated_categories != curr_categories:
                setattr(article_obj, "categories", updated_categories)
                article_obj.save()
            no_change_articles += 1

        # Update article metrics
        (new_max_importance, new_min_article_relevance) = calcualte_relevance(
            publisher=feed.publisher,
            feed=feed,
            feed_position=article_feed_position,
            hash=scraped_article__guid,
            pub_date=article_obj.pub_date,
            article_type=article_obj.content_type,
        )

        # Add feed position linking
        feed_position = FeedPosition(
            feed=feed,
            article=article_obj,
            position=article_feed_position,
            importance=new_max_importance,
            relevance=new_min_article_relevance,
        )
        feed_position.save()

        # check if important news for push notification
        now = datetime.datetime.now()
        notifications_sent = cache.get("notifications_sent", [])
        if (
            article_obj.pk not in notifications_sent
            and (article_obj.categories is None or "no push" not in str(article_obj.categories).lower())
            and (
                ("sidebar" in str(article_obj.categories).lower() and article_obj.publisher.renowned >= 2)
                or ("frontpage" in str(article_obj.categories).lower() and article_obj.importance_type == "breaking")
                or (
                    feed.importance == 4
                    and article_feed_position <= 3
                    and article_obj.publisher.renowned >= 2
                    and now.hour >= 5
                    and now.hour <= 19
                )
            )
            and (settings.TIME_ZONE_OBJ.localize(datetime.datetime.now()) - article_obj.added_date).total_seconds() / 60
            < 15  # added less than 15min ago
            and (settings.TIME_ZONE_OBJ.localize(datetime.datetime.now()) - article_obj.pub_date).total_seconds()
            / (60 * 60)
            < 72  # published less than 72h/3d ago
        ):
            try:
                send_group_notification(
                    group_name="all",
                    payload={
                        "head": (
                            f"{article_obj.publisher.name} "
                            + (
                                "#Breaking"
                                if article_obj.importance_type == "breaking"
                                else "#Ticker"
                                if "sidebar" in str(article_obj.categories).lower()
                                else "#Headline"
                            )
                        ),
                        "body": f"{article_obj.title}",
                        "url": f"/view/{article_obj.pk}/" if article_obj.has_full_text else article_obj.link,
                    },
                    ttl=60 * 90,  # keep 90 minutes on server
                )
                cache.set(
                    "notifications_sent",
                    notifications_sent + [article_obj.pk],
                    3600 * 1000,
                )
                print(
                    f"Web Push Notification sent for ({article_obj.pk})"
                    f" {article_obj.publisher.name} - {article_obj.title}"
                )
            except Exception as e:
                print(
                    "Error sending Web Push Notification for "
                    f"({article_obj.pk}) {article_obj.publisher.name} - {article_obj.title}: {e}"
                )

    print(
        f"Refreshed '{feed}' feed with {added_articles} added, {updated_articles} changed, and {no_change_articles} "
        f"not modified articles (total feed {len(fetched_feed.entries)})"
    )
    return added_articles, fetched_feed__last_updated
