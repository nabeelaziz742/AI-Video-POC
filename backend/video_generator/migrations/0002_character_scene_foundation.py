from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("video_generator", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Character",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("role", models.CharField(blank=True, max_length=120)),
                ("age_description", models.CharField(blank=True, max_length=120)),
                ("appearance", models.TextField(blank=True)),
                ("clothing", models.TextField(blank=True)),
                ("personality", models.TextField(blank=True)),
                ("description", models.TextField(blank=True)),
                ("visual_prompt", models.TextField(blank=True)),
                ("reference_image_url", models.URLField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="characters", to="video_generator.videoproject")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="VideoScene",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scene_number", models.PositiveIntegerField()),
                ("duration", models.PositiveIntegerField()),
                ("prompt", models.TextField()),
                ("status", models.CharField(choices=[("planned", "Planned"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed")], default="planned", max_length=20)),
                ("provider", models.CharField(default="pending", max_length=50)),
                ("provider_project_id", models.CharField(blank=True, max_length=120, null=True)),
                ("video_url", models.URLField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scenes", to="video_generator.videoproject")),
                ("characters", models.ManyToManyField(blank=True, related_name="scenes", to="video_generator.character")),
            ],
            options={"ordering": ["scene_number"]},
        ),
        migrations.AddConstraint(
            model_name="videoscene",
            constraint=models.UniqueConstraint(fields=("project", "scene_number"), name="unique_project_scene_number"),
        ),
    ]
