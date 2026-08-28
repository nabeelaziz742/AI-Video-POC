from django.conf import settings
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

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="video_projects",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    input_type = models.CharField(max_length=20, choices=InputType.choices, default=InputType.STORY)
    prompt = models.TextField()
    aspect_ratio = models.CharField(max_length=10, default="9:16")
    duration = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    provider = models.CharField(max_length=50, default="json2video")
    provider_project_id = models.CharField(max_length=100, blank=True, null=True)
    video_url = models.URLField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Character(models.Model):
    project = models.ForeignKey(VideoProject, related_name="characters", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=120, blank=True)
    age_description = models.CharField(max_length=120, blank=True)
    appearance = models.TextField(blank=True)
    clothing = models.TextField(blank=True)
    personality = models.TextField(blank=True)
    description = models.TextField(blank=True)
    visual_prompt = models.TextField(blank=True)
    reference_image_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    @property
    def consistency_prompt(self):
        parts = [self.name, self.role, self.age_description, self.appearance, self.clothing, self.personality, self.description, self.visual_prompt]
        return ", ".join(part.strip() for part in parts if part and part.strip())

    def __str__(self):
        return f"{self.name} — {self.project.title}"


class VideoScene(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    project = models.ForeignKey(VideoProject, related_name="scenes", on_delete=models.CASCADE)
    scene_number = models.PositiveIntegerField()
    duration = models.PositiveIntegerField()
    prompt = models.TextField()
    characters = models.ManyToManyField(Character, related_name="scenes", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    provider = models.CharField(max_length=50, default="pending")
    provider_project_id = models.CharField(max_length=120, blank=True, null=True)
    video_url = models.URLField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scene_number"]
        constraints = [models.UniqueConstraint(fields=["project", "scene_number"], name="unique_project_scene_number")]

    def __str__(self):
        return f"{self.project.title} — Scene {self.scene_number}"
