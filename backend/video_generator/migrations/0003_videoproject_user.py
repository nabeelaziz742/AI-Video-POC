from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("video_generator", "0002_character_scene_foundation"),
    ]

    operations = [
        migrations.AddField(
            model_name="videoproject",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="video_projects",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
