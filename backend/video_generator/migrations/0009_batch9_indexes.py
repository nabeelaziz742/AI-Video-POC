# Generated for Batch 9 indexes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("video_generator", "0007_billing_event"),
        ("video_generator", "0008_character_reference_attempt"),
    ]

    operations = [
        migrations.AlterField(
            model_name="credittransaction",
            name="kind",
            field=models.CharField(
                choices=[
                    ("grant", "Grant"),
                    ("reserve", "Reserve"),
                    ("release", "Release"),
                    ("consume", "Consume"),
                    ("refund", "Refund"),
                    ("adjustment", "Adjustment"),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="subscription",
            name="provider_subscription_id",
            field=models.CharField(blank=True, db_index=True, max_length=120),
        ),
        migrations.AlterField(
            model_name="usageevent",
            name="kind",
            field=models.CharField(
                choices=[
                    ("project", "Project"),
                    ("scene", "Scene"),
                    ("character_reference", "Character reference"),
                    ("assembly", "Assembly"),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="videoproject",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name="videoproject",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("queued", "Queued"),
                    ("processing", "Processing"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                db_index=True,
                default="draft",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="videoscene",
            name="provider_project_id",
            field=models.CharField(blank=True, db_index=True, max_length=120, null=True),
        ),
        migrations.AlterField(
            model_name="videoscene",
            name="status",
            field=models.CharField(
                choices=[
                    ("planned", "Planned"),
                    ("processing", "Processing"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                db_index=True,
                default="planned",
                max_length=20,
            ),
        ),
    ]
