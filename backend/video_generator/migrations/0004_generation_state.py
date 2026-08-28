from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("video_generator", "0003_videoproject_user")]

    operations = [
        migrations.AddField(model_name="videoproject", name="generation_attempt", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="videoproject", name="processing_started_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="videoproject", name="completed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="videoproject", name="failed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="videoscene", name="generation_attempt", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="videoscene", name="processing_started_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="videoscene", name="completed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="videoscene", name="failed_at", field=models.DateTimeField(blank=True, null=True)),
    ]
