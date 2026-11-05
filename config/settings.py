"""Inställningar för Bitero Budget.

Systemet körs lokalt på din dator och lyssnar bara på 127.0.0.1.
"""

import os
import secrets
from pathlib import Path

from .datadir import DB_NAMN, hitta_backupmapp, hitta_datamapp

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = hitta_datamapp()
BACKUP_DIR = hitta_backupmapp(DATA_DIR)

# Hemlig nyckel skapas vid första start och sparas lokalt (ska inte delas).
_key_file = DATA_DIR / "secret_key.txt"
if not _key_file.exists():
    _key_file.write_text(secrets.token_urlsafe(50))
SECRET_KEY = _key_file.read_text().strip()

# Driftläge som standard: waitress + WhiteNoise. Utvecklingsläge: BUDGET_DEBUG=1.
DEBUG = os.environ.get("BUDGET_DEBUG") == "1"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ekonomi",
    "budget",
    "tillgangar",
    "assistent",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "config.middleware.LoginRequiredEverywhere",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "ekonomi.context_processors.meny",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / DB_NAMN,
        "OPTIONS": {"init_command": "PRAGMA journal_mode=WAL;"},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
]

LANGUAGE_CODE = "sv"
FORMAT_MODULE_PATH = ["config.formats"]  # datum som ÅÅÅÅ-MM-DD
TIME_ZONE = "Europe/Stockholm"
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = False  # belopp formateras med filtret |kr

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG

FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 20000  # budgetformuläret har många fält

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"tid": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {
        "fil": {"class": "logging.handlers.RotatingFileHandler", "filename": DATA_DIR / "fel.log",
                "maxBytes": 2_000_000, "backupCount": 3, "encoding": "utf-8", "formatter": "tid",
                "level": "WARNING"},
        "terminal": {"class": "logging.StreamHandler", "level": "ERROR"},
    },
    "loggers": {
        "django": {"handlers": ["fil", "terminal"], "level": "ERROR", "propagate": False},
        "waitress": {"handlers": ["fil", "terminal"], "level": "WARNING", "propagate": False},
    },
    "root": {"handlers": ["fil"], "level": "WARNING"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
