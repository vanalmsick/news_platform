# -*- coding: utf-8 -*-
"""Django Admin Space for Market Data App/Models"""
from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import DataGroup, DataSource


# Register your models here.
class DataSourceImportExport(resources.ModelResource):
    """Data class for import/export functionality of DataSource"""

    class Meta:
        """Meta linkage for django to source model"""

        model = DataSource


@admin.register(DataSource)
class DataSourceAdmin(ImportExportModelAdmin):
    """Main Admin Feed View"""

    list_display = [
        "group",
        "name",
        "pinned",
        "ticker",
    ]
    ordering = ("group__position", "-pinned", "name")
    resource_classes = [DataSource]


@admin.register(DataGroup)
class DataGroupAdmin(admin.ModelAdmin):
    """Main Admin Article View"""

    list_display = [
        "name",
        "position",
    ]
    ordering = (
        "position",
        "name",
    )
