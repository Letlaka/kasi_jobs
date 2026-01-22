from typing import ClassVar

from django.db import models


class Skill(models.Model):
    name = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["name"]

    def __str__(self) -> str:
        return str(self.name)
