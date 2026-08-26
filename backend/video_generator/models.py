from django.db import models


class VideoProject(models.Model):
    class InputType(models.TextChoices):
        STORY = "story", "Story"
        SCRIPT = "script", "Script"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    title = models.CharField(max_length=255)

    input_type = models.CharField(
        max_length=20,
        choices=InputType.choices,
        default=InputType.STORY,
    )

    prompt = models.TextField()

    aspect_ratio = models.CharField(
        max_length=10,
        default="9:16",
    )

    duration = models.PositiveIntegerField(
        default=30,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    provider = models.CharField(
        max_length=50,
        default="json2video",
    )

    provider_project_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    video_url = models.URLField(
        blank=True,
        null=True,
    )

    error_message = models.TextField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title