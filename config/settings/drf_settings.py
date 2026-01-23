from __future__ import annotations

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "default": "15/min",
        "job": "10/min",
        "application": "20/min",
        "application_action": "30/min",
        # action-specific scopes for accept/reject endpoints
        "application_accept": "6/min",
        "application_reject": "6/min",
    },
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Fleet/School Shuttle API",
    "DESCRIPTION": "API documentation for Fleet/School Shuttle API endpoints",
    "VERSION": "1.0.0",
}

# Simple JWT defaults. Adjust lifetimes and rotation to suit your security policy.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": 300,  # seconds (5 minutes) - tune as needed
    "REFRESH_TOKEN_LIFETIME": 60 * 60 * 24 * 7,  # 7 days
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    # Use sliding tokens or additional settings as needed
}
