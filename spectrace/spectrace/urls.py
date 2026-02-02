"""URL configuration for spectrace project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import include, path

from requirements.urls import admin_urlpatterns, api_urlpatterns

# Admin views must come before admin.site.urls
urlpatterns = admin_urlpatterns.copy()

# Conditionally include domain app URLs if installed
try:
    from hospitality import urls as hospitality_urls

    urlpatterns += hospitality_urls.urlpatterns
except ImportError:
    pass  # Domain app not installed

# Admin site and API
urlpatterns += [
    path("admin/", admin.site.urls),
]
urlpatterns += api_urlpatterns
