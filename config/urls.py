from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from accounts import admin_views

urlpatterns = [
    path("metrics/", RedirectView.as_view(url="/metrics", permanent=False)),
    path("", include("django_prometheus.urls")),
    path("admin/accounts/rate-limits/", admin_views.rate_limit_dashboard, name="admin-rate-limits"),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    # Core app (health checks and misc endpoints)
    path("", include("core.urls")),
    # API routes
    path("api/v1/", include("api.urls")),
]
