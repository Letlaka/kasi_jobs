# Generated migration: enforce one application per seeker per job

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("applications", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="application",
            constraint=models.UniqueConstraint(
                fields=["job", "seeker"],
                name="unique_application_job_seeker",
            ),
        ),
    ]
