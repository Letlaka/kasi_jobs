from django.contrib import admin

from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("job", "seeker", "applied_at", "is_accepted")
    raw_id_fields = ("job", "seeker")
