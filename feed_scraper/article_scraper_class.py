# -*- coding: utf-8 -*-

import datetime
import html
import re
import time
import urllib

import langid
from bs4 import BeautifulSoup
from django.conf import settings

from .google_news_decode import decode_google_news_url

# from newspaper import Article
# import hashlib


# Content types (default: article)
LIVE_TICKER_KEYWORDS = [
    "liveticker",
    "liveblog",
    "live blog",
    "live news",
    "live update",
    "live:",
]

BRIEFING_NEWS_KEYWORDS = [
    "start your day:",
    "briefing:",
    "newsletter:",
    "daily:",
    "weekly:",
    "markets wrap",
    "list of key events",
    "firstft",
    "power on",
    "this week in",
    "weekly recap",
]

# Importance types (default: normal)
BREAKING_NEWS_KEYWORDS = [
    "breaking news",
    "developing story",
]

HEADLINE_NEWS_KEYWORDS = [
    "big read",
    "news in depth",
]

# keywords to detect paywall items
PAYWALL_KEYWORDS = ["standard digital", "continue reading"]


def is_valid_url(url):
    """small helper function to check if url (e.g. image url) is a valid url"""
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def ensure_dt_is_tz_aware(dt):
    """small helper function to ensure all datetime.datetime are time-zone aware"""
    if type(dt) is datetime.datetime and dt.tzinfo is None:
        dt = settings.TIME_ZONE_OBJ.localize(dt)
    return dt


def html_clean_up(article_html):
    """helper function to clean-up html code and remove unwanted parts"""
    soup = BeautifulSoup(article_html, "html.parser")
    for i, img in enumerate(soup.find_all("img")):
        img["style"] = "max-width: 100%; max-height: 80vh; width: auto; height: auto;"
        if img["src"].lower() in ["src", "none", ""]:
            if "data-url" in img.attrs:
                img["src"] = str(img["data-url"]).replace("${formatId}", "906")
            elif "data-src" in img.attrs:
                img["src"] = img["data-src"]
        if "srcset" in img.attrs:
            img["srcset"] = ""
        img["referrerpolicy"] = "no-referrer"

    for own_class in ["headline", "breaking", "live", "briefing"]:
        matches = soup.find_all(class_=own_class)
        for match in matches:
            match["class"].remove(own_class)

    for figure in soup.find_all("figure"):
        figure["class"] = "figure"

    for figcaption in soup.find_all("figcaption"):
        figcaption["class"] = "figure-caption"

    for span in soup.find_all("span", attrs={"data-caps": "initial"}):
        span["class"] = "h3"

    for a in soup.find_all("a"):
        a["target"] = "_blank"
        a["referrerpolicy"] = "no-referrer"
        a["class"] = "link-trace"

    for link in soup.find_all("link"):
        if link is not None:
            link.decompose()
    for form in soup.find_all("form"):
        if form is not None:
            form.decompose()

    for input in soup.find_all("input"):
        if input is not None:
            input.decompose()

    for button in soup.find_all("button"):
        if button is not None:
            button.decompose()

    for meta in soup.find_all("meta"):
        if meta is not None:
            meta.decompose()

    for noscript in soup.find_all("noscript"):
        if noscript is not None:
            noscript.name = "div"

    for div_type, id in [
        ("div", "barrierContent"),
        ("div", "nousermsg"),
        ("div", "trial_print_message"),
        ("div", "print_blocked_message"),
        ("div", "copy_blocked_message"),
        ("div", "posted-in"),
        ("div", "related-articles"),
        ("div", "video-html5-playlist"),
        ("div", "article-meta"),
        ("div", "hidden"),
        ("p", "vjs-no-js"),
        ("section", "ad"),
        ("blockquote", "twitter-tweet"),
        ("aside", "read-more"),
        ("nav", "breadcrumbs"),
        ("button", "toolbar-item-parent-share-2909"),
        ("button", "CreateFreeAccountButton-buttonContainer"),
        ("ul", "toolbar-item-dropdown-share-2909"),
    ]:
        divs = soup.find_all(div_type, id=id)
        if divs is None:
            divs = soup.find_all(div_type, class_=id)
        if divs is not None:
            for div in divs:
                div.decompose()

    article_html = soup.prettify()
    article_text = soup.text
    # article_text = " ".join(html.unescape(article_text).split())
    article_text = re.sub(r"\n+", "\n", article_text).strip()

    return article_html, article_text


class ScrapedArticle:
    """
    Class to collect all article information from scraping.

    Class attribute naming scheme: field_name__source (sources: feed, meta, scrape)
    """

    def __init__(self, feed_model):
        self.feed_obj__model = feed_model
        self.paywall = False
        self.aggregator_source = False
        self.current_categories = None

    ################################# PARSE AND STANDARDIZE ATTRIBUTES #################################

    def __parse_attrs(self, obj, translate_dict):
        """
        function to extract attributes from source object, standardize the data type, and save with standardized name
        """

        # KEYS_USED = []
        for key_src, key_dest in translate_dict.items():
            if (value := obj.get(key_src, None) if isinstance(obj, dict) else getattr(obj, key_src, None)) is not None:
                # convert struct_time to datetime
                if isinstance(value, time.struct_time):
                    value = datetime.datetime.fromtimestamp(time.mktime(value))

                # make datetime timezone aware
                value = ensure_dt_is_tz_aware(value)

                # convert non-list items to lists
                if "lst" in key_dest and not isinstance(value, list):
                    value = [value]

                # don't update item if paywall
                if isinstance(value, str) and any([i in value.lower() for i in PAYWALL_KEYWORDS]):
                    self.paywall = True
                else:
                    # set/update attr
                    if "lst" in key_dest and (value_curr := getattr(self, key_dest, None)) is not None:
                        setattr(self, key_dest, [*value_curr, *value])
                    else:
                        setattr(self, key_dest, value)

                    # KEYS_USED.append(key_src)
        # if 'href' in obj:
        #    print()
        # print('Not Used:', [i for i in obj.keys() if i not in KEYS_USED])

    def add_feed_attrs(self, feed_obj, article_obj):
        """parse attributes from rss feed data"""
        FEED_MAPPING = {
            "subtitle": "feed_subtitle__feed",
            "link": "feed_link__feed",
            "links": "feed_link_lst__feed",
            "title": "feed_title__feed",
            "sy_updatefrequency": "feed_update_freq_n__feed",
            "sy_updateperiod": "feed_update_freq_period__feed",
            "updated_parsed": "feed_last_updated__feed",
            "tags": "feed_tag_lst__feed",
            "language": "feed_language__feed",
            "media_thumbnail": "feed_thumbnail_lst__feed",
            "image": "feed_thumbnail_lst__feed",
        }
        ARTICLE_MAPPING = {
            "title": "article_title__feed",
            "link": "article_link__feed",
            "links": "article_link_lst__feed",
            "author": "article_author__feed",
            "summary": "article_summary__feed",
            "id": "article_id__feed",
            "published_parsed": "article_published__feed",
            "updated_parsed": "article_last_updated__feed",
            "tags": "article_tag_lst__feed",
            "language": "article_language__feed",
            "media_thumbnail": "article_thumbnail_lst__feed",
            "media_content": "article_thumbnail_lst__feed",
            "image": "article_thumbnail_lst__feed",
            "content": "article_content_lst__feed",
            "source": "article_publisher__feed",
        }
        self.__parse_attrs(feed_obj, FEED_MAPPING)
        self.__parse_attrs(article_obj, ARTICLE_MAPPING)

        # check if summary is html or text
        if (article_html := getattr(self, "article_summary__feed", None)) not in [
            None,
            "",
        ]:
            if bool(BeautifulSoup(article_html, "html.parser").find()):  # html
                (
                    self.article_summary_html__feed,
                    self.article_summary_text__feed,
                ) = html_clean_up(article_html)
                self.article_summary_text__feed = " ".join(html.unescape(self.article_summary_text__feed).split())
            else:
                self.article_summary_text__feed = article_html
                self.article_summary_html__feed = f"<p>{article_html}</p>"

        # convert content list to html and text
        if (content_lst := getattr(self, "article_content_lst__feed", None)) is not None:
            new_content_html = ""
            for content_i in content_lst:
                content_i_value = content_i.get("value", "")
                content_i_is_html = "html" in content_i.get("type", "") or (
                    content_i_value != "" and bool(BeautifulSoup(content_i_value, "html.parser").find())
                )
                new_content_html += f"{content_i_value}<br>\n" if content_i_is_html else f"<p>{content_i_value}</p>\n"
            (
                self.article_content_html__feed,
                self.article_content_text__feed,
            ) = html_clean_up(new_content_html)

    def parse_meta_attrs(self, response_obj):
        """parse attributes from <meta> tags in html of article link/url"""
        META_MAPPING = {
            "article_title__meta": ["title__", "meta__og:title"],
            "article_summary__meta": ["meta__description", "meta__og:description"],
            "article_thumbnail__meta": ["meta__og:image"],
            "article_language__meta": ["meta__og:locale"],
            "article_link__meta": ["meta__og:url"],
            "article_published__meta": ["meta__article:published_time"],
            "article_last_updated__meta": ["meta__article:modified_time"],
            "article_author__meta": ["meta__article:author"],
            "article_tag_lst__meta": ["meta__article:tag"],
        }
        soup = BeautifulSoup(response_obj.text, "html.parser")
        for key_dest, key_src_lst in META_MAPPING.items():
            for key_src in key_src_lst:
                tag, attr = key_src.split("__")
                match = soup.find(tag, None if attr == "" else {"property": attr})

                if match is not None:
                    value = match.text if tag == "title" else match["content"]

                    # format iso datetime str
                    if "_time" in attr:
                        value = datetime.datetime.fromisoformat(value)
                        value = ensure_dt_is_tz_aware(value)

                    setattr(self, key_dest, value)
                    break

    def parse_scrape_attrs(self, json_dict):
        """parse attributes from full-text scraper - currently used five-filters.org but later own scraper"""
        SCRAPE_MAPPING = {
            "title": "article_title__scrape",
            "og_title": "article_title__scrape",
            "excerpt": "article_summary__scrape",
            "og_description": "article_summary__scrape",
            "date": "article_last_updated__scrape",
            "author": "article_author__scrape",
            "language": "article_language__scrape",
            "effective_url": "article_link__scrape",
            "content": "article_content_html__scrape",
            "og_image": "article_thumbnail__scrape",
        }
        self.__parse_attrs(json_dict, SCRAPE_MAPPING)
        if (value := getattr(self, "article_last_updated__scrape", None)) is not None:
            value = datetime.datetime.fromisoformat(value)
            value = ensure_dt_is_tz_aware(value)
            setattr(self, "article_last_updated__scrape", value)
        if (article_html := getattr(self, "article_content_html__scrape", None)) is not None:
            (
                self.article_content_html__scrape,
                self.article_content_text__scrape,
            ) = html_clean_up(article_html)

    ################################# SELECT BEST ATTRIBUTES FROM ALL AVAILABLE #################################

    @property
    def article_link__final(self):
        """article target url/link (decode/follow to true source if news aggregator like google news)"""
        article_url = self.article_link__feed
        if "news.google" in article_url:
            article_url = decode_google_news_url(article_url)
            self.aggregator_source = True
        return article_url

    @property
    def article_publisher__final(self):
        if self.aggregator_source or self.feed_obj__model is None:
            publisher_dict = dict(getattr(self, "article_publisher__feed", {}))
            # rename keys to be identical to Publisher django model
            for old_key, new_key in {"title": "name", "href": "link"}.items():
                if old_key in publisher_dict:
                    publisher_dict[new_key] = publisher_dict.pop(old_key)
            return publisher_dict
        else:
            return self.feed_obj__model.publisher

    @property
    def article_id__final(self):
        """unique id from feed data or url as fallback"""
        feed_obj = self.feed_obj__model
        pk = 0 if feed_obj is None else feed_obj.publisher.pk
        if (guid := getattr(self, "article_id__feed", None)) is not None:
            return f"{pk}_{guid}"
        else:
            return f'{pk}_{self.article_link__feed.split("?")[0].lower()}'

    @property
    def article_hash__final(self):
        """unique hash using article url"""
        return f"{self.article_link__final.split('?')[0].lower()}"
        # return f"{hashlib.sha256(self.article_link__final.split('?')[0].lower().encode('utf-8')).hexdigest()}"

    @property
    def article_img_lst__final(self):
        """get all image urls from all attributes ordered by most likely to be good article thumbnail to least"""
        img_lst = []
        if (tmp_img := getattr(self, "article_thumbnail__meta", None)) is not None:
            if ".svg" not in tmp_img:
                img_lst.append(tmp_img)
        if (tmp_img := getattr(self, "article_thumbnail__scrape", None)) is not None:
            if ".svg" not in tmp_img:
                img_lst.append(tmp_img)
        if (tmp_img_lst := getattr(self, "article_thumbnail_lst__feed", None)) is not None:
            for tmp_img_i in tmp_img_lst:
                if "url" in tmp_img_i and is_valid_url(tmp_img_i["url"]) and ".svg" not in tmp_img_i["url"]:
                    img_lst.append(tmp_img_i["url"])
                elif "href" in tmp_img_i and is_valid_url(tmp_img_i["href"]) and ".svg" not in tmp_img_i["href"]:
                    img_lst.append(tmp_img_i["href"])
                elif "src" in tmp_img_i and is_valid_url(tmp_img_i["src"]) and ".svg" not in tmp_img_i["src"]:
                    img_lst.append(tmp_img_i["src"])
        if (tmp_content_html := getattr(self, "article_summary_html__feed", None)) is not None:
            tmp_soup = BeautifulSoup(tmp_content_html, "html.parser")
            for tmp_img in tmp_soup.find_all("img"):
                if "src" in tmp_img.attrs and is_valid_url(tmp_img["src"]) and ".svg" not in tmp_img["src"]:
                    img_lst.append(tmp_img["src"])
        if (tmp_content_html := getattr(self, "article_content_html__feed", None)) is not None:
            tmp_soup = BeautifulSoup(tmp_content_html, "html.parser")
            for tmp_img in tmp_soup.find_all("img"):
                if "src" in tmp_img.attrs and is_valid_url(tmp_img["src"]) and ".svg" not in tmp_img["src"]:
                    img_lst.append(tmp_img["src"])
        if (tmp_content_html := getattr(self, "article_content_html__scrape", None)) is not None:
            tmp_soup = BeautifulSoup(tmp_content_html, "html.parser")
            for tmp_img in tmp_soup.find_all("img"):
                if "src" in tmp_img.attrs and is_valid_url(tmp_img["src"]) and ".svg" not in tmp_img["src"]:
                    img_lst.append(tmp_img["src"])
        return img_lst

    @property
    def article_thumbnail__final(self):
        """take first image from image list as article thumbnail as image list is ordered"""
        img_lst = self.article_img_lst__final
        if len(img_lst) == 0:
            return None
        else:
            return img_lst[0]

    @property
    def article_importance_type__final(self):
        title_texts = [
            getattr(self, "article_title__feed", "").lower(),
            getattr(self, "article_title__meta", "").lower(),
            getattr(self, "article_title__scrape", "").lower(),
        ]
        summary_texts = [
            getattr(self, "article_summary_text__feed", "").lower(),
            getattr(self, "article_summary__meta", "").lower(),
            getattr(self, "article_summary__scrape", "").lower(),
        ]
        # ToDo: add tag check too

        if any([any([i in j for j in title_texts] + [i in j for j in summary_texts]) for i in BREAKING_NEWS_KEYWORDS]):
            return "breaking"
        elif any(
            [any([i in j for j in title_texts] + [i in j for j in summary_texts]) for i in HEADLINE_NEWS_KEYWORDS]
        ):
            return "headline"
        else:
            return "normal"

    @property
    def article_content_type__final(self):
        title_texts = [
            getattr(self, "feed_title__feed", "").lower(),
            getattr(self, "article_title__meta", "").lower(),
            getattr(self, "article_title__scrape", "").lower(),
        ]
        summary_texts = [
            getattr(self, "article_summary__feed", "").lower(),
            getattr(self, "article_summary_text__feed", "").lower(),
            getattr(self, "article_summary__meta", "").lower(),
            getattr(self, "article_summary__scrape", "").lower(),
        ]
        # ToDo: add tag check too

        if any([any([i in j for j in title_texts] + [i in j for j in summary_texts]) for i in LIVE_TICKER_KEYWORDS]):
            return "ticker"
        elif any(
            [any([i in j for j in title_texts] + [i in j for j in summary_texts]) for i in BRIEFING_NEWS_KEYWORDS]
        ):
            return "briefing"
        else:
            return "article"

    @property
    def article_title__final(self):
        prio_order = [
            "article_title__feed",
            "article_title__meta",
            "article_title__scrape",
        ]
        if self.article_content_type__final == "ticker":
            # if live ticker prefer <meta> tag title and scraped title over feed provided title as might be outdated
            prio_order = prio_order[1:] + prio_order[:1]
        for attr in prio_order:
            if (title := getattr(self, attr, None)) is not None:
                return title

    @property
    def article_summary__final(self):
        prio_order = [
            "article_summary_text__feed",
            "article_summary__meta",
            "article_summary__scrape",
        ]
        if self.article_content_type__final == "ticker":
            # if live ticker prefer <meta> tag title and scraped title over feed provided title as might be outdated
            prio_order = [
                "article_summary__meta",
                "article_summary__scrape",
                "article_summary_text__feed",
            ]
        elif getattr(self, "article_summary__feed", "") != "" and bool(
            BeautifulSoup(getattr(self, "article_summary__feed", "empty"), "html.parser").find()
        ):
            # if summary from feed is html prefer <meta> tag summary
            prio_order = [
                "article_summary__meta",
                "article_summary_text__feed",
                "article_summary__scrape",
            ]
        fallback_summary = None
        for attr in prio_order:
            if (summary := getattr(self, attr, None)) is not None:
                fallback_summary = summary
                if len(summary) >= 25:  # favor longer than 25 char summaries
                    return summary
        return fallback_summary

    @property
    def article_has_summary__final(self):
        summary = getattr(self, "article_summary__final", None)
        content = getattr(self, "article_content_text__final", None)
        if summary is None:
            return False
        else:
            if content is not None and len(summary) > 6 and summary.lower()[:-5] in content.lower():
                return False
            else:
                return True

    @property
    def article_content_source__final(self):
        content_feed = getattr(self, "article_content_text__feed", None)
        content_scrape = getattr(self, "article_content_text__scrape", None)
        if content_feed is not None and content_scrape is not None:  # if several sources
            if len(content_scrape) > len(content_feed) * 1.25:
                return "scrape"
            else:
                return "feed"
        elif content_feed is not None:  # if only one source - feed
            return "feed"
        elif content_scrape is not None:  # if only one source - scrape
            return "scrape"
        else:  # if no source
            return None

    @property
    def article_content_text__final(self):
        if self.article_content_source__final == "scrape":
            return self.article_content_text__scrape
        elif self.article_content_source__final == "feed":
            return self.article_content_text__feed
        else:
            return None

    @property
    def article_content_html__final(self):
        if self.article_content_source__final == "scrape":
            return self.article_content_html__scrape
        elif self.article_content_source__final == "feed":
            return self.article_content_html__feed
        else:
            return None

    @property
    def article_has_content__final(self):
        return (
            self.paywall is False
            and self.article_content_text__final is not None
            and len(self.article_content_text__final) >= 1500
        )

    @property
    def article_author__final(self):
        prio_order = [
            "article_author__feed",
            "article_author__meta",
            "article_author__scrape",
        ]
        for attr in prio_order:
            if (author := getattr(self, attr, None)) is not None:
                return author

    @property
    def article_language__final(self):
        language_lst = [
            getattr(self, "article_language__feed", None),
            getattr(self, "feed_language__feed", None),
            getattr(self, "article_language__meta", None),
        ]
        all_three_agree = all(
            [
                all([j[:2].lower() == i[:2].lower() for j in language_lst if j is not None and len(j) >= 2])
                for i in language_lst
                if i is not None and len(i) >= 2
            ]
        )
        if all_three_agree and language_lst != [None, None, None]:
            for language_i in language_lst:
                if language_i is not None and len(language_i) == 2:
                    return f"{language_i}-XX"
                elif language_i is not None and len(language_i) == 5:
                    return language_i.replace("_", "-")

        # if no suitable language attr found - detect yourself
        lang = langid.classify(f"{self.article_title__final}\n{self.article_summary__final}")
        return f"{lang[0]}-XX"

    @property
    def article_published__final(self):
        prio_order = ["article_published__feed", "article_published__meta"]
        for attr in prio_order:
            if (published := getattr(self, attr, None)) is not None:
                return published

    @property
    def article_published_filled__final(self):
        prio_order = [
            "article_published__final",
            "feed_last_updated__feed",
            "feed_last_updated__feed",
            "article_last_updated__feed",
            "article_last_updated__meta",
            "article_last_updated__scrape",
        ]
        for attr in prio_order:
            if (published := getattr(self, attr, None)) is not None:
                return published
        # fallback - now
        return settings.TIME_ZONE_OBJ.localize(datetime.datetime.now())

    @property
    def article_last_updated__final(self):
        prio_order = [
            "article_last_updated__feed",
            "article_last_updated__meta",
            "article_last_updated__scrape",
        ]
        for attr in prio_order:
            if (updated := getattr(self, attr, None)) is not None:
                return updated

    @property
    def article_last_updated_filled__final(self):
        prio_order = [
            "article_last_updated__final",
            "feed_last_updated__feed",
            "article_published_filled__final",
        ]
        for attr in prio_order:
            if (updated := getattr(self, attr, None)) is not None:
                return updated

    @property
    def article_tags__final(self):
        tags = (
            [
                {"term": i}
                for i in ([] if self.current_categories is None else self.current_categories.split(";"))
                + ([] if self.feed_obj__model is None else self.feed_obj__model.source_categories.split(";"))
            ]
            + getattr(self, "feed_tag_lst__feed", [])
            + getattr(self, "article_tag_lst__feed", [])
            + [
                {"term": i}
                for i in getattr(self, "article_tag_lst__meta", "").replace(", ", ";").replace(",", ";").split(";")
                if i != ""
            ]
        )
        new_tags = ";"
        for tag in tags:
            if tag["term"].lower() not in new_tags.lower() and tag["term"] != "":
                new_tags += tag["term"] + ";"
        return new_tags[1:-1]

    def get_final_attrs(self):
        return {
            "publisher": self.article_publisher__final,
            "title": self.article_title__final,
            "author": self.article_author__final,
            "link": self.article_link__final,
            "image_url": self.article_thumbnail__final,
            "importance_type": self.article_importance_type__final,
            "content_type": self.article_content_type__final,
            "extract": self.article_summary__final,
            "has_extract": self.article_has_summary__final,
            "full_text_html": self.article_content_html__final,
            "full_text_text": self.article_content_text__final,
            "has_full_text": self.article_has_content__final,
            "pub_date": self.article_published_filled__final,
            "last_updated_date": self.article_last_updated_filled__final,
            "categories": self.article_tags__final,
            "language": self.article_language__final,
            "guid": self.article_id__final,
            "hash": self.article_hash__final,
        }


## Download HTML yourself and insert into Newspaper3k
# n3k_article = Article(article_url)
# n3k_article.download(input_html=response.text)
# n3k_article.parse()
# n3k_article.nlp()
# boday_html = lxml.etree.tostring(n3k_article.clean_top_node, pretty_print=True)
