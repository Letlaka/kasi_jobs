# Generated migration: add PayoutStatus and status field to Payout

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="payout",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("processing", "Processing"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                    ("refunded", "Refunded"),
                ],
                default="pending",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="historicalpayout",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("processing", "Processing"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                    ("refunded", "Refunded"),
                ],
                default="pending",
                max_length=32,
            ),
        ),
        migrations.AddIndex(
            model_name="payout",
            index=models.Index(fields=["status"], name="payments_payout_status_idx"),
        ),
    ]
