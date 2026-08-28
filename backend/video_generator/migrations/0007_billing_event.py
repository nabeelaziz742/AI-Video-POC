from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("video_generator", "0008_character_reference_attempt")]

    operations = [migrations.CreateModel(
        name="BillingEvent",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("provider", models.CharField(default="stripe", max_length=30)),
            ("event_id", models.CharField(max_length=255, unique=True)),
            ("event_type", models.CharField(max_length=100)),
            ("payload_hash", models.CharField(max_length=64)),
            ("processed_at", models.DateTimeField(auto_now_add=True)),
        ],
    )]
