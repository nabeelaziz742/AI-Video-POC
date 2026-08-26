from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import VideoProject, VideoScene
from .scene_planner import build_scene_plan, get_dimensions, validate_generation_options
from .serializers import VideoProjectSerializer
from .services import JSON2VideoService


class VideoProjectCreateView(APIView):
    def post(self, request):
        title = str(request.data.get("title", "Untitled Video")).strip() or "Untitled Video"
        prompt = str(request.data.get("prompt", "")).strip()
        input_type = request.data.get("input_type", "story")
        aspect_ratio = request.data.get("aspect_ratio", "9:16")

        if not prompt:
            return Response(
                {"detail": "Prompt or script is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            duration, aspect_ratio = validate_generation_options(
                request.data.get("duration", 10), aspect_ratio
            )
        except (TypeError, ValueError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if input_type not in VideoProject.InputType.values:
            return Response(
                {"detail": "input_type must be story or script."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        width, height = get_dimensions(aspect_ratio)
        scene_plan = build_scene_plan(prompt, duration)

        with transaction.atomic():
            project = VideoProject.objects.create(
                title=title,
                prompt=prompt,
                input_type=input_type,
                aspect_ratio=aspect_ratio,
                duration=duration,
                status=VideoProject.Status.PROCESSING,
            )

            VideoScene.objects.bulk_create(
                [
                    VideoScene(
                        project=project,
                        scene_number=scene["scene_number"],
                        duration=scene["duration"],
                        prompt=scene["prompt"],
                    )
                    for scene in scene_plan
                ]
            )

        # JSON2Video remains the current rendering fallback. The scene layer is
        # provider-neutral so a real AI video provider can replace this later.
        movie_payload = {
            "width": width,
            "height": height,
            "scenes": [
                {
                    "duration": scene.duration,
                    "elements": [
                        {
                            "type": "text",
                            "text": scene.prompt,
                            "style": "001",
                        }
                    ],
                }
                for scene in project.scenes.all()
            ],
            "client-data": {"project_id": project.id},
        }

        try:
            service = JSON2VideoService()
            result = service.create_movie(movie_payload)

            project.provider_project_id = result["project"]
            project.save(update_fields=["provider_project_id", "updated_at"])

            return Response(
                VideoProjectSerializer(project).data,
                status=status.HTTP_201_CREATED,
            )

        except Exception as exc:
            project.status = VideoProject.Status.FAILED
            project.error_message = str(exc)
            project.save(update_fields=["status", "error_message", "updated_at"])

            return Response(
                {"detail": "Video generation failed.", "error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class VideoProjectStatusView(APIView):
    def get(self, request, project_id):
        try:
            project = VideoProject.objects.get(id=project_id)
        except VideoProject.DoesNotExist:
            return Response(
                {"detail": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if project.provider_project_id:
            try:
                service = JSON2VideoService()
                result = service.get_movie(project.provider_project_id)
                movie = result.get("movie", {})
                provider_status = movie.get("status")

                if provider_status == "done":
                    project.status = VideoProject.Status.COMPLETED
                    project.video_url = movie.get("url")
                    project.save(update_fields=["status", "video_url", "updated_at"])
                elif provider_status in ["error", "timeout"]:
                    project.status = VideoProject.Status.FAILED
                    project.error_message = movie.get("message", "Video generation failed.")
                    project.save(update_fields=["status", "error_message", "updated_at"])
                else:
                    project.status = VideoProject.Status.PROCESSING
                    project.save(update_fields=["status", "updated_at"])
            except Exception as exc:
                project.status = VideoProject.Status.FAILED
                project.error_message = str(exc)
                project.save(update_fields=["status", "error_message", "updated_at"])

        return Response(VideoProjectSerializer(project).data)
