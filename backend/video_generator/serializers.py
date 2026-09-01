from rest_framework import serializers

from .models import Character, VideoJob, VideoProject, VideoScene, Workspace, WorkspaceMembership
from .scene_planner import SUPPORTED_ASPECT_RATIOS, SUPPORTED_DURATIONS


class WorkspaceMembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = WorkspaceMembership
        fields = ["id", "user_id", "username", "email", "role", "created_at", "updated_at"]
        read_only_fields = ["id", "user_id", "username", "email", "created_at", "updated_at"]


class WorkspaceSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    members_count = serializers.SerializerMethodField()
    current_user_role = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = ["id", "name", "owner_id", "owner_username", "is_personal", "members_count", "current_user_role", "created_at", "updated_at"]
        read_only_fields = ["id", "owner_id", "owner_username", "is_personal", "members_count", "current_user_role", "created_at", "updated_at"]

    def get_members_count(self, obj):
        return obj.memberships.count()

    def get_current_user_role(self, obj):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return None
        if obj.owner_id == request.user.id:
            return WorkspaceMembership.Role.OWNER
        membership = obj.memberships.filter(user=request.user).first()
        return membership.role if membership else None


class CharacterSerializer(serializers.ModelSerializer):
    consistency_prompt = serializers.ReadOnlyField()

    class Meta:
        model = Character
        fields = ["id", "name", "role", "age_description", "appearance", "clothing", "personality", "description", "visual_prompt", "reference_image_url", "reference_generation_attempt", "consistency_prompt"]
        read_only_fields = ["id", "reference_generation_attempt", "consistency_prompt"]


class VideoSceneSerializer(serializers.ModelSerializer):
    characters = CharacterSerializer(many=True, read_only=True)

    class Meta:
        model = VideoScene
        fields = ["id", "scene_number", "duration", "prompt", "characters", "status", "provider", "provider_project_id", "video_url", "error_message", "generation_attempt", "processing_started_at", "completed_at", "failed_at"]
        read_only_fields = fields


class VideoJobSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(source="project.id", read_only=True)
    workspace_id = serializers.IntegerField(source="workspace.id", read_only=True, allow_null=True)
    target_scene_id = serializers.IntegerField(source="target_scene.id", read_only=True, allow_null=True)

    class Meta:
        model = VideoJob
        fields = [
            "id",
            "project_id",
            "workspace_id",
            "job_type",
            "status",
            "current_stage",
            "total_scenes",
            "completed_scenes",
            "progress_percent",
            "provider",
            "provider_job_id",
            "video_url",
            "error_message",
            "reservation_key",
            "credits_reserved",
            "credits_consumed",
            "target_scene_id",
            "retry_count",
            "max_retries",
            "metadata",
            "queued_at",
            "started_at",
            "completed_at",
            "failed_at",
            "cancelled_at",
            "updated_at",
        ]
        read_only_fields = fields


class VideoProjectSerializer(serializers.ModelSerializer):
    characters = CharacterSerializer(many=True, read_only=True)
    scenes = VideoSceneSerializer(many=True, read_only=True)
    latest_job = serializers.SerializerMethodField()
    workspace_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = VideoProject
        fields = ["id", "workspace_id", "version_group", "version_number", "title", "input_type", "prompt", "aspect_ratio", "duration", "status", "provider", "provider_project_id", "video_url", "error_message", "generation_attempt", "processing_started_at", "completed_at", "failed_at", "characters", "scenes", "latest_job", "created_at", "updated_at"]
        read_only_fields = ["id", "workspace_id", "version_group", "version_number", "status", "provider", "provider_project_id", "video_url", "error_message", "generation_attempt", "processing_started_at", "completed_at", "failed_at", "characters", "scenes", "latest_job", "created_at", "updated_at"]

    def get_latest_job(self, obj):
        job = obj.jobs.first()
        return VideoJobSerializer(job).data if job else None

    def validate_duration(self, value):
        if value not in SUPPORTED_DURATIONS:
            raise serializers.ValidationError("Duration must be 10, 30, or 60 seconds.")
        return value

    def validate_aspect_ratio(self, value):
        if value not in SUPPORTED_ASPECT_RATIOS:
            raise serializers.ValidationError("Aspect ratio must be 9:16, 16:9, or 1:1.")
        return value


