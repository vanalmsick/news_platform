# -*- coding: utf-8 -*-
"""Celery task config"""

import ctypes
import gc
import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_postrun, worker_init

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "news_platform.settings")

app = Celery("news_platform")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


# --------------------------------------------------------------------------
# Memory-related worker configuration
#
# These are applied *after* config_from_object so they win over anything in
# settings.py. Everything here is about bounding how much a forked celery child
# is allowed to accumulate before it gets recycled.
# --------------------------------------------------------------------------

# Task results live in redis and none of them are read back (the views only use
# task_id, and the pipeline below chains with immutable signatures). Without an
# expiry these keys accumulate for a full day at the celery default.
app.conf.result_expires = int(os.getenv("CELERY_RESULT_EXPIRES", 60 * 60))

# Adaptive backstop: recycle a child once its RSS crosses this many KiB. Unlike
# --max-tasks-per-child this reacts to what the task actually did, so a child
# that happened to scrape one enormous feed is retired even if it only ran once.
app.conf.worker_max_memory_per_child = int(os.getenv("CELERY_MAX_MEMORY_PER_CHILD_KB", 400_000))

# Never let a child buffer task payloads it is not working on yet.
app.conf.worker_prefetch_multiplier = 1

# `group_articles` is the only task that imports torch/sentence-transformers.
# Giving it its own queue means it can later be moved to a dedicated worker
# (`-Q ml --concurrency 1 --max-tasks-per-child 1`) without a code change. By
# default a single worker consumes both queues - see supervisord.conf.
app.conf.task_routes = {
    "news_platform.pages.pageHome.group_articles": {"queue": "ml"},
}

app.conf.beat_schedule = {
    "daytime": {
        "task": "news_platform.pages.pageHome.refresh_feeds",
        "schedule": crontab(minute="*/15", hour="5-18"),
        "args": (),
    },
    "nighttime": {
        "task": "news_platform.pages.pageHome.refresh_feeds",
        "schedule": crontab(minute="*/30", hour="18-23"),
        "args": (),
    },
    "webpush-cleanup": {
        "task": "news_platform.pages.pageHome.cleanup_webpush_subscriptions",
        "schedule": crontab(minute="58,28", hour="4-22"),
        "args": (),
    },
}


# --------------------------------------------------------------------------
# Returning memory to the OS
# --------------------------------------------------------------------------

_libc = None


def _get_libc():
    """Lazily resolve libc once per process (None on non-glibc platforms)."""
    global _libc
    if _libc is False:
        return None
    if _libc is None:
        try:
            _libc = ctypes.CDLL("libc.so.6")
        except (OSError, AttributeError):
            _libc = False
            return None
    return _libc


@worker_init.connect
def freeze_gc_before_fork(**kwargs):
    """Move everything imported at startup out of the GC's reach before forking.

    Runs in the worker *master*, before the prefork pool creates its children.
    Without this the GC walks Django/celery's long-lived object graph inside every
    child, and each header it touches dirties a page that was until then shared
    copy-on-write with the parent - so idle children slowly grow towards a full
    private copy of the interpreter heap.
    """
    gc.collect()
    gc.freeze()


@task_postrun.connect
def release_memory_to_os(**kwargs):
    """Collect cycles and hand freed arenas back to the OS after every task.

    MALLOC_TRIM_THRESHOLD_ (set in the Dockerfile) only lets glibc trim the top
    of the heap. Scraping fragments the arenas, so a large amount of freed-but-
    unreturned memory stays in the child's RSS until an explicit malloc_trim.
    """
    gc.collect()
    libc = _get_libc()
    if libc is not None:
        try:
            libc.malloc_trim(0)
        except (OSError, AttributeError):  # pragma: no cover - platform dependent
            pass


def is_task_already_executing(task_name: str) -> bool:
    """Returns whether the task with given task_name is already being executed.

    `inspect().active()` is a broadcast over the broker: it returns None when no
    worker replies inside the timeout (startup, a busy worker, a broker blip) and
    it can raise if the broker is unreachable. Both cases used to surface as an
    AttributeError inside the calling task, which then retried and made the
    situation worse. Failing open is the safe direction here - the caller holds a
    cache lock as the real mutual-exclusion mechanism.

    Args:
        task_name: Name of the task to check if it is running currently.
    Returns: A boolean indicating whether the task with the given task name is
        running currently.
    """
    try:
        active_tasks = app.control.inspect(timeout=2).active()
    except Exception as e:  # broker unreachable, serialization error, ...
        print(f"Could not inspect active celery tasks ({e}) - assuming none are running")
        return False

    if not active_tasks:
        return False

    task_count = 0
    for _worker, running_tasks in active_tasks.items():
        for task in running_tasks or []:
            if isinstance(task, dict) and task.get("name") == task_name:
                task_count += 1

    return task_count > 1
