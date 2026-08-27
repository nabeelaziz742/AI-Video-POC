from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .character_generation import CharacterGenerationError, generate_character_reference
from .models import VideoProject, VideoScene
from .providers import VideoProviderError, get_video_provider
from .scene_planner import get_dimensions
from .serializers import VideoProjectSerializer, VideoSceneSerializer
from .services import JSON2VideoService


class CharacterReferenceView(APIView):
    def post(self, request, project_id, character_id):
        from .models import Character
        character = get_object_or_404(Character, id=character_id, project_id=project_id)
        try:
            url = generate_character_reference(character)
        except CharacterGenerationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"character": character.id, "reference_image_url": url})


class SceneGenerateView(APIView):
    def post(self, request, project_id, scene_id):
        project = get_object_or_404(VideoProject, id=project_id)
        scene = get_object_or_404(VideoScene, id=scene_id, project=project)
        provider_name = request.data.get("provider") or "fal_pixverse_c1"
        references = [
            {"image_url": character.reference_image_url, "type": "subject", "ref_name": f"character{index}"}
            for index, character in enumerate(
                scene.characters.filter(reference_image_url__isnull=False).order_by("id"), start=1
            )
        ]
        if not references:
            return Response({"detail": "Generate character reference images before generating this scene."}, status=status.HTTP_400_BAD_REQUEST)
        if scene.status == VideoScene.Status.PROCESSING and scene.provider_project_id:
            return Response(VideoSceneSerializer(scene).data, status=status.HTTP_202_ACCEPTED)
        try:
            provider = get_video_provider(provider_name)
            job = provider.submit_scene(prompt=scene.prompt, duration=scene.duration, aspect_ratio=project.aspect_ratio, references=references)
        except VideoProviderError as exc:
            scene.status = VideoScene.Status.FAILED
            scene.error_message = str(exc)
            scene.save(update_fields=["status", "error_message"])
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        scene.status = VideoScene.Status.PROCESSING
        scene.provider = provider_name
        scene.provider_project_id = job["request_id"]
        scene.video_url = None
        scene.error_message = None
        scene.save(update_fields=["status", "provider", "provider_project_id", "video_url", "error_message"])
        return Response(VideoSceneSerializer(scene).data, status=status.HTTP_202_ACCEPTED)


class SceneStatusView(APIView):
    def get(self, request, project_id, scene_id):
        project = get_object_or_404(VideoProject, id=project_id)
        scene = get_object_or_404(VideoScene, id=scene_id, project=project)
        if not scene.provider_project_id or scene.provider != "fal_pixverse_c1":
            return Response(VideoSceneSerializer(scene).data)
        try:
            provider = get_video_provider(scene.provider)
            result = provider.get_scene_result(scene.provider_project_id)
        except VideoProviderError as exc:
            scene.status = VideoScene.Status.FAILED
            scene.error_message = str(exc)
            scene.save(update_fields=["status", "error_message"])
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        if result["status"] == "completed":
            video_url = result.get("video_url")
            if not video_url:
                scene.status = VideoScene.Status.FAILED
                scene.error_message = "Provider marked the scene completed but returned no video URL."
                scene.save(update_fields=["status", "error_message"])
                return Response(VideoSceneSerializer(scene).data)
            scene.status = VideoScene.Status.COMPLETED
            scene.video_url = video_url
            scene.error_message = None
            scene.save(update_fields=["status", "video_url", "error_message"])
        elif result["status"] in {"queued", "processing"}:
            scene.status = VideoScene.Status.PROCESSING
            scene.save(update_fields=["status"])
        elif result["status"] in {"failed", "error", "cancelled"}:
            scene.status = VideoScene.Status.FAILED
            scene.error_message = result.get("error") or "AI video generation failed."
            scene.save(update_fields=["status", "error_message"])
        return Response(VideoSceneSerializer(scene).data)


class SceneRegenerateView(SceneGenerateView):
    """Explicitly start a fresh provider job for a scene after failure or revision."""
    def post(self, request, project_id, scene_id):
        scene = get_object_or_404(VideoScene, id=scene_id, project_id=project_id)
        scene.status = VideoScene.Status.PLANNED
        scene.provider_project_id = None
        scene.video_url = None
        scene.error_message = None
        scene.save(update_fields=["status", "provider_project_id", "video_url", "error_message"])
        return super().post(request, project_id, scene_id)


class ProjectAssembleView(APIView):
    def post(self, request, project_id):
        project = get_object_or_404(VideoProject, id=project_id)
        scenes = list(project.scenes.order_by("scene_number"))
        if not scenes or any(scene.status != VideoScene.Status.COMPLETED or not scene.video_url for scene in scenes):
            return Response({"detail": "All scenes must be completed and have a video URL before assembly."}, status=status.HTTP_400_BAD_REQUEST)
        clips = [{"scene_number": scene.scene_number, "video_url": scene.video_url} for scene in scenes]
        width, height = get_dimensions(project.aspect_ratio)
        try:
            result = JSON2VideoService().create_movie_from_clips(clips=clips, width=width, height=height, project_id=project.id)
        except Exception as exc:
            project.status = VideoProject.Status.FAILED
            project.error_message = str(exc)
            project.save(update_fields=["status", "error_message", "updated_at"])
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        project.provider = "json2video"
        project.provider_project_id = result["project"]
        project.status = VideoProject.Status.PROCESSING
        project.error_message = None
        project.save(update_fields=["provider", "provider_project_id", "status", "error_message", "updated_at"])
        return Response(VideoProjectSerializer(project).data, status=status.HTTP_202_ACCEPTED)
