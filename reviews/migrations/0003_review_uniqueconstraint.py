# Generated migration: replace unique_together with named UniqueConstraint on Review

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0002_historicalreview"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="review",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="review",
            constraint=models.UniqueConstraint(
                fields=["job", "reviewer"],
                name="unique_review_job_reviewer",
            ),
        ),
    ]
