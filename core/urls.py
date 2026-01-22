from django.urls import path

from .views import CSPReportView, HealthView, IndexView

app_name = "core"

urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("health/", HealthView.as_view(), name="health"),
    path("csp-report/", CSPReportView.as_view(), name="csp-report"),
]
