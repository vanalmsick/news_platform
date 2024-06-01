# -*- coding: utf-8 -*-
"""mange.py command add_defaullt_feeds to add default data to database"""
from django.core.management import BaseCommand

from feeds.models import Feed, Publisher
from markets.models import DataGroup, DataSource
from preferences.models import Page


class Command(BaseCommand):
    """command for manage.py"""

    # Show this when the user types help
    help = "Adds StartUp default feeds"

    def handle(self, *args, **options):
        """adds default data to database"""
        initial_publishers = [
            {
                "name": "Financial Times",
                "link": "https://www.ft.com",
                "renowned": 3,
                "paywall": "Y",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "Tagesschau",
                "link": "https://www.tagesschau.de",
                "renowned": 3,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "de",
            },
            {
                "name": "ZDF Heute",
                "link": "https://www.heute.de",
                "renowned": 3,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "de",
            },
            {
                "name": "Redations Netzwerk Deutschland",
                "link": "https://www.rnd.de",
                "renowned": 2,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "de",
            },
            {
                "name": "FAZ",
                "link": "https://www.faz.net",
                "renowned": 2,
                "paywall": "Y",
                "unique_article_id": "guid",
                "language": "de",
            },
            {
                "name": "The Economist",
                "link": "http://www.economist.com",
                "renowned": 2,
                "paywall": "Y",
                "unique_article_id": "url",
                "language": "en",
            },
            {
                "name": "Harvard Business Review",
                "link": "https://hbr.org",
                "renowned": 1,
                "paywall": "Y",
                "unique_article_id": "url",
                "language": "en",
            },
            {
                "name": "MIT",
                "link": "https://sloanreview.mit.edu",
                "renowned": 1,
                "paywall": "Y",
                "unique_article_id": "url",
                "language": "en",
            },
            {
                "name": "Wall Street Journal",
                "link": "https://www.wsj.com/",
                "renowned": 2,
                "paywall": "Y",
                "unique_article_id": "url",
                "language": "en",
            },
            {
                "name": "Al Jazeera",
                "link": "https://www.aljazeera.com",
                "renowned": 1,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "CNBC",
                "link": "https://www.cnbc.com",
                "renowned": 1,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "CNN",
                "link": "https://www.cnn.com",
                "renowned": 1,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "Risk.net",
                "link": "https://www.risk.net",
                "renowned": 0,
                "paywall": "Y",
                "unique_article_id": "url",
                "language": "en",
            },
            {
                "name": "Hedge Week",
                "link": "https://www.hedgeweek.com",
                "renowned": 1,
                "paywall": "N",
                "unique_article_id": "url",
                "language": "en",
            },
            {
                "name": "Reuters",
                "link": "https://www.reuters.com",
                "renowned": 1,
                "paywall": "N",
                "unique_article_id": "url",
                "language": "en",
            },
            {
                "name": "Deutsche Welle",
                "link": "https://www.dw.com",
                "renowned": 1,
                "paywall": "N",
                "unique_article_id": "title",
                "language": "en",
            },
            {
                "name": "n-tv.de",
                "link": "https://www.n-tv.de",
                "renowned": 1,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "de",
            },
            {
                "name": "Bloomberg",
                "link": "https://www.bloomberg.com",
                "renowned": 3,
                "paywall": "Y",
                "unique_article_id": "url",
                "language": "en",
            },
            {
                "name": "BBC",
                "link": "https://www.bbc.com",
                "renowned": 0,
                "paywall": "N",
                "unique_article_id": "url",
                "language": "en",
            },
            {
                "name": "Nature Magazine",
                "link": "https://www.nature.com",
                "renowned": 0,
                "paywall": "N",
                "unique_article_id": "url",
                "language": "en",
            },
            {
                "name": "The Trade",
                "link": "http://www.thetradenews.com",
                "renowned": 0,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "9to5mac.com",
                "link": "http://www.9to5mac.com",
                "renowned": 2,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "TechCrunch",
                "link": "https://techcrunch.com",
                "renowned": 1,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "Futurity",
                "link": "https://www.futurity.org/",
                "renowned": 1,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "The Verge",
                "link": "http://www.theverge.com",
                "renowned": 1,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "Medium",
                "link": "http://www.medium.com",
                "renowned": 0,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "Google News",
                "link": "https://news.google.com",
                "renowned": -1,
                "paywall": "N",
                "unique_article_id": "url",
                "language": "en",
            },
            {
                "name": "Stuff Made Here",
                "link": "https://www.youtube.com/@StuffMadeHere",
                "renowned": 0,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "Teulu Tribe",
                "link": "https://www.youtube.com/@TeuluTribe",
                "renowned": 0,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "Kristinas Travels",
                "link": "https://www.youtube.com/@KristinasTravels",
                "renowned": 0,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "Veritasium",
                "link": "https://www.youtube.com/@veritasium",
                "renowned": 0,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "BigThink",
                "link": "https://www.youtube.com/@bigthink",
                "renowned": 0,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "EconomicsExplained",
                "link": "https://www.youtube.com/@EconomicsExplained",
                "renowned": 0,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "Wendover Productions",
                "link": "https://www.youtube.com/@Wendoverproductions",
                "renowned": 0,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "RealEngineering",
                "link": "https://www.youtube.com/@RealEngineering",
                "renowned": 0,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "TED",
                "link": "https://www.ted.com/",
                "renowned": 1,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "Vox",
                "link": "https://www.vox.com/",
                "renowned": 1,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
            {
                "name": "TheNextWeb",
                "link": "https://www.thenextweb.com/",
                "renowned": 1,
                "paywall": "N",
                "unique_article_id": "guid",
                "language": "en",
            },
        ]

        for publisher in initial_publishers:
            if len(Publisher.objects.filter(name=publisher["name"])) == 0:
                Publisher(**publisher).save()

        initial_feeds = [
            ########################### English News ###########################
            {
                "name": "Home International",
                "publisher": Publisher.objects.get(name="Financial Times"),
                "url": "https://www.ft.com/rss/home/international",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "N",
                "source_categories": "frontpage",
                "importance": 4,
            },
            {
                "name": "Markets",
                "publisher": Publisher.objects.get(name="Financial Times"),
                "url": "https://www.ft.com/markets?format=rss",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "N",
                "source_categories": "frontpage;markets",
                "importance": 1,
            },
            {
                "name": "News In Depth",
                "publisher": Publisher.objects.get(name="Financial Times"),
                "url": "https://www.ft.com/news-in-depth?format=rss",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "N",
                "source_categories": "frontpage;News In Depth;headline",
                "importance": 2,
            },
            {
                "name": "The Big Read",
                "publisher": Publisher.objects.get(name="Financial Times"),
                "url": "https://www.ft.com/the-big-read?format=rss",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "N",
                "source_categories": "frontpage;The Big Read;headline",
                "importance": 2,
            },
            {
                "name": "Country US",
                "publisher": Publisher.objects.get(name="Financial Times"),
                "url": "https://www.ft.com/us?format=rss",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "N",
                "source_categories": "frontpage;usa",
                "importance": 0,
            },
            {
                "name": "Country UK",
                "publisher": Publisher.objects.get(name="Financial Times"),
                "url": "https://www.ft.com/world-uk?format=rss",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "N",
                "source_categories": "frontpage;uk",
                "importance": 0,
            },
            {
                "name": "Region Europe",
                "publisher": Publisher.objects.get(name="Financial Times"),
                "url": "https://www.ft.com/europe?format=rss",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "N",
                "source_categories": "frontpage;europe",
                "importance": 0,
            },
            {
                "name": "Region Asia Pacific",
                "publisher": Publisher.objects.get(name="Financial Times"),
                "url": "https://www.ft.com/asia-pacific?format=rss",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "N",
                "source_categories": "asia",
                "importance": 0,
            },
            # {
            #    "name": "Region Asia",
            #    "publisher": Publisher.objects.get(name="CNN"),
            #    "url": (
            #        "http://FEED-CREATOR.local/extract.php?url=https%3A%2F%2Fedition.cnn.com%2Fworld%2Fasia"
            #        "&item=a.container__link&item_title=span.container__headline-text"
            #        "&max=13&order=document&guid=url"
            #    ),
            #    "active": True,
            #    "feed_ordering": "d",
            #    "full_text_fetch": "Y",
            #    "source_categories": "asia",
            #    "importance": 1,
            # },
            {
                "name": "Top News",
                "publisher": Publisher.objects.get(name="CNBC"),
                "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "frontpage;no push",
                "importance": 1,
            },
            {
                "name": "Markets",
                "publisher": Publisher.objects.get(name="CNBC"),
                "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "frontpage;markets;no push",
                "importance": 1,
            },
            # {
            #    "name": "Markets",
            #    "publisher": Publisher.objects.get(name="Reuters"),
            #    "url": (
            #        "http://FEED-CREATOR.local/extract.php?url=https%3A%2F%2Fwww.reuters.com%2Fmarkets%2F&"
            #        "in_id_or_class=content-layout__item__SC_GG&max=19&order=document&guid=0&strip_if_url%5B0%5D="
            #        "author&strip=.label__label__f9Hew%2C.events__data__18XBG%2C.media-story-card__placement-"
            #        "container__1R55-%2C.topic__header__3T_p2&keep_qs_params="
            #    ),
            #    "active": True,
            #    "feed_ordering": "r",
            #    "full_text_fetch": "Y",
            #    "source_categories": "frontpage;markets",
            #    "importance": 0,
            # },
            {
                "name": "All News",
                "publisher": Publisher.objects.get(name="Risk.net"),
                "url": "http://www.risk.net/feeds/rss/",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "frontpage",
                "importance": 0,
            },
            {
                "name": "All News",
                "publisher": Publisher.objects.get(name="Al Jazeera"),
                "url": "https://www.aljazeera.com/xml/rss/all.xml",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "frontpage",
                "importance": 2,
            },
            {
                "name": "All News",
                "publisher": Publisher.objects.get(name="Deutsche Welle"),
                "url": "http://rss.dw.com/rdf/rss-en-all",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "source_categories": "frontpage",
                "importance": 1,
            },
            {
                "name": "Markets",
                "publisher": Publisher.objects.get(name="Bloomberg"),
                "url": "https://feeds.bloomberg.com/markets/news.rss",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "N",
                "source_categories": "frontpage;markets",
                "importance": 3,
            },
            {
                "name": "Politics",
                "publisher": Publisher.objects.get(name="Bloomberg"),
                "url": "https://feeds.bloomberg.com/politics/news.rss",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "N",
                "source_categories": "frontpage;politics",
                "importance": 3,
            },
            # {
            #    "name": "Top News",
            #    "publisher": Publisher.objects.get(name="The Economist"),
            #    "url": (
            #        "http://FEED-CREATOR.local/mergefeeds.php?url%5B0%5D=https%3A%2F%2Fwww.economist.com%2F"
            #        "briefing%2Frss.xml&url%5B1%5D=https%3A%2F%2Fwww.economist.com%2Ffinance-and-economics%2F"
            #        "rss.xml&max=5&order=date"
            #    ),
            #    "active": True,
            #    "feed_ordering": "r",
            #    "full_text_fetch": "Y",
            #    "source_categories": "frontpage;magazine",
            #    "importance": 2,
            # },
            # {
            #    "name": "Countries",
            #    "publisher": Publisher.objects.get(name="The Economist"),
            #    "url": (
            #        "http://FEED-CREATOR.local/mergefeeds.php?url%5B0%5D=https%3A%2F%2Fwww.economist.com%2F"
            #        "europe%2Frss.xml&url%5B1%5D=https%3A%2F%2Fwww.economist.com%2Finternational%2Frss.xml&"
            #        "url%5B2%5D=https%3A%2F%2Fwww.economist.com%2Funited-states%2Frss.xml&url%5B3%5D="
            #        "https%3A%2F%2Fwww.economist.com%2Fthe-americas%2Frss.xml&url%5B4%5D=https%3A%2F%2F"
            #        "www.economist.com%2Fmiddle-east-and-africa%2Frss.xml&url%5B5%5D=https%3A%2F%2F"
            #        "www.economist.com%2Fasia%2Frss.xml&url%5B6%5D=https%3A%2F%2F"
            #        "www.economist.com%2Fchina%2Frss.xml&url%5B7%5D=https%3A%2F%2F"
            #        "www.economist.com%2Fbritain%2Frss.xml&max=12&order=date"
            #    ),
            #    "active": True,
            #    "feed_ordering": "r",
            #    "full_text_fetch": "Y",
            #    "source_categories": "frontpage;magazine;world",
            #    "importance": 2,
            # },
            ########################### Fund News ###########################
            {
                "name": "All News",
                "publisher": Publisher.objects.get(name="The Trade"),
                "url": "https://www.thetradenews.com/feed/",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "source_categories": "frontpage;funds;sidebar",
                "importance": 1,
            },
            {
                "name": "Latest",
                "publisher": Publisher.objects.get(name="Hedge Week"),
                "url": "https://www.hedgeweek.com/feed/",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "source_categories": "hedge funds;funds;sidebar",
                "importance": 3,
            },
            {
                "name": "Hedge Funds",
                "publisher": Publisher.objects.get(name="Financial Times"),
                "url": "https://www.ft.com/hedge-funds?format=rss",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "source_categories": "hedge funds;sidebar;breaking",
                "importance": 2,
            },
            {
                "name": "Fund Management",
                "publisher": Publisher.objects.get(name="Financial Times"),
                "url": "https://www.ft.com/fund-management?format=rss",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "source_categories": "funds;sidebar",
                "importance": 0,
            },
            {
                "name": 'Search "Hedge Funds"',
                "publisher": Publisher.objects.get(name="Google News"),
                "url": "https://news.google.com/rss/search?q=hedge+fund",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "source_categories": "google news;hedge funds;funds;sidebar",
                "importance": 0,
            },
            {
                "name": "Search Publisher:Bloomberg.com",
                "publisher": Publisher.objects.get(name="Google News"),
                "url": "https://news.google.com/rss/search?q=site%3ABloomberg.com%20when%3A1d",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "N",
                "source_categories": "google news",
                "importance": 1,
            },
            ########################### German News ###########################
            {
                "name": "Startseite",
                "publisher": Publisher.objects.get(name="Tagesschau"),
                "url": "https://www.tagesschau.de/index~rss2.xml",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "startseite",
                "importance": 2,
            },
            {
                "name": "Wirtschaft",
                "publisher": Publisher.objects.get(name="Tagesschau"),
                "url": "https://www.tagesschau.de/wirtschaft/index~rss2.xml",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "wirtschaft",
                "importance": 1,
            },
            {
                "name": "Ausland",
                "publisher": Publisher.objects.get(name="Tagesschau"),
                "url": "https://www.tagesschau.de/ausland/index~rss2.xml",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "ausland",
                "importance": 1,
            },
            {
                "name": "Startseite",
                "publisher": Publisher.objects.get(name="FAZ"),
                "url": "https://www.faz.net/rss/aktuell/",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "startseite",
                "importance": 0,
            },
            {
                "name": "Startseite",
                "publisher": Publisher.objects.get(name="ZDF Heute"),
                "url": "https://www.zdf.de/rss/zdf/nachrichten",
                "active": False,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "startseite",
                "importance": 2,
            },
            {
                "name": "Wirtschaft",
                "publisher": Publisher.objects.get(name="n-tv.de"),
                "url": "https://www.n-tv.de/wirtschaft/rss",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "wirtschaft",
                "importance": 2,
            },
            {
                "name": "Politik",
                "publisher": Publisher.objects.get(name="n-tv.de"),
                "url": "https://www.n-tv.de/politik/rss",
                "active": False,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "politik",
                "importance": 1,
            },
            {
                "name": "Politik",
                "publisher": Publisher.objects.get(
                    name="Redations Netzwerk Deutschland"
                ),
                "url": "https://www.rnd.de/arc/outboundfeeds/rss/category/politik/",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "wirtschaft",
                "importance": 1,
            },
            {
                "name": "Wirtschaft",
                "publisher": Publisher.objects.get(
                    name="Redations Netzwerk Deutschland"
                ),
                "url": "https://www.rnd.de/arc/outboundfeeds/rss/category/wirtschaft/",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "politik",
                "importance": 1,
            },
            ########################### Tech News ###########################
            {
                "name": "Technology",
                "publisher": Publisher.objects.get(name="Bloomberg"),
                "url": "https://feeds.bloomberg.com/technology/news.rss",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "N",
                "source_categories": "tech",
                "importance": 0,
            },
            {
                "name": "Home",
                "publisher": Publisher.objects.get(name="9to5mac.com"),
                "url": "http://9to5mac.com/feed/",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "source_categories": "tech",
                "importance": 3,
            },
            {
                "name": "Home",
                "publisher": Publisher.objects.get(name="TechCrunch"),
                "url": "https://techcrunch.com/feed/",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "tech",
                "importance": 2,
            },
            {
                "name": "Home",
                "publisher": Publisher.objects.get(name="The Verge"),
                "url": "http://www.theverge.com/rss/full.xml",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "tech",
                "importance": 2,
            },
            {
                "name": "Home",
                "publisher": Publisher.objects.get(name="TheNextWeb"),
                "url": "https://thenextweb.com/feed",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "tech",
                "importance": 2,
            },
            {
                "name": "#Python",
                "publisher": Publisher.objects.get(name="Medium"),
                "url": "https://medium.com/feed/tag/python",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "N",
                "source_categories": "tech",
                "importance": 0,
            },
            {
                "name": "@Python In Plain English",
                "publisher": Publisher.objects.get(name="Medium"),
                "url": "https://medium.com/feed/python-in-plain-english",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "N",
                "source_categories": "tech;python",
                "importance": 1,
            },
            {
                "name": "@Towards Data Science",
                "publisher": Publisher.objects.get(name="Medium"),
                "url": "https://medium.com/feed/towards-data-science",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "N",
                "source_categories": "tech;python;data science",
                "importance": 1,
            },
            ########################### Magazine Articles ###########################
            {
                "name": "Management",
                "publisher": Publisher.objects.get(name="Financial Times"),
                "url": "https://www.ft.com/management?format=rss",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "source_categories": "magazine;management",
                "importance": 1,
            },
            {
                "name": "Economics",
                "publisher": Publisher.objects.get(name="Nature Magazine"),
                "url": "https://www.nature.com/subjects/economics.rss",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "source_categories": "magazine;economics",
                "importance": 0,
            },
            {
                "name": "Finance",
                "publisher": Publisher.objects.get(name="Nature Magazine"),
                "url": "https://www.nature.com/subjects/finance.rss",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "source_categories": "magazine;finance",
                "importance": 0,
            },
            {
                "name": "Futurity",
                "publisher": Publisher.objects.get(name="Futurity"),
                "url": "https://www.futurity.org/feed/",
                "active": True,
                "feed_ordering": "r",
                "full_text_fetch": "Y",
                "source_categories": "magazine;science",
                "importance": 1,
            },
            {
                "name": "HBR",
                "publisher": Publisher.objects.get(name="Harvard Business Review"),
                "url": "http://feeds.hbr.org/harvardbusiness/",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "source_categories": "magazine;business;personal development",
                "importance": 2,
            },
            {
                "name": "Sloan Management Review",
                "publisher": Publisher.objects.get(name="MIT"),
                "url": "http://feeds.feedburner.com/mitsmr",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "source_categories": "magazine;business;personal development",
                "importance": 1,
            },
            {
                "name": "@Personal Growth",
                "publisher": Publisher.objects.get(name="Medium"),
                "url": "https://medium.com/feed/personal-growth",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "N",
                "source_categories": "magazine;personal development",
                "importance": 0,
            },
            {
                "name": "@Mind Cafe",
                "publisher": Publisher.objects.get(name="Medium"),
                "url": "https://medium.com/feed/mind-cafe",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "N",
                "source_categories": "magazine;personal development",
                "importance": 0,
            },
            ########################### YouTube Channels ###########################
            {
                "name": "Originals - YouTube Channel",
                "publisher": Publisher.objects.get(name="Bloomberg"),
                "url": "https://www.youtube.com/Bloomberg",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "business",
                "importance": 2,
            },
            {
                "name": "Quicktake - YouTube Channel",
                "publisher": Publisher.objects.get(name="Bloomberg"),
                "url": "https://www.youtube.com/@BloombergQuicktake",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "business",
                "importance": 0,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="Financial Times"),
                "url": "https://www.youtube.com/@FinancialTimes",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "business",
                "importance": 1,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="The Economist"),
                "url": "https://www.youtube.com/@TheEconomist",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "business",
                "importance": 1,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="Harvard Business Review"),
                "url": "https://www.youtube.com/@harvardbusinessreview",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "business",
                "importance": 2,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="Wall Street Journal"),
                "url": "https://www.youtube.com/@wsj",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "business",
                "importance": 3,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="Teulu Tribe"),
                "url": "https://www.youtube.com/@TeuluTribe",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "travel;sailing",
                "importance": 3,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="Kristinas Travels"),
                "url": "https://www.youtube.com/@KristinasTravels",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "travel;sailing",
                "importance": 3,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="Deutsche Welle"),
                "url": "https://www.youtube.com/@DWDocumentary",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "documentary",
                "importance": 2,
            },
            {
                "name": "CNBC - YouTube Channel",
                "publisher": Publisher.objects.get(name="CNBC"),
                "url": "https://www.youtube.com/@CNBC",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "business",
                "importance": 2,
            },
            {
                "name": "CNBC International - YouTube Channel",
                "publisher": Publisher.objects.get(name="CNBC"),
                "url": "https://www.youtube.com/@CNBCi",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "business",
                "importance": 2,
            },
            {
                "name": "TED - YouTube Channel",
                "publisher": Publisher.objects.get(name="TED"),
                "url": "https://www.youtube.com/@TED",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "educational",
                "importance": 2,
            },
            {
                "name": "TEDed - YouTube Channel",
                "publisher": Publisher.objects.get(name="TED"),
                "url": "https://www.youtube.com/@TEDEd",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "educational",
                "importance": 1,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="Vox"),
                "url": "https://www.youtube.com/@Vox",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "investigative",
                "importance": 1,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="Wendover Productions"),
                "url": "https://www.youtube.com/@Wendoverproductions",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "documentary",
                "importance": 1,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="BigThink"),
                "url": "https://www.youtube.com/@bigthink",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "educational",
                "importance": 3,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="EconomicsExplained"),
                "url": "https://www.youtube.com/@EconomicsExplained",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "documentary;business",
                "importance": 2,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="Stuff Made Here"),
                "url": "https://www.youtube.com/@StuffMadeHere",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "engineering",
                "importance": 0,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="Veritasium"),
                "url": "https://www.youtube.com/@veritasium",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "science",
                "importance": 3,
            },
            {
                "name": "YouTube Channel",
                "publisher": Publisher.objects.get(name="RealEngineering"),
                "url": "https://www.youtube.com/@RealEngineering",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-channel",
                "source_categories": "engineering",
                "importance": 1,
            },
            {
                "name": "World Services - YouTube Playlist",
                "publisher": Publisher.objects.get(name="BBC"),
                "url": "https://www.youtube.com/playlist?list=PLz_B0PFGIn4fADt3h_U2SOWErIq-xtXPD",
                "active": True,
                "feed_ordering": "d",
                "full_text_fetch": "Y",
                "feed_type": "y-playlist",
                "source_categories": "documentary",
                "importance": 1,
            },
        ]

        for feed in initial_feeds:
            if len(Feed.objects.filter(url=feed["url"])) == 0:
                Feed(**feed).save()

        initial_pages = [
            {
                "position_index": 1,
                "html_icon": "",
                "name": "Frontpage",
                "url_parameters": "categories=frontpage",
            },
            {
                "position_index": 2,
                "html_icon": (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"'
                    ' fill="currentColor" class="bi bi-translate" viewBox="0 0 16 16"'
                    ' style="margin: 0px 5px 0px 0px;"><path d="M4.545 6.714 4.11'
                    " 8H3l1.862-5h1.284L8 8H6.833l-.435-1.286H4.545zm1.634-.736L5.5"
                    ' 3.956h-.049l-.679 2.022H6.18z"/><path d="M0 2a2 2 0 0 1 2-2h7a2 2'
                    " 0 0 1 2 2v3h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H7a2 2 0 0"
                    " 1-2-2v-3H2a2 2 0 0 1-2-2V2zm2-1a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h7a1"
                    " 1 0 0 0 1-1V2a1 1 0 0 0-1-1H2zm7.138"
                    " 9.995c.193.301.402.583.63.846-.748.575-1.673 1.001-2.768"
                    " 1.292.178.217.451.635.555.867 1.125-.359 2.08-.844"
                    " 2.886-1.494.777.665 1.739 1.165 2.93"
                    " 1.472.133-.254.414-.673.629-.89-1.125-.253-2.057-.694-2.82-1.284.681-.747"
                    " 1.222-1.651 1.621-2.757H14V8h-3v1.047h.765c-.318.844-.74"
                    " 1.546-1.272 2.13a6.066 6.066 0 0 1-.415-.492 1.988 1.988 0 0"
                    ' 1-.94.31z"/></svg>'
                ),
                "name": "German",
                "url_parameters": "language=de",
            },
            {
                "position_index": 3,
                "html_icon": "#",
                "name": "Tech",
                "url_parameters": "categories=tech",
            },
            {
                "position_index": 4,
                "html_icon": (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"'
                    ' fill="currentColor" class="bi bi-clock" viewBox="0 0 16 16"'
                    ' style="margin: 0px 5px 0px 0px;"><path d="M8 3.5a.5.5 0 0 0-1'
                    " 0V9a.5.5 0 0 0 .252.434l3.5 2a.5.5 0 0 0 .496-.868L8"
                    ' 8.71V3.5z"/><path d="M8 16A8 8 0 1 0 8 0a8 8 0 0 0 0 16zm7-8A7 7'
                    ' 0 1 1 1 8a7 7 0 0 1 14 0z"/></svg>'
                ),
                "name": "Latest: Funds",
                "url_parameters": "special=sidebar",
            },
            {
                "position_index": 5,
                "html_icon": (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
                    'fill="currentColor" class="bi bi-book" viewBox="0 0 16 16" '
                    'style="margin: 0px 5px 0px 0px;"><path d="M1 2.828c.885-.37 '
                    "2.154-.769 3.388-.893 1.33-.134 2.458.063 3.112.752v9.746c-."
                    "935-.53-2.12-.603-3.213-.493-1.18.12-2.37.461-3.287.811zm7.5-"
                    ".141c.654-.689 1.782-.886 3.112-.752 1.234.124 2.503.523 3.38"
                    "8.893v9.923c-.918-.35-2.107-.692-3.287-.81-1.094-.111-2.278-."
                    "039-3.213.492zM8 1.783C7.015.936 5.587.81 4.287.94c-1.514.153"
                    "-3.042.672-3.994 1.105A.5.5 0 0 0 0 2.5v11a.5.5 0 0 0 .707.45"
                    "5c.882-.4 2.303-.881 3.68-1.02 1.409-.142 2.59.087 3.223.877a"
                    ".5.5 0 0 0 .78 0c.633-.79 1.814-1.019 3.222-.877 1.378.139 2."
                    "8.62 3.681 1.02A.5.5 0 0 0 16 13.5v-11a.5.5 0 0 0-.293-.455c-"
                    '.952-.433-2.48-.952-3.994-1.105C10.413.809 8.985.936 8 1.783"'
                    "/></svg>"
                ),
                "name": "In Depth Articles",
                "url_parameters": ("categories=news+in+depth,the+big+read,magazine"),
            },
            {
                "position_index": 6,
                "html_icon": (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"'
                    ' fill="currentColor" class="bi bi-play-btn" viewBox="0 0 16 16"'
                    ' style="margin: 0px 5px 0px 0px;"><path d="M6.79 5.093A.5.5 0 0 0'
                    " 6 5.5v5a.5.5 0 0 0 .79.407l3.5-2.5a.5.5 0 0 0"
                    ' 0-.814l-3.5-2.5z"/><path d="M0 4a2 2 0 0 1 2-2h12a2 2 0 0 1 2'
                    " 2v8a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V4zm15 0a1 1 0 0 0-1-1H2a1 1 0 0"
                    ' 0-1 1v8a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V4z"/></svg>'
                ),
                "name": "Videos",
                "url_parameters": "content_type=video",
            },
            {
                "position_index": 7,
                "html_icon": (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"'
                    ' fill="currentColor" class="bi bi-bookmark" viewBox="0 0 16 16"'
                    ' style="margin: 0px 5px 0px 0px;">  <path d="M2 2a2 2 0 0 1'
                    " 2-2h8a2 2 0 0 1 2 2v13.5a.5.5 0 0 1-.777.416L8 13.101l-5.223"
                    " 2.815A.5.5 0 0 1 2 15.5zm2-1a1 1 0 0 0-1"
                    " 1v12.566l4.723-2.482a.5.5 0 0 1 .554 0L13 14.566V2a1 1 0 0"
                    ' 0-1-1z"/></svg>'
                ),
                "name": "Read Later",
                "url_parameters": "read_later=true",
            },
        ]

        for page in initial_pages:
            if len(Page.objects.filter(position_index=page["position_index"])) == 0:
                Page(**page).save()

        # For Marekt Data
        initial_data_groups = [
            {
                "name": "Indices",
                "position": 1,
            },
            {
                "name": "FX",
                "position": 2,
            },
            {
                "name": "Rates",
                "position": 3,
            },
            {
                "name": "Commodities",
                "position": 4,
            },
            {
                "name": "Winners/Loosers",
                "position": 5,
            },
        ]

        for group in initial_data_groups:
            if len(DataGroup.objects.filter(name=group["name"])) == 0:
                DataGroup(**group).save()

        initial_data_sources = [
            {
                "group": DataGroup.objects.get(name="Indices"),
                "name": "S&P 500 (US)",
                "pinned": False,
                "ticker": "^GSPC",
            },
            {
                "group": DataGroup.objects.get(name="Indices"),
                "name": "NASDAQ (US)",
                "pinned": False,
                "ticker": "^IXIC",
            },
            {
                "group": DataGroup.objects.get(name="Indices"),
                "name": "FTSE 100 (UK)",
                "pinned": False,
                "ticker": "^FTSE",
            },
            {
                "group": DataGroup.objects.get(name="Indices"),
                "name": "DAX (DE)",
                "pinned": False,
                "ticker": "^GDAXI",
            },
            {
                "group": DataGroup.objects.get(name="Indices"),
                "name": "STOXX600 (EU)",
                "pinned": False,
                "ticker": "^STOXX",
            },
            {
                "group": DataGroup.objects.get(name="Indices"),
                "name": "Nikkei 225 (JP)",
                "pinned": False,
                "ticker": "^N225",
            },
            {
                "group": DataGroup.objects.get(name="Indices"),
                "name": "Hang Seng (HK)",
                "pinned": False,
                "ticker": "^HSI",
            },
            {
                "group": DataGroup.objects.get(name="Indices"),
                "name": "Shenzhen (CN)",
                "pinned": False,
                "ticker": "399001.SZ",
            },
            {
                "group": DataGroup.objects.get(name="Indices"),
                "name": "Vix (Vola)",
                "pinned": True,
                "ticker": "^VIX",
            },
            {
                "group": DataGroup.objects.get(name="Rates"),
                "name": "US 10Y",
                "pinned": False,
                "data_source": "te",
                "ticker": "United States",
            },
            {
                "group": DataGroup.objects.get(name="Rates"),
                "name": "UK 10Y",
                "pinned": False,
                "data_source": "te",
                "ticker": "United Kingdom",
            },
            {
                "group": DataGroup.objects.get(name="Rates"),
                "name": "JP 10Y",
                "pinned": False,
                "data_source": "te",
                "ticker": "Japan",
            },
            {
                "group": DataGroup.objects.get(name="Rates"),
                "name": "DE 10Y",
                "pinned": False,
                "data_source": "te",
                "ticker": "Germany",
            },
            {
                "group": DataGroup.objects.get(name="Rates"),
                "name": "FR 10Y",
                "pinned": False,
                "data_source": "te",
                "ticker": "France",
            },
            {
                "group": DataGroup.objects.get(name="Rates"),
                "name": "IT 10Y",
                "pinned": False,
                "data_source": "te",
                "ticker": "Italy",
            },
            {
                "group": DataGroup.objects.get(name="FX"),
                "name": "USD $",
                "pinned": True,
                "ticker": "EURUSD=X",
            },
            {
                "group": DataGroup.objects.get(name="FX"),
                "name": "EUR €",
                "pinned": True,
                "ticker": "EUR=X",
            },
            {
                "group": DataGroup.objects.get(name="FX"),
                "name": "GBP £",
                "pinned": True,
                "ticker": "GBP=X",
            },
            {
                "group": DataGroup.objects.get(name="FX"),
                "name": "CNY ¥",
                "pinned": False,
                "ticker": "CNY=X",
            },
            {
                "group": DataGroup.objects.get(name="FX"),
                "name": "JPY ¥",
                "pinned": False,
                "ticker": "JPY=X",
            },
            {
                "group": DataGroup.objects.get(name="FX"),
                "name": "IDR ₹",
                "pinned": False,
                "ticker": "IDR=X",
            },
            {
                "group": DataGroup.objects.get(name="FX"),
                "name": "BTC ₿",
                "pinned": False,
                "ticker": "BTC-USD",
            },
            {
                "group": DataGroup.objects.get(name="Commodities"),
                "name": "Gold",
                "pinned": True,
                "ticker": "GC=F",
            },
            {
                "group": DataGroup.objects.get(name="Commodities"),
                "name": "Crude Oil",
                "pinned": True,
                "ticker": "CL=F",
            },
            {
                "group": DataGroup.objects.get(name="Commodities"),
                "name": "Silver",
                "pinned": False,
                "ticker": "SI=F",
            },
            {
                "group": DataGroup.objects.get(name="Commodities"),
                "name": "Platinum",
                "pinned": False,
                "ticker": "PL=F",
            },
            {
                "group": DataGroup.objects.get(name="Commodities"),
                "name": "Copper",
                "pinned": False,
                "ticker": "HG=F",
            },
            {
                "group": DataGroup.objects.get(name="Commodities"),
                "name": "Palladium",
                "pinned": False,
                "ticker": "PA=F",
            },
            {
                "group": DataGroup.objects.get(name="Commodities"),
                "name": "Natural Gas",
                "pinned": False,
                "ticker": "NG=F",
            },
            {
                "group": DataGroup.objects.get(name="Commodities"),
                "name": "Brent Crude Oil",
                "pinned": False,
                "ticker": "BZ=F",
            },
        ]

        for data_src in initial_data_sources:
            if len(DataSource.objects.filter(ticker=data_src["ticker"])) == 0:
                DataSource(**data_src).save()
