from django.contrib import admin

from profiles.models.poster import PosterProfile
from profiles.models.seeker import SeekerProfile
from profiles.models.seeker_skills import SeekerSkill
from profiles.models.skills import Skill

admin.site.register(Skill)
admin.site.register(SeekerSkill)


@admin.register(SeekerProfile)
class SeekerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "hourly_rate", "id_verified")
    raw_id_fields = ("user",)


@admin.register(PosterProfile)
class PosterProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "organization_name", "default_location")
    raw_id_fields = ("user",)
