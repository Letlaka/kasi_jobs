"""
Signal registration for accounts app.

Importing these modules registers all signal receivers.
"""

from .audit import *  # noqa: F403
from .auth import *  # noqa: F403
from .profile import *  # noqa: F403
