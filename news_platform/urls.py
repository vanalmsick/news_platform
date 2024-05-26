# -*- coding: utf-8 -*-
"""news_platform URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path

from news_platform.pages.pageAPI import (
    ArchiveView,
    ReadLaterView,
    RestArticleAPIView,
    RestLastRefeshAPIView,
    RestPublisherAPIView,
)
from news_platform.pages.pageArticle import articleView
from news_platform.pages.pageHome import (
    RedirectView,
    RestHomeView,
    TriggerManualRefreshView,
    homeView,
)
from news_platform.pages.pageLogin import LoginView


def trigger_error(request):
    """To intentionally trigger error when user opens url /sentry-debug/ to test if Sentry error monitoring works"""
    print(1 / 0)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", LoginView, name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("api/article/<int:pk>/", RestArticleAPIView.as_view(), name="article_api"),
    path(
        "api/publisher/<int:pk>/", RestPublisherAPIView.as_view(), name="publisher_api"
    ),
    path("api/page/", RestHomeView.as_view(), name="page_api"),
    path("api/refresh/", RestLastRefeshAPIView.as_view(), name="refesh_api"),
    path("read-later/<str:action>/<int:pk>/", ReadLaterView, name="read-later"),
    path("archive/<str:action>/<int:pk>/", ArchiveView, name="read-later"),
    path("refresh/", TriggerManualRefreshView, name="refresh_news"),
    path("view/<int:article>/", articleView, name="view_article"),
    path("redirect/<int:article>/", RedirectView, name="redirect_article"),
    path("", homeView, name="home"),
    path("auth/", include("djoser.urls")),
    path("auth/", include("djoser.urls.jwt")),
    path("webpush/", include("webpush.urls")),
    path("", include("pwa.urls")),
    path("sentry-debug/", trigger_error),
    # path('restapi/v1/accounts/', transactions.api_views.AccountList.as_view()),
    # path('favicon.ico', RedirectView.as_view(url=staticfiles_storage.url('favicon.ico')))
]
