# -*- coding: utf-8 -*-
"""Data scraping for Market Data i.e. Stock/FX/Comm prices"""

import datetime
import traceback
from io import StringIO

import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests  # type: ignore
from django.conf import settings
from django.core.cache import cache
from django.db.models import F, SmallIntegerField
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
    base_data = cache.get("market_base_data", {})

    url_crumb = "https://query1.finance.yahoo.com/v1/test/getcrumb"
    request_crumb = requests.request("GET", url_crumb, impersonate="chrome")

    url = "https://query1.finance.yahoo.com/v1/finance/screener"

    querystring = {
        "formatted": "true",
        "useRecordsResponse": "true",
        "lang": "en-US",
        "region": "US",
        "crumb": request_crumb.text,
    }

    results = {}
    for screen, sortField, sortType in [
        ("Most Active Stocks (G7)", "dayvolume", "desc"),
        ("Stock Gainers (G7)", "percentchange", "desc"),
        ("Stock Losers (G7)", "percentchange", "asc"),
    ]:
        querystring = {
            "size": 50,
            "offset": 0,
            "sortType": sortType,
            "sortField": sortField,
            "includeFields": [
                "ticker",
                "companyshortname",
                "intradayprice",
                "intradaypricechange",
                "percentchange",
                "dayvolume",
                "avgdailyvol3m",
                "intradaymarketcap",
                "peratio.lasttwelvemonths",
                "day_open_price",
                "fiftytwowklow",
                "fiftytwowkhigh",
            ],
            "topOperator": "AND",
            "query": {
                "operator": "and",
                "operands": [
                    {
                        "operator": "or",
                        "operands": [
                            {"operator": "eq", "operands": ["region", "us"]},
                            {"operator": "eq", "operands": ["region", "de"]},
                            {"operator": "eq", "operands": ["region", "fr"]},
                            {"operator": "eq", "operands": ["region", "gb"]},
                            {"operator": "eq", "operands": ["region", "jp"]},
                            {"operator": "eq", "operands": ["region", "it"]},
                            {"operator": "eq", "operands": ["region", "ca"]},
                        ],
                    },
                    {
                        "operator": "or",
                        "operands": [
                            {"operator": "gt", "operands": ["lastclosemarketcap.lasttwelvemonths", 10_000_000_000]}
                        ],
                    },
                    {"operator": "or", "operands": [{"operator": "gt", "operands": ["avgdailyvol3m", 500_000]}]},
                    {"operator": "or", "operands": [{"operator": "gt", "operands": ["intradayprice", 10]}]},
                ],
            },
            "quoteType": "EQUITY",
        }

        request = requests.request(
            "POST",
            url,
            json=querystring,
            cookies=request_crumb.cookies,
            headers={"x-crumb": request_crumb.text},
            impersonate="chrome",
        )
        data = request.json().get("finance", {}).get("result", [{}])[0].get("quotes", [])
        data_clean = [
            {k: (v.get("raw", v) if isinstance(v, dict) else v) for k, v in kwargs.items()} for kwargs in data
        ]
        top5 = pd.DataFrame(data_clean)

        top5["name"] = top5["longName"].fillna(top5["shortName"])
        top5["priceAge"] = (datetime.datetime.now() - pd.to_datetime(top5["regularMarketTime"], unit="s")).dt.seconds
        top5 = top5[top5["priceAge"] < 60 * 60 * 6]  # exclude quotes where the market closed more than 6 hours ago
        top5.drop_duplicates(subset=["longName"], inplace=True, keep="first")
        top5 = top5.iloc[: min(len(top5), 5)]

        for idx, row in top5.iterrows():
            if screen not in results:
                results[screen] = []

            if row["symbol"] not in base_data:
                profile_url = (
                    f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{row['symbol']}?modules=assetProfile"
                )
                profile_response = requests.get(
                    profile_url,
                    cookies=request_crumb.cookies,
                    headers={"x-crumb": request_crumb.text},
                    impersonate="chrome",
                )
                if profile_response.ok:
                    profile_data = profile_response.json()
                    base_data[row["symbol"]] = (
                        profile_data.get("quoteSummary", {}).get("result", [{}])[0].get("assetProfile", {})
                    )
                else:
                    base_data[row["symbol"]] = None
                cache.set("market_base_data", base_data, 604800)  # 7 days
            if base_data[row["symbol"]] is None:
                sector_country = None
            else:
                country = base_data[row["symbol"]]["country"]
                sector = base_data[row["symbol"]]["sector"]
                if sector == "" and sector == "":
                    sector_country = None
                elif sector == "":
                    sector_country = country
                elif country == "":
                    sector_country = sector
                else:
                    sector_country = f"{sector}, {country}"

            name = str(row["name"]).title() if str(row["name"]).isupper() else str(row["name"])
            name = (
                name.replace("Public Limited Company", "Plc.")
                .replace("Akitengesellschaft", "AG")
                .replace("Limited", "Ltd.")
                .replace("Corporation", "Corp.")
                .replace("Incorporated", "Inc.")
            )

            results[screen].append(
                {
                    "source": {
                        "name": name,
                        "tagline": sector_country,
                        "pinned": False,
                        "notification_threshold": (5 if "active" in str(screen).lower() else 10),
                        "data_source": "yf",
                        "src_url": f'https://finance.yahoo.com/quote/{row["symbol"]}?p={row["symbol"]}',
                    },
                    "worst_perf_idx": idx,
                    "market_closed": "PRE" in str(row["marketState"]) or "POST" in str(row["marketState"]),
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
                market_closed=(
                    datetime.datetime.now() - pd.to_datetime(summary_box["regularMarketTime"], unit="s")
                ).seconds
                > 60 * 60,
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
    for market_data_i in latest_data:
        source = market_data_i.source
        id = source.pk
        past_notifications_i = notifications_sent.get(id, 0)
        notification_threshold = float(source.notification_threshold)
        if market_data_i.market_closed:
            # markets closed - delete this day's notification
            notifications_sent.pop(id, None)
            cache.set("market_notifications_sent", notifications_sent, 3600 * 1000)
        elif (
            market_data_i.change_today > notification_threshold + (notification_threshold * past_notifications_i * 0.5)
        ) or (
            market_data_i.change_today
            < -(notification_threshold + (notification_threshold * past_notifications_i * 0.5))
        ):
            # today's market move exceeds notification threshold (in 50% increments re-notify above threshold)
            try:
                payload = {
                    "head": "Market Alert",
                    "body": (
                        f"{source.group.name}: {source.name} "
                        + f" {'{0:+.2f}'.format(market_data_i.change_today)}"
                        + f"{'%' if source.data_source == 'yfin' else 'bps'} "
                        + ("up" if market_data_i.change_today > 0 else "down")
                    ),
                    "url": source.src_url,
                }
                send_group_notification(
                    group_name="all",
                    payload=payload,
                    ttl=60 * 90,  # keep 90 minutes on server
                )
                print(f"Web Push Notification sent for ({source.pk}) Market Alert - {source.name}")
                notifications_sent[id] = past_notifications_i + 1
                cache.set("market_notifications_sent", notifications_sent, 3600 * 1000)

            except Exception as e:
                print(f"Error sending Web Push Notification for ({source.pk}) Market Alert - {source.name}: {e}")

    data_active_gainers_loosers = active_gainers_loosers()

    final_data = {}
    for i in latest_data:
        if i.source.group.name not in final_data:
            final_data[i.source.group.name] = []
            if i.source.group.name.lower() == "indices":
                final_data = {**final_data, **data_active_gainers_loosers}
        final_data[i.source.group.name].append(i)

    # delete market data older than 45 days
    DataEntry.objects.filter(
        ref_date_time__lte=settings.TIME_ZONE_OBJ.localize(datetime.datetime.now() - datetime.timedelta(days=45))
    ).delete()

    print("Market Data was successfully refreshed.")

    cache.set("latestMarketData", final_data, 60 * 60 * 12)
