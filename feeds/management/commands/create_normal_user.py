# -*- coding: utf-8 -*-
from django.contrib.auth.models import User
from django.core.management import BaseCommand


class Command(BaseCommand):
    # Show this when the user types help
    help = "Adds StartUp default feeds"

    def handle(self, *args, **options):
        user = User.objects.create_user("user", password="password")
        user.is_superuser = False
        user.is_staff = True
        user.save()
