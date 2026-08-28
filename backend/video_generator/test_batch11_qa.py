import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .billing import PLANS, ensure_subscription, handle_stripe_event
from .character_generation import CharacterGenerationError
from .credits import (
    FREE_MONTHLY_CREDITS,
    generation_cost,
    get_or_create_credit_account,
    refund_transaction,
    reserve_credits,
    reserve_generation,
)
from .models import (
    Character,
    CreditAccount,
    CreditTransaction,
    Subscription,
    UsageEvent,
    VideoProject,
    VideoScene,
)
from .providers import VideoProviderError
from .scene_planner import build_scene_plan, validate_generation_options

User = get_user_model()


class Batch11DeepQATests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="Password123!")
        self.other_user = User.objects.create_user(username="bob", email="bob@example.com", password="Password123!")
        self.staff_user = User.objects.create_user(username="admin", email="admin@example.com", password="Password123!", is_staff=True)

        ensure_subscription(self.user)
        ensure_subscription(self.other_user)
        ensure_subscription(self.staff_user)

        self.account = get_or_create_credit_account(self.user)
        self.account.balance = 500
        self.account.save(update_fields=["balance"])

        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        cache.clear()

    # =========================================================================
    # 1. DURATION & CREDIT ECONOMICS (10s, 30s, 60s)
    # =========================================================================

    def test_duration_and_credit_cost_calculations(self):
        """Test duration validation and 1-credit-per-second economics across 10s, 30s, 60s."""
        self.assertEqual(generation_cost(10), 10)
        self.assertEqual(generation_cost(30), 30)
        self.assertEqual(generation_cost(60), 60)

        # Scene durations
        self.assertEqual(generation_cost(5), 5)
        self.assertEqual(generation_cost(6), 6)

        # Unsupported durations
        self.assertEqual(generation_cost(0), 0)
        self.assertEqual(generation_cost(-10), 0)
        self.assertEqual(generation_cost(65), 0)

        # Scene planner deterministic split
        plan10 = build_scene_plan("Story 10", 10)
        self.assertEqual(len(plan10), 2)
        self.assertEqual(sum(s["duration"] for s in plan10), 10)

        plan30 = build_scene_plan("Story 30", 30)
        self.assertEqual(len(plan30), 5)
        self.assertEqual(sum(s["duration"] for s in plan30), 30)

        plan60 = build_scene_plan("Story 60", 60)
        self.assertEqual(len(plan60), 10)
        self.assertEqual(sum(s["duration"] for s in plan60), 60)

    def test_reserve_generation_across_durations(self):
        """Verify reserve_generation succeeds for 10s, 30s, and 60s projects."""
        p10 = VideoProject.objects.create(user=self.user, title="P10", prompt="P10", duration=10)
        p30 = VideoProject.objects.create(user=self.user, title="P30", prompt="P30", duration=30)
        p60 = VideoProject.objects.create(user=self.user, title="P60", prompt="P60", duration=60)

        self.assertEqual(reserve_generation(self.user, p10, idempotency_key="res:p10"), 10)
        self.assertEqual(reserve_generation(self.user, p30, idempotency_key="res:p30"), 30)
        self.assertEqual(reserve_generation(self.user, p60, idempotency_key="res:p60"), 60)

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 500 - 10 - 30 - 60)

    # =========================================================================
    # 2. INPUT VALIDATION & BOUNDARY TESTS
    # =========================================================================

    def test_project_create_validation_edges(self):
        """Test validation error cases on project creation."""
        # Empty prompt
        res = self.client.post("/api/video/projects/", {"prompt": "", "characters": [{"name": "Hero"}]}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Whitespace prompt
        res = self.client.post("/api/video/projects/", {"prompt": "   ", "characters": [{"name": "Hero"}]}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing characters
        res = self.client.post("/api/video/projects/", {"prompt": "Valid story", "characters": []}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Character with empty name
        res = self.client.post("/api/video/projects/", {"prompt": "Valid story", "characters": [{"name": "  "}]}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Invalid duration
        res = self.client.post("/api/video/projects/", {"prompt": "Valid story", "duration": 45, "characters": [{"name": "Hero"}]}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Invalid aspect ratio
        res = self.client.post("/api/video/projects/", {"prompt": "Valid story", "aspect_ratio": "4:3", "characters": [{"name": "Hero"}]}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Invalid input_type
        res = self.client.post("/api/video/projects/", {"prompt": "Valid story", "input_type": "novel", "characters": [{"name": "Hero"}]}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # =========================================================================
    # 3. CHARACTER REFERENCE WORKFLOW, REUSE, AND REFUNDS
    # =========================================================================

    @patch("video_generator.ai_views.generate_character_reference")
    def test_character_reference_success_and_reuse(self, mock_gen):
        """Verify character reference generation, usage recording, and smart reuse."""
        mock_gen.return_value = "https://cdn.example.com/character_ref.png"

        # Create project
        res = self.client.post("/api/video/projects/", {
            "title": "Village Story",
            "prompt": "Farmer in village",
            "duration": 10,
            "characters": [{"name": "Farmer", "appearance": "tall with beard", "clothing": "green vest"}],
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        project_id = res.data["id"]
        char_id = res.data["characters"][0]["id"]

        # Generate reference
        ref_res = self.client.post(f"/api/video/projects/{project_id}/characters/{char_id}/reference/")
        self.assertEqual(ref_res.status_code, status.HTTP_200_OK)
        self.assertEqual(ref_res.data["reused"], False)
        self.assertEqual(ref_res.data["reference_image_url"], "https://cdn.example.com/character_ref.png")

        # Second request reuses existing reference without calling provider
        mock_gen.reset_mock()
        reuse_res = self.client.post(f"/api/video/projects/{project_id}/characters/{char_id}/reference/")
        self.assertEqual(reuse_res.status_code, status.HTTP_200_OK)
        self.assertEqual(reuse_res.data["reused"], True)
        mock_gen.assert_not_called()

    @patch("video_generator.ai_views.generate_character_reference")
    def test_character_reference_failure_refunds_credits(self, mock_gen):
        """Verify credit reservation is refunded when character generation encounters a provider error."""
        mock_gen.side_effect = CharacterGenerationError("Provider unavailable")

        res = self.client.post("/api/video/projects/", {
            "title": "Village Story",
            "prompt": "Farmer in village",
            "duration": 10,
            "characters": [{"name": "Farmer"}],
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        project_id = res.data["id"]
        char_id = res.data["characters"][0]["id"]

        bal_before = CreditAccount.objects.get(user=self.user).balance
        ref_res = self.client.post(f"/api/video/projects/{project_id}/characters/{char_id}/reference/")
        self.assertEqual(ref_res.status_code, status.HTTP_502_BAD_GATEWAY)

        # Balance must be fully restored
        bal_after = CreditAccount.objects.get(user=self.user).balance
        self.assertEqual(bal_after, bal_before)

        # Refund transaction must exist
        refund = CreditTransaction.objects.filter(kind=CreditTransaction.Kind.REFUND).first()
        self.assertIsNotNone(refund)
        self.assertEqual(refund.amount, 5)

    # =========================================================================
    # 4. VERSIONING & CHARACTER CONTINUITY (V1 -> V2 -> V3 -> Failed V4)
    # =========================================================================

    def test_versioning_lifecycle_and_isolation(self):
        """Test that V1, V2, V3 create distinct versions and failure in V4 does not corrupt previous versions."""
        # Create V1
        res_v1 = self.client.post("/api/video/projects/", {
            "title": "Story V1",
            "prompt": "Farmer in village sunrise",
            "duration": 10,
            "characters": [{"name": "Farmer", "appearance": "tall", "clothing": "brown robe"}],
        }, format="json")
        self.assertEqual(res_v1.status_code, status.HTTP_201_CREATED)
        v1_id = res_v1.data["id"]
        char_v1 = Character.objects.get(project_id=v1_id)
        char_v1.reference_image_url = "https://cdn.example.com/farmer_ref.png"
        char_v1.save(update_fields=["reference_image_url"])

        # Complete V1
        p_v1 = VideoProject.objects.get(id=v1_id)
        p_v1.status = VideoProject.Status.COMPLETED
        p_v1.video_url = "https://cdn.example.com/v1_final.mp4"
        p_v1.save(update_fields=["status", "video_url"])

        # Create V2 (same character definition -> reuses reference)
        res_v2 = self.client.post(f"/api/video/projects/{v1_id}/versions/", {
            "title": "Story V2",
            "prompt": "Farmer in village sunset with buffalo",
            "characters": [{"name": "Farmer", "appearance": "tall", "clothing": "brown robe"}],
        }, format="json")
        self.assertEqual(res_v2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_v2.data["version_number"], 2)
        v2_id = res_v2.data["id"]

        char_v2 = Character.objects.get(project_id=v2_id)
        self.assertEqual(char_v2.reference_image_url, "https://cdn.example.com/farmer_ref.png")

        # Complete V2
        p_v2 = VideoProject.objects.get(id=v2_id)
        p_v2.status = VideoProject.Status.COMPLETED
        p_v2.video_url = "https://cdn.example.com/v2_final.mp4"
        p_v2.save(update_fields=["status", "video_url"])

        # Create V3 (modified character appearance -> resets reference)
        res_v3 = self.client.post(f"/api/video/projects/{v2_id}/versions/", {
            "title": "Story V3",
            "prompt": "Farmer in futuristic city",
            "characters": [{"name": "Farmer", "appearance": "tall with cybernetic eye", "clothing": "neon jacket"}],
        }, format="json")
        self.assertEqual(res_v3.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_v3.data["version_number"], 3)
        v3_id = res_v3.data["id"]

        char_v3 = Character.objects.get(project_id=v3_id)
        self.assertIsNone(char_v3.reference_image_url)  # Must be reset because appearance changed!

        # Complete V3
        p_v3 = VideoProject.objects.get(id=v3_id)
        p_v3.status = VideoProject.Status.COMPLETED
        p_v3.video_url = "https://cdn.example.com/v3_final.mp4"
        p_v3.save(update_fields=["status", "video_url"])

        # Create V4 and mark it failed
        res_v4 = self.client.post(f"/api/video/projects/{v3_id}/versions/", {
            "title": "Story V4",
            "prompt": "Farmer on moon",
        }, format="json")
        self.assertEqual(res_v4.status_code, status.HTTP_201_CREATED)
        v4_id = res_v4.data["id"]
        p_v4 = VideoProject.objects.get(id=v4_id)
        p_v4.status = VideoProject.Status.FAILED
        p_v4.error_message = "Generation failed"
        p_v4.save(update_fields=["status", "error_message"])

        # Check version history query
        hist_res = self.client.get(f"/api/video/projects/{v4_id}/versions/")
        self.assertEqual(hist_res.status_code, status.HTTP_200_OK)
        versions = hist_res.data
        self.assertEqual(len(versions), 4)
        self.assertEqual([v["version_number"] for v in versions], [1, 2, 3, 4])
        self.assertEqual(versions[0]["status"], "completed")
        self.assertEqual(versions[1]["status"], "completed")
        self.assertEqual(versions[2]["status"], "completed")
        self.assertEqual(versions[3]["status"], "failed")

        # Previous videos are pristine
        self.assertEqual(versions[0]["video_url"], "https://cdn.example.com/v1_final.mp4")
        self.assertEqual(versions[1]["video_url"], "https://cdn.example.com/v2_final.mp4")
        self.assertEqual(versions[2]["video_url"], "https://cdn.example.com/v3_final.mp4")

    # =========================================================================
    # 5. SCENE GENERATION, TIMEOUT RECOVERY, AND REGENERATION
    # =========================================================================

    @patch("video_generator.ai_views.get_video_provider")
    def test_scene_generation_and_status_polling(self, mock_provider_getter):
        """Test scene generation submission, status polling, and completion."""
        mock_provider = MagicMock()
        mock_provider.submit_scene.return_value = {"request_id": "req-scene-123"}
        mock_provider_getter.return_value = mock_provider

        # Setup project with character reference
        res = self.client.post("/api/video/projects/", {
            "title": "Scene Test",
            "prompt": "Two scene story",
            "duration": 10,
            "characters": [{"name": "Hero"}],
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        project_id = res.data["id"]
        char = Character.objects.get(project_id=project_id)
        char.reference_image_url = "https://cdn.example.com/hero.png"
        char.save()

        scene1 = VideoScene.objects.filter(project_id=project_id, scene_number=1).first()

        # Generate Scene 1
        gen_res = self.client.post(f"/api/video/projects/{project_id}/scenes/{scene1.id}/generate/")
        self.assertEqual(gen_res.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(gen_res.data["status"], "processing")
        self.assertEqual(gen_res.data["provider_project_id"], "req-scene-123")

        # Poll status while in progress
        mock_provider.get_scene_result.return_value = {"status": "processing"}
        poll_res = self.client.get(f"/api/video/projects/{project_id}/scenes/{scene1.id}/status/")
        self.assertEqual(poll_res.data["status"], "processing")

        # Poll status when completed
        mock_provider.get_scene_result.return_value = {
            "status": "completed",
            "video_url": "https://cdn.example.com/scene1.mp4",
        }
        poll_res2 = self.client.get(f"/api/video/projects/{project_id}/scenes/{scene1.id}/status/")
        self.assertEqual(poll_res2.data["status"], "completed")
        self.assertEqual(poll_res2.data["video_url"], "https://cdn.example.com/scene1.mp4")

    @patch("video_generator.ai_views.get_video_provider")
    def test_scene_generation_timeout_auto_refund(self, mock_provider_getter):
        """Test that a stuck processing scene times out safely and auto-refunds."""
        project = VideoProject.objects.create(user=self.user, title="Timeout Test", prompt="Story", duration=10)
        char = Character.objects.create(project=project, name="Hero", reference_image_url="https://cdn.example.com/hero.png")
        scene = VideoScene.objects.create(
            project=project,
            scene_number=1,
            duration=5,
            prompt="Scene 1",
            status=VideoScene.Status.PROCESSING,
            provider="fal_pixverse_c1",
            provider_project_id="stuck-job-999",
            generation_attempt=1,
            processing_started_at=timezone.now() - timedelta(seconds=2000),
        )
        scene.characters.add(char)

        # Create reservation transaction
        charge_key = f"scene-generation:{scene.id}:1"
        reserve_credits(self.user, 5, idempotency_key=charge_key, project=project)
        bal_before = CreditAccount.objects.get(user=self.user).balance

        with override_settings(PROVIDER_JOB_TIMEOUT_SECONDS=1800):
            res = self.client.get(f"/api/video/projects/{project.id}/scenes/{scene.id}/status/")
            self.assertEqual(res.data["status"], "failed")
            self.assertIn("timed out", res.data["error_message"].lower())

        bal_after = CreditAccount.objects.get(user=self.user).balance
        self.assertEqual(bal_after, bal_before + 5)

        # Polling again does NOT duplicate refund
        self.client.get(f"/api/video/projects/{project.id}/scenes/{scene.id}/status/")
        bal_again = CreditAccount.objects.get(user=self.user).balance
        self.assertEqual(bal_again, bal_after)

    # =========================================================================
    # 6. ASSEMBLY VALIDATION & REFUNDS
    # =========================================================================

    def test_assembly_rejects_incomplete_scenes(self):
        """Verify video assembly rejects project if any scenes are not completed."""
        project = VideoProject.objects.create(user=self.user, title="Assembly Test", prompt="Story", duration=10)
        VideoScene.objects.create(project=project, scene_number=1, duration=5, prompt="S1", status=VideoScene.Status.COMPLETED, video_url="https://cdn.example.com/s1.mp4")
        VideoScene.objects.create(project=project, scene_number=2, duration=5, prompt="S2", status=VideoScene.Status.PROCESSING)

        res = self.client.post(f"/api/video/projects/{project.id}/assemble/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("All scenes must be completed", res.data["detail"])

    @patch("video_generator.views.JSON2VideoService")
    @patch("video_generator.ai_views.JSON2VideoService")
    def test_assembly_success_and_status(self, mock_ai_j2v, mock_views_j2v):
        """Verify assembly submission and status check to completion."""
        mock_svc = MagicMock()
        mock_svc.create_movie_from_clips.return_value = {"project": "j2v-movie-123"}
        mock_svc.get_movie.return_value = {
            "movie": {
                "status": "done",
                "url": "https://cdn.example.com/final_assembly.mp4",
            }
        }
        mock_ai_j2v.return_value = mock_svc
        mock_views_j2v.return_value = mock_svc

        project = VideoProject.objects.create(user=self.user, title="Assembly Test", prompt="Story", duration=10)
        VideoScene.objects.create(project=project, scene_number=1, duration=5, prompt="S1", status=VideoScene.Status.COMPLETED, video_url="https://cdn.example.com/s1.mp4")
        VideoScene.objects.create(project=project, scene_number=2, duration=5, prompt="S2", status=VideoScene.Status.COMPLETED, video_url="https://cdn.example.com/s2.mp4")

        # Post assemble
        res = self.client.post(f"/api/video/projects/{project.id}/assemble/")
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(res.data["status"], "processing")

        # Get status
        status_res = self.client.get(f"/api/video/projects/{project.id}/status/")
        self.assertEqual(status_res.data["status"], "completed")
        self.assertEqual(status_res.data["video_url"], "https://cdn.example.com/final_assembly.mp4")

    # =========================================================================
    # 7. STRIPE BILLING & WEBHOOK IDEMPOTENCY
    # =========================================================================

    def test_stripe_webhook_idempotency(self):
        """Verify sending duplicate Stripe webhook events is idempotent and does not double-grant credits."""
        event_id = f"evt_{uuid.uuid4().hex}"
        event = {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "client_reference_id": str(self.user.id),
                    "metadata": {"user_id": str(self.user.id), "plan_code": "creator"},
                    "customer": "cus_123",
                    "subscription": "sub_123",
                }
            },
        }

        # First call processes and grants allowance
        first_result = handle_stripe_event(event)
        self.assertTrue(first_result)

        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan_code, "creator")
        self.assertEqual(sub.status, "active")

        bal_after_first = CreditAccount.objects.get(user=self.user).balance

        # Second duplicate call must return False and not grant extra credits
        second_result = handle_stripe_event(event)
        self.assertFalse(second_result)

        bal_after_second = CreditAccount.objects.get(user=self.user).balance
        self.assertEqual(bal_after_first, bal_after_second)

    # =========================================================================
    # 8. IDOR & ADMIN SECURITY
    # =========================================================================

    def test_idor_protection_across_endpoints(self):
        """Ensure Bob cannot read or modify Alice's projects, scenes, or versions."""
        alice_project = VideoProject.objects.create(user=self.user, title="Alice Secret", prompt="Story", duration=10)
        alice_scene = VideoScene.objects.create(project=alice_project, scene_number=1, duration=5, prompt="S1")

        # Authenticate as Bob
        self.client.force_authenticate(user=self.other_user)

        # Try to view Alice's project status
        res = self.client.get(f"/api/video/projects/{alice_project.id}/status/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # Try to generate Alice's scene
        res = self.client.post(f"/api/video/projects/{alice_project.id}/scenes/{alice_scene.id}/generate/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # Try to branch Alice's version
        res = self.client.post(f"/api/video/projects/{alice_project.id}/versions/", {"prompt": "Hacked"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # Try to access admin stats as normal user
        res = self.client.get("/api/video/admin/stats/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as staff user
        self.client.force_authenticate(user=self.staff_user)
        admin_res = self.client.get("/api/video/admin/stats/")
        self.assertEqual(admin_res.status_code, status.HTTP_200_OK)
        self.assertIn("users", admin_res.data)
        self.assertIn("projects", admin_res.data)
