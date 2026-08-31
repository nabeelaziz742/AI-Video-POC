import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient
from video_generator.models import EmailVerificationToken, CreditAccount, CreditTransaction

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def run_e2e_manual_flow():
    print("=" * 60)
    print("STARTING MANUAL END-TO-END FLOW TEST")
    print("=" * 60)

    cache.clear()
    mail.outbox = []

    client = APIClient()
    username = "e2e_production_user"
    email = "e2e_prod_user@example.com"
    password = "SuperSecurePass123!"

    # Clean up prior test user if exists
    User.objects.filter(email__iexact=email).delete()
    User.objects.filter(username__iexact=username).delete()

    # Step 1: Signup
    print("\n[Step 1] User Signs Up...")
    signup_resp = client.post(
        "/api/video/auth/signup/",
        {"username": username, "email": email, "password": password},
        format="json",
    )
    print(f"Signup Status: {signup_resp.status_code}")
    print(f"Signup Data: {signup_resp.data}")
    assert signup_resp.status_code == 201, f"Expected 201, got {signup_resp.status_code}"
    assert "verification_token" not in signup_resp.data, "Raw verification token MUST NOT be exposed in signup response!"

    # Step 2: Confirm Account is Inactive & Credits = 0
    print("\n[Step 2] Checking Account State...")
    user = User.objects.get(username=username)
    print(f"User is_active: {user.is_active}")
    account = CreditAccount.objects.get(user=user)
    print(f"User credits balance: {account.balance}")
    assert not user.is_active, "User must NOT be active at signup!"
    assert account.balance == 0, "User must have 0 credits at signup!"

    # Confirm unverified user cannot log in
    print("\n[Step 2b] Confirming Unverified Login is Blocked...")
    login_attempt = client.post(
        "/api/video/auth/login/",
        {"username": username, "password": password},
        format="json",
    )
    print(f"Login Attempt Status: {login_attempt.status_code}")
    print(f"Login Attempt Data: {login_attempt.data}")
    assert login_attempt.status_code == 403, f"Expected 403, got {login_attempt.status_code}"
    assert "verify your email" in login_attempt.data["detail"].lower()

    # Step 3: Send Verification Email (Resend)
    print("\n[Step 3] Clicking 'Send Verification Email'...")
    mail.outbox = []
    resend_resp = client.post(
        "/api/video/auth/resend-verification/",
        {"email": email},
        format="json",
    )
    print(f"Resend Status: {resend_resp.status_code}")
    print(f"Resend Data: {resend_resp.data}")
    assert resend_resp.status_code == 200, f"Expected 200, got {resend_resp.status_code}"
    assert resend_resp.data["message"] == "Verification email sent. Please check your inbox."
    assert "verification_token" not in resend_resp.data

    # Step 4: Open Email & Extract Token
    print("\n[Step 4] Reading Dispatched Email from Inbox...")
    assert len(mail.outbox) == 1, "Expected 1 email in outbox"
    email_obj = mail.outbox[0]
    print(f"Email Subject: {email_obj.subject}")
    print(f"Email To: {email_obj.to}")
    assert email_obj.subject == "Verify your AI Video Studio account"
    assert email in email_obj.to

    token_obj = EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).latest("created_at")
    token_str = token_obj.token
    print(f"Secure Token in Email: {token_str[:8]}... (truncated for safety)")

    # Step 5: User clicks "Activate Account" (Hits verify endpoint)
    print("\n[Step 5] Clicking 'Activate Account'...")
    verify_resp = client.post(
        "/api/video/auth/verify-email/",
        {"token": token_str},
        format="json",
    )
    print(f"Verify Status: {verify_resp.status_code}")
    print(f"Verify Data: {verify_resp.data}")
    assert verify_resp.status_code == 200, f"Expected 200, got {verify_resp.status_code}"
    assert verify_resp.data["user"]["username"] == username
    assert verify_resp.data["user"]["email_verified"] is True
    assert verify_resp.data["user"]["credits_balance"] == 10

    # Step 6: Verify User is Active, 10 Credits Granted, and Auto-Logged In
    print("\n[Step 6] Confirming Auto-Login Session & Dashboard Entitlements...")
    user.refresh_from_db()
    account.refresh_from_db()
    assert user.is_active is True, "User should now be active!"
    assert account.balance == 10, "User should now have exactly 10 credits!"

    # Auto-login check: /api/video/auth/me/ without entering password
    me_resp = client.get("/api/video/auth/me/")
    print(f"/auth/me/ Status: {me_resp.status_code}")
    print(f"/auth/me/ User: {me_resp.data['user']['username']}")
    assert me_resp.status_code == 200
    assert me_resp.data["user"]["username"] == username

    # Check credits endpoint
    credits_resp = client.get("/api/video/credits/")
    print(f"/credits/ Status: {credits_resp.status_code}, Balance: {credits_resp.data['balance']}")
    assert credits_resp.status_code == 200
    assert credits_resp.data["balance"] == 10

    # Step 7: Check Duration Restrictions (10s allowed, 30s/60s locked)
    print("\n[Step 7] Checking Free Tier Limits (10s allowed, 30s locked, 60s locked)...")
    # 30s generation attempt
    resp30 = client.post(
        "/api/video/projects/",
        {"title": "30s Attempt", "prompt": "A test prompt.", "duration": 30, "aspect_ratio": "16:9"},
        format="json",
    )
    print(f"30s Project Create Status: {resp30.status_code} ({resp30.data.get('detail')})")
    assert resp30.status_code == 400
    assert "10 seconds" in resp30.data["detail"]

    # 10s generation attempt
    resp10 = client.post(
        "/api/video/projects/",
        {"title": "10s Allowed", "prompt": "A quick 10s story.", "duration": 10, "aspect_ratio": "9:16"},
        format="json",
    )
    print(f"10s Project Create Status: {resp10.status_code} (Project ID: {resp10.data.get('id')})")
    assert resp10.status_code == 201

    # Step 8: Click the SAME email activation link again
    print("\n[Step 8] Reusing Same Activation Link...")
    reuse_resp = client.post(
        "/api/video/auth/verify-email/",
        {"token": token_str},
        format="json",
    )
    print(f"Reuse Status: {reuse_resp.status_code}")
    print(f"Reuse Data: {reuse_resp.data}")
    assert reuse_resp.status_code == 400, f"Expected 400, got {reuse_resp.status_code}"
    assert reuse_resp.data["detail"] == "This verification link has already been used."

    # Confirm NO duplicate credits granted
    account.refresh_from_db()
    # Note: 10 credits were granted, 10 were reserved for the 10s video creation in step 7, balance is 0.
    total_grants = CreditTransaction.objects.filter(account=account, kind=CreditTransaction.Kind.GRANT).count()
    print(f"Total Grant Transactions in Ledger: {total_grants}")
    assert total_grants == 1, f"Expected exactly 1 grant transaction, found {total_grants}!"

    print("\n" + "=" * 60)
    print("ALL MANUAL END-TO-END VERIFICATION CHECKS PASSED PERFECTLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_e2e_manual_flow()
