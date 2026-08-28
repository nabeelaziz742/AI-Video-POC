from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("video_generator", "0005_project_versioning"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plan_code", models.CharField(choices=[("free", "Free"), ("creator", "Creator"), ("pro", "Pro")], default="free", max_length=30)),
                ("status", models.CharField(choices=[("active", "Active"), ("trialing", "Trialing"), ("past_due", "Past due"), ("cancelled", "Cancelled")], default="active", max_length=30)),
                ("provider", models.CharField(default="manual", max_length=30)),
                ("provider_customer_id", models.CharField(blank=True, max_length=120)),
                ("provider_subscription_id", models.CharField(blank=True, max_length=120)),
                ("current_period_start", models.DateTimeField(blank=True, null=True)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("cancel_at_period_end", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="subscription", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
