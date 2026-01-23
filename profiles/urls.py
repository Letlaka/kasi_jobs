from django.urls import path

from .views import private_file_view

app_name = "profiles"

urlpatterns = [
    path("files/<str:token>/", private_file_view, name="private_file"),
]
