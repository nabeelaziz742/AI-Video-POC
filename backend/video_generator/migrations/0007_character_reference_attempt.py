from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("video_generator", "0006_usage_events")]

    operations = [migrations.AddField(
        model_name="character",
        name="reference_generation_attempt",
        field=models.PositiveIntegerField(default=0),
    )]
