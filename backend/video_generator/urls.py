from django.urls import path

from .ai_views import CharacterReferenceView, ProjectAssembleView, SceneGenerateView, SceneRegenerateView, SceneStatusView
from .auth_views import CSRFTokenView, LoginView, LogoutView, MeView, SignupView
from .health import HealthCheckView
from .views import VideoProjectCreateView, VideoProjectStatusView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("auth/csrf/", CSRFTokenView.as_view(), name="csrf-token"),
    path("auth/signup/", SignupView.as_view(), name="signup"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("projects/", VideoProjectCreateView.as_view(), name="video-projects"),
    path("projects/<int:project_id>/status/", VideoProjectStatusView.as_view(), name="video-project-status"),
    path("projects/<int:project_id>/characters/<int:character_id>/reference/", CharacterReferenceView.as_view(), name="character-reference"),
    path("projects/<int:project_id>/scenes/<int:scene_id>/generate/", SceneGenerateView.as_view(), name="scene-generate"),
    path("projects/<int:project_id>/scenes/<int:scene_id>/regenerate/", SceneRegenerateView.as_view(), name="scene-regenerate"),
    path("projects/<int:project_id>/scenes/<int:scene_id>/status/", SceneStatusView.as_view(), name="scene-status"),
    path("projects/<int:project_id>/assemble/", ProjectAssembleView.as_view(), name="project-assemble"),
]
