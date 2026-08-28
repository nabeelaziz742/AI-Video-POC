from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Character, VideoProject, VideoScene
from .rate_limit import allow_request, rate_limited_response
from .scene_planner import build_scene_plan, validate_generation_options
from .serializers import VideoProjectSerializer


class VideoProjectCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        projects = VideoProject.objects.filter(user=request.user).prefetch_related("characters", "scenes").order_by("-created_at")
        return Response(VideoProjectSerializer(projects, many=True).data)

    def post(self, request):
        if not allow_request(request, "project-create", limit=10, window=60):
            return rate_limited_response()
        title = str(request.data.get("title", "Untitled Video")).strip() or "Untitled Video"
        prompt = str(request.data.get("prompt", "")).strip()
        input_type = request.data.get("input_type", "story")
        aspect_ratio = request.data.get("aspect_ratio", "9:16")
        characters_input = request.data.get("characters", [])
        if not prompt:
            return Response({"detail": "Prompt or script is required."}, status=status.HTTP_400_BAD_REQUEST)
        if input_type not in VideoProject.InputType.values:
            return Response({"detail": "input_type must be story or script."}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(characters_input, list) or not characters_input:
            return Response({"detail": "At least one recurring character is required for AI character video generation."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            duration, aspect_ratio = validate_generation_options(request.data.get("duration", 10), aspect_ratio)
            scene_plan = build_scene_plan(prompt, duration)
            normalized_characters = []
            for item in characters_input:
                if not isinstance(item, dict) or not str(item.get("name", "")).strip():
                    raise ValueError("Each character must have a name.")
                normalized_characters.append(item)
        except (TypeError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            project = VideoProject.objects.create(
                user=request.user, title=title, prompt=prompt, input_type=input_type,
                aspect_ratio=aspect_ratio, duration=duration, status=VideoProject.Status.QUEUED,
                provider="fal_pixverse_c1",
            )
            characters = [Character.objects.create(
                project=project, name=str(item["name"]).strip(), role=str(item.get("role", "")).strip(),
                age_description=str(item.get("age_description", "")).strip(), appearance=str(item.get("appearance", "")).strip(),
                clothing=str(item.get("clothing", "")).strip(), personality=str(item.get("personality", "")).strip(),
                description=str(item.get("description", "")).strip(), visual_prompt=str(item.get("visual_prompt", "")).strip(),
                reference_image_url=item.get("reference_image_url") or None,
            ) for item in normalized_characters]
            character_block = "\nCharacter continuity: " + "; ".join(character.consistency_prompt for character in characters) + ". Keep recurring characters visually identical across scenes."
            scenes = [VideoScene(project=project, scene_number=scene["scene_number"], duration=scene["duration"], prompt=scene["prompt"] + character_block) for scene in scene_plan]
            VideoScene.objects.bulk_create(scenes)
            for scene in project.scenes.all():
                scene.characters.set(characters)
        return Response(VideoProjectSerializer(project).data, status=status.HTTP_201_CREATED)


class VideoProjectStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = VideoProject.objects.filter(id=project_id, user=request.user).prefetch_related("characters", "scenes").first()
        if not project:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        if project.provider_project_id and project.provider == "json2video":
            from .services import JSON2VideoService
            try:
                result = JSON2VideoService().get_movie(project.provider_project_id)
                movie = result.get("movie", {})
                provider_status = movie.get("status")
                if provider_status == "done":
                    video_url = movie.get("url")
                    if not video_url:
                        project.status = VideoProject.Status.FAILED
                        project.error_message = "JSON2Video marked the movie done but returned no video URL."
                    else:
                        project.status = VideoProject.Status.COMPLETED
                        project.video_url = video_url
                        project.error_message = None
                    project.save(update_fields=["status", "video_url", "error_message", "updated_at"])
                elif provider_status in {"error", "timeout"}:
                    project.status = VideoProject.Status.FAILED
                    project.error_message = "Video rendering failed at the assembly provider."
                    project.save(update_fields=["status", "error_message", "updated_at"])
                else:
                    project.status = VideoProject.Status.PROCESSING
                    project.save(update_fields=["status", "updated_at"])
            except Exception:
                project.status = VideoProject.Status.FAILED
                project.error_message = "Unable to read the video assembly provider status."
                project.save(update_fields=["status", "error_message", "updated_at"])
        return Response(VideoProjectSerializer(project).data)
