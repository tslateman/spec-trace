"""
Django settings for spectrace project.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.2/ref/settings/
"""

import os
from pathlib import Path

import dj_database_url
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# In production, set SECRET_KEY environment variable
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-key-change-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
# Set DEBUG=false in production environment
DEBUG = os.environ.get("DEBUG", "true").lower() in ("true", "1", "yes")

# ALLOWED_HOSTS must be set in production
# Set as comma-separated list: ALLOWED_HOSTS=example.com,www.example.com
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()
] or ["localhost", "127.0.0.1", "[::1]"]

# API key for external systems to submit data
# Required for /api/update-slo-status, /api/submit-validation-result, etc.
SPECTRACE_API_KEY = os.environ.get("SPECTRACE_API_KEY", "")

# Project this installation owns. Requirements parsed without a project of their
# own land here, and coverage reports it when the caller names no other.
SPECTRACE_PROJECT = os.environ.get("SPECTRACE_PROJECT", "spectrace")

# GitHub App configuration for CI/CD integration
# Create a GitHub App at https://github.com/settings/apps
GITHUB_APP_ID = os.environ.get("GITHUB_APP_ID", "")
GITHUB_PRIVATE_KEY = os.environ.get("GITHUB_PRIVATE_KEY", "")  # PEM format
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

# Optional: restrict webhooks to specific repositories (comma-separated)
# Leave empty to allow all repositories where the app is installed
GITHUB_ALLOWED_REPOS = [
    r.strip() for r in os.environ.get("GITHUB_ALLOWED_REPOS", "").split(",") if r.strip()
]


# Application definition

INSTALLED_APPS = [
    # django-unfold must be before django.contrib.admin
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "treebeard",
    # Local apps
    "requirements",
    "spectrace_client",
]

# django-unfold configuration
UNFOLD = {
    "SITE_TITLE": "SpecTrace",
    "SITE_HEADER": "SpecTrace Dashboard",
    "DASHBOARD_CALLBACK": "requirements.dashboard.dashboard_callback",
    "SIDEBAR": {
        "show_search": False,
        "show_all_applications": False,
        "navigation": [
            {
                "title": _("Overview"),
                "separator": True,
                "items": [
                    {
                        "title": _("Dashboard"),
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                    {
                        "title": _("About SpecTrace"),
                        "icon": "info",
                        "link": reverse_lazy("admin-about"),
                    },
                ],
            },
            {
                "title": _("Specs"),
                "separator": True,
                "items": [
                    {
                        "title": _("Requirements"),
                        "icon": "assignment",
                        "link": reverse_lazy("admin:requirements_requirement_changelist"),
                    },
                    {
                        "title": _("Traceability Matrix"),
                        "icon": "grid_on",
                        "link": reverse_lazy("admin-matrix"),
                    },
                    {
                        "title": _("Impact Analysis"),
                        "icon": "analytics",
                        "link": reverse_lazy("admin-impact-analysis"),
                    },
                    {
                        "title": _("Spec Syntax Guide"),
                        "icon": "article",
                        "link": reverse_lazy("admin-spec-syntax"),
                    },
                ],
            },
            {
                "title": _("Standards"),
                "separator": True,
                "items": [
                    {
                        "title": _("Corpus Entries"),
                        "icon": "gavel",
                        "link": reverse_lazy("admin:requirements_corpusentry_changelist"),
                    },
                    {
                        "title": _("Corpus Versions"),
                        "icon": "history",
                        "link": reverse_lazy("admin:requirements_corpusentryversion_changelist"),
                    },
                    {
                        "title": _("Corpus Snapshots"),
                        "icon": "photo_camera",
                        "link": reverse_lazy("admin:requirements_corpussnapshot_changelist"),
                    },
                    {
                        "title": _("Spec Reviews"),
                        "icon": "rule",
                        "link": reverse_lazy("admin:requirements_specreview_changelist"),
                    },
                ],
            },
            {
                "title": _("Results"),
                "separator": True,
                "items": [
                    {
                        "title": _("Verification Runs"),
                        "icon": "fact_check",
                        "link": reverse_lazy("admin-validation-runs"),
                    },
                    {
                        "title": _("Test Runs"),
                        "icon": "science",
                        "link": reverse_lazy("admin:requirements_testrun_changelist"),
                    },
                    {
                        "title": _("Vendor Coverage"),
                        "icon": "business",
                        "link": reverse_lazy("admin-vendor-coverage"),
                    },
                ],
            },
        ],
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    *([] if DEBUG else ["whitenoise.middleware.WhiteNoiseMiddleware"]),
    "requirements.middleware.RequestSizeLimitMiddleware",
    "requirements.middleware.RequestIDMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "spectrace.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "spectrace.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
