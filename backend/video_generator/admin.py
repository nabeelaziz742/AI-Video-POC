from django.contrib import admin

from .models import Character, VideoProject, VideoScene


@admin.register(VideoProject)
class VideoProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "status", "duration", "aspect_ratio", "created_at", "updated_at")
    list_filter = ("status", "input_type", "aspect_ratio", "duration")
    search_fields = ("title", "prompt", "user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "reference_image_url", "created_at")
    search_fields = ("name", "project__title", "project__user__username")
    readonly_fields = ("created_at",)


@admin.register(VideoScene)
class VideoSceneAdmin(admin.ModelAdmin):
    list_display = ("project", "scene_number", "status", "duration", "provider", "created_at")
    list_filter = ("status", "provider", "duration")
    search_fields = ("project__title", "prompt")
    readonly_fields = ("created_at",)
