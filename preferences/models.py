# -*- coding: utf-8 -*-
"""models for App called Preferences"""

from urllib.parse import parse_qs

from django.db import models


def url_parm_encode(**kwargs):
    """function too translate url paramaters from GET request in dictionary to hash string"""
    kwargs = {k: ",".join(v if isinstance(v, list) else [v]).split(",") for k, v in kwargs.items()}
    kwargs = {k: [v] if isinstance(v, str) else v for k, v in kwargs.items()}
    kwargs_hash = "articles_" + str({k.lower(): [i.lower() for i in sorted(v)] for k, v in kwargs.items()})
    kwargs_hash = "".join([i if i.isalnum() else "_" for i in kwargs_hash])
    return kwargs_hash, kwargs


def get_page_lst():
    queryset = Page.objects.all().only("url_hash", "url_parameters_json")
    return {i.url_hash: i.url_parameters_json for i in queryset}


# Create your models here.
class Page(models.Model):
    """model for page sections"""

    name = models.CharField(max_length=40, default="USA")
    url_parameters = models.CharField(
        max_length=500,
        default="publisher__name=financial+times,bloomberg&categories=usa&content_type=article",
    )
    html_icon = models.TextField(default="#", blank=True)
    position_index = models.SmallIntegerField()

    def __str__(self):
        """display/string repreesentation of individual element"""
        if "<" in self.html_icon:
            return f"[ICON]{self.name}"
        else:
            return f"{self.html_icon}{self.name}"

    url_hash = models.CharField(max_length=300)
    url_parameters_json = models.JSONField()

    def __calc_url_hash(self):
        url_parameters = parse_qs(self.url_parameters)
        url_hash, _ = url_parm_encode(**url_parameters)
        return url_hash, url_parameters

    def save(self, *args, **kwargs):
        self.url_hash, self.url_parameters_json = self.__calc_url_hash()
        super(Page, self).save(*args, **kwargs)
