from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .credits import get_or_create_credit_account, reserve_generation
from .models import Character, VideoProject, VideoScene
from .rate_limit import allow_request, rate_limited_response
from .scene_planner import build_scene_plan, validate_generation_options
from .serializers import VideoProjectSerializer
from .services import JSON2VideoService


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
            project = VideoProject.objects.create(user=request.user, title=title, version_number=1, prompt=prompt, input_type=input_type, aspect_ratio=aspect_ratio, duration=duration, status=VideoProject.Status.QUEUED, provider="fal_pixverse_c1")
            try:
                reserve_generation(request.user, project, idempotency_key=f"project:{project.id}:generation:1")
            except Exception as exc:
                return Response(exc.detail if hasattr(exc, "detail") else {"detail": str(exc)}, status=status.HTTP_402_PAYMENT_REQUIRED)
            characters = [Character.objects.create(project=project, name=str(item["name"]).strip(), role=str(item.get("role", "")).strip(), age_description=str(item.get("age_description", "")).strip(), appearance=str(item.get("appearance", "")).strip(), clothing=str(item.get("clothing", "")).strip(), personality=str(item.get("personality", "")).strip(), description=str(item.get("description", "")).strip(), visual_prompt=str(item.get("visual_prompt", "")).strip(), reference_image_url=item.get("reference_image_url") or None) for item in normalized_characters]
            character_block = "\nCharacter continuity: " + "; ".join(character.consistency_prompt for character in characters) + ". Keep recurring characters visually identical across scenes."
            scenes = [VideoScene(project=project, scene_number=scene["scene_number"], duration=scene["duration"], prompt=scene["prompt"] + character_block) for scene in scene_plan]
            VideoScene.objects.bulk_create(scenes)
            for scene in project.scenes.all():
                scene.characters.set(characters)
        return Response(VideoProjectSerializer(project).data, status=status.HTTP_201_CREATED)


class CreditBalanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        account = get_or_create_credit_account(request.user)
        return Response({"balance": account.balance, "monthly_allowance": account.monthly_allowance})


class VideoProjectVersionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get_root_group(self, request, project_id):
        return get_object_or_404(VideoProject, id=project_id, user=request.user).version_group

    def get(self, request, project_id):
        group = self.get_root_group(request, project_id)
        versions = VideoProject.objects.filter(user=request.user, version_group=group).prefetch_related("characters", "scenes").order_by("version_number")
        return Response(VideoProjectSerializer(versions, many=True).data)

    def post(self, request, project_id):
        source = get_object_or_404(VideoProject.objects.prefetch_related("characters"), id=project_id, user=request.user)
        if not allow_request(request, "version-create", limit=10, window=60):
            return rate_limited_response()
        prompt = str(request.data.get("prompt", source.prompt)).strip()
        title = str(request.data.get("title", source.title)).strip() or source.title
        input_type = request.data.get("input_type", source.input_type)
        aspect_ratio = request.data.get("aspect_ratio", source.aspect_ratio)
        duration = request.data.get("duration", source.duration)
        characters_input = request.data.get("characters")
        if not prompt:
            return Response({"detail": "Prompt or script is required."}, status=status.HTTP_400_BAD_REQUEST)
        if input_type not in VideoProject.InputType.values:
            return Response({"detail": "input_type must be story or script."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            duration, aspect_ratio = validate_generation_options(duration, aspect_ratio)
            scene_plan = build_scene_plan(prompt, duration)
        except (TypeError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        source_chars = list(source.characters.all())
        if characters_input is None:
            characters_input = [{"name": c.name, "role": c.role, "age_description": c.age_description, "appearance": c.appearance, "clothing": c.clothing, "personality": c.personality, "description": c.description, "visual_prompt": c.visual_prompt} for c in source_chars]
        if not isinstance(characters_input, list) or not characters_input:
            return Response({"detail": "At least one recurring character is required."}, status=status.HTTP_400_BAD_REQUEST)
        source_by_name = {c.name.strip().lower(): c for c in source_chars}
        normalized = []
        for item in characters_input:
            if not isinstance(item, dict) or not str(item.get("name", "")).strip():
                return Response({"detail": "Each character must have a name."}, status=status.HTTP_400_BAD_REQUEST)
            name = str(item["name"]).strip()
            old = source_by_name.get(name.lower())
            definition = {key: str(item.get(key, "")).strip() for key in ["role", "age_description", "appearance", "clothing", "personality", "description", "visual_prompt"]}
            same_definition = old and all(getattr(old, key) == value for key, value in definition.items())
            normalized.append({"name": name, **definition, "reference_image_url": old.reference_image_url if same_definition else None})
        with transaction.atomic():
            next_number = VideoProject.objects.select_for_update().filter(version_group=source.version_group).order_by("-version_number").values_list("version_number", flat=True).first() or 0
            version = VideoProject.objects.create(user=request.user, version_group=source.version_group, version_number=next_number + 1, title=title, input_type=input_type, prompt=prompt, aspect_ratio=aspect_ratio, duration=duration, status=VideoProject.Status.QUEUED, provider="fal_pixverse_c1")
            try:
                reserve_generation(request.user, version, idempotency_key=f"project:{version.id}:generation:1")
            except Exception as exc:
                return Response(exc.detail if hasattr(exc, "detail") else {"detail": str(exc)}, status=status.HTTP_402_PAYMENT_REQUIRED)
            characters = [Character.objects.create(project=version, **item) for item in normalized]
            character_block = "\nCharacter continuity: " + "; ".join(c.consistency_prompt for c in characters) + ". Keep recurring characters visually identical across scenes."
            scenes = [VideoScene(project=version, scene_number=item["scene_number"], duration=item["duration"], prompt=item["prompt"] + character_block) for item in scene_plan]
            VideoScene.objects.bulk_create(scenes)
            for scene in version.scenes.all():
                scene.characters.set(characters)
        return Response(VideoProjectSerializer(version).data, status=status.HTTP_201_CREATED)


class VideoProjectStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = VideoProject.objects.filter(id=project_id, user=request.user).prefetch_related("characters", "scenes").first()
        if not project:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        if project.provider_project_id and project.provider == "json2video":
            try:
                result = JSON2VideoService().get_movie(project.provider_project_id)
                movie = result.get("movie", {})
                provider_status = movie.get("status")
                if provider_status == "done":
                    video_url = movie.get("url")
                    if not video_url:
                        project.status = VideoProject.Status.FAILED
                        project.error_message = "JSON2Video marked the movie done but returned no video URL."
                        project.failed_at = timezone.now()
                    else:
                        project.status = VideoProject.Status.COMPLETED
                        project.video_url = video_url
                        project.error_message = None
                        project.completed_at = timezone.now()
                        project.failed_at = None
                    project.save(update_fields=["status", "video_url", "error_message", "completed_at", "failed_at", "updated_at"])
                elif provider_status in {"error", "timeout"}:
                    project.status = VideoProject.Status.FAILED
                    project.error_message = "Video rendering failed at the assembly provider."
                    project.failed_at = timezone.now()
                    project.save(update_fields=["status", "error_message", "failed_at", "updated_at"])
                else:
                    project.status = VideoProject.Status.PROCESSING
                    project.save(update_fields=["status", "updated_at"])
            except Exception:
                project.status = VideoProject.Status.FAILED
                project.error_message = "Unable to read the video assembly provider status."
                project.failed_at = timezone.now()
                project.save(update_fields=["status", "error_message", "failed_at", "updated_at"])
        return Response(VideoProjectSerializer(project).data)
