from django.contrib import admin

from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "poster", "location", "is_active", "posted_at")
    raw_id_fields = ("poster",)
