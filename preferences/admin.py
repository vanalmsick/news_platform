# -*- coding: utf-8 -*-
"""Admin view for PPreferences Section/App"""

from django.contrib import admin
from unfold.admin import ModelAdmin

# Register your models here.
from .models import Page


@admin.register(Page)
class PageAdmin(ModelAdmin):
    """Main Admin Article View"""

    list_display = [
        "__str__",
        "position_index",
        "url_parameters",
    ]
    readonly_fields = (
        "url_hash",
        "url_parameters_json",
    )
    ordering = ("position_index",)
