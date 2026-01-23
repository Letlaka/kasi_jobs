from django.contrib import admin

from .models import Application, ApplicationAction


class ApplicationActionInline(admin.TabularInline):
    model = ApplicationAction
    extra = 0
    fields = ("action", "performed_by", "performed_at", "metadata")
    readonly_fields = ("performed_at",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("job", "seeker", "applied_at", "status")
    raw_id_fields = ("job", "seeker")
    inlines = (ApplicationActionInline,)


@admin.register(ApplicationAction)
class ApplicationActionAdmin(admin.ModelAdmin):
    list_display = ("application", "action", "performed_by", "performed_at")
    raw_id_fields = ("application", "performed_by")
    readonly_fields = ("performed_at",)
