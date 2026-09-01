import logging
import time
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .character_generation import CharacterGenerationError, generate_character_reference
from .credits import (
    ASSEMBLY_COST,
    consume_job_credits,
    generation_cost,
    refund_job_credits,
    reserve_job_credits,
)
from .models import Character, UsageEvent, VideoJob, VideoProject, VideoScene
from .providers import VideoProviderError, get_video_provider
from .scene_planner import get_dimensions
from .security import validate_safe_url
from .services import JSON2VideoService

logger = logging.getLogger(__name__)

# Dedicated background executor pool
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="video-worker")


class JobCancelledException(Exception):
    """Raised when a job is cancelled by user during execution."""


def _check_cancellation(job_id: int):
    close_old_connections()
    job = VideoJob.objects.filter(id=job_id).only("status").first()
    if job and job.status == VideoJob.Status.CANCELLED:
        raise JobCancelledException("Job was cancelled by user.")


def run_video_job(job_id: int) -> VideoJob:
    """
    Core resilient execution pipeline for a VideoJob.
    Persists all stages, scene clips, provider IDs, and final output in the database.
    Atomically handles credit reservation, consumption on success, and refund on failure.
    """
    close_old_connections()
    try:
        job = VideoJob.objects.select_related("project", "workspace", "user", "target_scene").get(id=job_id)
    except VideoJob.DoesNotExist:
        logger.error("VideoJob #%s does not exist", job_id)
        return None

    if job.status in {VideoJob.Status.COMPLETED, VideoJob.Status.CANCELLED}:
        return job

    project = job.project

    # 1. Credit Reservation
    try:
        reserve_job_credits(job)
    except ValidationError as exc:
        detail = exc.detail.get("detail", str(exc.detail)) if isinstance(exc.detail, dict) else str(exc.detail)
        job.status = VideoJob.Status.FAILED
        job.current_stage = "failed"
        job.error_message = detail
        job.failed_at = timezone.now()
        job.save(update_fields=["status", "current_stage", "error_message", "failed_at", "updated_at"])

        project.status = VideoProject.Status.FAILED
        project.error_message = detail
        project.failed_at = timezone.now()
        project.save(update_fields=["status", "error_message", "failed_at", "updated_at"])
        return job

    job.status = VideoJob.Status.PROCESSING
    job.started_at = job.started_at or timezone.now()
    job.current_stage = "starting"
    job.progress_percent = 5
    job.save(update_fields=["status", "started_at", "current_stage", "progress_percent", "updated_at"])

    project.status = VideoProject.Status.PROCESSING
    project.processing_started_at = project.processing_started_at or timezone.now()
    project.error_message = None
    project.save(update_fields=["status", "processing_started_at", "error_message", "updated_at"])

    try:
        # Check cancellation
        _check_cancellation(job.id)

        # 2. Scene / Job Routing
        if job.job_type == VideoJob.JobType.SCENE_REGENERATION and job.target_scene:
            _execute_scene_regeneration(job)
        else:
            _execute_full_generation(job)

        # 3. Finalize Job
        job.refresh_from_db()
        if job.status != VideoJob.Status.CANCELLED:
            job.status = VideoJob.Status.COMPLETED
            job.current_stage = "completed"
            job.progress_percent = 100
            job.completed_at = timezone.now()
            job.error_message = None
            job.save(update_fields=["status", "current_stage", "progress_percent", "completed_at", "error_message", "updated_at"])

            project.status = VideoProject.Status.COMPLETED
            project.video_url = job.video_url
            project.completed_at = timezone.now()
            project.error_message = None
            project.save(update_fields=["status", "video_url", "completed_at", "error_message", "updated_at"])

            consume_job_credits(job)
            logger.info("VideoJob #%s completed successfully.", job.id)

    except JobCancelledException:
        logger.info("VideoJob #%s cancelled.", job.id)
        job.status = VideoJob.Status.CANCELLED
        job.current_stage = "cancelled"
        job.cancelled_at = timezone.now()
        job.save(update_fields=["status", "current_stage", "cancelled_at", "updated_at"])

        project.status = VideoProject.Status.CANCELLED
        project.error_message = "Generation cancelled by user."
        project.save(update_fields=["status", "error_message", "updated_at"])

        refund_job_credits(job)

    except Exception as exc:
        logger.exception("VideoJob #%s failed: %s", job.id, exc)
        job.refresh_from_db()
        if job.status != VideoJob.Status.CANCELLED:
            job.status = VideoJob.Status.FAILED
            job.current_stage = "failed"
            job.error_message = str(exc)
            job.failed_at = timezone.now()
            job.save(update_fields=["status", "current_stage", "error_message", "failed_at", "updated_at"])

            project.status = VideoProject.Status.FAILED
            project.error_message = str(exc)
            project.failed_at = timezone.now()
            project.save(update_fields=["status", "error_message", "failed_at", "updated_at"])

            refund_job_credits(job)

    finally:
        close_old_connections()

    return job


def _execute_full_generation(job: VideoJob):
    project = job.project

    # Stage A: Character reference generation
    job.current_stage = "character_reference"
    job.progress_percent = 10
    job.save(update_fields=["current_stage", "progress_percent", "updated_at"])

    characters = list(project.characters.all())
    for character in characters:
        _check_cancellation(job.id)
        if not character.reference_image_url:
            try:
                url = generate_character_reference(character)
                character.reference_image_url = url
                character.save(update_fields=["reference_image_url"])
            except CharacterGenerationError as exc:
                raise VideoProviderError(f"Character reference generation failed: {exc}") from exc

    # Stage B: AI Scene Clip Generation via FAL.ai
    job.current_stage = "generating_scenes"
    job.save(update_fields=["current_stage", "updated_at"])

    scenes = list(project.scenes.order_by("scene_number"))
    job.total_scenes = len(scenes)
    job.save(update_fields=["total_scenes", "updated_at"])

    provider = get_video_provider("fal_pixverse_c1")

    for index, scene in enumerate(scenes):
        _check_cancellation(job.id)

        # Skip already completed scenes if valid video_url exists
        if scene.status == VideoScene.Status.COMPLETED and scene.video_url:
            completed_count = project.scenes.filter(status=VideoScene.Status.COMPLETED).count()
            job.completed_scenes = completed_count
            job.progress_percent = int(10 + 65 * (completed_count / max(1, job.total_scenes)))
            job.save(update_fields=["completed_scenes", "progress_percent", "updated_at"])
            continue

        scene.status = VideoScene.Status.PROCESSING
        scene.processing_started_at = timezone.now()
        scene.generation_attempt += 1
        scene.save(update_fields=["status", "processing_started_at", "generation_attempt"])

        # Character reference images for consistency
        refs = [
            {"image_url": c.reference_image_url, "type": "subject", "ref_name": f"character{i}"}
            for i, c in enumerate(scene.characters.filter(reference_image_url__isnull=False).order_by("id"), start=1)
        ]
        if not refs:
            # If scene has no character refs attached, use project's characters with refs
            refs = [
                {"image_url": c.reference_image_url, "type": "subject", "ref_name": f"character{i}"}
                for i, c in enumerate(project.characters.filter(reference_image_url__isnull=False).order_by("id"), start=1)
            ]

        # Submit to provider
        sub = provider.submit_scene(
            prompt=scene.prompt,
            duration=scene.duration,
            aspect_ratio=project.aspect_ratio,
            references=refs,
        )
        req_id = sub.get("request_id")
        if not req_id:
            raise VideoProviderError("FAL provider did not return a generation request ID.")

        scene.provider = "fal_pixverse_c1"
        scene.provider_project_id = req_id
        scene.save(update_fields=["provider", "provider_project_id"])

        job.provider = "fal_pixverse_c1"
        job.provider_job_id = req_id
        job.metadata.setdefault("scene_jobs", {})[str(scene.id)] = req_id
        job.save(update_fields=["provider", "provider_job_id", "metadata", "updated_at"])

        # Poll FAL until completed
        video_url = _poll_scene_until_complete(provider, req_id, job.id)
        if not video_url or not validate_safe_url(video_url, allow_empty=False):
            raise VideoProviderError(f"Scene {scene.scene_number} completed without a valid video URL.")

        scene.status = VideoScene.Status.COMPLETED
        scene.video_url = video_url
        scene.error_message = None
        scene.completed_at = timezone.now()
        scene.save(update_fields=["status", "video_url", "error_message", "completed_at"])

        completed_count = project.scenes.filter(status=VideoScene.Status.COMPLETED).count()
        job.completed_scenes = completed_count
        job.progress_percent = int(10 + 65 * (completed_count / max(1, job.total_scenes)))
        job.save(update_fields=["completed_scenes", "progress_percent", "updated_at"])

    # Stage C: JSON2Video Multi-Scene Assembly
    _execute_assembly(job)


def _execute_scene_regeneration(job: VideoJob):
    scene = job.target_scene
    project = job.project

    job.current_stage = "generating_scenes"
    job.total_scenes = 1
    job.completed_scenes = 0
    job.progress_percent = 20
    job.save(update_fields=["current_stage", "total_scenes", "completed_scenes", "progress_percent", "updated_at"])

    scene.status = VideoScene.Status.PROCESSING
    scene.processing_started_at = timezone.now()
    scene.generation_attempt += 1
    scene.save(update_fields=["status", "processing_started_at", "generation_attempt"])

    refs = [
        {"image_url": c.reference_image_url, "type": "subject", "ref_name": f"character{i}"}
        for i, c in enumerate(scene.characters.filter(reference_image_url__isnull=False).order_by("id"), start=1)
    ]
    if not refs:
        refs = [
            {"image_url": c.reference_image_url, "type": "subject", "ref_name": f"character{i}"}
            for i, c in enumerate(project.characters.filter(reference_image_url__isnull=False).order_by("id"), start=1)
        ]

    provider = get_video_provider("fal_pixverse_c1")
    sub = provider.submit_scene(
        prompt=scene.prompt,
        duration=scene.duration,
        aspect_ratio=project.aspect_ratio,
        references=refs,
    )
    req_id = sub.get("request_id")
    if not req_id:
        raise VideoProviderError("FAL provider did not return a generation request ID.")

    scene.provider = "fal_pixverse_c1"
    scene.provider_project_id = req_id
    scene.save(update_fields=["provider", "provider_project_id"])

    job.provider_job_id = req_id
    job.metadata.setdefault("scene_jobs", {})[str(scene.id)] = req_id
    job.save(update_fields=["provider_job_id", "metadata", "updated_at"])

    video_url = _poll_scene_until_complete(provider, req_id, job.id)
    if not video_url or not validate_safe_url(video_url, allow_empty=False):
        raise VideoProviderError(f"Scene {scene.scene_number} completed without a valid video URL.")

    scene.status = VideoScene.Status.COMPLETED
    scene.video_url = video_url
    scene.error_message = None
    scene.completed_at = timezone.now()
    scene.save(update_fields=["status", "video_url", "error_message", "completed_at"])

    job.completed_scenes = 1
    job.progress_percent = 75
    job.save(update_fields=["completed_scenes", "progress_percent", "updated_at"])

    # Re-assemble the video with the updated scene clip
    _execute_assembly(job)


def _execute_assembly(job: VideoJob):
    project = job.project
    _check_cancellation(job.id)

    job.status = VideoJob.Status.ASSEMBLING
    job.current_stage = "assembling"
    job.progress_percent = 80
    job.save(update_fields=["status", "current_stage", "progress_percent", "updated_at"])

    scenes = list(project.scenes.order_by("scene_number"))
    if not scenes or any(s.status != VideoScene.Status.COMPLETED or not s.video_url for s in scenes):
        raise VideoProviderError("All scenes must be completed before final assembly.")

    clips = [{"scene_number": s.scene_number, "video_url": s.video_url} for s in scenes]
    width, height = get_dimensions(project.aspect_ratio)

    svc = JSON2VideoService()
    res = svc.create_movie_from_clips(clips=clips, width=width, height=height, project_id=project.id)
    assembly_id = res.get("project")
    if not assembly_id:
        raise VideoProviderError("JSON2Video assembly did not return a movie project ID.")

    job.provider = "json2video"
    job.provider_job_id = assembly_id
    job.metadata["assembly_project_id"] = assembly_id
    job.save(update_fields=["provider", "provider_job_id", "metadata", "updated_at"])

    project.provider = "json2video"
    project.provider_project_id = assembly_id
    project.save(update_fields=["provider", "provider_project_id", "updated_at"])

    final_url = _poll_assembly_until_complete(svc, assembly_id, job.id)
    if not final_url or not validate_safe_url(final_url, allow_empty=False):
        raise VideoProviderError("JSON2Video completed without a valid video URL.")

    job.video_url = final_url
    job.save(update_fields=["video_url", "updated_at"])


def _poll_scene_until_complete(provider, request_id: str, job_id: int, max_seconds: int = 1800) -> str:
    start = time.time()
    while time.time() - start < max_seconds:
        _check_cancellation(job_id)
        result = provider.get_scene_result(request_id)
        p_status = result.get("status")
        if p_status == "completed":
            return result.get("video_url")
        if p_status in {"failed", "error"}:
            raise VideoProviderError(result.get("error") or "Scene generation failed at provider.")
        time.sleep(1.0)
    raise VideoProviderError("Scene generation timed out.")


def _poll_assembly_until_complete(svc: JSON2VideoService, assembly_id: str, job_id: int, max_seconds: int = 1800) -> str:
    start = time.time()
    while time.time() - start < max_seconds:
        _check_cancellation(job_id)
        data = svc.get_movie(assembly_id)
        movie = data.get("movie", {})
        m_status = movie.get("status")
        if m_status == "done":
            return movie.get("url")
        if m_status in {"error", "timeout"}:
            raise VideoProviderError(movie.get("message") or "Video assembly provider failed.")
        time.sleep(1.0)
    raise VideoProviderError("Video assembly timed out.")


def dispatch_video_job(job_id: int, async_exec: bool = True):
    """
    Submits a VideoJob for execution.
    When async_exec=True, runs asynchronously via ThreadPoolExecutor so HTTP returns immediately.
    When async_exec=False, runs synchronously (ideal for testing).
    """
    if async_exec:
        _EXECUTOR.submit(run_video_job, job_id)
    else:
        run_video_job(job_id)
