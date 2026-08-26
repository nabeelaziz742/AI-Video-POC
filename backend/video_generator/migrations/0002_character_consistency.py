from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("video_generator", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="character",
            name="age_description",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="character",
            name="appearance",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="character",
            name="clothing",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="character",
            name="personality",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="videoscene",
            name="characters",
            field=models.ManyToManyField(blank=True, related_name="scenes", to="video_generator.character"),
        ),
    ]
