# -*- coding: utf-8 -*-
"""Decode encoded Google News entry URLs."""

import requests
import functools
from googlenewsdecoder import new_decoderv1

# Old Solution from https://gist.github.com/huksley/bc3cb046157a99cd9d1517b32f91a99e?permalink_comment_id=5132769
# New Solution package googlenewsdecoder


@functools.lru_cache(2048)
def decode_google_news_url(source_url):
    """Get redirect url from goole news url in rss feed"""
    url = requests.utils.urlparse(source_url)
    path = url.path.split("/")
    if url.hostname == "news.google.com" and len(path) > 1 and path[-2] == "articles":
        decoded_url = new_decoderv1(source_url)
        if decoded_url.get("status"):
            return decoded_url["decoded_url"]
        else:
            print("GNews Decode Error:", decoded_url["message"])
    return source_url


# Example usage
if __name__ == "__main__":
    source_url = "https://news.google.com/rss/articles/CBMisgFBVV95cUxNWHRheHZncTJIR0FjT2tGTXZ5VHVrc2U4RkQyaldCYUJEaU1URzFLTWNTUEsyRjZ4djFMNng2WkNHbmFUUURKTGJLQ0R3S2xlR1hzVHZMTGs1RnZ2b3R5RjhNbmU3NjVqZXl6NGVZMmZrbW9XM3ZieVVlMlQ5dWlVdzBsSmVQTG5HSk44Z1A0dUNBamZKaTVzMTZUMkJWbjlqbEFfSlhZN3BKLWZVZVdjSlV3?oc=5"
    decoded_url = decode_google_news_url(source_url)
    print(decoded_url)
