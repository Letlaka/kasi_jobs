from __future__ import annotations

from django.db import models
from simple_history.models import HistoricalRecords


class AuditedModel(models.Model):
    """
    Abstract base model that wires in auditability for concrete models:
    - `history` from django-simple-history (HistoricalRecords)
    Concrete models should inherit from this to gain history tracking.

    Auditlog (django-auditlog) registration is handled in
    `utilities.apps.UtilitiesConfig.ready()` so concrete subclasses are
    registered automatically when the app is loaded.
    """

    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True
