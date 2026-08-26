from django.urls import path

from .ai_views import (
    CharacterReferenceView,
    ProjectAssembleView,
    SceneGenerateView,
    SceneStatusView,
)
from .views import VideoProjectCreateView, VideoProjectStatusView


urlpatterns = [
    path("projects/", VideoProjectCreateView.as_view(), name="video-project-create"),
    path(
        "projects/<int:project_id>/status/",
        VideoProjectStatusView.as_view(),
        name="video-project-status",
    ),
    path(
        "projects/<int:project_id>/characters/<int:character_id>/reference/",
        CharacterReferenceView.as_view(),
        name="character-reference",
    ),
    path(
        "projects/<int:project_id>/scenes/<int:scene_id>/generate/",
        SceneGenerateView.as_view(),
        name="scene-generate",
    ),
    path(
        "projects/<int:project_id>/scenes/<int:scene_id>/status/",
        SceneStatusView.as_view(),
        name="scene-status",
    ),
    path(
        "projects/<int:project_id>/assemble/",
        ProjectAssembleView.as_view(),
        name="project-assemble",
    ),
]
