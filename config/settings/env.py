import os
from dataclasses import dataclass
from pathlib import Path

try:
    import environ
except (ImportError, ModuleNotFoundError):
    environ = None

BASE_DIR = Path(__file__).resolve().parent.parent.parent


if environ is not None:
    env = environ.FileAwareEnv(
        SITE_ID=(int, 1),
        # Django settings
        DJANGO_DEBUG=(bool, False),
        # Do NOT provide a usable default for secret keys; require explicit setting.
        DJANGO_SECRET_KEY=(str, None),
        HMAC_SECRET_KEY=(str, None),
        DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
        # Email settings
        EMAIL_PORT=(int, 587),
        EMAIL_USE_TLS=(bool, True),
        # Database settings
        POSTGRES_PORT=(int, 5432),
        POSTGRES_HOST=(str, None),
        POSTGRES_DB=(str, None),
        POSTGRES_USER=(str, None),
        POSTGRES_PASSWORD=(str, None),
        # Celery settings
        CELERY_BROKER_URL=(str, "redis://localhost:6379/0"),
        CELERY_RESULT_BACKEND=(str, "redis://localhost:6379/0"),
        CELERY_TASK_RESULT_EXPIRES=(int, 3600),
        # Security & HTTPS settings
        SECURE_SSL_REDIRECT=(bool, False),
        SESSION_COOKIE_SECURE=(bool, True),
        CSRF_COOKIE_SECURE=(bool, True),
        # HSTS settings
        SECURE_HSTS_SECONDS=(int, 31536000),
        SECURE_HSTS_INCLUDE_SUBDOMAINS=(bool, True),
        SECURE_HSTS_PRELOAD=(bool, True),
        # Security settings
        SECURE_CONTENT_TYPE_NOSNIFF=(bool, True),
        SECURE_BROWSER_XSS_FILTER=(bool, True),
        SECURE_PROXY_SSL_HEADER=(str, "HTTP_X_FORWARDED_PROTO, http"),
        proxy_header=(str, "HTTP_X_FORWARDED_PROTO, http"),
        # Clickjacking protection
        X_FRAME_OPTIONS=(str, "X_FRAME_OPTIONS"),
        # Optional: Cookie samesite settings
        SESSION_COOKIE_SAMESITE=(str, "SESSION_COOKIE_SAMESITE"),
        CSRF_COOKIE_SAMESITE=(str, "CSRF_COOKIE_SAMESITE"),
        # django-auditlog global settings (POPIA / privacy friendly defaults)
        AUDITLOG_INCLUDE_ALL_MODELS=(bool, False),
        AUDITLOG_EXCLUDE_TRACKING_FIELDS=(
            list,
            ["created_at", "updated_at", "is_active", "deleted_at", "password"],
        ),
        AUDITLOG_DISABLE_REMOTE_ADDR=(bool, True),
        # django-cors-headers settings
        CORS_ALLOW_ALL_ORIGINS=(bool, False),
        CORS_ALLOWED_ORIGINS=(list, ["http://localhost:8000"]),
        CORS_ALLOW_CREDENTIALS=(bool, True),
        CORS_ALLOW_HEADERS=(
            list,
            [
                "accept",
                "accept-encoding",
                "authorization",
                "content-type",
                "dnt",
                "origin",
                "user-agent",
                "x-csrftoken",
                "x-requested-with",
            ],
        ),
        CORS_ALLOW_METHODS=(list, ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]),
        CORS_URLS_REGEX=(str, "CORS_URLS_REGEX"),
        # Content Security Policy (CSP) settings
        CSP_DEFAULT_SRC=(list, ["'self'"]),
        CSP_SCRIPT_SRC=(list, ["'self'"]),
        CSP_STYLE_SRC=(list, ["'self'"]),
        CSP_IMG_SRC=(list, ["'self'", "data:"]),
        CSP_FONT_SRC=(list, ["'self'", "https://fonts.gstatic.com"]),
        CSP_CONNECT_SRC=(list, ["'self'"]),
        CSP_FRAME_SRC=(list, ["'self'"]),
        CSP_INCLUDE_NONCE_IN=(str, "script-src,style-src"),
        CSP_REPORT_ONLY=(bool, False),
        CSP_REPORT_URI=(str, "CSP_REPORT_URI"),
        # django-axes settings
        AXES_ENABLED=(bool, True),
        AXES_FAILURE_LIMIT=(int, 5),
        AXES_COOLOFF_TIME=(int, 900),
        AXES_LOCKOUT_PARAMETERS=(str, "username,ip_address"),
        AXES_USERNAME_FORM_FIELD=(str, "login"),
        AXES_IPWARE_META_PRECEDENCE_ORDER=(
            list,
            ["HTTP_X_REAL_IP", "HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"],
        ),
        AXES_CACHE=(str, "default"),
        AXES_HANDLER=(str, "axes.handlers.database.AxesDatabaseHandler"),
        AXES_RESET_ON_SUCCESS=(bool, True),
        AXES_SENSITIVE_PARAMETERS=(list, ["password", "username", "ip_address"]),
        # Account / login rate-limit defaults (centralised)
        ACCOUNTS_LOGIN_MAX_ATTEMPTS=(int, 5),
        ACCOUNTS_LOGIN_WINDOW_SECONDS=(int, 300),
        ACCOUNTS_LOCKOUT_SECONDS=(int, 900),
        AD_USERNAME=(str, "AD_USERNAME"),
        AD_PASSWORD=(str, "AD_PASSWORD"),
        AD_BASE_DN=(str, "AD_BASE_DN"),
        AD_SERVER=(str, "AD_SERVER"),
        AD_SUFFIX=(str, ".gauteng.gpg.local"),
        AD_WORKERS=(int, 20),
        AD_BULK_EXPORT=(bool, True),
        AD_PAGED_SIZE=(int, 1000),
        AD_PORT=(int, "AD_PORT"),
        AD_USE_SSL=(bool, "AD_USE_SSL"),
    )

    import contextlib

    # Only load a local `.env` file when running in a development-like
    # environment. Accept both `development` and `dev` (and common aliases)
    # so `DJANGO_ENV=dev` works in docker-compose while still preventing
    # accidental `.env` loads in production.
    django_env = os.getenv("DJANGO_ENV", "development") or "development"
    if str(django_env).lower() in ("development", "dev", "local") or str(
        django_env
    ).lower().startswith("dev"):
        with contextlib.suppress(Exception):
            env.read_env(BASE_DIR / ".env")
else:

    class _FallbackEnv:
        """Minimal env provider used when `environ` is not installed.

        This mirrors the small subset of the `environ.FileAwareEnv` API used
        by the project: callable access, `bool()`, `int()`, and `list()`.
        Behavior is intentionally simple and preserves existing defaults.
        """

        def __init__(self) -> None:
            self._os = os.environ

        def __call__(self, key: str, default: str | None = None) -> str | None:
            return self._os.get(key, default)

        def _raw(self, key: str) -> str | None:
            """Return the raw string value from the environment or None."""
            return self._os.get(key)

        def bool(self, key: str, *, default: bool = False) -> bool:
            v = self._raw(key)
            if v is None:
                return default
            return str(v).lower() in ("1", "true", "yes", "on")

        def int(self, key: str, *, default: int = 0) -> int:
            v = self._raw(key)
            if v is None:
                return default
            try:
                return int(v)
            except (TypeError, ValueError):
                return default

        def list(self, key: str, *, default: list[str] | None = None) -> list[str]:
            v = self._raw(key)
            if v is None:
                return [] if default is None else default
            return [p.strip() for p in v.split(",") if p.strip()]

    env = _FallbackEnv()


@dataclass
class ADConfig:
    server: str
    username: str
    password: str
    base_dn: str
    use_ssl: bool
    port: int | None


def get_ad_config() -> ADConfig:
    """Return an ADConfig populated from environment variables.

    This centralises AD-related environment parsing so other scripts can
    consume a single, well-formed object.
    """
    server_raw = str(env("AD_SERVER") or "").strip()
    username = str(env("AD_USERNAME") or "")
    password = str(env("AD_PASSWORD") or "")
    base_dn = str(env("AD_BASE_DN") or "")

    # Normalize server and detect scheme if present. If the URL contains
    # an explicit ldap:// or ldaps:// scheme, honour it and strip the scheme
    # from the returned host. Otherwise, fall back to `AD_USE_SSL` flag.
    # Call `env.bool` without the named `default=` to avoid a typing mismatch
    # between environ.FileAwareEnv and our local _FallbackEnv implementation.
    use_ssl_env = env.bool("AD_USE_SSL")
    server_host = server_raw
    use_ssl = bool(use_ssl_env)
    if server_raw.lower().startswith("ldaps://"):
        use_ssl = True
        server_host = server_raw.split("://", 1)[1]
    elif server_raw.lower().startswith("ldap://"):
        use_ssl = False
        server_host = server_raw.split("://", 1)[1]

    # Determine port: prefer explicit AD_PORT if provided, else default to
    # 636 for SSL and 389 otherwise.
    # Use a conservative parsing path to ensure an `int` is produced even if
    # the underlying env implementation returns unexpected types.
    raw_port = env("AD_PORT")
    if raw_port in (None, ""):
        port_val = 0
    else:
        try:
            # Convert to str first so `int()` always receives a proper type
            # and the type checker can reason about the call.
            port_val = int(str(raw_port))
        except (TypeError, ValueError):
            port_val = 0
    port = port_val or (636 if use_ssl else 389)
    # final server_host may include a trailing path; strip any trailing /
    server_host = server_host.rstrip("/")
    return ADConfig(
        server=server_host,
        username=username,
        password=password,
        base_dn=base_dn,
        use_ssl=use_ssl,
        port=port,
    )


# Helper to require a value from the environment. This mirrors the simple
# behaviour used elsewhere but centralises the check so callers can fail
# fast when a critical secret is missing.
def require_env(key: str) -> str:
    value = env(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return str(value)
