import logging
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from rest_framework.exceptions import PermissionDenied

from .models import VideoProject, Workspace, WorkspaceMembership

logger = logging.getLogger("video_generator")
User = get_user_model()

ROLE_HIERARCHY = {
    WorkspaceMembership.Role.VIEWER: 1,
    WorkspaceMembership.Role.EDITOR: 2,
    WorkspaceMembership.Role.ADMIN: 3,
    WorkspaceMembership.Role.OWNER: 4,
}


def get_or_create_personal_workspace(user) -> Workspace:
    """
    Returns the user's personal workspace, creating it (and an OWNER membership)
    atomically if it does not yet exist.
    """
    with transaction.atomic():
        workspace = Workspace.objects.filter(owner=user, is_personal=True).first()
        if not workspace:
            workspace = Workspace.objects.create(
                name=f"{user.username}'s Workspace",
                owner=user,
                is_personal=True,
            )
        WorkspaceMembership.objects.get_or_create(
            workspace=workspace,
            user=user,
            defaults={"role": WorkspaceMembership.Role.OWNER},
        )
        return workspace


def get_user_workspaces(user):
    """Returns all workspaces where the user is an owner or has active membership."""
    return Workspace.objects.filter(
        Q(owner=user) | Q(memberships__user=user)
    ).distinct().order_by("-is_personal", "-created_at")


def get_user_workspace_role(user, workspace: Workspace) -> str | None:
    """Returns the user's highest role string in the given workspace, or None."""
    if not user or not user.is_authenticated:
        return None
    if workspace.owner_id == user.pk:
        return WorkspaceMembership.Role.OWNER
    membership = WorkspaceMembership.objects.filter(workspace=workspace, user=user).first()
    return membership.role if membership else None


def user_has_workspace_role(user, workspace: Workspace, min_role: str = WorkspaceMembership.Role.VIEWER) -> bool:
    """Evaluates whether the user satisfies the minimum role requirement in the workspace."""
    if not user or not user.is_authenticated:
        return False
    user_role = get_user_workspace_role(user, workspace)
    if not user_role:
        return False
    return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(min_role, 0)


def ensure_project_workspace(project: VideoProject) -> Workspace:
    """Ensures legacy or unassigned projects have a valid workspace."""
    if project.workspace_id:
        return project.workspace
    if project.user_id:
        workspace = get_or_create_personal_workspace(project.user)
        project.workspace = workspace
        project.save(update_fields=["workspace", "updated_at"])
        return workspace
    raise Http404("Project has no assigned workspace.")


def get_workspace_project_for_user(user, project_id: int, min_role: str = WorkspaceMembership.Role.VIEWER) -> VideoProject:
    """
    Securely resolves a VideoProject by ID with strict workspace isolation.
    - If the project does not exist, or the user is not a member of its workspace: raises 404 (IDOR guard).
    - If the user is a member but lacks the required permission: raises 403 (PermissionDenied).
    """
    try:
        project = VideoProject.objects.select_related("workspace", "workspace__owner", "user").prefetch_related("characters", "scenes").get(id=project_id)
    except VideoProject.DoesNotExist:
        raise Http404("Project not found.")

    workspace = ensure_project_workspace(project)

    user_role = get_user_workspace_role(user, workspace)
    if not user_role:
        # IDOR guard: Do not leak existence of other workspaces' projects
        raise Http404("Project not found.")

    if ROLE_HIERARCHY.get(user_role, 0) < ROLE_HIERARCHY.get(min_role, 0):
        raise PermissionDenied("You do not have sufficient permissions to perform this action in this workspace.")

    return project
