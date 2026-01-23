from contextlib import suppress
from typing import ClassVar, cast

from applications.models import Application
from django.contrib.auth import get_user_model
from jobs.models import Job
from profiles.models.seeker import SeekerProfile
from profiles.models.skills import Skill
from rest_framework import serializers

User = get_user_model()


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields: ClassVar[list[str]] = ["id", "name"]


class JobSerializer(serializers.ModelSerializer):
    poster: serializers.PrimaryKeyRelatedField = serializers.PrimaryKeyRelatedField(read_only=True)  # pyright: ignore[reportAssignmentType]
    skills_needed: SkillSerializer = SkillSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields: ClassVar[list[str]] = [
            "id",
            "poster",
            "title",
            "description",
            "location",
            "skills_needed",
            "estimated_hours",
            "hourly_rate",
            "posted_at",
            "status",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "poster", "posted_at"]


class ApplicationSerializer(serializers.ModelSerializer):
    seeker: serializers.PrimaryKeyRelatedField = serializers.PrimaryKeyRelatedField(read_only=True)  # pyright: ignore[reportAssignmentType]
    # avoid evaluating Job.objects at import time (mypy without django-stubs complains)
    # mark read_only here to avoid DRF asserting a queryset at import time;
    # the real queryset is still set lazily in `get_fields` for runtime use.
    job: serializers.PrimaryKeyRelatedField = serializers.PrimaryKeyRelatedField(read_only=True)  # pyright: ignore[reportAssignmentType]

    class Meta:
        model = Application
        fields: ClassVar[list[str]] = [
            "id",
            "job",
            "seeker",
            "cover_note",
            "proposed_rate",
            "applied_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "seeker", "applied_at"]

    def get_fields(self) -> dict:
        fields = super().get_fields()
        # set queryset lazily so static type checkers don't require django-stubs
        with suppress(Exception):
            # set queryset lazily so static type checkers don't require django-stubs
            cast("serializers.PrimaryKeyRelatedField", fields["job"]).queryset = Job.objects.all()  # type: ignore[attr-defined]
        return fields


class SeekerProfileSerializer(serializers.ModelSerializer):
    user: serializers.PrimaryKeyRelatedField = serializers.PrimaryKeyRelatedField(read_only=True)  # pyright: ignore[reportAssignmentType]
    skills: SkillSerializer = SkillSerializer(many=True, read_only=True)

    class Meta:
        model = SeekerProfile
        fields: ClassVar[list[str]] = [
            "id",
            "user",
            "is_verified",
            "bio",
            "skills",
            "hourly_rate",
            "availability_notes",
            "has_transport",
            "willing_to_travel_km",
            "id_verified",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "user", "is_verified", "id_verified"]


class ApplicationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating an application within a job context.

    Exposes only fields that a seeker may set when applying.
    """

    cover_note = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Application
        fields: ClassVar[list[str]] = ["cover_note", "proposed_rate"]


class ApplicationReadSerializer(serializers.ModelSerializer):
    seeker: serializers.PrimaryKeyRelatedField = serializers.PrimaryKeyRelatedField(read_only=True)  # pyright: ignore[reportAssignmentType]

    class Meta:
        model = Application
        fields: ClassVar[list[str]] = [
            "id",
            "job",
            "seeker",
            "cover_note",
            "proposed_rate",
            "applied_at",
            "status",
        ]
        read_only_fields: ClassVar[list[str]] = fields
