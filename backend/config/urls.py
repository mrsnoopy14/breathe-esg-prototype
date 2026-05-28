"""
Root URL configuration.

Auth endpoints live under /api/auth/
Ingestion/data endpoints live under /api/
Django admin is at /admin/
In DEBUG mode, media files are served by Django's dev server.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/', include('ingestion.urls')),
]

# Serve uploaded media files in development.
# In production, a reverse proxy (nginx / CDN) should handle /media/.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
