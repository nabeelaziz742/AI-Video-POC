from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing import ensure_subscription, get_plan
from .character_generation import CharacterGenerationError, generate_character_reference
from .credits import generation_cost, record_usage, reserve_credits, refund_transaction
from .models import Character, VideoProject, VideoScene, UsageEvent, WorkspaceMembership
from .providers import VideoProviderError, get_video_provider
from .rate_limit import allow_request, rate_limited_response
from .scene_planner import get_dimensions
from .security import validate_safe_url
from .serializers import VideoProjectSerializer, VideoSceneSerializer
from .services import JSON2VideoService
from .workspaces import get_workspace_project_for_user

CHARACTER_REFERENCE_COST = 5
ASSEMBLY_COST = 5


def _plan_generation_error(user, duration):
    if not user.is_active:
        return "Please verify your email address before generating videos."
    subscription = ensure_subscription(user)
    if subscription.status not in {subscription.Status.ACTIVE, subscription.Status.TRIALING}:
        return "Your subscription is not active. Please update your plan before generating a video."
    plan = get_plan(subscription.plan_code)
    if duration > plan.max_duration:
        return f"Your {plan.name} plan supports videos up to {plan.max_duration} seconds."
    return None


class OwnedProjectMixin:
    permission_classes = [IsAuthenticated]

    def get_project(self, request, project_id, min_role=WorkspaceMembership.Role.VIEWER):
        return get_workspace_project_for_user(request.user, project_id, min_role=min_role)


class CharacterReferenceView(OwnedProjectMixin, APIView):
    def post(self, request, project_id, character_id):
        if not allow_request(request, "character-reference", limit=10, window=60):
            return rate_limited_response()
        project = self.get_project(request, project_id, min_role=WorkspaceMembership.Role.EDITOR)
        with transaction.atomic():
            character = get_object_or_404(Character.objects.select_for_update(), id=character_id, project=project)
            if character.reference_image_url and not request.data.get("force"):
                return Response({"character": character.id, "reference_image_url": character.reference_image_url, "reused": True})
            attempt = character.reference_generation_attempt + 1
            character.reference_generation_attempt = attempt
            character.save(update_fields=["reference_generation_attempt"])
            charge_key = f"character-reference:{character.id}:{attempt}"
            try:
                reserve_credits(request.user, CHARACTER_REFERENCE_COST, idempotency_key=charge_key, project=project, note="Character reference generation")
            except ValidationError as exc:
                return Response(exc.detail, status=status.HTTP_402_PAYMENT_REQUIRED)
        try:
            url = generate_character_reference(character)
            character.reference_image_url = url
            character.save(update_fields=["reference_image_url"])
        except CharacterGenerationError as exc:
            refund_transaction(reservation_key=charge_key, idempotency_key=f"refund:{charge_key}")
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        record_usage(request.user, kind=UsageEvent.Kind.CHARACTER_REFERENCE, credits=CHARACTER_REFERENCE_COST, idempotency_key=f"usage:{charge_key}", project=project, character=character)
        return Response({"character": character.id, "reference_image_url": url, "reused": False})


class SceneGenerateView(OwnedProjectMixin, APIView):
    def post(self, request, project_id, scene_id):
        if not allow_request(request, "scene-generate", limit=12, window=60):
            return rate_limited_response()
        project = self.get_project(request, project_id, min_role=WorkspaceMembership.Role.EDITOR)
        plan_error = _plan_generation_error(request.user, project.duration)
        if plan_error:
            return Response({"detail": plan_error}, status=status.HTTP_402_PAYMENT_REQUIRED)
        with transaction.atomic():
            scene = get_object_or_404(VideoScene.objects.select_for_update(), id=scene_id, project=project)
            if scene.status == VideoScene.Status.PROCESSING and scene.provider_project_id:
                return Response(VideoSceneSerializer(scene).data, status=status.HTTP_202_ACCEPTED)
            provider_name = request.data.get("provider") or "fal_pixverse_c1"
            references = [{"image_url": character.reference_image_url, "type": "subject", "ref_name": f"character{index}"} for index, character in enumerate(scene.characters.filter(reference_image_url__isnull=False).order_by("id"), start=1)]
            if not references:
                return Response({"detail": "Generate character reference images before generating this scene."}, status=status.HTTP_400_BAD_REQUEST)
            cost = generation_cost(scene.duration)
            attempt = scene.generation_attempt + 1
            scene.generation_attempt = attempt
            scene.save(update_fields=["generation_attempt"])
            charge_key = f"scene-generation:{scene.id}:{attempt}"
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
            refund_transaction(reservation_key=charge_key, idempotency_key=f"refund:{charge_key}")
            scene.status = VideoScene.Status.FAILED
            scene.error_message = str(exc)
            scene.failed_at = timezone.now()
            scene.save(update_fields=["status", "error_message", "failed_at"])
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            refund_transaction(reservation_key=charge_key, idempotency_key=f"refund:{charge_key}")
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
        scene.processing_started_at = timezone.now()
        scene.completed_at = None
        scene.failed_at = None
        scene.save(update_fields=["status", "provider", "provider_project_id", "video_url", "error_message", "processing_started_at", "completed_at", "failed_at"])
        record_usage(request.user, kind=UsageEvent.Kind.SCENE, credits=cost, idempotency_key=f"usage:{charge_key}", project=project, scene=scene)
        return Response(VideoSceneSerializer(scene).data, status=status.HTTP_202_ACCEPTED)


class SceneStatusView(OwnedProjectMixin, APIView):
    def get(self, request, project_id, scene_id):
        project = self.get_project(request, project_id, min_role=WorkspaceMembership.Role.VIEWER)
        scene = get_object_or_404(VideoScene, id=scene_id, project=project)
        if not scene.provider_project_id or scene.provider == "pending" or (scene.status == VideoScene.Status.COMPLETED and scene.video_url) or scene.status == VideoScene.Status.FAILED:
            return Response(VideoSceneSerializer(scene).data)

        timeout_seconds = getattr(settings, "PROVIDER_JOB_TIMEOUT_SECONDS", 1800)
        if scene.status == VideoScene.Status.PROCESSING and scene.processing_started_at:
            if (timezone.now() - scene.processing_started_at).total_seconds() > timeout_seconds:
                self._fail_and_refund(scene, "Scene generation timed out after exceeding the maximum processing window.")
                return Response(VideoSceneSerializer(scene).data)

        try:
            provider = get_video_provider(scene.provider)
            result = provider.get_scene_result(scene.provider_project_id)
        except VideoProviderError as exc:
            self._fail_and_refund(scene, str(exc))
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            self._fail_and_refund(scene, "Unable to read the AI scene generation status.")
            return Response({"detail": scene.error_message}, status=status.HTTP_502_BAD_GATEWAY)
        provider_status = result.get("status")
        if provider_status == "completed":
            video_url = result.get("video_url")
            if not video_url or not validate_safe_url(video_url, allow_empty=False):
                self._fail_and_refund(scene, "Provider marked the scene completed but returned no valid video URL.")
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
            self._fail_and_refund(scene, result.get("error") or "AI video generation failed.")
        return Response(VideoSceneSerializer(scene).data)

    @staticmethod
    def _fail_and_refund(scene, message):
        scene.status = VideoScene.Status.FAILED
        scene.error_message = message
        scene.failed_at = timezone.now()
        scene.save(update_fields=["status", "error_message", "failed_at"])
        reservation_key = f"scene-generation:{scene.id}:{scene.generation_attempt}"
        refund_transaction(reservation_key=reservation_key, idempotency_key=f"refund:{reservation_key}")


class SceneRegenerateView(SceneGenerateView):
    def post(self, request, project_id, scene_id):
        project = self.get_project(request, project_id, min_role=WorkspaceMembership.Role.EDITOR)
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
        project = self.get_project(request, project_id, min_role=WorkspaceMembership.Role.EDITOR)
        with transaction.atomic():
            project = get_object_or_404(VideoProject.objects.select_for_update(), id=project.id)
            if project.provider_project_id and project.provider == "json2video" and project.status == VideoProject.Status.PROCESSING:
                return Response(VideoProjectSerializer(project).data, status=status.HTTP_202_ACCEPTED)
            scenes = list(project.scenes.order_by("scene_number"))
            if not scenes or any(scene.status != VideoScene.Status.COMPLETED or not scene.video_url for scene in scenes):
                return Response({"detail": "All scenes must be completed and have a video URL before assembly."}, status=status.HTTP_400_BAD_REQUEST)
            attempt = project.generation_attempt + 1
            project.generation_attempt = attempt
            project.save(update_fields=["generation_attempt"])
            charge_key = f"assembly:{project.id}:{attempt}"
            try:
                reserve_credits(request.user, ASSEMBLY_COST, idempotency_key=charge_key, project=project, note="Final video assembly")
            except ValidationError as exc:
                return Response(exc.detail, status=status.HTTP_402_PAYMENT_REQUIRED)
        clips = [{"scene_number": scene.scene_number, "video_url": scene.video_url} for scene in scenes]
        width, height = get_dimensions(project.aspect_ratio)
        try:
            result = JSON2VideoService().create_movie_from_clips(clips=clips, width=width, height=height, project_id=project.id)
            provider_project_id = result.get("project")
            if not provider_project_id:
                raise RuntimeError("Assembly provider did not return a project ID.")
        except Exception:
            refund_transaction(reservation_key=charge_key, idempotency_key=f"refund:{charge_key}")
            project.status = VideoProject.Status.FAILED
            project.error_message = "Video assembly provider failed."
            project.failed_at = timezone.now()
            project.save(update_fields=["status", "error_message", "failed_at", "updated_at"])
            return Response({"detail": "Video assembly provider failed."}, status=status.HTTP_502_BAD_GATEWAY)
        project.provider = "json2video"
        project.provider_project_id = provider_project_id
        project.status = VideoProject.Status.PROCESSING
        project.error_message = None
        project.processing_started_at = timezone.now()
        project.completed_at = None
        project.failed_at = None
        project.save(update_fields=["provider", "provider_project_id", "status", "error_message", "processing_started_at", "completed_at", "failed_at", "updated_at"])
        record_usage(request.user, kind=UsageEvent.Kind.ASSEMBLY, credits=ASSEMBLY_COST, idempotency_key=f"usage:{charge_key}", project=project)
        return Response(VideoProjectSerializer(project).data, status=status.HTTP_202_ACCEPTED)

