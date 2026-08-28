from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("video_generator", "0005_credit_ledger"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.CreateModel(
        name="UsageEvent",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("kind", models.CharField(choices=[("project", "Project"), ("scene", "Scene"), ("character_reference", "Character reference"), ("assembly", "Assembly")], max_length=30)),
            ("quantity", models.PositiveIntegerField(default=1)),
            ("credits", models.PositiveIntegerField(default=0)),
            ("idempotency_key", models.CharField(max_length=160, unique=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("character", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="usage_events", to="video_generator.character")),
            ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="usage_events", to="video_generator.videoproject")),
            ("scene", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="usage_events", to="video_generator.videoscene")),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="video_usage_events", to=settings.AUTH_USER_MODEL)),
        ],
    )]
