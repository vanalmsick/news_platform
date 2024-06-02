# -*- coding: utf-8 -*-
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

NEWS_IMPORTANCE = [
    (4, "Lead Articles News"),
    (3, "Breaking & Top News"),
    (2, "Frontpage News"),
    (1, "Latest News"),
    (0, "Normal"),
]

YES_NO = [("Y", "Yes"), ("N", "No")]


# Create your models here.
class Publisher(models.Model):
    """Model for news publishers."""

    name = models.CharField(max_length=30)
    link = models.URLField()
    RENOWNED_LEVES = [
        (3, "Top Publisher"),
        (2, "Higly Renowned Publisher"),
        (1, "Renowned Publisher"),
        (0, "Regular Publisher"),
        (-1, "Lesser-known Publisher"),
        (-2, "Unknown Publisher"),
        (-3, "Inaccurate Publisher"),
    ]
    paywall = models.CharField(max_length=1, choices=YES_NO, default="N")
    renowned = models.SmallIntegerField(choices=RENOWNED_LEVES, default=0)
    UNIQUE_ARTICLE_ID = [("guid", "GUID"), ("url", "URL"), ("title", "Title")]
    unique_article_id = models.CharField(choices=UNIQUE_ARTICLE_ID, default="guid", max_length=5)
    language = models.CharField(max_length=5, default="en", blank=True)

    def __str__(self):
        """print-out representation of individual model entry"""
        return f"{self.name}"


@receiver(pre_save, sender=Publisher)
def truncate_long_fields(sender, instance, **kwargs):
    """Make sure fields with a max_length attr are truncated if too long"""
    # Define a list of fields you want to check and truncate
    fields_to_check = [
        "name",
        "link",
    ]  # all fields with max_length limit and not filled by code

    for field_name in fields_to_check:
        field = getattr(instance, field_name)
        max_length = instance._meta.get_field(field_name).max_length
        if field is not None and len(field) > max_length:
            setattr(instance, field_name, field[:max_length])


class Feed(models.Model):
    """Model for individual rss/youtube news feeds."""

    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE)

    name = models.CharField(max_length=40)
    url = models.URLField(max_length=600)
    active = models.BooleanField(default=True)
    last_fetched = models.DateTimeField(null=True, blank=True)
    importance = models.SmallIntegerField(choices=NEWS_IMPORTANCE)
    FEED_TYPES = [
        ("rss", "RSS Feed"),
        ("y-channel", "YouTube Channel"),
        ("y-playlist", "YouTube Playlist"),
    ]
    feed_type = models.CharField(max_length=10, choices=FEED_TYPES, default="rss")
    source_categories = models.CharField(max_length=250, null=True, blank=True)
    FEED_ORDER = [("r", "Relavance"), ("d", "Date")]
    feed_ordering = models.CharField(max_length=1, choices=FEED_ORDER)
    full_text_fetch = models.CharField(max_length=1, choices=YES_NO, default="Y")

    def __str__(self):
        """print-out representation of individual model entry"""
        return f"{self.publisher.name} - {self.name}"
