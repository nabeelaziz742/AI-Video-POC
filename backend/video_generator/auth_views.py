import secrets
from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing import ensure_subscription
from .credits import get_or_create_credit_account, grant_free_allowance
from .models import EmailVerificationToken
from .rate_limit import allow_request, rate_limited_response


DISPOSABLE_EMAIL_DOMAINS = {
    "mailinator.com",
    "10minutemail.com",
    "tempmail.com",
    "guerrillamail.com",
    "sharklasers.com",
    "yopmail.com",
    "trashmail.com",
    "dispostable.com",
    "getairmail.com",
    "temp-mail.org",
    "fakeinbox.com",
    "mytemp.email",
    "throwawaymail.com",
}


class UserSerializer(serializers.ModelSerializer):
    plan_code = serializers.SerializerMethodField()
    credits_balance = serializers.SerializerMethodField()
    email_verified = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "is_staff",
            "is_superuser",
            "is_active",
            "plan_code",
            "credits_balance",
            "email_verified",
        ]
        read_only_fields = [
            "id",
            "is_staff",
            "is_superuser",
            "is_active",
            "plan_code",
            "credits_balance",
            "email_verified",
        ]

    def get_plan_code(self, obj):
        sub = getattr(obj, "subscription", None)
        return sub.plan_code if sub else "free"

    def get_credits_balance(self, obj):
        acc = getattr(obj, "credit_account", None)
        return acc.balance if acc else 0

    def get_email_verified(self, obj):
        return bool(obj.is_active)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFTokenView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not allow_request(request, "signup", limit=10, window=60):
            return rate_limited_response()

        username = str(request.data.get("username", "")).strip()
        email = str(request.data.get("email", "")).strip().lower()
        password = str(request.data.get("password", ""))

        if len(username) < 3:
            return Response(
                {"detail": "Username must be at least 3 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not email:
            return Response(
                {"detail": "Email address is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # One email address = one account
        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {"detail": "Email already exists. Please sign in instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Username uniqueness
        if User.objects.filter(username__iexact=username).exists():
            return Response(
                {"detail": "Username already exists. Please choose another username."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Disposable email check
        domain = email.split("@")[-1] if "@" in email else ""
        if domain in DISPOSABLE_EMAIL_DOMAINS:
            return Response(
                {"detail": "Disposable or temporary email addresses are not permitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Password strength validation via Django framework
        temp_user = User(username=username, email=email)
        try:
            validate_password(password, user=temp_user)
        except DjangoValidationError:
            return Response(
                {"detail": "Password is too weak. Please choose a stronger password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create unverified user
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_active = False
        user.save(update_fields=["is_active"])

        # Setup subscription & credit account (with 0 initial balance until verified)
        ensure_subscription(user)
        get_or_create_credit_account(user)

        # Generate single-use expiring email verification token
        token_str = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=24)
        token_obj = EmailVerificationToken.objects.create(
            user=user,
            token=token_str,
            expires_at=expires_at,
        )

        return Response(
            {
                "message": (
                    "Account created. Please check your email to verify your address "
                    "and activate your 10 Free credits."
                ),
                "email": email,
                "verification_token": token_obj.token,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = str(request.data.get("token", "")).strip() or str(request.query_params.get("token", "")).strip()
        if not token_str:
            return Response(
                {"detail": "Verification token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_obj = EmailVerificationToken.objects.filter(token=token_str).first()
        if not token_obj or token_obj.expires_at < timezone.now():
            return Response(
                {"detail": "Invalid or expired verification token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if token_obj.used_at is not None:
            return Response(
                {"detail": "This verification token has already been used."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Activate user
        user = token_obj.user
        token_obj.used_at = timezone.now()
        token_obj.save(update_fields=["used_at"])

        user.is_active = True
        user.save(update_fields=["is_active"])

        # Grant 10 Free credits post-verification
        grant_free_allowance(user)

        # Auto-login the verified user
        login(request, user)

        return Response(
            {
                "message": "Email verified successfully! 10 Free credits have been granted to your account.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )

    def get(self, request):
        return self.post(request)


class ResendVerificationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not allow_request(request, "resend-verify", limit=5, window=300):
            return rate_limited_response()

        email = str(request.data.get("email", "")).strip().lower()
        if not email and request.user.is_authenticated:
            email = request.user.email

        if not email:
            return Response(
                {"detail": "Email address is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response(
                {"message": "If an account exists with this email, a verification link has been sent."},
                status=status.HTTP_200_OK,
            )

        if user.is_active:
            return Response(
                {"detail": "This email is already verified. Please sign in."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Invalidate past unused tokens
        EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).update(
            used_at=timezone.now()
        )

        token_str = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=24)
        token_obj = EmailVerificationToken.objects.create(
            user=user,
            token=token_str,
            expires_at=expires_at,
        )

        return Response(
            {
                "message": "A new verification email has been sent.",
                "verification_token": token_obj.token,
            },
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not allow_request(request, "login", limit=20, window=60):
            return rate_limited_response()

        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", ""))

        # Check if user exists by username or email
        user_candidate = (
            User.objects.filter(username__iexact=username).first()
            or User.objects.filter(email__iexact=username).first()
        )

        if user_candidate and not user_candidate.check_password(password):
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user_candidate and not user_candidate.is_active:
            return Response(
                {"detail": "Please verify your email address to activate your account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user = authenticate(
            request,
            username=user_candidate.username if user_candidate else username,
            password=password,
        )
        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            return Response(
                {"detail": "Please verify your email address to activate your account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        login(request, user)
        return Response({"user": UserSerializer(user).data})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"user": UserSerializer(request.user).data})
