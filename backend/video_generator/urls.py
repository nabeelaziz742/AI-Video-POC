from django.urls import path

from .views import (
    VideoProjectCreateView,
    VideoProjectStatusView,
)


urlpatterns = [
    path(
        "projects/",
        VideoProjectCreateView.as_view(),
        name="video-project-create",
    ),
    path(
        "projects/<int:project_id>/status/",
        VideoProjectStatusView.as_view(),
        name="video-project-status",
    ),
]