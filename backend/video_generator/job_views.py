import logging
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing import ensure_subscription, get_plan
from .credits import get_or_create_credit_account, refund_job_credits
from .models import VideoJob, VideoProject, VideoScene, WorkspaceMembership
from .pipeline import dispatch_video_job
from .rate_limit import allow_request, rate_limited_response
from .serializers import VideoJobSerializer
from .workspaces import get_workspace_project_for_user, user_has_workspace_role

logger = logging.getLogger(__name__)


class VideoJobCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not allow_request(request, "job-create", limit=15, window=60):
            return rate_limited_response()

        if not request.user.is_active:
            return Response(
                {"detail": "Please verify your email address before generating videos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        project_id = request.data.get("project_id")
        if not project_id:
            return Response({"detail": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = get_workspace_project_for_user(request.user, int(project_id), min_role=WorkspaceMembership.Role.EDITOR)
        except (ValueError, Exception):
            return Response({"detail": "Project not found or permission denied."}, status=status.HTTP_404_NOT_FOUND)

        # Check subscription entitlements
        subscription = ensure_subscription(request.user)
        plan = get_plan(subscription.plan_code)
        if project.duration > plan.max_duration:
            return Response(
                {"detail": f"Your {plan.name} plan supports videos up to {plan.max_duration} seconds. Upgrade to generate longer videos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job_type = request.data.get("job_type", VideoJob.JobType.FULL_GENERATION)
        target_scene = None
        if job_type == VideoJob.JobType.SCENE_REGENERATION:
            scene_id = request.data.get("scene_id")
            if not scene_id:
                return Response({"detail": "scene_id is required for scene_regeneration."}, status=status.HTTP_400_BAD_REQUEST)
            target_scene = get_object_or_404(VideoScene, id=scene_id, project=project)

        # Check for active running job on this project
        active_job = VideoJob.objects.filter(
            project=project,
            status__in=[VideoJob.Status.QUEUED, VideoJob.Status.PROCESSING, VideoJob.Status.ASSEMBLING],
        ).first()
        if active_job:
            return Response(VideoJobSerializer(active_job).data, status=status.HTTP_202_ACCEPTED)

        # Create new persistent VideoJob
        job = VideoJob.objects.create(
            project=project,
            workspace=project.workspace,
            user=request.user,
            job_type=job_type,
            status=VideoJob.Status.QUEUED,
            current_stage="queued",
            total_scenes=project.scenes.count(),
            target_scene=target_scene,
            provider="fal_pixverse_c1",
        )

        project.status = VideoProject.Status.QUEUED
        project.save(update_fields=["status", "updated_at"])

        # Determine async vs sync (for testing or configuration)
        async_exec = request.data.get("async", True)
        if isinstance(async_exec, str):
            async_exec = async_exec.lower() != "false"

        dispatch_video_job(job.id, async_exec=bool(async_exec))
        return Response(VideoJobSerializer(job).data, status=status.HTTP_201_CREATED)


class VideoJobDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        job = get_object_or_404(VideoJob.objects.select_related("project", "workspace"), id=job_id)

        # Workspace ownership check
        if job.workspace:
            if not user_has_workspace_role(request.user, job.workspace, min_role=WorkspaceMembership.Role.VIEWER):
                return Response({"detail": "Not found or permission denied."}, status=status.HTTP_404_NOT_FOUND)
        elif job.user_id != request.user.id and not request.user.is_staff:
            return Response({"detail": "Not found or permission denied."}, status=status.HTTP_404_NOT_FOUND)

        return Response(VideoJobSerializer(job).data)


class VideoJobCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        job = get_object_or_404(VideoJob.objects.select_related("project", "workspace"), id=job_id)

        # Workspace editor / owner permission check
        if job.workspace:
            if not user_has_workspace_role(request.user, job.workspace, min_role=WorkspaceMembership.Role.EDITOR):
                return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        elif job.user_id != request.user.id and not request.user.is_staff:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        if job.status in [VideoJob.Status.COMPLETED, VideoJob.Status.FAILED, VideoJob.Status.CANCELLED]:
            return Response(VideoJobSerializer(job).data, status=status.HTTP_200_OK)

        job.status = VideoJob.Status.CANCELLED
        job.current_stage = "cancelled"
        job.cancelled_at = timezone.now()
        job.save(update_fields=["status", "current_stage", "cancelled_at", "updated_at"])

        project = job.project
        project.status = VideoProject.Status.CANCELLED
        project.error_message = "Generation cancelled by user."
        project.save(update_fields=["status", "error_message", "updated_at"])

        refunded = refund_job_credits(job)
        logger.info("Cancelled VideoJob #%s and refunded %s credits.", job.id, refunded)

        return Response(VideoJobSerializer(job).data, status=status.HTTP_200_OK)
