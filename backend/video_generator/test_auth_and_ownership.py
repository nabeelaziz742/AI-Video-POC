from django.contrib.auth.models import User
from rest_framework.test import APITestCase


class AuthAndOwnershipTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="StrongPass123")
        self.bob = User.objects.create_user(username="bob", password="StrongPass456")
        self.project_payload = {
            "title": "Alice Project",
            "input_type": "story",
            "prompt": "A farmer walks through a village at sunrise.",
            "duration": 10,
            "aspect_ratio": "9:16",
            "characters": [{"name": "Farmer", "role": "main character"}],
        }

    def project_url(self, project_id):
        return f"/api/video/projects/{project_id}/status/"

    def test_signup_creates_authenticated_session(self):
        response = self.client.post("/api/video/auth/signup/", {"username": "charlie", "email": "charlie@example.com", "password": "StrongPass789"}, format="json")
        self.assertEqual(response.status_code, 201)
        token = response.data["verification_token"]
        verify = self.client.post("/api/video/auth/verify-email/", {"token": token}, format="json")
        self.assertEqual(verify.status_code, 200)
        me = self.client.get("/api/video/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["user"]["username"], "charlie")

    def test_login_and_logout(self):
        login = self.client.post("/api/video/auth/login/", {"username": "alice", "password": "StrongPass123"}, format="json")
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.client.get("/api/video/auth/me/").status_code, 200)
        logout = self.client.post("/api/video/auth/logout/", format="json")
        self.assertEqual(logout.status_code, 204)
        self.assertEqual(self.client.get("/api/video/auth/me/").status_code, 403)

    def test_projects_require_authentication(self):
        response = self.client.get("/api/video/projects/")
        self.assertEqual(response.status_code, 403)

    def test_user_only_sees_own_projects(self):
        self.client.force_authenticate(self.alice)
        create = self.client.post("/api/video/projects/", self.project_payload, format="json")
        self.assertEqual(create.status_code, 201)
        project_id = create.data["id"]
        self.assertEqual(len(self.client.get("/api/video/projects/").data), 1)
        self.client.force_authenticate(self.bob)
        self.assertEqual(self.client.get("/api/video/projects/").data, [])
        self.assertEqual(self.client.get(self.project_url(project_id)).status_code, 404)

    def test_nested_generation_endpoint_enforces_ownership(self):
        self.client.force_authenticate(self.alice)
        create = self.client.post("/api/video/projects/", self.project_payload, format="json")
        self.assertEqual(create.status_code, 201)
        project_id = create.data["id"]
        scene_id = create.data["scenes"][0]["id"]
        self.client.force_authenticate(self.bob)
        response = self.client.post(f"/api/video/projects/{project_id}/scenes/{scene_id}/generate/", {}, format="json")
        self.assertEqual(response.status_code, 404)
