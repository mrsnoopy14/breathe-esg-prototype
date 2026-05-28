"""
WSGI config for the ESG platform.

Exposes the WSGI callable as a module-level variable named ``application``.
Gunicorn picks this up automatically when pointed at config.wsgi.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()
