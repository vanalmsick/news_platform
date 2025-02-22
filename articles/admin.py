# -*- coding: utf-8 -*-
"""Definition of Article View in Django Admin Space"""

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Article, FeedPosition, ArticleGroup


# Register your models here.
class FeedPositionInline(TabularInline):
    """Table of feeds to be shown in single-Publisher view"""

    model = FeedPosition
    fk_name = "article"
    extra = 0


@admin.register(Article)
class ArticleAdmin(ModelAdmin):
    """Main Admin Article View"""

    list_display = [
        "title",
        "publisher",
        "content_type",
        "has_full_text",
        "added_date",
        "min_article_relevance",
        "categories",
        "language",
    ]
    readonly_fields = (
        "publisher_article_position",
        "max_importance",
        "min_feed_position",
        "min_article_relevance",
        "added_date",
        "last_updated_date",
        "mailto_link",
    )
    ordering = ("-added_date",)
    inlines = [
        FeedPositionInline,
    ]


class ArticleInline(TabularInline):
    """Table of feeds to be shown in single-Publisher view"""

    model = Article
    fk_name = "article_group"
    extra = 0


@admin.register(ArticleGroup)
class ArticleGroupAdmin(ModelAdmin):
    """Main Admin ArticleGroup View"""

    inlines = [
        ArticleInline,
    ]
