from __future__ import annotations

import os

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.signing import BadSignature, SignatureExpired, loads
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404

from .models.seeker import SeekerProfile


def private_file_view(request, token: str):
    """Serve a private file if the signed token is valid and user authorised.

    Token format: signed payload produced by `django.core.signing.dumps`, containing
    {'path': '<storage path>', 'profile_id': <profile_pk>}.
    """
    try:
        max_age = getattr(settings, "SIGNED_URL_MAX_AGE", None)
        if max_age is None:
            payload = loads(token)
        else:
            payload = loads(token, max_age=max_age)
    except SignatureExpired:
        raise Http404("Token expired")
    except BadSignature:
        raise Http404("Invalid token")

    path = payload.get("path")
    profile_id = payload.get("profile_id")
    if not path or not profile_id:
        raise Http404()

    profile = get_object_or_404(SeekerProfile, pk=profile_id)

    # authorization: only owner or staff may download
    user = getattr(request, "user", None)
    if not (user and (user.is_authenticated and (user.is_staff or user == profile.user))):
        return HttpResponseForbidden()

    if not default_storage.exists(path):
        raise Http404()

    fh = default_storage.open(path, "rb")
    filename = os.path.basename(path)
    response = FileResponse(fh, as_attachment=True, filename=filename)
    return response
