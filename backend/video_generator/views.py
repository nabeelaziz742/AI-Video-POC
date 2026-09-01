from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing import ensure_subscription, get_plan
from .character_extraction import extract_characters_from_story
from .credits import get_or_create_credit_account, refund_transaction
from .models import Character, CreditTransaction, UsageEvent, VideoProject, VideoScene, Workspace, WorkspaceMembership
from .rate_limit import allow_request, rate_limited_response
from .scene_planner import build_scene_plan, validate_generation_options
from .security import validate_safe_url
from .serializers import VideoProjectSerializer
from .services import JSON2VideoService
from .workspaces import (
    get_or_create_personal_workspace,
    get_user_workspaces,
    get_workspace_project_for_user,
    user_has_workspace_role,
)


class VideoProjectCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        workspace_id = request.query_params.get("workspace_id")
        if workspace_id:
            try:
                target_workspace = Workspace.objects.get(id=int(workspace_id))
                if not user_has_workspace_role(request.user, target_workspace, min_role=WorkspaceMembership.Role.VIEWER):
                    return Response([], status=status.HTTP_200_OK)
                projects = VideoProject.objects.filter(workspace=target_workspace).prefetch_related("characters", "scenes").order_by("-created_at")
            except (ValueError, Workspace.DoesNotExist):
                return Response([], status=status.HTTP_200_OK)
        else:
            user_workspaces = get_user_workspaces(request.user)
            # Include projects explicitly assigned to user's workspaces or legacy user projects
            projects = VideoProject.objects.filter(
                Q(workspace__in=user_workspaces) | Q(workspace__isnull=True, user=request.user)
            ).distinct().prefetch_related("characters", "scenes").order_by("-created_at")
        return Response(VideoProjectSerializer(projects, many=True).data)

    def post(self, request):
        if not allow_request(request, "project-create", limit=10, window=60):
            return rate_limited_response()
        if not request.user.is_active:
            return Response({"detail": "Please verify your email address before generating videos."}, status=status.HTTP_403_FORBIDDEN)

        # Resolve target workspace
        workspace_id = request.data.get("workspace_id")
        if workspace_id:
            try:
                target_workspace = Workspace.objects.get(id=int(workspace_id))
            except (ValueError, Workspace.DoesNotExist):
                return Response({"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)
            if not user_has_workspace_role(request.user, target_workspace, min_role=WorkspaceMembership.Role.EDITOR):
                return Response({"detail": "You do not have permission to create projects in this workspace."}, status=status.HTTP_403_FORBIDDEN)
            workspace = target_workspace
        else:
            workspace = get_or_create_personal_workspace(request.user)

        title = str(request.data.get("title", "Untitled Video")).strip() or "Untitled Video"
        prompt = str(request.data.get("prompt", "")).strip()
        input_type = request.data.get("input_type", "story")
        aspect_ratio = request.data.get("aspect_ratio", "9:16")
        characters_input = request.data.get("characters")
        if not prompt:
            return Response({"detail": "Prompt or script is required."}, status=status.HTTP_400_BAD_REQUEST)
        if input_type not in VideoProject.InputType.values:
            return Response({"detail": "input_type must be story or script."}, status=status.HTTP_400_BAD_REQUEST)
        if characters_input is None:
            characters_input = extract_characters_from_story(prompt)
        elif isinstance(characters_input, list) and not characters_input:
            return Response({"detail": "At least one recurring character is required for AI character video generation."}, status=status.HTTP_400_BAD_REQUEST)
        elif not isinstance(characters_input, list):
            return Response({"detail": "Characters must be a list."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            duration, aspect_ratio = validate_generation_options(request.data.get("duration", 10), aspect_ratio)
            subscription = ensure_subscription(request.user)
            plan = get_plan(subscription.plan_code)
            if duration > plan.max_duration:
                return Response({"detail": f"Your {plan.name} plan supports videos up to {plan.max_duration} seconds. Upgrade to generate longer videos."}, status=status.HTTP_400_BAD_REQUEST)
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
                user=request.user,
                workspace=workspace,
                title=title,
                version_number=1,
                prompt=prompt,
                input_type=input_type,
                aspect_ratio=aspect_ratio,
                duration=duration,
                status=VideoProject.Status.QUEUED,
                provider="fal_pixverse_c1",
            )
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
        used = CreditTransaction.objects.filter(account=account, kind=CreditTransaction.Kind.RESERVE).aggregate(total=Sum("amount"))["total"] or 0
        return Response({"balance": account.balance, "monthly_allowance": account.monthly_allowance, "used": used})


class UsageSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        events = UsageEvent.objects.filter(user=request.user)
        return Response({
            "projects": events.filter(kind=UsageEvent.Kind.PROJECT).aggregate(total=Sum("quantity"))["total"] or 0,
            "scenes": events.filter(kind=UsageEvent.Kind.SCENE).aggregate(total=Sum("quantity"))["total"] or 0,
            "character_references": events.filter(kind=UsageEvent.Kind.CHARACTER_REFERENCE).aggregate(total=Sum("quantity"))["total"] or 0,
            "assemblies": events.filter(kind=UsageEvent.Kind.ASSEMBLY).aggregate(total=Sum("quantity"))["total"] or 0,
            "credits_consumed": events.aggregate(total=Sum("credits"))["total"] or 0,
        })


class VideoProjectVersionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        source = get_workspace_project_for_user(request.user, project_id, min_role=WorkspaceMembership.Role.VIEWER)
        versions = VideoProject.objects.filter(workspace=source.workspace, version_group=source.version_group).prefetch_related("characters", "scenes").order_by("version_number")
        return Response(VideoProjectSerializer(versions, many=True).data)

    def post(self, request, project_id):
        if not request.user.is_active:
            return Response({"detail": "Please verify your email address before generating videos."}, status=status.HTTP_403_FORBIDDEN)
        source = get_workspace_project_for_user(request.user, project_id, min_role=WorkspaceMembership.Role.EDITOR)
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
            subscription = ensure_subscription(request.user)
            plan = get_plan(subscription.plan_code)
            if duration > plan.max_duration:
                return Response({"detail": f"Your {plan.name} plan supports videos up to {plan.max_duration} seconds. Upgrade to generate longer videos."}, status=status.HTTP_400_BAD_REQUEST)
            scene_plan = build_scene_plan(prompt, duration)
        except (TypeError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        source_chars = list(source.characters.all())
        if characters_input is None:
            if source_chars:
                characters_input = [{"name": c.name, "role": c.role, "age_description": c.age_description, "appearance": c.appearance, "clothing": c.clothing, "personality": c.personality, "description": c.description, "visual_prompt": c.visual_prompt} for c in source_chars]
            else:
                characters_input = extract_characters_from_story(prompt)
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
            version = VideoProject.objects.create(
                user=request.user,
                workspace=source.workspace,
                version_group=source.version_group,
                version_number=next_number + 1,
                title=title,
                input_type=input_type,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                duration=duration,
                status=VideoProject.Status.QUEUED,
                provider="fal_pixverse_c1",
            )
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
        project = get_workspace_project_for_user(request.user, project_id, min_role=WorkspaceMembership.Role.VIEWER)

        timeout_seconds = getattr(settings, "PROVIDER_JOB_TIMEOUT_SECONDS", 1800)
        if project.status == VideoProject.Status.PROCESSING and project.processing_started_at:
            if (timezone.now() - project.processing_started_at).total_seconds() > timeout_seconds:
                self._fail_and_refund(project, "Video assembly timed out after exceeding the maximum processing window.")
                return Response(VideoProjectSerializer(project).data)

        if not project.provider_project_id or project.provider != "json2video" or (project.status == VideoProject.Status.COMPLETED and project.video_url) or project.status == VideoProject.Status.FAILED:
            return Response(VideoProjectSerializer(project).data)

        try:
            result = JSON2VideoService().get_movie(project.provider_project_id)
            movie = result.get("movie", {})
            provider_status = movie.get("status")
            if provider_status == "done":
                video_url = movie.get("url")
                if not video_url or not validate_safe_url(video_url, allow_empty=False):
                    self._fail_and_refund(project, "JSON2Video marked the movie done but returned no valid video URL.")
                else:
                    project.status = VideoProject.Status.COMPLETED
                    project.video_url = video_url
                    project.error_message = None
                    project.completed_at = timezone.now()
                    project.failed_at = None
                    project.save(update_fields=["status", "video_url", "error_message", "completed_at", "failed_at", "updated_at"])
            elif provider_status in {"error", "timeout"}:
                self._fail_and_refund(project, "Video rendering failed at the assembly provider.")
            else:
                project.status = VideoProject.Status.PROCESSING
                project.save(update_fields=["status", "updated_at"])
        except Exception:
            self._fail_and_refund(project, "Unable to read the video assembly provider status.")
        return Response(VideoProjectSerializer(project).data)

    @staticmethod
    def _fail_and_refund(project, message):
        project.status = VideoProject.Status.FAILED
        project.error_message = message
        project.failed_at = timezone.now()
        project.save(update_fields=["status", "error_message", "failed_at", "updated_at"])
        reservation_key = f"assembly:{project.id}:{project.generation_attempt}"
        refund_transaction(reservation_key=reservation_key, idempotency_key=f"refund:{reservation_key}")

