import uuid

from django.conf import settings
from django.db import models


class Workspace(models.Model):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="owned_workspaces",
        on_delete=models.CASCADE,
    )
    is_personal = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.owner.username})"


class WorkspaceMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        EDITOR = "editor", "Editor"
        VIEWER = "viewer", "Viewer"

    workspace = models.ForeignKey(
        Workspace,
        related_name="memberships",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="workspace_memberships",
        on_delete=models.CASCADE,
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VIEWER,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user"],
                name="unique_workspace_membership",
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role} @ {self.workspace.name}"


class VideoProject(models.Model):
    class InputType(models.TextChoices):
        STORY = "story", "Story"
        SCRIPT = "script", "Script"
    class Status(models.TextChoices):
        DRAFT="draft","Draft"; QUEUED="queued","Queued"; PROCESSING="processing","Processing"; COMPLETED="completed","Completed"; FAILED="failed","Failed"; CANCELLED="cancelled","Cancelled"
    user=models.ForeignKey(settings.AUTH_USER_MODEL,related_name="video_projects",on_delete=models.CASCADE,null=True,blank=True)
    workspace=models.ForeignKey(Workspace,related_name="projects",on_delete=models.CASCADE,null=True,blank=True,db_index=True)
    version_group=models.UUIDField(default=uuid.uuid4,editable=False,db_index=True)
    version_number=models.PositiveIntegerField(default=1)
    title=models.CharField(max_length=255)
    input_type=models.CharField(max_length=20,choices=InputType.choices,default=InputType.STORY)
    prompt=models.TextField()
    aspect_ratio=models.CharField(max_length=10,default="9:16")
    duration=models.PositiveIntegerField(default=30)
    status=models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT,db_index=True)
    provider=models.CharField(max_length=50,default="json2video")
    provider_project_id=models.CharField(max_length=100,blank=True,null=True)
    video_url=models.URLField(blank=True,null=True)
    error_message=models.TextField(blank=True,null=True)
    generation_attempt=models.PositiveIntegerField(default=0)
    processing_started_at=models.DateTimeField(blank=True,null=True)
    completed_at=models.DateTimeField(blank=True,null=True)
    failed_at=models.DateTimeField(blank=True,null=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=["-created_at"]; constraints=[models.UniqueConstraint(fields=["version_group","version_number"],name="unique_project_version")]
    def __str__(self): return f"{self.title} — V{self.version_number}"

class Character(models.Model):
    project=models.ForeignKey(VideoProject,related_name="characters",on_delete=models.CASCADE); name=models.CharField(max_length=120); role=models.CharField(max_length=120,blank=True); age_description=models.CharField(max_length=120,blank=True); appearance=models.TextField(blank=True); clothing=models.TextField(blank=True); personality=models.TextField(blank=True); description=models.TextField(blank=True); visual_prompt=models.TextField(blank=True); reference_image_url=models.URLField(blank=True,null=True); reference_generation_attempt=models.PositiveIntegerField(default=0); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["id"]
    @property
    def consistency_prompt(self): return ", ".join(p.strip() for p in [self.name,self.role,self.age_description,self.appearance,self.clothing,self.personality,self.description,self.visual_prompt] if p and p.strip())
    def __str__(self): return f"{self.name} — {self.project.title}"

class VideoScene(models.Model):
    class Status(models.TextChoices): PLANNED="planned","Planned"; PROCESSING="processing","Processing"; COMPLETED="completed","Completed"; FAILED="failed","Failed"; CANCELLED="cancelled","Cancelled"
    project=models.ForeignKey(VideoProject,related_name="scenes",on_delete=models.CASCADE); scene_number=models.PositiveIntegerField(); duration=models.PositiveIntegerField(); prompt=models.TextField(); characters=models.ManyToManyField(Character,related_name="scenes",blank=True); status=models.CharField(max_length=20,choices=Status.choices,default=Status.PLANNED,db_index=True); provider=models.CharField(max_length=50,default="pending"); provider_project_id=models.CharField(max_length=120,blank=True,null=True,db_index=True); video_url=models.URLField(blank=True,null=True); error_message=models.TextField(blank=True,null=True); generation_attempt=models.PositiveIntegerField(default=0); processing_started_at=models.DateTimeField(blank=True,null=True); completed_at=models.DateTimeField(blank=True,null=True); failed_at=models.DateTimeField(blank=True,null=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["scene_number"]; constraints=[models.UniqueConstraint(fields=["project","scene_number"],name="unique_project_scene_number")]
    def __str__(self): return f"{self.project.title} — Scene {self.scene_number}"

class CreditAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="credit_account", on_delete=models.CASCADE, null=True, blank=True)
    workspace = models.OneToOneField("Workspace", related_name="credit_pool", on_delete=models.CASCADE, null=True, blank=True)
    balance = models.PositiveIntegerField(default=0)
    monthly_allowance = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        owner_str = self.workspace.name if self.workspace else str(self.user)
        return f"{owner_str} — {self.balance} credits"

class CreditTransaction(models.Model):
    class Kind(models.TextChoices): GRANT="grant","Grant"; RESERVE="reserve","Reserve"; RELEASE="release","Release"; CONSUME="consume","Consume"; REFUND="refund","Refund"; ADJUSTMENT="adjustment","Adjustment"
    account=models.ForeignKey(CreditAccount,related_name="transactions",on_delete=models.CASCADE); kind=models.CharField(max_length=20,choices=Kind.choices,db_index=True); amount=models.PositiveIntegerField(); project=models.ForeignKey(VideoProject,related_name="credit_transactions",on_delete=models.SET_NULL,null=True,blank=True); idempotency_key=models.CharField(max_length=120,unique=True); note=models.CharField(max_length=255,blank=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["-created_at"]
    def __str__(self): return f"{self.kind}: {self.amount}"

class UsageEvent(models.Model):
    class Kind(models.TextChoices): PROJECT="project","Project"; SCENE="scene","Scene"; CHARACTER_REFERENCE="character_reference","Character reference"; ASSEMBLY="assembly","Assembly"
    user=models.ForeignKey(settings.AUTH_USER_MODEL,related_name="video_usage_events",on_delete=models.CASCADE); kind=models.CharField(max_length=30,choices=Kind.choices,db_index=True); quantity=models.PositiveIntegerField(default=1); credits=models.PositiveIntegerField(default=0); project=models.ForeignKey(VideoProject,related_name="usage_events",on_delete=models.SET_NULL,null=True,blank=True); scene=models.ForeignKey(VideoScene,related_name="usage_events",on_delete=models.SET_NULL,null=True,blank=True); character=models.ForeignKey(Character,related_name="usage_events",on_delete=models.SET_NULL,null=True,blank=True); idempotency_key=models.CharField(max_length=160,unique=True); created_at=models.DateTimeField(auto_now_add=True)

class Subscription(models.Model):
    class Plan(models.TextChoices):
        FREE = "free", "Free"
        CREATOR = "creator", "Creator"
        PRO = "pro", "Pro"
        STUDIO = "studio", "Studio"
        ENTERPRISE = "enterprise", "Enterprise"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TRIALING = "trialing", "Trialing"
        PAST_DUE = "past_due", "Past due"
        CANCELLED = "cancelled", "Cancelled"

    user=models.OneToOneField(settings.AUTH_USER_MODEL,related_name="subscription",on_delete=models.CASCADE); plan_code=models.CharField(max_length=30,choices=Plan.choices,default="free"); status=models.CharField(max_length=30,choices=Status.choices,default="active"); provider=models.CharField(max_length=30,default="manual"); provider_customer_id=models.CharField(max_length=120,blank=True); provider_subscription_id=models.CharField(max_length=120,blank=True,db_index=True); current_period_start=models.DateTimeField(blank=True,null=True); current_period_end=models.DateTimeField(blank=True,null=True); cancel_at_period_end=models.BooleanField(default=False); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    def __str__(self): return f"{self.user} — {self.plan_code}"

class BillingEvent(models.Model):
    provider=models.CharField(max_length=30,default="stripe"); event_id=models.CharField(max_length=255,unique=True); event_type=models.CharField(max_length=100); payload_hash=models.CharField(max_length=64); processed_at=models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.provider}:{self.event_type}:{self.event_id}"

class EmailVerificationToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="verification_tokens", on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.token}"

    @property
    def is_valid(self):
        from django.utils import timezone
        return self.used_at is None and timezone.now() < self.expires_at


class VideoJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        ASSEMBLING = "assembling", "Assembling"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class JobType(models.TextChoices):
        FULL_GENERATION = "full_generation", "Full Generation"
        SCENE_REGENERATION = "scene_regeneration", "Scene Regeneration"
        ASSEMBLY = "assembly", "Assembly"

    project = models.ForeignKey(VideoProject, related_name="jobs", on_delete=models.CASCADE, db_index=True)
    workspace = models.ForeignKey(Workspace, related_name="video_jobs", on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="video_jobs", on_delete=models.CASCADE, db_index=True)
    job_type = models.CharField(max_length=30, choices=JobType.choices, default=JobType.FULL_GENERATION, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    current_stage = models.CharField(max_length=50, default="queued")

    total_scenes = models.PositiveIntegerField(default=0)
    completed_scenes = models.PositiveIntegerField(default=0)
    progress_percent = models.PositiveIntegerField(default=0)

    provider = models.CharField(max_length=50, default="fal_pixverse_c1")
    provider_job_id = models.CharField(max_length=120, blank=True, null=True, db_index=True)
    video_url = models.URLField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    reservation_key = models.CharField(max_length=160, blank=True, null=True, db_index=True)
    credits_reserved = models.PositiveIntegerField(default=0)
    credits_consumed = models.PositiveIntegerField(default=0)

    target_scene = models.ForeignKey(VideoScene, related_name="regeneration_jobs", on_delete=models.SET_NULL, null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=2)

    metadata = models.JSONField(default=dict, blank=True)

    queued_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-queued_at"]

    def __str__(self):
        return f"Job #{self.id} ({self.job_type}) - {self.status} [{self.project.title}]"

