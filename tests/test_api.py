"""Tests for FastAPI endpoints."""

import pytest
from unittest.mock import patch, MagicMock


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, app_client, test_api_key):
        """Test health check returns status."""
        response = app_client.get("/api/v1/admin/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "schemas_count" in data
        assert "skills_count" in data


class TestSkillsEndpoint:
    """Tests for skills API endpoints."""

    def test_list_skills_requires_auth(self, app_client):
        """Test that listing skills requires API key."""
        response = app_client.get("/api/v1/skills")
        assert response.status_code == 401

    def test_list_skills_with_auth(self, app_client, test_api_key):
        """Test listing skills with valid API key."""
        response = app_client.get(
            "/api/v1/skills",
            headers={"X-API-Key": test_api_key}
        )
        assert response.status_code == 200

        data = response.json()
        assert "skills" in data
        assert "total" in data

    def test_list_skills_filter_by_schema(self, app_client, test_api_key):
        """Test filtering skills by schema ID."""
        response = app_client.get(
            "/api/v1/skills?schema_id=test_schema",
            headers={"X-API-Key": test_api_key}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["schema_id"] == "test_schema"


class TestSchemasEndpoint:
    """Tests for schemas API endpoints."""

    def test_list_schemas(self, app_client, test_api_key):
        """Test listing schemas."""
        response = app_client.get(
            "/api/v1/schemas",
            headers={"X-API-Key": test_api_key}
        )
        assert response.status_code == 200

        data = response.json()
        assert "schemas" in data
        assert "total" in data

    def test_get_schema_detail(self, app_client, test_api_key):
        """Test getting schema details."""
        response = app_client.get(
            "/api/v1/schemas/test_schema",
            headers={"X-API-Key": test_api_key}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["schema"]["schema_id"] == "test_schema"
        assert "skills" in data

    def test_get_schema_not_found(self, app_client, test_api_key):
        """Test getting non-existent schema."""
        response = app_client.get(
            "/api/v1/schemas/nonexistent",
            headers={"X-API-Key": test_api_key}
        )
        assert response.status_code == 404


class TestExecuteEndpoint:
    """Tests for execution API endpoints."""

    def test_execute_requires_auth(self, app_client):
        """Test that execution requires API key."""
        response = app_client.post(
            "/api/v1/execute",
            json={"document": "test", "schema_id": "test"}
        )
        assert response.status_code == 401

    def test_execute_schema_not_found(self, app_client, test_api_key):
        """Test execution with non-existent schema."""
        response = app_client.post(
            "/api/v1/execute",
            headers={"X-API-Key": test_api_key},
            json={
                "document": "test document",
                "schema_id": "nonexistent"
            }
        )
        assert response.status_code == 404

    def test_execute_invalid_skill_ids(self, app_client, test_api_key):
        """Test execution with invalid skill IDs."""
        response = app_client.post(
            "/api/v1/execute",
            headers={"X-API-Key": test_api_key},
            json={
                "document": "test document",
                "schema_id": "test_schema",
                "skill_ids": ["nonexistent_skill"]
            }
        )
        assert response.status_code == 400


class TestWebhookEndpoint:
    """Tests for webhook endpoints."""

    def test_force_reload(self, app_client):
        """Test force reload endpoint."""
        response = app_client.post("/api/v1/webhooks/reload")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert "affected_schemas" in data

    def test_git_webhook_wrong_branch(self, app_client):
        """Test Git webhook ignores wrong branch."""
        response = app_client.post(
            "/api/v1/webhooks/git",
            json={
                "ref": "refs/heads/feature-branch",
                "after": "abc123",
                "commits": []
            }
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ignored"

    def test_git_webhook_main_branch(self, app_client):
        """Test Git webhook processes main branch."""
        response = app_client.post(
            "/api/v1/webhooks/git",
            json={
                "ref": "refs/heads/main",
                "after": "abc123",
                "commits": [
                    {
                        "added": ["skills/test_schema/prompts/new.md"],
                        "modified": [],
                        "removed": []
                    }
                ]
            }
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"

    def test_get_events(self, app_client):
        """Test getting recent events."""
        response = app_client.get("/api/v1/webhooks/events")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)


class TestAdminEndpoint:
    """Tests for admin endpoints."""

    def test_get_config(self, app_client, test_api_key):
        """Test getting configuration."""
        response = app_client.get(
            "/api/v1/admin/config",
            headers={"X-API-Key": test_api_key}
        )
        assert response.status_code == 200

        data = response.json()
        assert "app_name" in data
        assert "default_vendor" in data
        # Sensitive values should not be exposed
        assert "anthropic_api_key" not in data
