from django.urls import path
from .admin_views import (
    AdminProjectsView,
    AdminStatsView,
    AdminSystemHealthView,
    AdminUserCreditsView,
    AdminUsersView,
)
from .ai_views import (
    CharacterReferenceView,
    ProjectAssembleView,
    SceneGenerateView,
    SceneRegenerateView,
    SceneStatusView,
)
from .auth_views import (
    CSRFTokenView,
    LoginView,
    LogoutView,
    MeView,
    ResendVerificationView,
    SignupView,
    VerifyEmailView,
)
from .billing_views import (
    BillingWebhookView,
    PlansView,
    SubscriptionChangeView,
    SubscriptionView,
)
from .health import HealthCheckView, ReadinessCheckView
from .views import (
    CreditBalanceView,
    UsageSummaryView,
    VideoProjectCreateView,
    VideoProjectStatusView,
    VideoProjectVersionsView,
)
from .workspace_views import (
    WorkspaceDetailView,
    WorkspaceListCreateView,
    WorkspaceMemberDetailView,
    WorkspaceMemberListCreateView,
)

urlpatterns = [
    # Health checks
    path("health/", HealthCheckView.as_view()),
    path("health/live/", HealthCheckView.as_view()),
    path("health/ready/", ReadinessCheckView.as_view()),

    # Auth
    path("auth/csrf/", CSRFTokenView.as_view()),
    path("auth/signup/", SignupView.as_view()),
    path("auth/verify-email/", VerifyEmailView.as_view()),
    path("auth/resend-verification/", ResendVerificationView.as_view()),
    path("auth/login/", LoginView.as_view()),
    path("auth/logout/", LogoutView.as_view()),
    path("auth/me/", MeView.as_view()),

    # Workspaces & Multi-Tenancy
    path("workspaces/", WorkspaceListCreateView.as_view()),
    path("workspaces/<int:workspace_id>/", WorkspaceDetailView.as_view()),
    path("workspaces/<int:workspace_id>/members/", WorkspaceMemberListCreateView.as_view()),
    path("workspaces/<int:workspace_id>/members/<int:member_id>/", WorkspaceMemberDetailView.as_view()),

    # Credits & Usage
    path("credits/", CreditBalanceView.as_view()),
    path("usage/", UsageSummaryView.as_view()),

    # Billing
    path("billing/plans/", PlansView.as_view()),
    path("billing/subscription/", SubscriptionView.as_view()),
    path("billing/subscription/change/", SubscriptionChangeView.as_view()),
    path("billing/webhook/", BillingWebhookView.as_view()),

    # Projects & Generation
    path("projects/", VideoProjectCreateView.as_view()),
    path("projects/<int:project_id>/versions/", VideoProjectVersionsView.as_view()),
    path("projects/<int:project_id>/status/", VideoProjectStatusView.as_view()),
    path("projects/<int:project_id>/characters/<int:character_id>/reference/", CharacterReferenceView.as_view()),
    path("projects/<int:project_id>/scenes/<int:scene_id>/generate/", SceneGenerateView.as_view()),
    path("projects/<int:project_id>/scenes/<int:scene_id>/regenerate/", SceneRegenerateView.as_view()),
    path("projects/<int:project_id>/scenes/<int:scene_id>/status/", SceneStatusView.as_view()),
    path("projects/<int:project_id>/assemble/", ProjectAssembleView.as_view()),

    # Admin Infrastructure Endpoints
    path("admin/stats/", AdminStatsView.as_view()),
    path("admin/users/", AdminUsersView.as_view()),
    path("admin/users/<int:user_id>/credits/", AdminUserCreditsView.as_view()),
    path("admin/projects/", AdminProjectsView.as_view()),
    path("admin/system/", AdminSystemHealthView.as_view()),
]