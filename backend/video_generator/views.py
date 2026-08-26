from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import VideoProject
from .serializers import VideoProjectSerializer
from .services import JSON2VideoService


class VideoProjectCreateView(APIView):

    def post(self, request):
        title = request.data.get("title", "Untitled Video")
        prompt = request.data.get("prompt")
        input_type = request.data.get("input_type", "story")

        if not prompt:
            return Response(
                {"detail": "Prompt or script is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = VideoProject.objects.create(
            title=title,
            prompt=prompt,
            input_type=input_type,
            aspect_ratio=request.data.get("aspect_ratio", "9:16"),
            duration=int(request.data.get("duration", 10)),
            status=VideoProject.Status.PROCESSING,
        )

        movie_payload = {
            "width": 1080,
            "height": 1920,
            "scenes": [
                {
                    "duration": project.duration,
                    "elements": [
                        {
                            "type": "text",
                            "text": prompt,
                            "style": "001",
                        }
                    ],
                }
            ],
            "client-data": {
                "project_id": project.id,
            },
        }

        try:
            service = JSON2VideoService()

            result = service.create_movie(movie_payload)

            project.provider_project_id = result["project"]
            project.save(
                update_fields=[
                    "provider_project_id",
                    "updated_at",
                ]
            )

            return Response(
                VideoProjectSerializer(project).data,
                status=status.HTTP_201_CREATED,
            )

        except Exception as exc:
            project.status = VideoProject.Status.FAILED
            project.error_message = str(exc)
            project.save()

            return Response(
                {
                    "detail": "Video generation failed.",
                    "error": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )


class VideoProjectStatusView(APIView):

    def get(self, request, project_id):
        try:
            project = VideoProject.objects.get(
                id=project_id
            )
        except VideoProject.DoesNotExist:
            return Response(
                {"detail": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if project.provider_project_id:
            service = JSON2VideoService()

            result = service.get_movie(
                project.provider_project_id
            )

            movie = result.get("movie", {})

            provider_status = movie.get("status")

            if provider_status == "done":
                project.status = VideoProject.Status.COMPLETED
                project.video_url = movie.get("url")
                project.save()

            elif provider_status in ["error", "timeout"]:
                project.status = VideoProject.Status.FAILED
                project.error_message = movie.get(
                    "message",
                    "Video generation failed.",
                )
                project.save()

            else:
                project.status = VideoProject.Status.PROCESSING
                project.save()

        return Response(
            VideoProjectSerializer(project).data
        )