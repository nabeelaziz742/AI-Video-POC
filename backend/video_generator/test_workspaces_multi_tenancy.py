from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import (
    Character,
    EmailVerificationToken,
    VideoProject,
    VideoScene,
    Workspace,
    WorkspaceMembership,
)
from .workspaces import (
    get_or_create_personal_workspace,
    get_user_workspace_role,
    get_user_workspaces,
    get_workspace_project_for_user,
    user_has_workspace_role,
)

User = get_user_model()


class WorkspaceMultiTenancyTests(TestCase):
    def setUp(self):
        self.client_a = APIClient()
        self.user_a = User.objects.create_user(username="alice", email="alice@test.com", password="Password123!")
        self.client_a.force_authenticate(user=self.user_a)

        self.client_b = APIClient()
        self.user_b = User.objects.create_user(username="bob", email="bob@test.com", password="Password123!")
        self.client_b.force_authenticate(user=self.user_b)

        self.client_c = APIClient()
        self.user_c = User.objects.create_user(username="charlie", email="charlie@test.com", password="Password123!")
        self.client_c.force_authenticate(user=self.user_c)

    def test_personal_workspace_creation_and_ownership(self):
        """Every user gets a personal workspace with role OWNER automatically."""
        ws_a = get_or_create_personal_workspace(self.user_a)
        self.assertIsNotNone(ws_a.id)
        self.assertEqual(ws_a.owner, self.user_a)
        self.assertTrue(ws_a.is_personal)

        membership = WorkspaceMembership.objects.get(workspace=ws_a, user=self.user_a)
        self.assertEqual(membership.role, WorkspaceMembership.Role.OWNER)
        self.assertEqual(get_user_workspace_role(self.user_a, ws_a), WorkspaceMembership.Role.OWNER)

    def test_user_workspaces_listing(self):
        """User only lists workspaces they own or belong to."""
        ws_a = get_or_create_personal_workspace(self.user_a)
        ws_b = get_or_create_personal_workspace(self.user_b)

        workspaces_a = get_user_workspaces(self.user_a)
        self.assertIn(ws_a, workspaces_a)
        self.assertNotIn(ws_b, workspaces_a)

        # API listing check
        resp = self.client_a.get("/api/video/workspaces/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        workspace_ids = [w["id"] for w in resp.data]
        self.assertIn(ws_a.id, workspace_ids)
        self.assertNotIn(ws_b.id, workspace_ids)

    def test_custom_team_workspace_creation(self):
        """User can create team workspaces where they become OWNER."""
        resp = self.client_a.post("/api/video/workspaces/", {"name": "Acme Creative Studio"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        ws_id = resp.data["id"]

        ws = Workspace.objects.get(id=ws_id)
        self.assertEqual(ws.name, "Acme Creative Studio")
        self.assertFalse(ws.is_personal)
        self.assertEqual(ws.owner, self.user_a)

        membership = WorkspaceMembership.objects.get(workspace=ws, user=self.user_a)
        self.assertEqual(membership.role, WorkspaceMembership.Role.OWNER)

    def test_workspace_membership_invitation_and_role_management(self):
        """Owner/Admin can add members with roles and update roles."""
        ws = Workspace.objects.create(name="Team Studio", owner=self.user_a, is_personal=False)
        WorkspaceMembership.objects.create(workspace=ws, user=self.user_a, role=WorkspaceMembership.Role.OWNER)

        # Alice invites Bob as EDITOR
        resp = self.client_a.post(f"/api/video/workspaces/{ws.id}/members/", {
            "username_or_email": "bob",
            "role": "editor",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        membership_id = resp.data["id"]

        self.assertTrue(user_has_workspace_role(self.user_b, ws, min_role=WorkspaceMembership.Role.EDITOR))

        # Alice changes Bob's role to VIEWER
        resp_patch = self.client_a.patch(f"/api/video/workspaces/{ws.id}/members/{membership_id}/", {
            "role": "viewer",
        }, format="json")
        self.assertEqual(resp_patch.status_code, status.HTTP_200_OK)
        self.assertFalse(user_has_workspace_role(self.user_b, ws, min_role=WorkspaceMembership.Role.EDITOR))
        self.assertTrue(user_has_workspace_role(self.user_b, ws, min_role=WorkspaceMembership.Role.VIEWER))

        # Bob (VIEWER) cannot invite Charlie
        resp_unauth = self.client_b.post(f"/api/video/workspaces/{ws.id}/members/", {
            "username_or_email": "charlie",
            "role": "viewer",
        }, format="json")
        self.assertEqual(resp_unauth.status_code, status.HTTP_403_FORBIDDEN)

        # Alice removes Bob
        resp_del = self.client_a.delete(f"/api/video/workspaces/{ws.id}/members/{membership_id}/")
        self.assertEqual(resp_del.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(user_has_workspace_role(self.user_b, ws, min_role=WorkspaceMembership.Role.VIEWER))

    def test_cannot_demote_or_remove_owner(self):
        """Workspace owner role cannot be modified or removed."""
        ws = Workspace.objects.create(name="Owner Test Studio", owner=self.user_a, is_personal=False)
        owner_membership = WorkspaceMembership.objects.create(workspace=ws, user=self.user_a, role=WorkspaceMembership.Role.OWNER)

        resp_patch = self.client_a.patch(f"/api/video/workspaces/{ws.id}/members/{owner_membership.id}/", {
            "role": "viewer",
        }, format="json")
        self.assertEqual(resp_patch.status_code, status.HTTP_400_BAD_REQUEST)

        resp_del = self.client_a.delete(f"/api/video/workspaces/{ws.id}/members/{owner_membership.id}/")
        self.assertEqual(resp_del.status_code, status.HTTP_400_BAD_REQUEST)

    def test_project_belongs_to_workspace(self):
        """Projects created belong to the user's workspace."""
        resp = self.client_a.post("/api/video/projects/", {
            "title": "Alice's Space Odyssey",
            "prompt": "An astronaut exploring a neon crystalline planet.",
            "duration": 10,
            "aspect_ratio": "9:16",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        project_id = resp.data["id"]

        project = VideoProject.objects.get(id=project_id)
        self.assertIsNotNone(project.workspace)
        self.assertEqual(project.workspace.owner, self.user_a)

    def test_idor_cross_workspace_project_isolation(self):
        """User B MUST NOT access or view User A's project, scenes, or characters."""
        resp_a = self.client_a.post("/api/video/projects/", {
            "title": "Secret Project A",
            "prompt": "A young hero discovering a hidden ancient sword.",
            "duration": 10,
            "aspect_ratio": "9:16",
        }, format="json")
        self.assertEqual(resp_a.status_code, status.HTTP_201_CREATED)
        project_a_id = resp_a.data["id"]

        # Bob tries to access Alice's project status -> 404 (IDOR guard)
        resp_b_get = self.client_b.get(f"/api/video/projects/{project_a_id}/status/")
        self.assertEqual(resp_b_get.status_code, status.HTTP_404_NOT_FOUND)

        # Bob tries to fetch Alice's project versions -> 404
        resp_b_versions = self.client_b.get(f"/api/video/projects/{project_a_id}/versions/")
        self.assertEqual(resp_b_versions.status_code, status.HTTP_404_NOT_FOUND)

        # Bob tries to branch version on Alice's project -> 404
        resp_b_branch = self.client_b.post(f"/api/video/projects/{project_a_id}/versions/", {
            "prompt": "Malicious prompt branch",
        }, format="json")
        self.assertEqual(resp_b_branch.status_code, status.HTTP_404_NOT_FOUND)

        # Bob tries to trigger scene generation in Alice's project -> 404
        scene_a = VideoScene.objects.filter(project_id=project_a_id).first()
        resp_b_scene = self.client_b.post(f"/api/video/projects/{project_a_id}/scenes/{scene_a.id}/generate/")
        self.assertEqual(resp_b_scene.status_code, status.HTTP_404_NOT_FOUND)

        # Bob tries to trigger character reference in Alice's project -> 404
        char_a = Character.objects.filter(project_id=project_a_id).first()
        resp_b_char = self.client_b.post(f"/api/video/projects/{project_a_id}/characters/{char_a.id}/reference/")
        self.assertEqual(resp_b_char.status_code, status.HTTP_404_NOT_FOUND)

        # Bob tries to assemble Alice's project -> 404
        resp_b_assemble = self.client_b.post(f"/api/video/projects/{project_a_id}/assemble/")
        self.assertEqual(resp_b_assemble.status_code, status.HTTP_404_NOT_FOUND)

    def test_role_enforcement_viewer_cannot_edit_or_generate(self):
        """Viewer role can read/view project status but CANNOT create versions or generate scenes."""
        ws = Workspace.objects.create(name="Collaboration Studio", owner=self.user_a, is_personal=False)
        WorkspaceMembership.objects.create(workspace=ws, user=self.user_a, role=WorkspaceMembership.Role.OWNER)
        WorkspaceMembership.objects.create(workspace=ws, user=self.user_b, role=WorkspaceMembership.Role.VIEWER)

        # Create project in team workspace
        project = VideoProject.objects.create(
            user=self.user_a,
            workspace=ws,
            title="Shared Animated Tale",
            prompt="A detective investigating a futuristic neo-noir city.",
            duration=10,
            aspect_ratio="9:16",
        )
        scene = VideoScene.objects.create(project=project, scene_number=1, duration=10, prompt="Scene 1")
        char = Character.objects.create(project=project, name="Detective Vance")

        # Bob (VIEWER) CAN view project status
        resp_view = self.client_b.get(f"/api/video/projects/{project.id}/status/")
        self.assertEqual(resp_view.status_code, status.HTTP_200_OK)

        # Bob (VIEWER) CAN view project versions
        resp_versions = self.client_b.get(f"/api/video/projects/{project.id}/versions/")
        self.assertEqual(resp_versions.status_code, status.HTTP_200_OK)

        # Bob (VIEWER) CANNOT branch new version -> 403 Forbidden
        resp_branch = self.client_b.post(f"/api/video/projects/{project.id}/versions/", {
            "prompt": "Modified prompt",
        }, format="json")
        self.assertEqual(resp_branch.status_code, status.HTTP_403_FORBIDDEN)

        # Bob (VIEWER) CANNOT generate scene -> 403 Forbidden
        resp_scene = self.client_b.post(f"/api/video/projects/{project.id}/scenes/{scene.id}/generate/")
        self.assertEqual(resp_scene.status_code, status.HTTP_403_FORBIDDEN)

        # Bob (VIEWER) CANNOT generate character reference -> 403 Forbidden
        resp_char = self.client_b.post(f"/api/video/projects/{project.id}/characters/{char.id}/reference/")
        self.assertEqual(resp_char.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_can_create_and_branch_in_workspace(self):
        """Editor role can create projects, branch versions, and generate scenes in workspace."""
        ws = Workspace.objects.create(name="Editor Studio", owner=self.user_a, is_personal=False)
        WorkspaceMembership.objects.create(workspace=ws, user=self.user_a, role=WorkspaceMembership.Role.OWNER)
        WorkspaceMembership.objects.create(workspace=ws, user=self.user_b, role=WorkspaceMembership.Role.EDITOR)

        # Bob (EDITOR) creates a project explicitly in this workspace
        resp = self.client_b.post("/api/video/projects/", {
            "workspace_id": ws.id,
            "title": "Bob's Team Project",
            "prompt": "Two friends travelling across the mountains.",
            "duration": 10,
            "aspect_ratio": "9:16",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        project_id = resp.data["id"]

        project = VideoProject.objects.get(id=project_id)
        self.assertEqual(project.workspace, ws)

        # Bob branches version
        resp_branch = self.client_b.post(f"/api/video/projects/{project_id}/versions/", {
            "prompt": "Two friends travelling across the magical snow mountains.",
        }, format="json")
        self.assertEqual(resp_branch.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_branch.data["version_number"], 2)

    def test_cannot_create_project_in_unauthorized_workspace(self):
        """User cannot create a project in a workspace they don't belong to or only have viewer role."""
        ws_a = get_or_create_personal_workspace(self.user_a)

        # Bob specifies Alice's workspace_id
        resp = self.client_b.post("/api/video/projects/", {
            "workspace_id": ws_a.id,
            "title": "Intrusion Attempt",
            "prompt": "Hacking the system.",
            "duration": 10,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
