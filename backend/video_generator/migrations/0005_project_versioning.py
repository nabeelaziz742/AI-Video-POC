import uuid

from django.db import migrations, models


def backfill_version_groups(apps, schema_editor):
    VideoProject = apps.get_model("video_generator", "VideoProject")
    for project in VideoProject.objects.all().iterator():
        project.version_group = uuid.uuid4()
        project.version_number = 1
        project.save(update_fields=["version_group", "version_number"])


class Migration(migrations.Migration):
    dependencies = [("video_generator", "0004_generation_state")]

    operations = [
        migrations.AddField(model_name="videoproject", name="version_group", field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False)),
        migrations.AddField(model_name="videoproject", name="version_number", field=models.PositiveIntegerField(default=1)),
        migrations.RunPython(backfill_version_groups, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="videoproject", constraint=models.UniqueConstraint(fields=("version_group", "version_number"), name="unique_project_version")),
    ]
