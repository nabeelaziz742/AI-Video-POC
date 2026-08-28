from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .character_generation import CharacterGenerationError, generate_character_reference
from .credits import generation_cost, record_usage, reserve_credits, refund_transaction
from .models import Character, VideoProject, VideoScene, UsageEvent
from .providers import VideoProviderError, get_video_provider
from .rate_limit import allow_request, rate_limited_response
from .scene_planner import get_dimensions
from .serializers import VideoProjectSerializer, VideoSceneSerializer
from .services import JSON2VideoService


CHARACTER_REFERENCE_COST = 5
ASSEMBLY_COST = 5


class OwnedProjectMixin:
    permission_classes = [IsAuthenticated]

    def get_project(self, request, project_id):
        return get_object_or_404(VideoProject, id=project_id, user=request.user)


class CharacterReferenceView(OwnedProjectMixin, APIView):
    def post(self, request, project_id, character_id):
        if not allow_request(request, "character-reference", limit=10, window=60):
            return rate_limited_response()
        project = self.get_project(request, project_id)
        character = get_object_or_404(Character, id=character_id, project=project)
        if character.reference_image_url and not request.data.get("force"):
            return Response({"character": character.id, "reference_image_url": character.reference_image_url, "reused": True})
        key = f"character-reference:{character.id}:{character.created_at.timestamp()}:{'force' if request.data.get('force') else 'initial'}"
        try:
            reserve_credits(request.user, CHARACTER_REFERENCE_COST, idempotency_key=key, project=project, note="Character reference generation")
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_402_PAYMENT_REQUIRED)
        try:
            url = generate_character_reference(character)
        except CharacterGenerationError as exc:
            refund_transaction(project, idempotency_key=f"refund:{key}")
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        record_usage(request.user, kind=UsageEvent.Kind.CHARACTER_REFERENCE, credits=CHARACTER_REFERENCE_COST, idempotency_key=f"usage:{key}", project=project, character=character)
        return Response({"character": character.id, "reference_image_url": url, "reused": False})


class SceneGenerateView(OwnedProjectMixin, APIView):
    def post(self, request, project_id, scene_id):
        if not allow_request(request, "scene-generate", limit=12, window=60):
            return rate_limited_response()
        project = self.get_project(request, project_id)
        scene = get_object_or_404(VideoScene, id=scene_id, project=project)
        if scene.status == VideoScene.Status.PROCESSING and scene.provider_project_id:
            return Response(VideoSceneSerializer(scene).data, status=status.HTTP_202_ACCEPTED)
        provider_name = request.data.get("provider") or "fal_pixverse_c1"
        references = [{"image_url": character.reference_image_url, "type": "subject", "ref_name": f"character{index}"} for index, character in enumerate(scene.characters.filter(reference_image_url__isnull=False).order_by("id"), start=1)]
        if not references:
            return Response({"detail": "Generate character reference images before generating this scene."}, status=status.HTTP_400_BAD_REQUEST)
        cost = generation_cost(scene.duration)
        charge_key = f"scene-generation:{scene.id}:{scene.generation_attempt + 1}"
        try:
            reserve_credits(request.user, cost, idempotency_key=charge_key, project=project, note="Scene generation")
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_402_PAYMENT_REQUIRED)
        try:
            provider = get_video_provider(provider_name)
            job = provider.submit_scene(prompt=scene.prompt, duration=scene.duration, aspect_ratio=project.aspect_ratio, references=references)
            request_id = job.get("request_id")
            if not request_id:
                raise VideoProviderError("Provider did not return a generation request ID.")
        except VideoProviderError as exc:
            refund_transaction(project, idempotency_key=f"refund:{charge_key}")
            scene.status = VideoScene.Status.FAILED
            scene.error_message = str(exc)
            scene.failed_at = timezone.now()
            scene.save(update_fields=["status", "error_message", "failed_at"])
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            refund_transaction(project, idempotency_key=f"refund:{charge_key}")
            scene.status = VideoScene.Status.FAILED
            scene.error_message = "Unable to submit the AI scene generation job."
            scene.failed_at = timezone.now()
            scene.save(update_fields=["status", "error_message", "failed_at"])
            return Response({"detail": scene.error_message}, status=status.HTTP_502_BAD_GATEWAY)
        scene.status = VideoScene.Status.PROCESSING
        scene.provider = provider_name
        scene.provider_project_id = request_id
        scene.video_url = None
        scene.error_message = None
        scene.generation_attempt += 1
        scene.processing_started_at = timezone.now()
        scene.completed_at = None
        scene.failed_at = None
        scene.save(update_fields=["status", "provider", "provider_project_id", "video_url", "error_message", "generation_attempt", "processing_started_at", "completed_at", "failed_at"])
        record_usage(request.user, kind=UsageEvent.Kind.SCENE, credits=cost, idempotency_key=f"usage:{charge_key}", project=project, scene=scene)
        return Response(VideoSceneSerializer(scene).data, status=status.HTTP_202_ACCEPTED)


class SceneStatusView(OwnedProjectMixin, APIView):
    def get(self, request, project_id, scene_id):
        project = self.get_project(request, project_id)
        scene = get_object_or_404(VideoScene, id=scene_id, project=project)
        if not scene.provider_project_id or scene.provider == "pending" or (scene.status == VideoScene.Status.COMPLETED and scene.video_url):
            return Response(VideoSceneSerializer(scene).data)
        try:
            provider = get_video_provider(scene.provider)
            result = provider.get_scene_result(scene.provider_project_id)
        except VideoProviderError as exc:
            scene.status = VideoScene.Status.FAILED
            scene.error_message = str(exc)
            scene.failed_at = timezone.now()
            scene.save(update_fields=["status", "error_message", "failed_at"])
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            scene.status = VideoScene.Status.FAILED
            scene.error_message = "Unable to read the AI scene generation status."
            scene.failed_at = timezone.now()
            scene.save(update_fields=["status", "error_message", "failed_at"])
            return Response({"detail": scene.error_message}, status=status.HTTP_502_BAD_GATEWAY)
        provider_status = result.get("status")
        if provider_status == "completed":
            video_url = result.get("video_url")
            if not video_url:
                scene.status = VideoScene.Status.FAILED
                scene.error_message = "Provider marked the scene completed but returned no video URL."
                scene.failed_at = timezone.now()
            else:
                scene.status = VideoScene.Status.COMPLETED
                scene.video_url = video_url
                scene.error_message = None
                scene.completed_at = timezone.now()
                scene.failed_at = None
            scene.save(update_fields=["status", "video_url", "error_message", "completed_at", "failed_at"])
        elif provider_status in {"queued", "processing"}:
            scene.status = VideoScene.Status.PROCESSING
            scene.save(update_fields=["status"])
        elif provider_status in {"failed", "error", "cancelled"}:
            scene.status = VideoScene.Status.FAILED
            scene.error_message = result.get("error") or "AI video generation failed."
            scene.failed_at = timezone.now()
            scene.save(update_fields=["status", "error_message", "failed_at"])
        return Response(VideoSceneSerializer(scene).data)


class SceneRegenerateView(SceneGenerateView):
    def post(self, request, project_id, scene_id):
        project = self.get_project(request, project_id)
        scene = get_object_or_404(VideoScene, id=scene_id, project=project)
        if scene.status == VideoScene.Status.PROCESSING and scene.provider_project_id:
            return Response(VideoSceneSerializer(scene).data, status=status.HTTP_202_ACCEPTED)
        scene.status = VideoScene.Status.PLANNED
        scene.provider_project_id = None
        scene.video_url = None
        scene.error_message = None
        scene.processing_started_at = None
        scene.completed_at = None
        scene.failed_at = None
        scene.save(update_fields=["status", "provider_project_id", "video_url", "error_message", "processing_started_at", "completed_at", "failed_at"])
        return super().post(request, project_id, scene_id)


class ProjectAssembleView(OwnedProjectMixin, APIView):
    def post(self, request, project_id):
        if not allow_request(request, "assemble", limit=6, window=60):
            return rate_limited_response()
        project = self.get_project(request, project_id)
        if project.provider_project_id and project.provider == "json2video" and project.status == VideoProject.Status.PROCESSING:
            return Response(VideoProjectSerializer(project).data, status=status.HTTP_202_ACCEPTED)
        scenes = list(project.scenes.order_by("scene_number"))
        if not scenes or any(scene.status != VideoScene.Status.COMPLETED or not scene.video_url for scene in scenes):
            return Response({"detail": "All scenes must be completed and have a video URL before assembly."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            reserve_credits(request.user, ASSEMBLY_COST, idempotency_key=f"assembly:{project.id}:{project.generation_attempt + 1}", project=project, note="Final video assembly")
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_402_PAYMENT_REQUIRED)
        clips = [{"scene_number": scene.scene_number, "video_url": scene.video_url} for scene in scenes]
        width, height = get_dimensions(project.aspect_ratio)
        charge_key = f"assembly:{project.id}:{project.generation_attempt + 1}"
        try:
            result = JSON2VideoService().create_movie_from_clips(clips=clips, width=width, height=height, project_id=project.id)
            provider_project_id = result.get("project")
            if not provider_project_id:
                raise RuntimeError("Assembly provider did not return a project ID.")
        except Exception:
            refund_transaction(project, idempotency_key=f"refund:{charge_key}")
            project.status = VideoProject.Status.FAILED
            project.error_message = "Video assembly provider failed."
            project.failed_at = timezone.now()
            project.save(update_fields=["status", "error_message", "failed_at", "updated_at"])
            return Response({"detail": "Video assembly provider failed."}, status=status.HTTP_502_BAD_GATEWAY)
        project.provider = "json2video"
        project.provider_project_id = provider_project_id
        project.status = VideoProject.Status.PROCESSING
        project.error_message = None
        project.generation_attempt += 1
        project.processing_started_at = timezone.now()
        project.completed_at = None
        project.failed_at = None
        project.save(update_fields=["provider", "provider_project_id", "status", "error_message", "generation_attempt", "processing_started_at", "completed_at", "failed_at", "updated_at"])
        record_usage(request.user, kind=UsageEvent.Kind.ASSEMBLY, credits=ASSEMBLY_COST, idempotency_key=f"usage:{charge_key}", project=project)
        return Response(VideoProjectSerializer(project).data, status=status.HTTP_202_ACCEPTED)
