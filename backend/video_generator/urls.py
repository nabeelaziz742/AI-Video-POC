from django.urls import path
from .ai_views import CharacterReferenceView, ProjectAssembleView, SceneGenerateView, SceneRegenerateView, SceneStatusView
from .auth_views import CSRFTokenView, LoginView, LogoutView, MeView, SignupView
from .billing_views import BillingWebhookView, PlansView, SubscriptionChangeView, SubscriptionView
from .health import HealthCheckView
from .views import CreditBalanceView, UsageSummaryView, VideoProjectCreateView, VideoProjectStatusView, VideoProjectVersionsView
urlpatterns=[
 path("health/",HealthCheckView.as_view()), path("auth/csrf/",CSRFTokenView.as_view()), path("auth/signup/",SignupView.as_view()), path("auth/login/",LoginView.as_view()), path("auth/logout/",LogoutView.as_view()), path("auth/me/",MeView.as_view()),
 path("credits/",CreditBalanceView.as_view()), path("usage/",UsageSummaryView.as_view()), path("billing/plans/",PlansView.as_view()), path("billing/subscription/",SubscriptionView.as_view()), path("billing/subscription/change/",SubscriptionChangeView.as_view()), path("billing/webhook/",BillingWebhookView.as_view()),
 path("projects/",VideoProjectCreateView.as_view()), path("projects/<int:project_id>/versions/",VideoProjectVersionsView.as_view()), path("projects/<int:project_id>/status/",VideoProjectStatusView.as_view()), path("projects/<int:project_id>/characters/<int:character_id>/reference/",CharacterReferenceView.as_view()), path("projects/<int:project_id>/scenes/<int:scene_id>/generate/",SceneGenerateView.as_view()), path("projects/<int:project_id>/scenes/<int:scene_id>/regenerate/",SceneRegenerateView.as_view()), path("projects/<int:project_id>/scenes/<int:scene_id>/status/",SceneStatusView.as_view()), path("projects/<int:project_id>/assemble/",ProjectAssembleView.as_view())]