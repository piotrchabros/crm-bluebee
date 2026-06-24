"""
Test settings for Django CRM backend.

Uses SQLite in-memory database instead of PostgreSQL for fast, isolated tests.
RLS (Row-Level Security) is PostgreSQL-only and is skipped on SQLite.
"""

import tempfile

from crm.settings import *  # noqa: F401, F403

# Isolate uploaded files in tests to a throwaway temp dir so the suite never
# writes into the real MEDIA_ROOT (production /media) and leaves no artifacts.
MEDIA_ROOT = tempfile.mkdtemp(prefix="crm-test-media-")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable Celery broker/result backend in tests (no Redis needed)
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
