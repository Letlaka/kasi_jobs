# no typing imports required here

import contextlib
import logging
from typing import Any

from applications.models import Application
from django.conf import settings
from django.db.models import Q
from django.db.models.query import QuerySet
from django.http import Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from jobs.models import Job
from profiles.models.seeker import SeekerProfile
from rest_framework import (
    serializers as _serializers,
    serializers as drf_serializers,
    status,
    viewsets,
)
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, Throttled
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from services.applications_service import accept_application, reject_application

from api.error_codes import INTERNAL_ERROR, JOB_NOT_OPEN, NOT_AUTHORIZED
from api.errors import ApiError

from .metrics import (
    API_ENDPOINT_ERRORS,
    APPLICATIONS_CREATED,
    THROTTLE_HITS,
    safe_inc,
)
from .pagination import BoundedPageNumberPagination
from .permissions import IsOwnerOrAdmin, IsPosterOrReadOnly, IsSeekerOrReadOnly
from .serializers import (
    ApplicationCreateSerializer,
    ApplicationReadSerializer,
    JobSerializer,
    SeekerProfileSerializer,
)
from .throttle_scopes import (
    THROTTLE_APPLICATION,
    THROTTLE_APPLICATION_ACCEPT,
    THROTTLE_APPLICATION_REJECT,
    THROTTLE_JOB,
)

logger = logging.getLogger(__name__)


class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, IsPosterOrReadOnly)
    throttle_scope = THROTTLE_JOB
    # Enforce a client-side page size cap to avoid deep paging and large
    # responses. Use cursor pagination for very large result sets.
    pagination_class = BoundedPageNumberPagination

    def get_serializer_class(self) -> type[Any]:
        """
        Explicit serializer selection by action.

        - Default job endpoints use `JobSerializer`.
        - The `applications` custom action is view-driven:
          - `GET /jobs/{id}/applications/` -> `ApplicationReadSerializer`
          - `POST /jobs/{id}/applications/` -> `ApplicationCreateSerializer`

        This prevents accidental exposure of fields if future refactors
        change `serializer_class` without considering action intent.
        """
        if getattr(self, "action", None) == "applications":
            if getattr(self, "request", None) is not None and self.request.method == "POST":
                return ApplicationCreateSerializer
            return ApplicationReadSerializer
        return JobSerializer

    @action(detail=True, methods=["get", "post"], permission_classes=[IsSeekerOrReadOnly])
    @extend_schema(
        description=(
            "List or create applications scoped to a job. POST creates an application "
            "on behalf of an authenticated seeker. GET is restricted to the job poster or staff."
        ),
        responses={
            200: ApplicationReadSerializer(many=True),
            201: ApplicationReadSerializer,
            403: inline_serializer(
                name="NotAuthorized",
                fields={"code": _serializers.CharField(), "detail": _serializers.CharField()},
            ),
        },
    )
    def applications(
        self, request: Request, pk: object = None, *_args: object, **_kwargs: object
    ) -> Response:
        """List or create applications scoped to this job.

        GET  /jobs/{id}/applications/  -> list applications for job (poster/admin view)
        POST /jobs/{id}/applications/  -> create application as authenticated seeker
        """
        # For GET we use the regular object lookup (which applies object
        # permissions). For POST we need to allow authenticated seekers to
        # attempt to create an application (so we fetch the job directly
        # to avoid triggering poster-only object permission checks).
        if request.method == "GET":
            job = self.get_object()
            # restrict listing to poster or admin
            if not (request.user.is_staff or getattr(job, "poster", None) == request.user):
                return Response(status=status.HTTP_403_FORBIDDEN)
            qs = job.applications.select_related("seeker").order_by("-applied_at")
            # paginate custom action explicitly to avoid unbounded responses
            page = self.paginate_queryset(qs)
            if page is not None:
                read_serializer = ApplicationReadSerializer(page, many=True)
                return self.get_paginated_response(read_serializer.data)
            read_serializer = ApplicationReadSerializer(qs, many=True)
            return Response(read_serializer.data)

        # POST -> create application for this job
        # prevent applying to non-open jobs
        try:
            job = Job.objects.get(pk=pk)  # type: ignore[attr-defined]
        except Job.DoesNotExist:
            raise Http404() from None
        job_status = getattr(job, "status", None)
        if job_status is not None and job_status != Job.JobStatus.OPEN:
            return Response(
                {"code": JOB_NOT_OPEN, "detail": "job is not open for applications"},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = ApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(seeker=request.user, job=job)
        # metrics: application created (best-effort)
        with contextlib.suppress(Exception):
            safe_inc(APPLICATIONS_CREATED)
        read_serializer = ApplicationReadSerializer(serializer.instance)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def get_queryset(self) -> QuerySet[Any]:
        """
        Return a queryset for jobs.

        Supports optional query parameters to reduce result sets and avoid
        full-table scans under growth:
        - `status`: filter by Job.status
        - `location`: case-insensitive contains match on `location`
        """
        qs = Job.objects.select_related().prefetch_related("skills_needed")  # type: ignore[attr-defined]
        # optional filters
        status_param = (
            self.request.query_params.get("status") if getattr(self, "request", None) else None
        )
        location_param = (
            self.request.query_params.get("location") if getattr(self, "request", None) else None
        )
        if status_param:
            qs = qs.filter(status=status_param)
        if location_param:
            qs = qs.filter(location__icontains=location_param)
        return qs.order_by("-posted_at")

    def perform_create(self, serializer: drf_serializers.BaseSerializer) -> None:
        serializer.save(poster=self.request.user)


class ApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = ApplicationReadSerializer
    permission_classes = (IsSeekerOrReadOnly,)
    throttle_scope = THROTTLE_APPLICATION

    def get_serializer_class(self) -> type[Any]:
        """
        Explicit serializer selection for application endpoints.

        - Read operations use `ApplicationReadSerializer`.
        - Creation (if ever enabled on this view) should use
          `ApplicationCreateSerializer` to avoid exposing read-only fields.
        """
        if getattr(self, "action", None) == "create":
            return ApplicationCreateSerializer
        return ApplicationReadSerializer

    def create(self, request: Request, *_args: object, **_kwargs: object) -> Response:
        # Disallow creating applications via the top-level collection. Use
        # POST /api/v1/jobs/{job_id}/applications/ instead to ensure proper
        # scoping and validation.
        # mark request as used to satisfy linters; creation via job-scoped endpoint only
        _ = request
        raise MethodNotAllowed("POST")

    def get_queryset(self) -> QuerySet[Any]:
        """
        Return applications queryset with optional filters to narrow results.

        Supported query params:
        - `job`: job id
        - `seeker`: seeker user id
        - `status`: application status
        """
        qs = Application.objects.select_related("job", "seeker")  # type: ignore[attr-defined]

        # apply optional filters from query params before applying auth scoping
        if getattr(self, "request", None):
            job_param = self.request.query_params.get("job")
            seeker_param = self.request.query_params.get("seeker")
            status_param = self.request.query_params.get("status")
            if job_param:
                with contextlib.suppress(Exception):
                    qs = qs.filter(job_id=int(job_param))
            if seeker_param:
                with contextlib.suppress(Exception):
                    qs = qs.filter(seeker_id=int(seeker_param))
            if status_param:
                qs = qs.filter(status=status_param)

        qs = qs.order_by("-applied_at")

        user = getattr(self.request, "user", None)
        if user is None:
            return qs.none()
        if user.is_staff:
            return qs
        # posters should see applications for their jobs; seekers see their own
        return qs.filter(Q(seeker=user) | Q(job__poster=user))

    def perform_create(self, serializer: drf_serializers.BaseSerializer) -> None:
        serializer.save(seeker=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsPosterOrReadOnly])
    @extend_schema(
        description=(
            "Accept an application. Allowed transition: PENDING -> ACCEPTED. "
            "Only job poster or staff may perform this. Returns a 409 with "
            "`application_not_pending` when the application is not in PENDING state."
        ),
        request=None,
        responses={
            200: inline_serializer(
                name="ApplicationAcceptResponse",
                fields={"status": _serializers.CharField()},
            ),
            403: OpenApiResponse(response={"$ref": "#/components/schemas/ErrorPayload"}),
            409: OpenApiResponse(response={"$ref": "#/components/schemas/ErrorPayload"}),
        },
    )
    def accept(
        self, request: Request, pk: object = None, *_args: object, **_kwargs: object
    ) -> Response:
        # Fetch the application directly so we can return 403 for unauthorized
        # users (instead of a 404 from the queryset filtering in `get_queryset`).
        try:
            app = Application.objects.select_related("job").get(pk=pk)  # type: ignore[attr-defined]
        except Application.DoesNotExist:
            raise Http404() from None
        # only job poster or staff can accept
        job = getattr(app, "job", None)
        if not (request.user.is_staff or getattr(job, "poster", None) == request.user):
            return Response(
                {"code": NOT_AUTHORIZED, "detail": "not authorized"},
                status=status.HTTP_403_FORBIDDEN,
            )
        # enforce per-action throttle
        self.throttle_scope = THROTTLE_APPLICATION_ACCEPT
        # will raise Throttled if exceeded; increment throttle metric when triggered
        try:
            self.check_throttles(request)
        except Throttled:
            with contextlib.suppress(Exception):
                env = getattr(settings, "ENVIRONMENT", None) or getattr(settings, "ENV", "local")
                safe_inc(THROTTLE_HITS, env, THROTTLE_APPLICATION_ACCEPT)
            raise
        try:
            accept_application(app, request.user)
        except ApiError as exc:
            with contextlib.suppress(Exception):
                env = getattr(settings, "ENVIRONMENT", None) or getattr(settings, "ENV", "local")
                safe_inc(API_ENDPOINT_ERRORS, env, "application.accept", "POST", str(exc.status))
            return Response(exc.to_payload(), status=exc.status)
        except Exception as exc:
            # Unexpected failures should not leak internals to clients.
            logger.exception("Unexpected error in accept: %s", exc)
            with contextlib.suppress(Exception):
                env = getattr(settings, "ENVIRONMENT", None) or getattr(settings, "ENV", "local")
                safe_inc(API_ENDPOINT_ERRORS, env, "application.accept", "POST", "500")
            return Response({"code": INTERNAL_ERROR, "detail": "internal server error"}, status=500)
        return Response({"status": "accepted"})

    @action(detail=True, methods=["post"], permission_classes=[IsPosterOrReadOnly])
    @extend_schema(
        description=(
            "Reject an application. Allowed transition: PENDING -> REJECTED. "
            "Only job poster or staff may perform this. Returns a 409 with "
            "`application_not_pending` when the application is not in PENDING state."
        ),
        request=None,
        responses={
            200: inline_serializer(
                name="ApplicationRejectResponse",
                fields={"status": _serializers.CharField()},
            ),
            403: OpenApiResponse(response={"$ref": "#/components/schemas/ErrorPayload"}),
            409: OpenApiResponse(response={"$ref": "#/components/schemas/ErrorPayload"}),
        },
    )
    def reject(
        self, request: Request, pk: object = None, *_args: object, **_kwargs: object
    ) -> Response:
        try:
            app = Application.objects.select_related("job").get(pk=pk)  # type: ignore[attr-defined]
        except Application.DoesNotExist:
            raise Http404() from None
        job = getattr(app, "job", None)
        if not (request.user.is_staff or getattr(job, "poster", None) == request.user):
            return Response(
                {"code": NOT_AUTHORIZED, "detail": "not authorized"},
                status=status.HTTP_403_FORBIDDEN,
            )
        # enforce per-action throttle
        self.throttle_scope = THROTTLE_APPLICATION_REJECT
        try:
            self.check_throttles(request)
        except Throttled:
            with contextlib.suppress(Exception):
                env = getattr(settings, "ENVIRONMENT", None) or getattr(settings, "ENV", "local")
                safe_inc(THROTTLE_HITS, env, THROTTLE_APPLICATION_REJECT)
            raise
        try:
            reject_application(app, request.user)
        except ApiError as exc:
            with contextlib.suppress(Exception):
                env = getattr(settings, "ENVIRONMENT", None) or getattr(settings, "ENV", "local")
                safe_inc(API_ENDPOINT_ERRORS, env, "application.reject", "POST", str(exc.status))
            return Response(exc.to_payload(), status=exc.status)
        except Exception as exc:
            logger.exception("Unexpected error in reject: %s", exc)
            with contextlib.suppress(Exception):
                env = getattr(settings, "ENVIRONMENT", None) or getattr(settings, "ENV", "local")
                safe_inc(API_ENDPOINT_ERRORS, env, "application.reject", "POST", "500")
            return Response({"code": INTERNAL_ERROR, "detail": "internal server error"}, status=500)
        return Response({"status": "rejected"})


class SeekerProfileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SeekerProfileSerializer
    permission_classes = (IsOwnerOrAdmin,)

    def get_serializer_class(self) -> type[Any]:
        """
        Explicitly return the profile serializer for all actions on this viewset.
        Keeps selection clear for future refactors.
        """
        return SeekerProfileSerializer

    def get_queryset(self) -> QuerySet[Any]:
        user = getattr(self.request, "user", None)
        qs = SeekerProfile.objects.select_related("user").prefetch_related("skills")  # type: ignore[attr-defined]
        if user is None or not user.is_authenticated:
            return qs.none()
        if user.is_staff:
            return qs.all()
        return qs.filter(user=user)
