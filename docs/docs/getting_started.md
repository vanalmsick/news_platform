## Quick Start / TL;DR

**Default user:** user / password  
**Default admin:** admin / password

_(Make sure Docker is installed: [go to docker.com](https://www.docker.com/get-started/))_

**Minimal Docker Run Command (CMD):**

```
# The container runs as the non-root user "app_user" (UID/GID 1000) and Docker
# does not change the ownership of host directories, so prepare the data dir once:
mkdir -p /your/local/data/dir/news_platform
sudo chown -R 1000:1000 /your/local/data/dir/news_platform

docker run \
    -p 80:80 \
    -v /your/local/data/dir/news_platform:/news_platform/data \
    --name my_news_platform \
    vanalmsick/news_platform
```

!!! warning
    If the host directory is not writable by UID 1000 the container aborts on start
    with `PermissionError: [Errno 13] Permission denied: 'data/__init__.py'`.
    Using a named docker volume instead of a bind mount requires no such step.

**All out [docker_compose.yml](https://github.com/vanalmsick/news_platform/blob/main//docker_compose.yml.template)
setup:**  
_docker_compose.yml:_

```
version: "3.9"

services:

  # The News Platform
  news-platform:
    image: vanalmsick/news_platform
    container_name: news-platform
    restart: always
    ports:
      - 9380:80    # for gui/website
      - 9381:5555  # for Celery Flower Task Que
      - 9382:9001  # for Docker Supervisor Process Manager
    volumes:
      - /your/local/data/dir/news_platform:/news_platform/data
    environment:
      MAIN_HOST: 'https://news.yourwebsite.com'
      HOSTS: 'http://localhost,http://127.0.0.1,http://0.0.0.0,http://docker-container-name,http://news.yourwebsite.com,https://news.yourwebsite.com'
      CUSTOM_PLATFORM_NAME: 'Personal News Platform'
      SIDEBAR_TITLE: 'Latest News'
      TIME_ZONE: 'Europe/London'
      ALLOWED_LANGUAGES: 'en,de'
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
      - 9480:80   # incoming http
      - 9443:443  # incoming https
    depends_on:
      - news-platform
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

_start-up command (CMD):_

```
docker compose -f "/your/local/path/docker_compose.yml" up --pull "always" -d
```
