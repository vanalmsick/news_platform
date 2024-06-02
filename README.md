# Personal News Platform

[Go to **Documentation & How-To**](https://vanalmsick.github.io/news_platform/)  
[Go to **DockerHub Container: vanalmsick/news_platform**](https://hub.docker.com/repository/docker/vanalmsick/news_platform)

News Aggregator - Aggregates news articles from several RSS feeds, fetches full-text if possible, sorts them by
relevance (based on user settings), and display on distraction-free homepage.

### PC Home Page:

<img src="docs/docs/imgs/home_pc.png" alt="PC Home Page" style="width:90%;"/><br>

### Article Reading View:

<img src="docs/docs/imgs/article.png" alt="Article Reading View" style="width:65%;"/><br>

### Phone Home Page:

<img src="docs/docs/imgs/home_phone.jpeg" alt="Phone Home Page" style="height:700px;"/><br>

## Features:

+ News article fetching from RSS feeds and videos from YouTube channels
+ Full-text article fetching where possible (currently using fivefilters.org full-text fetcher - later own full-text
  fetcher)
+ Market data fetching
+ Light/dark modus website
+ Responsive optimized for very large screens, large screens, tablets, phones
+ Webapp
+ Push notifications
+ Custom news sources, article sorting, news-sections/pages, news-ticker/sidebar
+ Article previews when sharing a link e.g. via iMessage, WhatsApp, MS Teams
+ Reading list & archive
+ Still functionable in browsers with JavaScript disabled (aka paranoid-modus)
+ All self-hosted without cookies & tracker (except required ones from Bootstrap style)
+ Optimized to run on low-power servers like RaspberryPi 3 and later

## Quick Start / TL;DR

*(Make sure Docker is installed: [go to docker.com](https://www.docker.com/get-started/))*

**Minimal Docker Run Command (CMD):**

```
docker run \
    -p 80:80 \
    -v /your/local/data/dir/news_platform:/news_platform/data \
    --name my_news_platform \
    vanalmsick/news_platform
```

**All out [docker_compose.yml](/docker_compose.yml.example) setup:**  
*docker_compose.yml:*

```
version: "3.9"

services:

  # The News Plattform
  news-platform:
    image: vanalmsick/news_platform
    container_name: news-platform
    restart: always
    ports:
      - 9380:80    # for gui/website
      - 9381:5555  # for Celery Flower Task Que
      - 9382:9001  # for Docker Supervisor Process Manager
    depends_on:
      - news-platform-letsencrypt
    volumes:
      - /your/local/data/dir/news_platform:/news_platform/data
    environment:
      MAIN_HOST: 'https://news.yourwebsite.com'
      HOSTS: 'http://localhost,http://127.0.0.1,http://0.0.0.0,http://docker-container-name,http://news.yourwebsite.com,https://news.yourwebsite.com'
      CUSTOM_PLATFORM_NAME: 'Personal News Platform'
      SIDEBAR_TITLE: 'Latest News'
      TIME_ZONE: 'Europe/London'
      ALLOWED_LANGUAGES: 'en,de'
      FULL_TEXT_URL: 'http://fivefilters:80/full-text-rss/'
      FEED_CREATOR_URL: 'http://fivefilters:80/feed-creator/'
      WEBPUSH_PUBLIC_KEY: '<YOUR_WEBPUSH_PUBLIC_KEY>'
      WEBPUSH_PRIVATE_KEY: '<YOUR_WEBPUSH_PRIVATE_KEY>'
      WEBPUSH_ADMIN_EMAIL: 'admin@example.com'
      OPENAI_API_KEY: '<YOUR_OPEN_AI_API_KEY>'
    labels:
      - "com.centurylinklabs.watchtower.enable=true"  # if you use Watchtower for container updates


  # HTTPS container for secure https connection [not required - only if you want https]
  news-platform-letsencrypt:
    image: linuxserver/letsencrypt
    container_name: news-platform-letsencrypt
    restart: always
    ports:
      - 9480:80   # incomming http
      - 9443:443  # incomming https
    volumes:
      - news_platform_letsencrypt:/config
    environment:
      - EMAIL=<YOUR_EMAIL>
      - URL=yourwebsite.com
      - SUBDOMAINS=news
      - VALIDATION=http
      - TZ=Europe/London
      - DNSPLUGIN=cloudflare
      - ONLY_SUBDOMAINS=true
    labels:
      - "com.centurylinklabs.watchtower.enable=true"  # if you use Watchtower for container updates


volumes:
  news_platform:
  news_platform_letsencrypt:
```

*start-up command (CMD):*

```
docker compose -f "/your/local/path/docker_compose.yml" up --pull "always" -d
```

## Environmental Variables:

| ENV-KEY              | Default Value / Data Type                         | Description                                                                                                                                                                                                                                                                                                                       |
|----------------------|---------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| MAIN_HOST            | "http://localhost" *(any str)*                    | Public/local-network facing main URL. Used for links e.g. for webpush push notifications e.g. "https://news.yourwebsite.com" or "http://19.168.172.100"                                                                                                                                                                           |
| HOSTS                | "http://localhost,http://127.0.0.1/" *(any str)*  | List of urls to access news platfrom from. Required to avoid CSRF errors from CSRF attack protection e.g. "http://localhost,http://127.0.0.1,http://0.0.0.0,http://docker-container-name,http://news.yourwebsite.com,https://news.yourwebsite.com"                                                                                |
| CUSTOM_PLATFORM_NAME | "Personal News Platform" *(any str)*              | Name of news plattform e.g. "John doe's Personal News Platform"                                                                                                                                                                                                                                                                   |
| SIDEBAR_TITLE        | "Latest News" *(any str)*                         | Name of sidebar news section e.g. "News Ticker"                                                                                                                                                                                                                                                                                   |
| TIME_ZONE            | "Europe/London" *(iso str per ICANN tz name)*     | Server time-zone as per official ICANN tz name e.g "Europe/Berlin"                                                                                                                                                                                                                                                                |
| ALLOWED_LANGUAGES    | "*" *(str list of ISO 639-2)*                     | List of languages in which articles are allowed e.g. "en,de". This is to exclude languages the user does not understand that might be from topic feeds e.g. all articles tagged with "Tech" which might be in English, German, Chines, Spanish etc.                                                                               |
| LANGUAGE_CODE        | "en-UK" *(two letter language-country ISO code)*  | ISO code of News Plattform's language and loclaization for internet browser e.g. "en-US" or "de-DE"                                                                                                                                                                                                                               |
| FULL_TEXT_URL        | "http://ftr.fivefilters.org/" *(None or str url)* | A local instance of [fivefilters full-text-rss](https://www.fivefilters.org/pricing/) for full-text fetching. Only required for full-text fetching - currently working on own full-text fetcher.                                                                                                                                  |
| FEED_CREATOR_URL     | None *(None or str url)*                          | Local instance of [fivefilters feed-creator](https://www.fivefilters.org/pricing/) if webpages don't have a rss feed to create an rss feed - working on own feed-creator.                                                                                                                                                         |
| WEBPUSH_PUBLIC_KEY   | "<hard-coded-key>" *(str of public vapid-key)*    | Get your own public & private keys for webpush push-notifications e.g. from [web-push-codelab.glitch.me](https://web-push-codelab.glitch.me) or follow these instructions [Google Dev Documentation](https://developers.google.com/web/fundamentals/push-notifications/subscribing-a-user#how_to_create_application_server_keys). |
| WEBPUSH_PRIVATE_KEY  | "<hard-coded-key>" *(str of private vapid-key)*   | Get your own public & private keys for webpush push-notifications e.g. from [web-push-codelab.glitch.me](https://web-push-codelab.glitch.me) or follow these instructions [Google Dev Documentation](https://developers.google.com/web/fundamentals/push-notifications/subscribing-a-user#how_to_create_application_server_keys). |
| WEBPUSH_ADMIN_EMAIL  | "news-platform@example.com" *(str email address)* | Email address to get notified in case something is wrong with the webpush push notification sending.                                                                                                                                                                                                                              |
| OPENAI_API_KEY       | None *(str of openai api key or None)*            | Open AI API key for artcile summaries.                                                                                                                                                                                                                                                                                            |
| SECRET_KEY           | "<hard-coded-key>" *(str of django secret key)*   | Django's production secret key.                                                                                                                                                                                                                                                                                                   |
| DEBUG                | True *(bool - currently only True working)*       | To run the news platform in production / dev modus. Currently the production modus does not work.                                                                                                                                                                                                                                 |
| TESTING              | False *(bool)*                                    | To run the news platfrom in real-life testing modus - i.e. fetiching only 10% of news sources to avoid waiting.                                                                                                                                                                                                                   |

These environmental variables can be

+ included in the docker_compose.yml file in section "environment:" as arguments *(as above in the docker_compose.yml
  example)*,
+ saved as an .env file [*(example)*](/.env.example) and passed to the docker_compose.yml file as argument "env_file:
  /your/local/dir/.env", or
+ saved as an .env file [*(example)*](/.env.example) in the news plattform container's data directory e.g. "
  /your/local/data/dir/news_platform/.env"

## More information available in the [Documentation](https://vanalmsick.github.io/news_platform/)

## How to [contribute & help add features](https://vanalmsick.github.io/news_platform/)
