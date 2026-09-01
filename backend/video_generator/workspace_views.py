from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing import ensure_subscription, get_plan
from .models import Workspace, WorkspaceMembership
from .serializers import WorkspaceMembershipSerializer, WorkspaceSerializer
from .workspaces import (
    get_or_create_personal_workspace,
    get_user_workspace_role,
    get_user_workspaces,
    user_has_workspace_role,
)

User = get_user_model()


class WorkspaceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Ensure user has their personal workspace
        get_or_create_personal_workspace(request.user)
        workspaces = get_user_workspaces(request.user)
        serializer = WorkspaceSerializer(workspaces, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        name = str(request.data.get("name", "")).strip()
        if not name:
            return Response({"detail": "Workspace name is required."}, status=status.HTTP_400_BAD_REQUEST)
        if len(name) > 100:
            return Response({"detail": "Workspace name cannot exceed 100 characters."}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce plan workspace limits
        subscription = ensure_subscription(request.user)
        plan = get_plan(subscription.plan_code)
        owned_custom_workspaces = Workspace.objects.filter(owner=request.user, is_personal=False).count()
        # Personal workspace is 1; additional custom workspaces allowed by plan
        max_custom = max(0, plan.max_workspaces - 1)
        if owned_custom_workspaces >= max_custom and plan.max_workspaces <= 1:
            return Response(
                {"detail": f"Your {plan.name} plan does not support creating additional team workspaces. Upgrade your plan to create team workspaces."},
                status=status.HTTP_403_FORBIDDEN
            )
        elif owned_custom_workspaces >= plan.max_workspaces:
            return Response(
                {"detail": f"Your {plan.name} plan supports up to {plan.max_workspaces} workspaces. Upgrade your plan to create more workspaces."},
                status=status.HTTP_403_FORBIDDEN
            )

        with transaction.atomic():
            workspace = Workspace.objects.create(
                name=name,
                owner=request.user,
                is_personal=False,
            )
            WorkspaceMembership.objects.create(
                workspace=workspace,
                user=request.user,
                role=WorkspaceMembership.Role.OWNER,
            )
        serializer = WorkspaceSerializer(workspace, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WorkspaceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_workspace(self, request, workspace_id: int, min_role: str = WorkspaceMembership.Role.VIEWER):
        workspace = get_object_or_404(Workspace, id=workspace_id)
        if not user_has_workspace_role(request.user, workspace, min_role=min_role):
            if not get_user_workspace_role(request.user, workspace):
                raise get_object_or_404(Workspace, id=-1)  # 404 for non-members
            raise PermissionDenied("Insufficient permissions in this workspace.")
        return workspace

    def get(self, request, workspace_id):
        workspace = self.get_workspace(request, workspace_id, min_role=WorkspaceMembership.Role.VIEWER)
        return Response(WorkspaceSerializer(workspace, context={"request": request}).data)

    def patch(self, request, workspace_id):
        workspace = self.get_workspace(request, workspace_id, min_role=WorkspaceMembership.Role.ADMIN)
        name = str(request.data.get("name", "")).strip()
        if not name:
            return Response({"detail": "Workspace name cannot be blank."}, status=status.HTTP_400_BAD_REQUEST)
        workspace.name = name
        workspace.save(update_fields=["name", "updated_at"])
        return Response(WorkspaceSerializer(workspace, context={"request": request}).data)

    def delete(self, request, workspace_id):
        workspace = self.get_workspace(request, workspace_id, min_role=WorkspaceMembership.Role.OWNER)
        if workspace.is_personal:
            return Response({"detail": "Cannot delete your personal workspace."}, status=status.HTTP_400_BAD_REQUEST)
        workspace.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceMemberListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_workspace(self, request, workspace_id: int, min_role: str = WorkspaceMembership.Role.VIEWER):
        workspace = get_object_or_404(Workspace, id=workspace_id)
        if not user_has_workspace_role(request.user, workspace, min_role=min_role):
            if not get_user_workspace_role(request.user, workspace):
                raise get_object_or_404(Workspace, id=-1)
            raise PermissionDenied("Insufficient permissions in this workspace.")
        return workspace

    def get(self, request, workspace_id):
        workspace = self.get_workspace(request, workspace_id, min_role=WorkspaceMembership.Role.VIEWER)
        members = workspace.memberships.select_related("user").order_by("created_at")
        return Response(WorkspaceMembershipSerializer(members, many=True).data)

    def post(self, request, workspace_id):
        workspace = self.get_workspace(request, workspace_id, min_role=WorkspaceMembership.Role.ADMIN)
        identifier = str(request.data.get("username_or_email", request.data.get("email", request.data.get("username", "")))).strip()
        role = str(request.data.get("role", WorkspaceMembership.Role.VIEWER)).lower().strip()

        if not identifier:
            return Response({"detail": "Username or email is required."}, status=status.HTTP_400_BAD_REQUEST)
        if role not in WorkspaceMembership.Role.values or role == WorkspaceMembership.Role.OWNER:
            return Response({"detail": f"Role must be one of: {WorkspaceMembership.Role.ADMIN}, {WorkspaceMembership.Role.EDITOR}, {WorkspaceMembership.Role.VIEWER}"}, status=status.HTTP_400_BAD_REQUEST)

        target_user = User.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier)).first()
        if not target_user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if target_user.pk == workspace.owner_id:
            return Response({"detail": "Workspace owner already has full access."}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce plan team member limits for new memberships
        if not workspace.memberships.filter(user=target_user).exists():
            owner_sub = ensure_subscription(workspace.owner)
            plan = get_plan(owner_sub.plan_code)
            current_members_count = workspace.memberships.count()
            if current_members_count >= plan.max_team_members:
                return Response(
                    {"detail": f"Your {plan.name} plan supports up to {plan.max_team_members} team member(s). Upgrade your plan to invite more members."},
                    status=status.HTTP_403_FORBIDDEN
                )

        with transaction.atomic():
            membership, created = WorkspaceMembership.objects.get_or_create(
                workspace=workspace,
                user=target_user,
                defaults={"role": role},
            )
            if not created:
                membership.role = role
                membership.save(update_fields=["role", "updated_at"])

        return Response(WorkspaceMembershipSerializer(membership).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)



class WorkspaceMemberDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, workspace_id, member_id):
        workspace = get_object_or_404(Workspace, id=workspace_id)
        if not user_has_workspace_role(request.user, workspace, min_role=WorkspaceMembership.Role.ADMIN):
            if not get_user_workspace_role(request.user, workspace):
                raise get_object_or_404(Workspace, id=-1)
            raise PermissionDenied("Insufficient permissions in this workspace.")

        membership = get_object_or_404(WorkspaceMembership.objects.select_related("user"), id=member_id, workspace=workspace)
        if membership.user_id == workspace.owner_id:
            return Response({"detail": "Cannot change the workspace owner's role."}, status=status.HTTP_400_BAD_REQUEST)

        new_role = str(request.data.get("role", "")).lower().strip()
        if new_role not in WorkspaceMembership.Role.values or new_role == WorkspaceMembership.Role.OWNER:
            return Response({"detail": f"Role must be one of: {WorkspaceMembership.Role.ADMIN}, {WorkspaceMembership.Role.EDITOR}, {WorkspaceMembership.Role.VIEWER}"}, status=status.HTTP_400_BAD_REQUEST)

        membership.role = new_role
        membership.save(update_fields=["role", "updated_at"])
        return Response(WorkspaceMembershipSerializer(membership).data)

    def delete(self, request, workspace_id, member_id):
        workspace = get_object_or_404(Workspace, id=workspace_id)
        membership = get_object_or_404(WorkspaceMembership.objects.select_related("user"), id=member_id, workspace=workspace)

        if membership.user_id == workspace.owner_id:
            return Response({"detail": "Cannot remove the workspace owner."}, status=status.HTTP_400_BAD_REQUEST)

        # Allow user to remove themselves, or require ADMIN/OWNER permission
        is_self = membership.user_id == request.user.id
        if not is_self and not user_has_workspace_role(request.user, workspace, min_role=WorkspaceMembership.Role.ADMIN):
            if not get_user_workspace_role(request.user, workspace):
                raise get_object_or_404(Workspace, id=-1)
            raise PermissionDenied("Insufficient permissions in this workspace.")

        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
