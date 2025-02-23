# -*- coding: utf-8 -*-
"""Data scraping for Market Data i.e. Stock/FX/Comm prices"""

import datetime
import traceback
from io import StringIO

import pandas as pd
from curl_cffi import requests  # type: ignore
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Q, SmallIntegerField
from django.db.models.expressions import Func, Window
from django.db.models.functions import Cast, RowNumber
from webpush import send_group_notification

from .models import DataEntry, DataSource


class ABS(Func):
    """abs() function for django querysets"""

    function = "ABS"


def __get_bonds(tickers, headers={"User-agent": "Mozilla/5.0"}):
    """Function to scrape rates market data form tradingeconomics.com"""
    site = "https://tradingeconomics.com/bonds"
    response = requests.get(site, headers=headers).text
    soup = BeautifulSoup(response, "lxml")

    span = soup.find("span", {"class": "market-negative-image"})
    while span is not None:
        new_tag = soup.new_tag("span")
        new_tag.string = "-"
        span.replace_with(new_tag)
        span = soup.find("span", {"class": "market-negative-image"})

    tables = pd.read_html(StringIO(str(soup)))
    data = tables[0].iloc[:, 1:].set_index("Major10Y").to_dict(orient="index")

    latest_data = []
    if len(tickers) > 0:
        for ticker in tickers:
            if ticker.ticker in data:
                data_yield = (
                    float("".join([i for i in data[ticker.ticker]["Yield"] if i.isdigit() or i == "-" or i == "."]))
                    if isinstance(data[ticker.ticker]["Yield"], str)
                    else data[ticker.ticker]["Yield"]
                )
                data_day = (
                    float("".join([i for i in data[ticker.ticker]["Day"] if i.isdigit() or i == "-" or i == "."]))
                    if isinstance(data[ticker.ticker]["Day"], str)
                    else data[ticker.ticker]["Day"]
                )
                obj = DataEntry(
                    source=ticker,
                    price=data_yield,
                    change_today=data_day * 100,
                )
                obj.save()
                latest_data.append(obj.pk)

    return latest_data


def __get_quote_table(ticker, headers={"User-agent": "Mozilla/5.0"}):
    """Scrape Market Data from Yahoo Finance"""

    url = "https://query1.finance.yahoo.com/v7/finance/spark"

    querystring = {
        "includePrePost": "false",
        "includeTimestamps": "false",
        "indicators": "close",
        "interval": "1d",
        "range": "1d",
        "symbols": ticker,
        "lang": "en-US",
        "region": "US",
    }

    request = requests.get(url, params=querystring, impersonate="chrome")
    request_json = request.json()
    converted_data = request_json.get("spark", {}).get("result", [{}])[0].get("response", [{}])[0].get("meta", {})

    return converted_data


def active_gainers_loosers():
    url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"

    results = {}
    for screen in ["MOST_ACTIVES", "DAY_GAINERS", "DAY_LOSERS"]:
        querystring = {
            "count": "25",
            "formatted": "true",
            "scrIds": screen,
            "start": "0",
            "useRecordsResponse": "false",
            "fields": "ticker,symbol,shortName,regularMarketPrice,regularMarketChange,regularMarketChangePercent,regularMarketVolume,averageDailyVolume3Month,marketCap,trailingPE,fiftyTwoWeekChangePercent,fiftyTwoWeekRange,regularMarketOpen",
        }

        request = requests.request("GET", url, params=querystring, impersonate="chrome")
        data = request.json().get("finance", {}).get("result", [{}])[0].get("quotes", [])
        data_clean = [
            {k: (v.get("raw", v) if isinstance(v, dict) else v) for k, v in kwargs.items()} for kwargs in data
        ]
        data_table = pd.DataFrame(data_clean)
        top5 = data_table[data_table["marketCap"] > 5_000_000].iloc[:5]

        nice_screen = screen.replace("_", " ").title()
        for idx, row in top5.iterrows():
            if nice_screen not in results:
                results[nice_screen] = []

            results[nice_screen].append(
                {
                    "source": {
                        "name": row["shortName"],
                        "pinned": False,
                        "notification_threshold": 20,
                        "data_source": "yf",
                    },
                    "worst_perf_idx": idx,
                    "market_closed": False,
                    "change_today": row["regularMarketChangePercent"],
                    "change_today_abs": abs(row["regularMarketChangePercent"]),
                }
            )

    return results


def scrape_market_data():
    """Get all data sources, scrape the data from the web, and update cached market data."""

    print("Refreshing Market Data...")

    all_scources = DataSource.objects.exclude(data_source="yfin")
    latest_data = []
    try:
        latest_data = __get_bonds(all_scources)
    except Exception as e:
        print(traceback.format_exc())
        print(f"Error fetching bond market data {e}")

    all_scources = DataSource.objects.filter(data_source="yfin")
    for data_src in all_scources:
        try:
            summary_box = __get_quote_table(data_src.ticker)
            obj = DataEntry(
                source=data_src,
                price=summary_box["regularMarketPrice"],
                change_today=(summary_box["regularMarketPrice"] / summary_box["chartPreviousClose"] - 1) * 100,
                market_closed=False,
            )
            obj.save()
            latest_data.append(obj.pk)
        except Exception as e:
            print(traceback.format_exc())
            print(f"Error fetching yahoo market data for {data_src} {e}")

    latest_data = (
        DataEntry.objects.filter(pk__in=latest_data)
        .annotate(change_today_int=Cast(F("change_today") * 1000, SmallIntegerField()))
        .annotate(change_today_abs=ABS(F("change_today")))
        .annotate(
            worst_perf_idx=Window(
                expression=RowNumber(),
                partition_by="source__group",
                order_by="change_today_int",
            )
        )
        .order_by("source__group__position", "-source__pinned", "change_today")
    )

    # Notify user of large daily changes
    notifications_sent = cache.get("market_notifications_sent", {})
    notifications = latest_data.filter(market_closed=False).filter(
        (
            Q(change_today__gte=F("source__notification_threshold"))
            | Q(change_today__lte=-F("source__notification_threshold"))
        )
    )
    for notification in notifications:
        if notification.source.pk not in notifications_sent or (
            datetime.date.today() != notifications_sent[notification.source.pk]
        ):
            try:
                payload = {
                    "head": "Market Alert",
                    "body": (
                        f"{notification.source.group.name}: {notification.source.name} "
                        + f" {'{0:+.2f}'.format(notification.change_today)}"
                        + f"{'%' if notification.source.data_source == 'yfin' else 'bps'} "
                        + ("up" if notification.change_today > 0 else "down")
                    ),
                    "url": (
                        "https://finance.yahoo.com/quote/"
                        + notification.source.ticker
                        + "?p="
                        + notification.source.ticker
                        if notification.source.data_source == "yfin"
                        else (
                            f"https://tradingeconomics.com/{notification.source.ticker.lower().replace(' ', '-')}"
                            "/government-bond-yield"
                        )
                    ),
                }
                send_group_notification(
                    group_name="all",
                    payload=payload,
                    ttl=60 * 90,  # keep 90 minutes on server
                )
                print(
                    f"Web Push Notification sent for ({notification.source.pk}) Market"
                    f" Alert - {notification.source.name}"
                )
                notifications_sent[notification.source.pk] = datetime.date.today()
                cache.set("market_notifications_sent", notifications_sent, 3600 * 1000)
            except Exception as e:
                print(
                    f"Error sending Web Push Notification for ({notification.source.pk}) Market"
                    f" Alert - {notification.source.name}: {e}"
                )

    data_active_gainers_loosers = active_gainers_loosers()

    final_data = {}
    for i in latest_data:
        if i.source.group.name not in final_data:
            final_data[i.source.group.name] = []
        final_data[i.source.group.name].append(i)

    final_data = {**final_data, **data_active_gainers_loosers}

    # delete market data older than 45 days
    DataEntry.objects.filter(
        ref_date_time__lte=settings.TIME_ZONE_OBJ.localize(datetime.datetime.now() - datetime.timedelta(days=45))
    ).delete()

    print("Market Data was successfully refreshed.")

    cache.set("latestMarketData", final_data, 60 * 60 * 12)
