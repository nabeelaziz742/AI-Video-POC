from rest_framework import serializers

from .models import VideoProject


class VideoProjectSerializer(serializers.ModelSerializer):
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
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "provider_project_id",
            "video_url",
            "error_message",
            "created_at",
            "updated_at",
        ]