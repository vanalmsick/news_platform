# -*- coding: utf-8 -*-
"""Bounded HTTP helpers for the scrapers.

`requests.get(url)` buffers the *entire* response body into memory before it
returns. Every article in every feed is fetched this way, so a single
mis-advertised URL - a PDF, a video file, a CDN error page that streams
megabytes of HTML - is enough to spike a celery child's RSS well past the
container limit. These helpers stream the response instead and refuse anything
that is either the wrong content type or larger than a hard byte cap.
"""

import requests  # type: ignore

# (connect timeout, read timeout). The scrapers previously used a single
# `timeout=5` which applies to each socket operation, not to the whole request.
DEFAULT_TIMEOUT = (3.05, 10)

# 2 MB of HTML is far more than any article page needs; the largest legitimate
# pages in a news feed sit well under 1 MB.
DEFAULT_MAX_BYTES = 2_000_000

HTML_CONTENT_TYPES = (
    "text/html",
    "application/xhtml+xml",
    "text/plain",
    "application/xml",
    "text/xml",
)

JSON_CONTENT_TYPES = (
    "application/json",
    "text/json",
    "text/plain",
)


class ResponseTooLarge(ValueError):
    """Raised when a response exceeds the configured byte cap."""


class UnexpectedContentType(ValueError):
    """Raised when a response is not of an accepted content type."""


def fetch_limited(
    url,
    timeout=DEFAULT_TIMEOUT,
    max_bytes=DEFAULT_MAX_BYTES,
    allowed_types=HTML_CONTENT_TYPES,
    headers=None,
):
    """GET `url`, never buffering more than `max_bytes` of the body.

    The response is streamed so the body is only pulled off the socket once the
    declared content type and length have been checked, and even then only up to
    the cap. The consumed bytes are written back onto the response object so
    callers can keep using `.text` / `.json()` as before.

    Raises `UnexpectedContentType`, `ResponseTooLarge`, or any `requests`
    exception. Callers are expected to treat a failure as "skip this article".
    """
    response = requests.get(url, timeout=timeout, stream=True, headers=headers)
    try:
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if allowed_types is not None and content_type and content_type not in allowed_types:
            raise UnexpectedContentType(f"unexpected content-type '{content_type}' for {url}")

        declared_length = response.headers.get("content-length")
        if declared_length is not None and declared_length.isdigit() and int(declared_length) > max_bytes:
            raise ResponseTooLarge(f"{url} declares {declared_length} bytes (cap {max_bytes})")

        # decode_content=True means the cap applies to the *decompressed* size,
        # so a gzip bomb cannot get past it. Reading one byte over the cap is how
        # an oversized body is detected without buffering all of it.
        body = response.raw.read(max_bytes + 1, decode_content=True) if response.raw is not None else b""
        if len(body) > max_bytes:
            raise ResponseTooLarge(f"{url} returned more than {max_bytes} bytes")

        # `.text` / `.json()` read from the private `_content` buffer, which is
        # normally filled by requests itself - the body was consumed above, so it
        # has to be handed back explicitly.
        response._content = body
        response._content_consumed = True
    finally:
        # Always release the connection: on the error paths the body is never
        # read, and leaving it dangling would keep the socket (and its buffers)
        # alive until the next GC pass.
        response.close()

    return response


def fetch_json_limited(url, timeout=DEFAULT_TIMEOUT, max_bytes=DEFAULT_MAX_BYTES, headers=None):
    """Same as `fetch_limited` but for the full-text extraction service."""
    return fetch_limited(
        url,
        timeout=timeout,
        max_bytes=max_bytes,
        allowed_types=JSON_CONTENT_TYPES,
        headers=headers,
    )


def head_status(url, timeout=DEFAULT_TIMEOUT):
    """Return the status code for `url` without downloading its body.

    Uses a streamed GET rather than HEAD because a fair number of news CDNs
    answer HEAD with 405 while serving GET perfectly well. With `stream=True`
    requests reads the status line and headers and stops, so no body is
    transferred as long as the response is closed - which it is, immediately.
    """
    response = requests.get(url, timeout=timeout, stream=True)
    try:
        return response.status_code, response.ok
    finally:
        response.close()
