# -*- coding: utf-8 -*-
"""This file is doing the video scraping"""

import datetime
import os
import time
import urllib
import feedparser
import scrapetube
from django.conf import settings

from articles.models import Article, FeedPosition
from feeds.models import Feed

from .article_scraper import calcualte_relevance, delete_feed_positions


def __extract_number_from_datestr(full_str, identifier):
    """Extracts the number before a certain string e.g. 30 from '30 minutes ago'"""
    first_part = full_str.split(" " + identifier)[0]
    reversed_int_str = ""
    for i in reversed(first_part):
        if i.isnumeric():
            reversed_int_str += i
        else:
            break
    return int("".join(reversed(reversed_int_str)))


def update_videos():
    """Main function that refreshes/scrapes videos from video feed sources."""
    start_time = time.time()

    feeds = Feed.objects.filter(active=True).exclude(feed_type="rss")
    if settings.TESTING:
        # when testing is turned on only fetch 10% of feeds to not having to wait too long
        feeds = [feeds[i] for i in range(0, len(feeds), len(feeds) // (len(feeds) // 10))]
    force_refetch = os.getenv("FORCE_REFETCH", "False").lower() == "true"

    if (
        datetime.datetime.now().weekday() == 6
        and datetime.datetime.now().hour >= 13
        and datetime.datetime.now().hour < 15
    ):  # every sunday force re-fetch the videos to update outdated images / texts / etc
        force_refetch = True

    added_videos = 0
    for feed in feeds:
        added_videos += fetch_feed(feed, force_refetch)

    end_time = time.time()
    print(f"Refreshed videos and added {added_videos} videos in" f" {int(end_time - start_time)} seconds")


def fetch_feed(feed, force_refetch, max_per_feed=200):
    """Fetcch/update/scrape all fideos for a specific source feed"""
    added_vids = 0

    if feed.feed_type == "y-channel":
        videos = scrapetube.get_channel(
            channel_url=feed.url,
            limit=max_per_feed,
            sort_by="popular" if feed.feed_ordering == "r" else "newest",
        )
        src = "youtube"
    elif feed.feed_type == "y-playlist":
        parsed_url = urllib.parse.parse_qs(urllib.parse.urlparse(feed.url).query)
        if "list" in parsed_url:
            playlist = parsed_url["list"][0]
            videos = scrapetube.get_playlist(playlist)
        else:
            print(f'Error: Invalid URL "{feed.url}" for YouTube Playlist "{feed.name}"')
            videos = []
        src = "youtube"
    elif feed.feed_type == "rss-playlist":
        videos = feedparser.parse(feed.url).entries
        src = "rss"
    else:
        videos = []
        src = "unknown"

    for i, video in enumerate(videos):
        if i == 0:
            matches = Article.objects.filter(
                hash=f"{src}_{video.get('videoId', video.get('id'))}", feedposition__position=1
            )
            if (
                feed.feed_type == "y-channel"
                and feed.feed_ordering != "r"
                and len(matches) > 0
                and force_refetch is False
            ):
                print(
                    f"Feed '{feed}' does not require refreshing - "
                    f"already up-to-date as same first video and chronological order."
                )
                break
            else:
                delete_feed_positions(feed)

        no_new_video = 0
        if no_new_video > 50:
            print(
                f"{feed} no new video found for the last {no_new_video} videos at video"
                f" {i + 1} thus stop checking more."
            )
        article_kwargs = {}
        article__feed_position = i + 1
        article_kwargs["min_feed_position"] = article__feed_position
        article_kwargs["publisher"] = feed.publisher
        article_kwargs["content_type"] = "video"
        article_kwargs["categories"] = ";".join(
            [
                str(i)
                for i in ["Video"]
                + ([] if feed.source_categories is None else feed.source_categories.split(";"))
                + [""]
            ]
        )

        if src == "youtube":
            article_kwargs["title"] = video["title"]["runs"][0]["text"] if "title" in video else None
            article_kwargs["extract"] = (
                video["descriptionSnippet"]["runs"][0]["text"] if "descriptionSnippet" in video else ""
            )
            if "lengthText" in video and "viewCountText" in video and "simpleText" in video["viewCountText"]:
                article_kwargs["extract"] = (
                    video["lengthText"]["simpleText"]
                    + (" h" if len(video["lengthText"]["simpleText"]) > 5 else " min")
                    + "  |  "
                    + video["viewCountText"]["simpleText"]
                    + "<br>\n"
                    + article_kwargs["extract"]
                )
            article_kwargs["image_url"] = video["thumbnail"]["thumbnails"][-1]["url"] if "thumbnail" in video else None
            article_kwargs["guid"] = video["videoId"]
            publishedTimeText = video["publishedTimeText"]["simpleText"] if "publishedTimeText" in video else ""
            article_kwargs["pub_date"] = datetime.datetime.now()
            if "min" in publishedTimeText:
                article_kwargs["pub_date"] -= datetime.timedelta(
                    minutes=__extract_number_from_datestr(publishedTimeText, "min")
                )
            elif "hour" in publishedTimeText:
                article_kwargs["pub_date"] -= datetime.timedelta(
                    hours=__extract_number_from_datestr(publishedTimeText, "hour")
                )
            elif "day" in publishedTimeText:
                article_kwargs["pub_date"] -= datetime.timedelta(
                    days=__extract_number_from_datestr(publishedTimeText, "day")
                )
            elif "week" in publishedTimeText:
                article_kwargs["pub_date"] -= datetime.timedelta(
                    days=__extract_number_from_datestr(publishedTimeText, "week") * 7
                )
            elif "month" in publishedTimeText:
                article_kwargs["pub_date"] -= datetime.timedelta(
                    days=__extract_number_from_datestr(publishedTimeText, "month") * 30
                )
            elif "year" in publishedTimeText:
                article_kwargs["pub_date"] -= datetime.timedelta(
                    days=__extract_number_from_datestr(publishedTimeText, "year") * 365
                )
            elif publishedTimeText == "":
                article_kwargs["pub_date"] -= datetime.timedelta(days=i * 7)
            else:
                print(f'Unknown date string "{publishedTimeText}"')
            article_kwargs["pub_date"] = settings.TIME_ZONE_OBJ.localize(article_kwargs["pub_date"])
            article_kwargs["hash"] = f"{src}_{video['videoId']}"
            article_kwargs["language"] = feed.publisher.language
            article_kwargs["link"] = f"https://www.youtube.com/watch?v={video['videoId']}"
            article_kwargs["full_text_html"] = f"""
            <iframe style="width: 100%; height: auto; min-height: 30vw; max-height:400px; aspect-ratio: 16 / 9;"
            referrerpolicy="no-referrer"
            src="https://www.youtube-nocookie.com/embed/{video['videoId']}?rel=0&autoplay=1"
            frameborder="0" allow="autoplay; encrypted-media" tabindex="0" allowfullscreen></iframe><br>\n
            <div>{article_kwargs["extract"]}</div>
            """

        elif src == "rss":
            article_kwargs["title"] = video.get("title")
            article_kwargs["extract"] = f"""
            {int(video.get('duration')) // 60} min  |  {video.get('author')}<br>
            {video.get('summary')}
            """

            article_kwargs["pub_date"] = settings.TIME_ZONE_OBJ.localize(
                datetime.datetime.fromtimestamp(time.mktime(video.get("published_parsed")))
            )
            article_kwargs["guid"] = video.get("id")
            article_kwargs["hash"] = f"{src}_{video.get('id')}"
            article_kwargs["language"] = feed.publisher.language
            article_kwargs["link"] = video.get("websiteurl")
            article_kwargs["full_text_html"] = f"""
            <video style="width: 100%; height: auto; min-height: 30vw; max-height:400px; aspect-ratio: 16 / 9;"
            referrerpolicy="no-referrer" controls>
                <source src="{video.get('link')}" type="video/mp4">
                Your browser does not support HTML video.
            </video><br>\n
            <div>{article_kwargs["extract"]}</div>
            """

        article_kwargs["has_full_text"] = True
        article_kwargs["has_extract"] = False

        search_article = Article.objects.filter(hash=article_kwargs["hash"])

        if len(search_article) == 0:
            article_obj = Article(**article_kwargs)
            added_vids += 1
            no_new_video = 0

        else:
            article_obj = search_article[0]
            setattr(article_obj, "image_url", article_kwargs.get("image_url"))
            setattr(article_obj, "full_text_html", article_kwargs.get("full_text_html"))
            setattr(article_obj, "extract", article_kwarg.get("extract"))
            setattr(article_obj, "title", article_kwarg.get("title"))
            no_new_video += 1
        article_obj.save()

        (max_importance, min_article_relevance) = calcualte_relevance(
            publisher=feed.publisher,
            feed=feed,
            feed_position=article__feed_position,
            hash=article_kwargs["hash"],
            pub_date=article_kwargs["pub_date"],
            article_type=article_kwargs["content_type"],
        )
        for k, v in article_kwargs.items():
            value = getattr(article_obj, k)
            if value is None and v is not None:
                setattr(article_obj, k, v)
            elif k == "categories" and article_kwargs["categories"] is not None:
                for category in article_kwargs["categories"].split(";"):
                    if category.upper() not in v.upper():
                        v += category + ";"
                setattr(article_obj, k, v)
        article_obj.save()

        # Add feed position linking
        feed_position = FeedPosition(
            feed=feed,
            article=article_obj,
            position=article__feed_position,
            importance=max_importance,
            relevance=min_article_relevance,
        )
        feed_position.save()

    total_articles = (
        article__feed_position
        if "article__feed_position" in vars() or "article__feed_position" in globals()
        else "Unknown"
    )
    print(f"Refreshed '{feed}' with {added_vids} new videos out of {total_articles}")
    return added_vids
