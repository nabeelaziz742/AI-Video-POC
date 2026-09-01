import os
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from .credits import (
    ASSEMBLY_COST,
    get_or_create_credit_account,
    grant_free_allowance,
    reserve_job_credits,
)
from .job_views import VideoJobCancelView, VideoJobCreateView, VideoJobDetailView
from .models import (
    Character,
    CreditTransaction,
    UsageEvent,
    VideoJob,
    VideoProject,
    VideoScene,
    Workspace,
    WorkspaceMembership,
)
from .pipeline import run_video_job
from .providers import VideoProviderError, get_video_provider
from .scene_planner import build_scene_plan, validate_generation_options

User = get_user_model()


class FakeFalProvider:
    name = "fal_pixverse_c1"

    def submit_scene(self, **kwargs):
        return {"request_id": "fal-req-123", "provider": self.name}

    def get_scene_result(self, request_id):
        return {
            "status": "completed",
            "video_url": "https://cdn.fal.media/scene_output.mp4",
        }


class FailingFalSubmitProvider:
    name = "fal_pixverse_c1"

    def submit_scene(self, **kwargs):
        raise VideoProviderError("FAL cluster capacity exceeded.")

    def get_scene_result(self, request_id):
        return {"status": "failed", "error": "Provider error"}


class FakeJSON2VideoService:
    def create_movie_from_clips(self, *, clips, width, height, project_id):
        return {"success": True, "project": "j2v-proj-789"}

    def get_movie(self, project_id):
        return {
            "success": True,
            "movie": {
                "status": "done",
                "url": "https://assets.json2video.com/final_movie.mp4",
            },
        }


class FailingJSON2VideoService:
    def create_movie_from_clips(self, **kwargs):
        raise RuntimeError("JSON2Video render error.")

    def get_movie(self, project_id):
        return {
            "movie": {
                "status": "error",
                "message": "Assembly timed out.",
            }
        }


class AsyncVideoJobTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="alice", email="alice@test.com", password="PassWord123!")
        grant_free_allowance(self.user)
        # Give enough credits for tests
        acc = get_or_create_credit_account(self.user)
        acc.balance = 200
        acc.save(update_fields=["balance"])

        self.workspace = Workspace.objects.create(name="Alice Team", owner=self.user, is_personal=False)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role=WorkspaceMembership.Role.OWNER)

        self.other_user = User.objects.create_user(username="bob", email="bob@test.com", password="PassWord123!")
        grant_free_allowance(self.other_user)

        self.project = VideoProject.objects.create(
            user=self.user,
            workspace=self.workspace,
            title="The Desert Traveler",
            prompt="A traveler embarks on a journey across sand dunes.",
            duration=10,
            aspect_ratio="9:16",
            status=VideoProject.Status.QUEUED,
        )
        self.character = Character.objects.create(
            project=self.project,
            name="Traveler",
            reference_image_url="https://example.com/traveler.png",
        )
        plan = build_scene_plan(self.project.prompt, 10)
        self.scenes = [
            VideoScene.objects.create(
                project=self.project,
                scene_number=item["scene_number"],
                duration=item["duration"],
                prompt=item["prompt"],
            )
            for item in plan
        ]
        for s in self.scenes:
            s.characters.add(self.character)

    # 1. Scene Duration Planning Tests (10s, 30s, 60s)
    def test_exact_scene_duration_planning_10s(self):
        plan = build_scene_plan("Story 10", 10)
        total_duration = sum(s["duration"] for s in plan)
        self.assertEqual(total_duration, 10)
        self.assertTrue(all(1 <= s["duration"] <= 15 for s in plan))

    def test_exact_scene_duration_planning_30s(self):
        plan = build_scene_plan("Story 30", 30)
        total_duration = sum(s["duration"] for s in plan)
        self.assertEqual(total_duration, 30)
        self.assertTrue(all(1 <= s["duration"] <= 15 for s in plan))

    def test_exact_scene_duration_planning_60s(self):
        plan = build_scene_plan("Story 60", 60)
        total_duration = sum(s["duration"] for s in plan)
        self.assertEqual(total_duration, 60)
        self.assertTrue(all(1 <= s["duration"] <= 15 for s in plan))

    # 2. Job Creation API & Workspace Security
    def test_create_job_endpoint_returns_201(self):
        request = self.factory.post(
            "/jobs/",
            {"project_id": self.project.id, "job_type": "full_generation", "async": False},
            format="json",
        )
        request.user = self.user
        response = VideoJobCreateView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["project_id"], self.project.id)
        self.assertEqual(response.data["status"], VideoJob.Status.QUEUED)

    def test_create_job_forbidden_for_other_user_without_workspace_membership(self):
        request = self.factory.post(
            "/jobs/",
            {"project_id": self.project.id, "job_type": "full_generation", "async": False},
            format="json",
        )
        request.user = self.other_user
        response = VideoJobCreateView.as_view()(request)
        self.assertEqual(response.status_code, 404)

    def test_get_job_detail_workspace_isolation(self):
        job = VideoJob.objects.create(
            project=self.project,
            workspace=self.workspace,
            user=self.user,
            status=VideoJob.Status.PROCESSING,
        )
        # Alice can view
        req_alice = self.factory.get(f"/jobs/{job.id}/")
        req_alice.user = self.user
        resp_alice = VideoJobDetailView.as_view()(req_alice, job_id=job.id)
        self.assertEqual(resp_alice.status_code, 200)

        # Bob cannot view
        req_bob = self.factory.get(f"/jobs/{job.id}/")
        req_bob.user = self.other_user
        resp_bob = VideoJobDetailView.as_view()(req_bob, job_id=job.id)
        self.assertEqual(resp_bob.status_code, 404)

    # 3. Full End-to-End Pipeline Execution with Mocks
    @patch("video_generator.pipeline.JSON2VideoService", return_value=FakeJSON2VideoService())
    @patch("video_generator.pipeline.get_video_provider", return_value=FakeFalProvider())
    def test_full_pipeline_success_end_to_end(self, mock_fal, mock_j2v):
        initial_balance = get_or_create_credit_account(self.user).balance
        job = VideoJob.objects.create(
            project=self.project,
            workspace=self.workspace,
            user=self.user,
            job_type=VideoJob.JobType.FULL_GENERATION,
            status=VideoJob.Status.QUEUED,
        )

        completed_job = run_video_job(job.id)
        self.assertIsNotNone(completed_job)
        self.assertEqual(completed_job.status, VideoJob.Status.COMPLETED)
        self.assertEqual(completed_job.current_stage, "completed")
        self.assertEqual(completed_job.progress_percent, 100)
        self.assertEqual(completed_job.video_url, "https://assets.json2video.com/final_movie.mp4")

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, VideoProject.Status.COMPLETED)
        self.assertEqual(self.project.video_url, "https://assets.json2video.com/final_movie.mp4")

        # Verify credit reservation and consumption
        expected_cost = self.project.duration  # 10
        final_balance = get_or_create_credit_account(self.user).balance
        self.assertEqual(final_balance, initial_balance - expected_cost)
        self.assertTrue(UsageEvent.objects.filter(project=self.project, kind=UsageEvent.Kind.PROJECT).exists())

    # 4. FAL Provider Failure triggers Refund
    @patch("video_generator.pipeline.get_video_provider", return_value=FailingFalSubmitProvider())
    def test_fal_provider_failure_marks_job_failed_and_refunds(self, mock_fal):
        initial_balance = get_or_create_credit_account(self.user).balance
        job = VideoJob.objects.create(
            project=self.project,
            workspace=self.workspace,
            user=self.user,
            job_type=VideoJob.JobType.FULL_GENERATION,
            status=VideoJob.Status.QUEUED,
        )

        failed_job = run_video_job(job.id)
        self.assertEqual(failed_job.status, VideoJob.Status.FAILED)
        self.assertIn("FAL cluster capacity exceeded", failed_job.error_message)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, VideoProject.Status.FAILED)

        # Credits must be refunded back to original balance
        final_balance = get_or_create_credit_account(self.user).balance
        self.assertEqual(final_balance, initial_balance)
        self.assertTrue(CreditTransaction.objects.filter(kind=CreditTransaction.Kind.REFUND).exists())

    # 5. JSON2Video Assembly Failure triggers Refund
    @patch("video_generator.pipeline.JSON2VideoService", return_value=FailingJSON2VideoService())
    @patch("video_generator.pipeline.get_video_provider", return_value=FakeFalProvider())
    def test_assembly_failure_marks_job_failed_and_refunds(self, mock_fal, mock_j2v):
        initial_balance = get_or_create_credit_account(self.user).balance
        job = VideoJob.objects.create(
            project=self.project,
            workspace=self.workspace,
            user=self.user,
            job_type=VideoJob.JobType.FULL_GENERATION,
            status=VideoJob.Status.QUEUED,
        )

        failed_job = run_video_job(job.id)
        self.assertEqual(failed_job.status, VideoJob.Status.FAILED)
        self.assertIn("JSON2Video render error", failed_job.error_message)

        # Credits refunded
        final_balance = get_or_create_credit_account(self.user).balance
        self.assertEqual(final_balance, initial_balance)
        self.assertTrue(CreditTransaction.objects.filter(kind=CreditTransaction.Kind.REFUND).exists())

    # 6. Job Cancellation Releases Credits
    def test_cancel_job_endpoint_releases_credits(self):
        job = VideoJob.objects.create(
            project=self.project,
            workspace=self.workspace,
            user=self.user,
            job_type=VideoJob.JobType.FULL_GENERATION,
            status=VideoJob.Status.QUEUED,
        )
        reserve_job_credits(job)
        account = get_or_create_credit_account(self.user)
        balance_after_reserve = account.balance

        request = self.factory.post(f"/jobs/{job.id}/cancel/")
        request.user = self.user
        response = VideoJobCancelView.as_view()(request, job_id=job.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], VideoJob.Status.CANCELLED)

        account.refresh_from_db()
        self.assertEqual(account.balance, balance_after_reserve + job.credits_reserved)
        self.assertTrue(CreditTransaction.objects.filter(kind=CreditTransaction.Kind.REFUND).exists())

    # 7. Scene Regeneration charges only that scene's duration
    @patch("video_generator.pipeline.JSON2VideoService", return_value=FakeJSON2VideoService())
    @patch("video_generator.pipeline.get_video_provider", return_value=FakeFalProvider())
    def test_scene_regeneration_job(self, mock_fal, mock_j2v):
        target_scene = self.scenes[0]
        # Scene 1 is already completed in a regeneration scenario
        self.scenes[1].status = VideoScene.Status.COMPLETED
        self.scenes[1].video_url = "https://example.com/scene2.mp4"
        self.scenes[1].save(update_fields=["status", "video_url"])

        initial_balance = get_or_create_credit_account(self.user).balance
        job = VideoJob.objects.create(
            project=self.project,
            workspace=self.workspace,
            user=self.user,
            job_type=VideoJob.JobType.SCENE_REGENERATION,
            target_scene=target_scene,
            status=VideoJob.Status.QUEUED,
        )

        completed_job = run_video_job(job.id)
        self.assertEqual(completed_job.status, VideoJob.Status.COMPLETED)

        self.assertEqual(completed_job.credits_reserved, target_scene.duration)  # 5 credits, not full 10

        final_balance = get_or_create_credit_account(self.user).balance
        self.assertEqual(final_balance, initial_balance - target_scene.duration)

    # 8. Missing Credentials handling
    def test_missing_fal_key_raises_configuration_error(self):
        with patch.dict(os.environ, {"FAL_KEY": ""}, clear=True):
            with self.assertRaises(VideoProviderError):
                get_video_provider("fal_pixverse_c1")
