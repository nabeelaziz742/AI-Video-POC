from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .billing import Subscription
from .credits import CreditAccount, CreditTransaction, grant_free_allowance
from .models import EmailVerificationToken, VideoProject

User = get_user_model()


class ProductImprovementsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    # 1. ONE EMAIL = ONE ACCOUNT
    def test_signup_rejects_duplicate_email(self):
        User.objects.create_user(username="user1", email="existing@example.com", password="StrongPassword123!")
        response = self.client.post(
            "/api/video/auth/signup/",
            {"username": "user2", "email": "existing@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Email already exists. Please sign in instead.")

    def test_signup_rejects_case_insensitive_duplicate_email(self):
        User.objects.create_user(username="user1", email="case@example.com", password="StrongPassword123!")
        response = self.client.post(
            "/api/video/auth/signup/",
            {"username": "user2", "email": "CASE@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Email already exists. Please sign in instead.")

    # 2. USERNAME UNIQUENESS
    def test_signup_rejects_duplicate_username(self):
        User.objects.create_user(username="samename", email="first@example.com", password="StrongPassword123!")
        response = self.client.post(
            "/api/video/auth/signup/",
            {"username": "samename", "email": "second@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Username already exists. Please choose another username.")

    # 3. PASSWORD SECURITY & DJANGO VALIDATOR
    def test_signup_rejects_weak_and_common_passwords(self):
        weak_passwords = ["00000000", "12345678", "password", "qwerty123", "short"]
        for idx, weak_pwd in enumerate(weak_passwords):
            response = self.client.post(
                "/api/video/auth/signup/",
                {"username": f"weakuser{idx}", "email": f"weak{idx}@example.com", "password": weak_pwd},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("password", response.data["detail"].lower())

    # 4. EMAIL VERIFICATION LIFECYCLE & 10 FREE CREDITS
    def test_email_verification_grants_ten_credits_and_activates_account(self):
        signup_resp = self.client.post(
            "/api/video/auth/signup/",
            {"username": "newcreator", "email": "creator@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(signup_resp.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="newcreator")
        self.assertFalse(user.is_active)
        self.assertEqual(CreditAccount.objects.get(user=user).balance, 0)

        # Unverified user cannot login
        login_resp = self.client.post(
            "/api/video/auth/login/",
            {"username": "newcreator", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(login_resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("verify your email", login_resp.data["detail"].lower())

        # Verify email using single-use token
        token = signup_resp.data["verification_token"]
        verify_resp = self.client.post(
            "/api/video/auth/verify-email/",
            {"token": token},
            format="json",
        )
        self.assertEqual(verify_resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(CreditAccount.objects.get(user=user).balance, 10)

        # Token cannot be reused
        reuse_resp = self.client.post(
            "/api/video/auth/verify-email/",
            {"token": token},
            format="json",
        )
        self.assertEqual(reuse_resp.status_code, status.HTTP_400_BAD_REQUEST)

    # 5. UNVERIFIED ACCOUNT CANNOT GENERATE VIDEOS
    def test_unverified_account_blocked_from_generation(self):
        unverified = User.objects.create_user(username="unverified", email="u@example.com", password="StrongPassword123!")
        unverified.is_active = False
        unverified.save(update_fields=["is_active"])
        self.client.force_authenticate(unverified)
        response = self.client.post(
            "/api/video/projects/",
            {"title": "Blocked", "prompt": "Story prompt", "duration": 10, "aspect_ratio": "9:16"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("verify your email", response.data["detail"].lower())

    # 6. DURATION LIMITS (FREE: 10s, CREATOR: 30s, PRO: 60s)
    def test_free_user_duration_limits(self):
        user = User.objects.create_user(username="freeuser", email="free@example.com", password="StrongPassword123!")
        grant_free_allowance(user)
        self.client.force_authenticate(user)

        # 10s allowed
        resp10 = self.client.post(
            "/api/video/projects/",
            {"title": "10s Video", "prompt": "A young explorer discovers a doorway.", "duration": 10, "aspect_ratio": "16:9"},
            format="json",
        )
        self.assertEqual(resp10.status_code, status.HTTP_201_CREATED)

        # 30s and 60s rejected on Free plan
        resp30 = self.client.post(
            "/api/video/projects/",
            {"title": "30s Video", "prompt": "A longer story.", "duration": 30, "aspect_ratio": "16:9"},
            format="json",
        )
        self.assertEqual(resp30.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("10 seconds", resp30.data["detail"])

        resp60 = self.client.post(
            "/api/video/projects/",
            {"title": "60s Video", "prompt": "A full narrative.", "duration": 60, "aspect_ratio": "16:9"},
            format="json",
        )
        self.assertEqual(resp60.status_code, status.HTTP_400_BAD_REQUEST)

    def test_creator_user_duration_limits(self):
        user = User.objects.create_user(username="creatoruser", email="creator@example.com", password="StrongPassword123!")
        Subscription.objects.create(user=user, plan_code=Subscription.Plan.CREATOR)
        self.client.force_authenticate(user)

        resp30 = self.client.post(
            "/api/video/projects/",
            {"title": "30s Video", "prompt": "A longer story.", "duration": 30, "aspect_ratio": "16:9"},
            format="json",
        )
        self.assertEqual(resp30.status_code, status.HTTP_201_CREATED)

        resp60 = self.client.post(
            "/api/video/projects/",
            {"title": "60s Video", "prompt": "A full narrative.", "duration": 60, "aspect_ratio": "16:9"},
            format="json",
        )
        self.assertEqual(resp60.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("30 seconds", resp60.data["detail"])

    def test_pro_user_duration_limits(self):
        user = User.objects.create_user(username="prouser", email="pro@example.com", password="StrongPassword123!")
        Subscription.objects.create(user=user, plan_code=Subscription.Plan.PRO)
        self.client.force_authenticate(user)

        resp60 = self.client.post(
            "/api/video/projects/",
            {"title": "60s Video", "prompt": "A full narrative.", "duration": 60, "aspect_ratio": "16:9"},
            format="json",
        )
        self.assertEqual(resp60.status_code, status.HTTP_201_CREATED)

    # 7. AUTOMATIC CHARACTER EXTRACTION
    def test_automatic_character_extraction_when_characters_omitted(self):
        user = User.objects.create_user(username="autouser", email="auto@example.com", password="StrongPassword123!")
        grant_free_allowance(user)
        self.client.force_authenticate(user)

        response = self.client.post(
            "/api/video/projects/",
            {
                "title": "Explorer Story",
                "prompt": "A young explorer walks through a futuristic city at sunset and discovers a glowing doorway.",
                "duration": 10,
                "aspect_ratio": "16:9",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = VideoProject.objects.get(id=response.data["id"])
        self.assertEqual(project.characters.count(), 1)
        character = project.characters.first()
        self.assertIn("Explorer", character.name)
        self.assertTrue(len(character.consistency_prompt) > 10)

    # 8. VERSIONING (V1 -> V2 WITHOUT OVERWRITING)
    def test_edit_story_creates_new_version(self):
        user = User.objects.create_user(username="veruser", email="ver@example.com", password="StrongPassword123!")
        grant_free_allowance(user)
        self.client.force_authenticate(user)

        v1_resp = self.client.post(
            "/api/video/projects/",
            {"title": "Versioned Story", "prompt": "V1 prompt", "duration": 10, "aspect_ratio": "16:9"},
            format="json",
        )
        self.assertEqual(v1_resp.status_code, status.HTTP_201_CREATED)
        v1_id = v1_resp.data["id"]

        v2_resp = self.client.post(
            f"/api/video/projects/{v1_id}/versions/",
            {"prompt": "V2 updated prompt", "duration": 10, "aspect_ratio": "16:9"},
            format="json",
        )
        self.assertEqual(v2_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(v2_resp.data["version_number"], 2)

        # Ensure V1 still exists untouched
        v1_obj = VideoProject.objects.get(id=v1_id)
        self.assertEqual(v1_obj.prompt, "V1 prompt")
        self.assertEqual(v1_obj.version_number, 1)
