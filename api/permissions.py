from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsPosterOrReadOnly(BasePermission):
    """Allow safe methods for everyone, but write only for the job poster or staff."""

    def has_object_permission(self, request: Request, _view: APIView, obj: object) -> bool:
        if request.method in SAFE_METHODS:
            return True
        poster = getattr(obj, "poster", None)
        return bool(request.user and (request.user.is_staff or poster == request.user))


class IsOwnerOrAdmin(BasePermission):
    """Allow object access only to the owner (one-to-one user) or admin."""

    def has_permission(self, request: Request, _view: APIView) -> bool:
        # generic: allow read to everyone, require auth for unsafe
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: Request, _view: APIView, obj: object) -> bool:
        # obj may be a profile with .user attribute or media with .owner
        owner = (
            getattr(obj, "user", None)
            or getattr(obj, "owner", None)
            or getattr(obj, "seeker", None)
        )
        return bool(request.user and (request.user.is_staff or owner == request.user))


class IsSeekerOrReadOnly(BasePermission):
    """Permit creation of applications to authenticated users; object access limited.

    Note: view-level checks should validate job ownership for posters.
    """

    def has_permission(self, request: Request, _view: APIView) -> bool:
        # Allow list/retrieve to authenticated users; creation requires authentication.
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: Request, _view: APIView, obj: object) -> bool:
        # Object-level access limited to owner (seeker) or admin. Business
        # rules (poster access, workflow) must be enforced in service layer
        # or view-level checks.
        if request.method in SAFE_METHODS:
            return True
        seeker = getattr(obj, "seeker", None)
        if request.user.is_staff:
            return True
        return bool(seeker is not None and seeker == request.user)
