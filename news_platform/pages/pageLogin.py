# -*- coding: utf-8 -*-

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render

from articles.models import Article


class LoginForm(forms.Form):
    """Form used on login page to enter password of default user."""

    password = forms.CharField(
        max_length=63,
        widget=forms.TextInput(attrs={"class": "form-control sentry-ignore"}),
    )


def LoginView(request):
    """Login view - page for user to login. Also contains artcile meta data if available"""
    form = LoginForm()
    message = ""
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                username="user",
                password=form.cleaned_data["password"],
            )
            if user is not None:
                message = "Login successful!"
                login(request, user)
                if "article" in request.GET:
                    return redirect(f"/view/{request.GET['article']}/?previous=login")
                else:
                    return redirect("/")
            else:
                message = "Login failed!"

    meta = f"""
        <title>{settings.CUSTOM_PLATFORM_NAME}</title>
        <meta property="og:type" content="website">
        <meta property="og:site_name" content="{settings.CUSTOM_PLATFORM_NAME}">
        """
    if "article" in request.GET:
        try:
            article_id = int(request.GET["article"])
            article = Article.objects.get(pk=article_id)
            meta = f"""
                <title>{article.title} - {article.publisher.name}</title>
                <meta name="description" property="og:description" content="{article.extract}">
                <meta name="image" property="og:image" content="{article.image_url}">
                <meta name="site_name" property="og:site_name" content="{article.publisher.name}">
                <meta name="author" property="og:author" content="{article.publisher.name}">
                <meta name="title" property="og:title" content="{article.title} - {article.publisher.name}">
                <meta name="type" property="og:type" content="article">
                <meta name="url" property="og:url" content="{article.link}">
                """
        except Exception as e:
            print(f"Not logged-in user with invalid article id: {e}")

    return render(
        request,
        "login.html",
        context={
            "form": form,
            "message": message,
            "meta": meta,
            "sentry_sdk": settings.SENTRY_SCRIPT_HEAD,
            "platform_name": settings.CUSTOM_PLATFORM_NAME,
        },
    )
