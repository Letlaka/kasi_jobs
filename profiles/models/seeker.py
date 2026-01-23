import logging
import mimetypes
import os
from decimal import Decimal
from typing import ClassVar, cast

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from utilities.app_logging import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName
from utilities.validators import sanitize_text_field, validate_decimal_range

from .base import BaseProfile
from .skills import Skill

logger = logging.getLogger(__name__)

MAX_TRAVEL_KM = 500


class SeekerProfile(BaseProfile):
    """Represents a job seeker profile (e.g. someone seeking work in trades).

    This class centralises upload validation for identity documents and
    provides a helper for producing signed download links consumed by
    `profiles.views.private_file_view`.
    """

    skills: models.ManyToManyField = models.ManyToManyField(
        Skill, blank=True, through="SeekerSkill", related_name="seekers"
    )

    hourly_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional hourly rate estimate",
    )

    availability_notes = models.CharField(max_length=255, blank=True)
    has_transport = models.BooleanField(default=False)

    willing_to_travel_km = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Maximum distance the worker is willing to travel from their base location",
    )

    id_document: models.FileField | None = models.FileField(
        upload_to="id_verification/", null=True, blank=True
    )  # type: ignore[misc]
    id_verified = models.BooleanField(default=False)

    # Upload validation settings
    MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MiB
    ALLOWED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg"}

    def _detect_mime(self, file_obj) -> str | None:
        """Detect MIME type using python-magic when available, else by filename."""
        try:
            import magic

            file_obj.seek(0)
            sample = file_obj.read(2048)
            file_obj.seek(0)
            m = magic.Magic(mime=True)
            return m.from_buffer(sample)
        except Exception:
            name = getattr(file_obj, "name", "") or ""
            mime, _ = mimetypes.guess_type(name)
            return mime

    def _scan_for_viruses(self, file_obj) -> tuple[bool, str | None] | None:
        """Scan file using ClamAV (python-clamd). Returns (True, None) if clean,
        (False, signature) if infected, or None if no scanner available."""
        try:
            import clamd
        except Exception:
            return None

        try:
            socket_path = os.environ.get("CLAMD_SOCKET")
            host = os.environ.get("CLAMD_HOST")
            port = int(os.environ.get("CLAMD_PORT")) if os.environ.get("CLAMD_PORT") else None
            if socket_path:
                cd = clamd.ClamdUnixSocket(socket_path)
            elif host and port:
                cd = clamd.ClamdNetworkSocket(host, port)
            else:
                cd = clamd.ClamdUnixSocket()

            file_obj.seek(0)
            data = file_obj.read()
            file_obj.seek(0)
            res = cd.scan_stream(data)
            if not res:
                return None
            stream_res = res.get("stream") or res.get(next(iter(res)))
            if not stream_res:
                return None
            status, signature = stream_res[0], stream_res[1]
            if status == "OK":
                return True, None
            return False, signature
        except Exception as exc:  # pragma: no cover - runtime/environmental
            logger.exception("Virus scanner error: %s", exc)
            return None

    def get_signed_document_url(
        self, *, request=None, expires_seconds: int | None = None, salt: str = "profiles.id_doc"
    ) -> dict | None:
        """Return signed URL info for the seeker's `id_document`.

        Returns a dict: ``{"url": ..., "token": ..., "expires_seconds": ...}``.
        The view enforces expiry via ``settings.SIGNED_URL_MAX_AGE`` when set.
        """
        if not self.id_document:
            return None

        payload = {"path": self.id_document.name, "profile_id": int(self.pk)}
        token = signing.dumps(payload, salt=salt)

        path = reverse("profiles:private_file", args=[token])
        if request is not None:
            url = request.build_absolute_uri(path)
        else:
            site_base = getattr(settings, "SITE_URL", None) or getattr(
                settings, "EXTERNAL_URL", None
            )
            url = (site_base.rstrip("/") + path) if site_base else path

        expires = (
            expires_seconds
            if expires_seconds is not None
            else getattr(settings, "SIGNED_URL_MAX_AGE", None)
        )
        return {"url": url, "token": token, "expires_seconds": expires}

    def clean(self) -> None:
        """Sanitise and validate seeker-specific fields, including file uploads."""
        super().clean()

        logger = get_logger(__name__)

        # Sanitize textual fields
        self.availability_notes = sanitize_text_field(
            cast("str | None", self.availability_notes), max_length=255
        )

        # Validate hourly_rate if present
        if self.hourly_rate is not None:
            try:
                validate_decimal_range(
                    cast("str | int | float | Decimal", self.hourly_rate), min_value=Decimal("0")
                )
            except Exception:
                log_event(
                    logger,
                    log_name=LogName.APPLICATION,
                    event_code=EventCode.AUDIT_VALIDATION_DECIMAL_FAILED,
                    event="seeker_hourly_rate_invalid",
                    field="hourly_rate",
                )
                raise

        # Validate willing_to_travel_km range (if set)
        if self.willing_to_travel_km is not None:
            try:
                travel = cast("int | float | str", self.willing_to_travel_km)
                if not (0 <= int(travel) <= MAX_TRAVEL_KM):
                    raise ValueError("willing_to_travel_km out of range")
            except Exception:
                log_event(
                    logger,
                    log_name=LogName.APPLICATION,
                    event_code=EventCode.AUDIT_VALIDATION_DECIMAL_FAILED,
                    event="seeker_travel_km_invalid",
                    field="willing_to_travel_km",
                )
                raise

        # File upload validations
        if self.id_document:
            try:
                size = getattr(self.id_document, "size", None)
                if size is None and hasattr(self.id_document, "file"):
                    size = getattr(self.id_document.file, "size", None)
                if size is not None and size > self.MAX_UPLOAD_SIZE:
                    raise ValidationError(
                        f"Uploaded file exceeds maximum size of {self.MAX_UPLOAD_SIZE} bytes"
                    )
            except ValidationError:
                raise
            except Exception:
                if not settings.DEBUG:
                    raise ValidationError("Unable to verify uploaded file size")

            # Detect MIME type
            mime = None
            try:
                with self.id_document.open("rb") as fh:
                    mime = self._detect_mime(fh) or None
            except Exception:
                mime = None

            if mime is None:
                name = getattr(self.id_document, "name", "") or ""
                mime, _ = mimetypes.guess_type(name)

            if mime not in self.ALLOWED_MIME_TYPES:
                raise ValidationError("Uploaded file type is not allowed")

            # Virus scan
            try:
                with self.id_document.open("rb") as fh:
                    scan_result = self._scan_for_viruses(fh)
            except Exception:
                scan_result = None

            if scan_result is None:
                if not settings.DEBUG:
                    raise ValidationError(
                        "Virus scanner not available in production; upload rejected"
                    )
                logger.warning("Virus scanner not available; skipping scan in DEBUG")
            else:
                ok, signature = scan_result
                if not ok:
                    raise ValidationError(f"Uploaded file flagged by virus scanner: {signature}")

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["hourly_rate"]),
            # `is_verified` is defined on BaseProfile (abstract) and indexed here intentionally.
            models.Index(fields=["is_verified"]),
        ]

    def __str__(self) -> str:
        username = getattr(self.user, "username", str(self.user))
        return f"{username}'s seeker profile"

    def clean(self) -> None:
        """Sanitize and validate seeker-specific fields."""
        super().clean()

        logger = get_logger(__name__)

        # Sanitize textual fields
        self.availability_notes = sanitize_text_field(
            cast("str | None", self.availability_notes), max_length=255
        )

        # Validate hourly_rate if present
        if self.hourly_rate is not None:
            try:
                validate_decimal_range(
                    cast("str | int | float | Decimal", self.hourly_rate),
                    min_value=Decimal("0"),
                )
            except Exception:
                log_event(
                    logger,
                    log_name=LogName.APPLICATION,
                    event_code=EventCode.AUDIT_VALIDATION_DECIMAL_FAILED,
                    event="seeker_hourly_rate_invalid",
                    field="hourly_rate",
                )
                raise

        # Validate willing_to_travel_km range (if set)
        if self.willing_to_travel_km is not None:
            try:
                travel = cast("int | float | str", self.willing_to_travel_km)
                if not (0 <= int(travel) <= MAX_TRAVEL_KM):
                    raise ValueError("willing_to_travel_km out of range")
            except Exception:
                log_event(
                    logger,
                    log_name=LogName.APPLICATION,
                    event_code=EventCode.AUDIT_VALIDATION_DECIMAL_FAILED,
                    event="seeker_travel_km_invalid",
                    field="willing_to_travel_km",
                )
                raise
