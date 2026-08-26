from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Character, VideoProject, VideoScene
from .scene_planner import build_scene_plan, get_dimensions, validate_generation_options
from .serializers import VideoProjectSerializer
from .services import JSON2VideoService


class VideoProjectCreateView(APIView):
    def post(self, request):
        title = str(request.data.get("title", "Untitled Video")).strip() or "Untitled Video"
        prompt = str(request.data.get("prompt", "")).strip()
        input_type = request.data.get("input_type", "story")
        aspect_ratio = request.data.get("aspect_ratio", "9:16")
        characters_input = request.data.get("characters", [])

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
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if input_type not in VideoProject.InputType.values:
            return Response(
                {"detail": "input_type must be story or script."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if characters_input and not isinstance(characters_input, list):
            return Response(
                {"detail": "characters must be an array of character objects."},
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

            characters = []
            for item in characters_input:
                if not isinstance(item, dict) or not str(item.get("name", "")).strip():
                    return Response(
                        {"detail": "Each character must have a name."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                characters.append(
                    Character.objects.create(
                        project=project,
                        name=str(item["name"]).strip(),
                        role=str(item.get("role", "")).strip(),
                        age_description=str(item.get("age_description", "")).strip(),
                        appearance=str(item.get("appearance", "")).strip(),
                        clothing=str(item.get("clothing", "")).strip(),
                        personality=str(item.get("personality", "")).strip(),
                        description=str(item.get("description", "")).strip(),
                        visual_prompt=str(item.get("visual_prompt", "")).strip(),
                        reference_image_url=item.get("reference_image_url") or None,
                    )
                )

            character_block = ""
            if characters:
                character_block = (
                    "\nCharacter continuity requirements:\n"
                    + "\n".join(
                        f"- {character.consistency_prompt}" for character in characters
                    )
                    + "\nKeep every recurring character visually consistent across all scenes."
                )

            scenes = []
            for scene in scene_plan:
                scenes.append(
                    VideoScene(
                        project=project,
                        scene_number=scene["scene_number"],
                        duration=scene["duration"],
                        prompt=scene["prompt"] + character_block,
                    )
                )
            VideoScene.objects.bulk_create(scenes)

            if characters:
                for scene in project.scenes.all():
                    scene.characters.set(characters)

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

            return Response(VideoProjectSerializer(project).data, status=status.HTTP_201_CREATED)
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
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

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
