from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import include, path

from accounts import admin_views
from django_prometheus.exports import ExportToDjangoView

urlpatterns = [
    # Prometheus metrics – restricted to staff to prevent leaking operational metrics
    # to the public internet. For scraping from monitoring systems, prefer guarding
    # /metrics at the load-balancer/network level (see SECURITY.md).
    path("metrics", staff_member_required(ExportToDjangoView), name="prometheus-django-metrics"),
    path("admin/accounts/rate-limits/", admin_views.rate_limit_dashboard, name="admin-rate-limits"),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    # Core app (health checks and misc endpoints)
    path("", include("core.urls")),
    # API routes
    path("api/v1/", include("api.urls")),
    # Private file serving for profiles (signed URL access)
    path("profiles/", include("profiles.urls")),
]
