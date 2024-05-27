#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Django's command-line utility for administrative tasks."""
import datetime
import os
import subprocess
import sys
import warnings

from dotenv import load_dotenv

from news_platform.pwa_splash_screen_generator import create as create_splash_screens


def __ensure_db_migration_folders_exist():
    """Ensure that init files exist in the data dir for the migration files."""
    init_files = [
        "static/splashscreens/__init__.py",
        "data/__init__.py",
        "data/db_migrations/__init__.py",
        "data/db_migrations/articles/__init__.py",
        "data/db_migrations/feeds/__init__.py",
        "data/db_migrations/preferences/__init__.py",
        "data/db_migrations/markets/__init__.py",
        "data/db_migrations/django_celery_beat/__init__.py",
        "data/db_migrations/webpush/__init__.py",
        "data/db_migrations/sessions/__init__.py",
        "data/db_migrations/auth/__init__.py",
        "data/db_migrations/authtoken/__init__.py",
        "data/db_migrations/admin/__init__.py",
        "data/db_migrations/contenttypes/__init__.py",
    ]

    if all([os.path.isfile(i) for i in init_files]) is False:
        for i in init_files:
            dir_only = "/".join(i.split("/")[:-1])
            os.makedirs(dir_only, exist_ok=True)
            open(i, "a").close()


def __ensure_webpush_vapid_keys():
    """Ensure that vapid keys for webpush were gereated"""
    if (
        os.environ.get("WEBPUSH_PUBLIC_KEY", None) is None
        or os.environ.get("WEBPUSH_PRIVATE_KEY", None) is None
    ):
        print("Generating vapid keys for webpush...")
        process = subprocess.Popen("vapid --gen", shell=True, stdout=subprocess.PIPE)
        process.wait()
        with open("private_key.pem") as f:
            private_key = f.read().replace("\n", "").split("-----")[2]
        with open("public_key.pem") as f:
            public_key = f.read().replace("\n", "").split("-----")[2]
        with open("data/.env", "a+") as f:
            f.write(f"\nWEBPUSH_PUBLIC_KEY='{public_key}'")
            f.write(f"\nWEBPUSH_PRIVATE_KEY='{private_key}'")
        os.environ["WEBPUSH_PUBLIC_KEY"] = public_key
        os.environ["WEBPUSH_PRIVATE_KEY"] = private_key
        print("Vapid keys for webpush were created.")
    else:
        print("Vapid keys for webpush already exist.")


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "news_platform.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    INITIAL_ARGV = sys.argv.copy()

    # Load .env files
    load_dotenv("data/.env")

    __ensure_db_migration_folders_exist()
    __ensure_webpush_vapid_keys()
    create_splash_screens()

    if os.environ.get("RUN_MAIN", "false") == "false":
        print(
            "Django Server was started at: "
            f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}"
        )
        warnings.filterwarnings(
            "ignore",
            message=(
                "Using slow pure-python SequenceMatcher. "
                "Install python-Levenshtein to remove this warning"
            ),
        )

        # Make data model migrations
        sys.argv = [INITIAL_ARGV[0], "makemigrations"]
        main()

        # Apply data model migrations
        sys.argv = [INITIAL_ARGV[0], "migrate"]
        main()

        from django.contrib.auth.models import User

        from feeds.models import Feed

        # Load initial feeds
        if len(Feed.objects.all()) == 0:
            print("Add default data")
            sys.argv = [INITIAL_ARGV[0], "add_default_data"]
            main()

        # Create Admin
        if len(User.objects.filter(username="admin")) == 0:
            print('Create super user "admin"')
            User.objects.create_superuser("admin", "", "password")
        if len(User.objects.filter(username="user")) == 0:
            print('Create normal user "user"')
            sys.argv = [INITIAL_ARGV[0], "create_normal_user"]
            main()

    else:
        print(
            "Django auto-reloader process executes second instance of django. "
            "Please turn-off for production usage by executing: "
            '"python manage.py runserver --noreload"'
        )

    # Run server
    sys.argv = INITIAL_ARGV
    main()
