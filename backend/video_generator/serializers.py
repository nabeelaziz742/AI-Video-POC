from rest_framework import serializers

from .models import Character, VideoProject, VideoScene
from .scene_planner import SUPPORTED_ASPECT_RATIOS, SUPPORTED_DURATIONS


class CharacterSerializer(serializers.ModelSerializer):
    consistency_prompt = serializers.ReadOnlyField()

    class Meta:
        model = Character
        fields = [
            "id",
            "name",
            "role",
            "age_description",
            "appearance",
            "clothing",
            "personality",
            "description",
            "visual_prompt",
            "reference_image_url",
            "consistency_prompt",
        ]
        read_only_fields = ["id", "consistency_prompt"]


class VideoSceneSerializer(serializers.ModelSerializer):
    characters = CharacterSerializer(many=True, read_only=True)

    class Meta:
        model = VideoScene
        fields = [
            "id",
            "scene_number",
            "duration",
            "prompt",
            "characters",
            "status",
            "provider",
            "provider_project_id",
            "video_url",
            "error_message",
        ]
        read_only_fields = fields


class VideoProjectSerializer(serializers.ModelSerializer):
    characters = CharacterSerializer(many=True, read_only=True)
    scenes = VideoSceneSerializer(many=True, read_only=True)

    class Meta:
        model = VideoProject
        fields = [
            "id",
            "title",
            "input_type",
            "prompt",
            "aspect_ratio",
            "duration",
            "status",
            "provider",
            "provider_project_id",
            "video_url",
            "error_message",
            "characters",
            "scenes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "provider",
            "provider_project_id",
            "video_url",
            "error_message",
            "characters",
            "scenes",
            "created_at",
            "updated_at",
        ]

    def validate_duration(self, value):
        if value not in SUPPORTED_DURATIONS:
            raise serializers.ValidationError("Duration must be 10, 30, or 60 seconds.")
        return value

    def validate_aspect_ratio(self, value):
        if value not in SUPPORTED_ASPECT_RATIOS:
            raise serializers.ValidationError("Aspect ratio must be 9:16, 16:9, or 1:1.")
        return value
