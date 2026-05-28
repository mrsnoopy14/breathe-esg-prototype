"""
Django settings for ESG Carbon Emissions Data Ingestion Platform.

Reads configuration from environment variables; falls back to safe development
defaults so the project works out-of-the-box without a .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root if present (no-op in production)
load_dotenv(BASE_DIR / '.env')

# ---------------------------------------------------------------------------
# Core security
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'dev-only-insecure-key-change-before-production-esg2024!'
)

DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = ['*']

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',

    # Project apps
    'accounts',
    'ingestion',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # serve static files in production
    'corsheaders.middleware.CorsMiddleware',         # must be before CommonMiddleware
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ---------------------------------------------------------------------------
# Database
# Parse DATABASE_URL manually to avoid adding dj-database-url dependency.
# Format: postgres://user:password@host:port/dbname
# ---------------------------------------------------------------------------
_DATABASE_URL = os.environ.get('DATABASE_URL', '')

if _DATABASE_URL:
    # Strip the scheme
    _url = _DATABASE_URL
    if _url.startswith('postgres://'):
        _url = _url[len('postgres://'):]
    elif _url.startswith('postgresql://'):
        _url = _url[len('postgresql://'):]

    # Split user:pass from host:port/name
    _user_info, _host_info = _url.split('@', 1)

    if ':' in _user_info:
        _db_user, _db_password = _user_info.split(':', 1)
    else:
        _db_user, _db_password = _user_info, ''

    # host:port/name  — port is optional
    if '/' in _host_info:
        _host_port, _db_name = _host_info.rsplit('/', 1)
    else:
        _host_port, _db_name = _host_info, ''

    if ':' in _host_port:
        _db_host, _db_port = _host_port.split(':', 1)
    else:
        _db_host, _db_port = _host_port, '5432'

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _db_name,
            'USER': _db_user,
            'PASSWORD': _db_password,
            'HOST': _db_host,
            'PORT': _db_port,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ---------------------------------------------------------------------------
# Custom user model
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = 'accounts.User'

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise compressed manifest storage for production.
# Django 5.1 uses the new STORAGES dict; STATICFILES_STORAGE is kept as a
# fallback alias that Django still accepts (with a deprecation notice).
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

# ---------------------------------------------------------------------------
# CORS (prototype — wide open; tighten in production)
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True

# ---------------------------------------------------------------------------
# Default primary key type
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
