from datetime import timedelta
import secrets

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .credits import CreditAccount, CreditTransaction
from .models import EmailVerificationToken

User = get_user_model()


class EmailVerificationFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    # 1. Signup creates inactive account
    def test_01_signup_creates_inactive_account(self):
        resp = self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser01", "email": "test01@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="testuser01")
        self.assertFalse(user.is_active)

    # 2. Signup gives 0 credits
    def test_02_signup_gives_zero_credits(self):
        resp = self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser02", "email": "test02@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="testuser02")
        account = CreditAccount.objects.get(user=user)
        self.assertEqual(account.balance, 0)

    # 3. Signup response does not expose verification token in production
    @override_settings(DEBUG=False)
    def test_03_signup_response_does_not_expose_verification_token_in_production(self):
        resp = self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser03", "email": "test03@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("verification_token", resp.data)

    # 4. Send verification email works
    def test_04_send_verification_email_works(self):
        mail.outbox = []
        resp = self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser04", "email": "test04@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        self.assertEqual(sent_mail.subject, "Verify your AI Video Studio account")
        self.assertIn("test04@example.com", sent_mail.to)
        token_obj = EmailVerificationToken.objects.get(user__username="testuser04")
        self.assertIn(f"token={token_obj.token}", sent_mail.body)
        self.assertIn("Activate Account", sent_mail.alternatives[0][0])

    # 5. Valid token activates the exact token.owner user
    def test_05_valid_token_activates_exact_token_owner_user(self):
        self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser05", "email": "test05@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        user = User.objects.get(username="testuser05")
        self.assertFalse(user.is_active)

        token_obj = EmailVerificationToken.objects.get(user=user)
        resp = self.client.post(
            "/api/video/auth/verify-email/",
            {"token": token_obj.token},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    # 6. Exact same user receives 10 credits
    def test_06_exact_same_user_receives_10_credits(self):
        self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser06", "email": "test06@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        user = User.objects.get(username="testuser06")
        token_obj = EmailVerificationToken.objects.get(user=user)
        resp = self.client.post(
            "/api/video/auth/verify-email/",
            {"token": token_obj.token},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        account = CreditAccount.objects.get(user=user)
        self.assertEqual(account.balance, 10)

    # 7. Successful verification auto-authenticates that same user
    def test_07_successful_verification_auto_authenticates_that_same_user(self):
        self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser07", "email": "test07@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        user = User.objects.get(username="testuser07")
        token_obj = EmailVerificationToken.objects.get(user=user)

        # Before verification: not logged in
        me_before = self.client.get("/api/video/auth/me/")
        self.assertEqual(me_before.status_code, status.HTTP_403_FORBIDDEN)

        # Verify token
        verify_resp = self.client.post(
            "/api/video/auth/verify-email/",
            {"token": token_obj.token},
            format="json",
        )
        self.assertEqual(verify_resp.status_code, status.HTTP_200_OK)

        # After verification: auto-authenticated as testuser07
        me_after = self.client.get("/api/video/auth/me/")
        self.assertEqual(me_after.status_code, status.HTTP_200_OK)
        self.assertEqual(me_after.data["user"]["username"], "testuser07")

    # 8. Successful verification returns user info for direct dashboard redirect
    def test_08_successful_verification_redirects_to_dashboard(self):
        self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser08", "email": "test08@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        token_obj = EmailVerificationToken.objects.get(user__username="testuser08")
        resp = self.client.post(
            "/api/video/auth/verify-email/",
            {"token": token_obj.token},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("user", resp.data)
        self.assertEqual(resp.data["user"]["credits_balance"], 10)
        self.assertTrue(resp.data["user"]["email_verified"])

    # 9. User is not asked to login again
    def test_09_user_not_asked_to_login_again(self):
        self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser09", "email": "test09@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        token_obj = EmailVerificationToken.objects.get(user__username="testuser09")
        self.client.post("/api/video/auth/verify-email/", {"token": token_obj.token}, format="json")

        # Can immediately query credits and projects without separate login
        credits_resp = self.client.get("/api/video/credits/")
        self.assertEqual(credits_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(credits_resp.data["balance"], 10)

    # 10. Same token cannot be reused
    def test_10_same_token_cannot_be_reused(self):
        self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser10", "email": "test10@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        token_obj = EmailVerificationToken.objects.get(user__username="testuser10")
        first_resp = self.client.post("/api/video/auth/verify-email/", {"token": token_obj.token}, format="json")
        self.assertEqual(first_resp.status_code, status.HTTP_200_OK)

        second_resp = self.client.post("/api/video/auth/verify-email/", {"token": token_obj.token}, format="json")
        self.assertEqual(second_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(second_resp.data["detail"], "This verification link has already been used.")

    # 11. Reused token cannot grant credits again
    def test_11_reused_token_cannot_grant_credits_again(self):
        self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser11", "email": "test11@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        user = User.objects.get(username="testuser11")
        token_obj = EmailVerificationToken.objects.get(user=user)
        self.client.post("/api/video/auth/verify-email/", {"token": token_obj.token}, format="json")

        # Balance is 10
        account = CreditAccount.objects.get(user=user)
        self.assertEqual(account.balance, 10)

        # Attempt reuse
        self.client.post("/api/video/auth/verify-email/", {"token": token_obj.token}, format="json")
        account.refresh_from_db()
        self.assertEqual(account.balance, 10)
        self.assertEqual(
            CreditTransaction.objects.filter(account=account, kind=CreditTransaction.Kind.GRANT).count(),
            1,
        )

    # 12. Expired token fails
    def test_12_expired_token_fails(self):
        self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser12", "email": "test12@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        user = User.objects.get(username="testuser12")
        token_obj = EmailVerificationToken.objects.get(user=user)
        token_obj.expires_at = timezone.now() - timedelta(minutes=1)
        token_obj.save(update_fields=["expires_at"])

        resp = self.client.post("/api/video/auth/verify-email/", {"token": token_obj.token}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["detail"], "Invalid or expired verification link.")

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(CreditAccount.objects.get(user=user).balance, 0)

    # 13. Invalid token fails
    def test_13_invalid_token_fails(self):
        resp = self.client.post("/api/video/auth/verify-email/", {"token": "completely_fake_token_12345"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["detail"], "Invalid or expired verification link.")

    # 14. Unverified login fails
    def test_14_unverified_login_fails(self):
        self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser14", "email": "test14@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        resp = self.client.post(
            "/api/video/auth/login/",
            {"username": "testuser14", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["detail"], "Please verify your email address to activate your account.")

    # 15. Resend creates a new token
    def test_15_resend_creates_new_token(self):
        self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser15", "email": "test15@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        user = User.objects.get(username="testuser15")
        old_token = EmailVerificationToken.objects.get(user=user)

        mail.outbox = []
        resend_resp = self.client.post(
            "/api/video/auth/resend-verification/",
            {"email": "test15@example.com"},
            format="json",
        )
        self.assertEqual(resend_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resend_resp.data["message"], "Verification email sent. Please check your inbox.")
        self.assertNotIn("verification_token", resend_resp.data)

        # Old token is invalidated
        old_token.refresh_from_db()
        self.assertIsNotNone(old_token.used_at)

        # New token exists and is valid
        new_token = EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).first()
        self.assertIsNotNone(new_token)
        self.assertNotEqual(old_token.token, new_token.token)
        self.assertEqual(len(mail.outbox), 1)

    # 16. Resend does not grant credits
    def test_16_resend_does_not_grant_credits(self):
        self.client.post(
            "/api/video/auth/signup/",
            {"username": "testuser16", "email": "test16@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        self.client.post("/api/video/auth/resend-verification/", {"email": "test16@example.com"}, format="json")
        user = User.objects.get(username="testuser16")
        self.assertFalse(user.is_active)
        self.assertEqual(CreditAccount.objects.get(user=user).balance, 0)

    # 17. Duplicate email remains blocked
    def test_17_duplicate_email_remains_blocked(self):
        User.objects.create_user(username="first_user", email="dup@example.com", password="StrongPassword123!")
        resp = self.client.post(
            "/api/video/auth/signup/",
            {"username": "second_user", "email": "DUP@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["detail"], "Email already exists. Please sign in instead.")

    # 18. Duplicate username remains blocked
    def test_18_duplicate_username_remains_blocked(self):
        User.objects.create_user(username="unique_user", email="user1@example.com", password="StrongPassword123!")
        resp = self.client.post(
            "/api/video/auth/signup/",
            {"username": "UNIQUE_USER", "email": "user2@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["detail"], "Username already exists. Please choose another username.")

    # 19. Weak passwords remain blocked
    def test_19_weak_passwords_remain_blocked(self):
        resp = self.client.post(
            "/api/video/auth/signup/",
            {"username": "weak_pwd_user", "email": "weak@example.com", "password": "password"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", resp.data["detail"].lower())

    # 20. CRITICAL: User A's verification token can never authenticate User B
    def test_20_critical_user_a_token_never_authenticates_or_credits_user_b(self):
        # User B exists and has an active session
        user_b = User.objects.create_user(username="user_b", email="b@example.com", password="StrongPassword123!")
        user_b.is_active = True
        user_b.save(update_fields=["is_active"])
        account_b = CreditAccount.objects.create(user=user_b, balance=0, monthly_allowance=10)

        # Log User B in
        self.client.force_login(user_b)
        me_resp = self.client.get("/api/video/auth/me/")
        self.assertEqual(me_resp.data["user"]["username"], "user_b")

        # User A signs up
        self.client.post(
            "/api/video/auth/signup/",
            {"username": "user_a", "email": "a@example.com", "password": "StrongPassword123!"},
            format="json",
        )
        user_a = User.objects.get(username="user_a")
        token_a = EmailVerificationToken.objects.get(user=user_a).token

        # Verify User A's token
        verify_resp = self.client.post("/api/video/auth/verify-email/", {"token": token_a}, format="json")
        self.assertEqual(verify_resp.status_code, status.HTTP_200_OK)

        # User A state: active, 10 credits
        user_a.refresh_from_db()
        self.assertTrue(user_a.is_active)
        account_a = CreditAccount.objects.get(user=user_a)
        self.assertEqual(account_a.balance, 10)

        # User B state: unchanged, 0 credits
        account_b.refresh_from_db()
        self.assertEqual(account_b.balance, 0)
        self.assertEqual(CreditTransaction.objects.filter(account=account_b).count(), 0)

        # Active session is now User A (switched to User A)
        me_after = self.client.get("/api/video/auth/me/")
        self.assertEqual(me_after.data["user"]["username"], "user_a")
