# -*- coding: utf-8 -*-
"""This file is doing the article scraping"""

import datetime
import html
import math
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

from articles.models import Article, FeedPosition
from feeds.models import Feed, Publisher

from .article_scraper_class import ScrapedArticle


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


def update_feeds():
    """Main function that refreshes/scrapes articles from article feed sources."""
    start_time = time.time()

    # delete feed positions of inactive feeds
    inactive_feeds = Feed.objects.filter(~Q(active=True))
    for feed in inactive_feeds:
        delete_feed_positions(feed=feed)

    # get acctive feeds
    feeds = Feed.objects.filter(active=True, feed_type="rss")
    if settings.TESTING:
        # when testing is turned on only fetch 10% of feeds to not having to wait too long
        feeds = [
            feeds[i] for i in range(0, len(feeds), len(feeds) // (len(feeds) // 10))
        ]

    added_articles = 0
    for feed in feeds:
        add_articles, feed__last_fetched = fetch_feed(feed)
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
            .annotate(
                calc_rel_feed_pos=F("min_feed_position")
                * 1000
                / (F("max_importance") + 4)
            )
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
                            (len_articles - i)
                            * float(getattr(article, "min_article_relevance")),
                            6,
                        )
                    ),
                    10_000,
                ),
            )
            article.save()

    # calculate next refesh time
    end_time = time.time()

    now = datetime.datetime.now()
    if now.hour >= 18 or now.hour < 6 or now.weekday() in [5, 6]:
        print(
            "No AI summaries are generated during non-business "
            "hours (i.e. between 18:00-6:00 and on Saturdays and Sundays)"
        )
    else:
        min_article_relevance = (
            Article.objects.filter(
                categories__icontains="FRONTPAGE", min_article_relevance__isnull=False
            )
            .order_by("min_article_relevance")[20]
            .min_article_relevance
        )

        articles_add_ai_summary = Article.objects.filter(
            has_full_text=True,
            ai_summary__isnull=True,
            min_article_relevance__isnull=False,
            content_type="article",
        ).filter(
            Q(
                Q(categories__icontains="FRONTPAGE")
                & Q(min_article_relevance__lte=min_article_relevance)
            )
            | Q(
                Q(categories__icontains="SIDEBAR")
                & Q(publisher__renowned__gte=2)
                & Q(
                    pub_date__gte=settings.TIME_ZONE_OBJ.localize(
                        datetime.datetime.now() - datetime.timedelta(days=2)
                    )
                )
            )
        )

        add_ai_summary(article_obj_lst=articles_add_ai_summary)

    old_articles = (
        Article.objects.filter(
            min_article_relevance__isnull=True,
            feedposition=None,
            added_date__lte=settings.TIME_ZONE_OBJ.localize(
                datetime.datetime.now() - datetime.timedelta(days=21)
            ),
        )
        .exclude(read_later=True)
        .exclude(archive=True)
    )
    if len(old_articles) > 0:
        print(f"Delete {len(old_articles)} old articles")
        old_articles.delete()
    else:
        print("No old articles to delete")

    print(
        f"Refreshed articles and added {added_articles} articles in"
        f" {int(end_time - start_time)} seconds"
    )

    # connection.close()


def calcualte_relevance(publisher, feed, feed_position, hash, pub_date, article_type):
    """
    This function calsucates the relvanec score for all artciles and videos depensing on user
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
        article_age = (
            settings.TIME_ZONE_OBJ.localize(datetime.datetime.now()) - pub_date
        ).total_seconds() / 3600

    factor_publisher__renowned = {
        3: 2 / 9,  # Top Publisher = 4.5x
        2: 4 / 6,  # Higly Renowned Publisher = 1.5x
        1: 5 / 6,  # Renowned Publisher = 1.2x
        0: 6 / 6,  # Regular Publisher = 1x
        -1: 8 / 6,  # Lesser-known Publisher = 0.75x
        -2: 10 / 6,  # Unknown Publisher = 0.6x
        -3: 12 / 6,  # Inaccurate Publisher = 0.5x
    }[publisher__renowned]

    # Publisher artcile ccount normalization
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
    # limit of 90k tokens per minute = 90k / 3k per request = 30 requets
    # limit of 3500 requests per minute
    # min(3.5k, 30) = 30 requests per minute
    return


def add_ai_summary(article_obj_lst):
    """Use OpenAI's ChatGPT API to get artcile summaries"""
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
                article_summary = article_summary.replace("- ", "<li>").replace(
                    "\n", "</li>\n"
                )
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

            with open(
                str(settings.BASE_DIR) + "/data/ai_summaries.csv", "a+"
            ) as myfile:
                myfile.write(";".join(logging) + "\n")

        TOTAL_API_COST += THIS_RUN_API_COST
        cache.set("OPENAI_API_COST_LAUNCH", TOTAL_API_COST, 3600 * 1000)
        print(
            f"Summarized {articles_summarized} articles costing"
            f" {THIS_RUN_API_COST} GBP. Total API cost since container launch"
            f" {TOTAL_API_COST} GBP."
        )


def fetch_feed(feed):
    """Fetch/update/scrape all articles for a specific source feed"""
    added_articles = 0
    updated_articles = 0
    no_change_articles = 0

    feed_url = feed.url
    if "http://FEED-CREATOR.local" in feed_url:
        feed_url = feed_url.replace(
            "http://FEED-CREATOR.local", settings.FEED_CREATOR_URL
        )

    fetched_feed = feedparser.parse(feed_url)
    if hasattr(fetched_feed.feed, "updated_parsed"):
        fetched_feed__last_updated = datetime.datetime.fromtimestamp(
            time.mktime(fetched_feed.feed.updated_parsed)
        )
    elif hasattr(fetched_feed.feed, "published_parsed"):
        fetched_feed__last_updated = datetime.datetime.fromtimestamp(
            time.mktime(fetched_feed.feed.published_parsed)
        )
    else:
        fetched_feed__last_updated = datetime.datetime.now()
    fetched_feed__last_updated = settings.TIME_ZONE_OBJ.localize(
        fetched_feed__last_updated
    )

    if (
        feed.last_fetched is not None
        and feed.last_fetched >= fetched_feed__last_updated
    ):
        fetched_feed.entries = []
        print(
            f"Feed '{feed}' does not require refreshing - already up-to-date "
            f"(lastest change at {fetched_feed__last_updated})"
        )

    if len(fetched_feed.entries) > 0:
        delete_feed_positions(feed)

    for article_feed_position, feed_article in enumerate(fetched_feed.entries, 1):
        scraped_article = ScrapedArticle(feed_model=feed)
        scraped_article.add_feed_attrs(
            feed_obj=fetched_feed.feed, article_obj=feed_article
        )

        scraped_article__url = scraped_article.article_link__final
        scraped_article__hash = scraped_article.article_hash__final
        scraped_article__guid = scraped_article.article_id__final
        scraped_article__last_updated = scraped_article.article_last_updated__final

        # check if article already exists
        matches = Article.objects.filter(
            guid=scraped_article__guid[:95]
            if type(scraped_article__guid) is str and len(scraped_article__guid) > 95
            else scraped_article__guid
        )
        if len(matches) == 0:
            matches = Article.objects.filter(
                hash=scraped_article__hash[:100]
                if type(scraped_article__hash) is str
                and len(scraped_article__hash) > 100
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
                            settings.TIME_ZONE_OBJ.localize(datetime.datetime.now())
                            - article_obj.pub_date
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
                print(
                    f'Error fetching meta for "{scraped_article.article_title__final}": {e}'
                )
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
                    print(
                        f'Error fetching full-text for "{scraped_article.article_title__final}": {e}'
                    )

        # create new entry
        if len(matches) == 0:
            article_kwargs = scraped_article.get_final_attrs()
            # if feed is news aggregator - find correct article publisher
            if type((publisher := article_kwargs["publisher"])) is dict:
                if "link" in publisher:
                    url = ".".join(publisher["link"].split(".")[-2:])
                    matching_publishers = Publisher.objects.filter(link__icontains=url)
                    # existing matching publisher found
                    if len(matching_publishers) > 0:
                        article_kwargs["publisher"] = matching_publishers[0]
                    # no existing found - create new
                    else:
                        publisher_obj = Publisher(
                            **article_kwargs["publisher"], renowned=-2
                        )
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
            and (
                article_obj.categories is None
                or "no push" not in str(article_obj.categories).lower()
            )
            and (
                (
                    "sidebar" in str(article_obj.categories).lower()
                    and article_obj.publisher.renowned >= 2
                )
                or (
                    "frontpage" in str(article_obj.categories).lower()
                    and article_obj.importance_type == "breaking"
                )
                or (
                    feed.importance == 4
                    and article_feed_position <= 3
                    and article_obj.publisher.renowned >= 2
                    and now.hour >= 5
                    and now.hour <= 19
                )
            )
            and (
                settings.TIME_ZONE_OBJ.localize(datetime.datetime.now())
                - article_obj.added_date
            ).total_seconds()
            / 60
            < 15  # added less than 15min ago
            and (
                settings.TIME_ZONE_OBJ.localize(datetime.datetime.now())
                - article_obj.pub_date
            ).total_seconds()
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
                        "url": f"/view/{article_obj.pk}/"
                        if article_obj.has_full_text
                        else article_obj.link,
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
