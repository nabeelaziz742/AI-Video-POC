from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Character, VideoProject, VideoScene
from .scene_planner import build_scene_plan, validate_generation_options
from .serializers import VideoProjectSerializer


class VideoProjectCreateView(APIView):
    """Create the project plan only; expensive AI rendering starts explicitly per scene."""

    def post(self, request):
        title = str(request.data.get("title", "Untitled Video")).strip() or "Untitled Video"
        prompt = str(request.data.get("prompt", "")).strip()
        input_type = request.data.get("input_type", "story")
        aspect_ratio = request.data.get("aspect_ratio", "9:16")
        characters_input = request.data.get("characters", [])

        if not prompt:
            return Response({"detail": "Prompt or script is required."}, status=status.HTTP_400_BAD_REQUEST)
        if input_type not in VideoProject.InputType.values:
            return Response({"detail": "input_type must be story or script."}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(characters_input, list) or not characters_input:
            return Response(
                {"detail": "At least one recurring character is required for AI character video generation."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            duration, aspect_ratio = validate_generation_options(
                request.data.get("duration", 10), aspect_ratio
            )
            scene_plan = build_scene_plan(prompt, duration)
            normalized_characters = []
            for item in characters_input:
                if not isinstance(item, dict) or not str(item.get("name", "")).strip():
                    raise ValueError("Each character must have a name.")
                normalized_characters.append(item)
        except (TypeError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            project = VideoProject.objects.create(
                title=title,
                prompt=prompt,
                input_type=input_type,
                aspect_ratio=aspect_ratio,
                duration=duration,
                status=VideoProject.Status.QUEUED,
                provider="fal_pixverse_c1",
            )

            characters = []
            for item in normalized_characters:
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

            character_block = (
                "\nCharacter continuity: "
                + "; ".join(character.consistency_prompt for character in characters)
                + ". Keep recurring characters visually identical across scenes."
            )
            scenes = [
                VideoScene(
                    project=project,
                    scene_number=scene["scene_number"],
                    duration=scene["duration"],
                    prompt=scene["prompt"] + character_block,
                )
                for scene in scene_plan
            ]
            VideoScene.objects.bulk_create(scenes)
            for scene in project.scenes.all():
                scene.characters.set(characters)

        return Response(VideoProjectSerializer(project).data, status=status.HTTP_201_CREATED)


class VideoProjectStatusView(APIView):
    def get(self, request, project_id):
        try:
            project = VideoProject.objects.get(id=project_id)
        except VideoProject.DoesNotExist:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        # Final assembly is polled only after ProjectAssembleView has stored a provider project id.
        if project.provider_project_id and project.provider == "json2video":
            from .services import JSON2VideoService

            try:
                result = JSON2VideoService().get_movie(project.provider_project_id)
                movie = result.get("movie", {})
                provider_status = movie.get("status")
                if provider_status == "done":
                    project.status = VideoProject.Status.COMPLETED
                    project.video_url = movie.get("url")
                    project.save(update_fields=["status", "video_url", "updated_at"])
                elif provider_status in {"error", "timeout"}:
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
