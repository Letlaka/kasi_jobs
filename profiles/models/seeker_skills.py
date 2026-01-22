from django.db import models

from .seeker import SeekerProfile
from .skills import Skill


class SeekerSkill(models.Model):
    seeker = models.ForeignKey(SeekerProfile, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    years_experience = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("seeker", "skill")
