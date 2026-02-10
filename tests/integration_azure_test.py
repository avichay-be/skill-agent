#!/usr/bin/env python3
"""Integration tests for Azure deployed application.

This script tests the live Azure Container Apps deployment.
Supports both app-level auth (X-API-Key) and Azure EasyAuth (Bearer token).

Usage:
    python tests/integration_azure_test.py                             # auto-detect
    API_KEY=<key> python tests/integration_azure_test.py               # app-level auth
    BEARER_TOKEN=<token> python tests/integration_azure_test.py        # Azure AD auth
    BASE_URL=https://... python tests/integration_azure_test.py        # custom URL
"""

import os
import sys
import time
from typing import Optional

import httpx

# Configuration from environment
BASE_URL = os.environ.get(
    "BASE_URL",
    "https://skill-agent-app.livelycliff-37840c5f.eastus.azurecontainerapps.io",
)
API_KEY = os.environ.get("API_KEY", "")
BEARER_TOKEN = os.environ.get("BEARER_TOKEN", "")
TIMEOUT = 30.0


class TestResult:
    """Test result container."""

    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.skipped = False
        self.error: Optional[str] = None
        self.response_time = 0.0

    def __repr__(self) -> str:
        if self.skipped:
            label = "SKIP"
        elif self.passed:
            label = "PASS"
        else:
            label = "FAIL"
        time_str = f"({self.response_time:.2f}s)"
        error_str = f" - {self.error}" if self.error else ""
        return f"{label} {self.name} {time_str}{error_str}"


def detect_azure_easyauth(base_url: str) -> bool:
    """Check if Azure EasyAuth is blocking requests at the infra level."""
    try:
        resp = httpx.get(f"{base_url}/health", timeout=TIMEOUT)
        if resp.status_code == 401:
            www_auth = resp.headers.get("www-authenticate", "")
            if "login.windows.net" in www_auth or "login.microsoftonline.com" in www_auth:
                return True
    except httpx.ConnectError:
        pass
    return False


class AzureIntegrationTests:
    """Integration tests for Azure deployment."""

    def __init__(self, base_url: str, api_key: str, bearer_token: str):
        self.base_url = base_url.rstrip("/")
        self.easyauth_enabled = False
        self.app_auth_enabled = False

        # Build auth headers
        auth_headers: dict[str, str] = {}
        if bearer_token:
            auth_headers["Authorization"] = f"Bearer {bearer_token}"
        if api_key:
            auth_headers["X-API-Key"] = api_key

        self.authed_client = httpx.Client(timeout=TIMEOUT, headers=auth_headers)
        self.anon_client = httpx.Client(timeout=TIMEOUT)
        self.results: list[TestResult] = []

    def run_all(self) -> bool:
        """Run all integration tests."""
        print(f"Running integration tests against: {self.base_url}")
        print(f"API key: {'set' if API_KEY else 'not set'}")
        print(f"Bearer token: {'set' if BEARER_TOKEN else 'not set'}\n")

        # Pre-flight: detect Azure EasyAuth
        self.easyauth_enabled = detect_azure_easyauth(self.base_url)
        if self.easyauth_enabled:
            if not BEARER_TOKEN:
                print("Azure EasyAuth (AD authentication) detected at infra level.")
                print("All unauthenticated requests are blocked before reaching the app.")
                print("To run authenticated tests, set: BEARER_TOKEN=<azure-ad-token>\n")
            else:
                print("Azure EasyAuth detected, using Bearer token.\n")

        # Detect app-level auth (REQUIRE_API_KEY) by probing a protected endpoint
        if not self.easyauth_enabled:
            try:
                probe = self.anon_client.get(f"{self.base_url}/api/v1/skills")
                self.app_auth_enabled = probe.status_code == 401
            except httpx.ConnectError:
                pass
            print(f"App-level API key auth: {'enabled' if self.app_auth_enabled else 'disabled'}\n")

        # Authenticated endpoint tests
        self.test_root_endpoint()
        self.test_health_endpoint()
        self.test_docs_endpoint()
        self.test_admin_health_endpoint()
        self.test_webhook_reload()
        self.test_webhook_events()
        self.test_skills_list()
        self.test_schemas_list()

        # Unauthenticated (should be rejected)
        self.test_skills_endpoint_rejects_anon()
        self.test_schemas_endpoint_rejects_anon()
        self.test_execute_endpoint_rejects_anon()

        return self.print_results()

    def _skip_if_easyauth(self, result: TestResult) -> bool:
        """Skip test if EasyAuth is active and no Bearer token is provided."""
        if self.easyauth_enabled and not BEARER_TOKEN:
            result.skipped = True
            result.error = "Azure EasyAuth active, no BEARER_TOKEN"
            self.results.append(result)
            return True
        return False

    # ---- Authenticated tests ----

    def test_root_endpoint(self) -> None:
        """Test root endpoint returns service info."""
        result = TestResult("Root endpoint")
        if self._skip_if_easyauth(result):
            return
        try:
            start = time.time()
            response = self.authed_client.get(f"{self.base_url}/")
            result.response_time = time.time() - start

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert "service" in data, "Missing 'service' in response"
            assert "version" in data, "Missing 'version' in response"
            assert data["service"] == "Skill Agent", f"Unexpected service name: {data['service']}"

            result.passed = True
        except Exception as e:
            result.error = str(e)
        self.results.append(result)

    def test_health_endpoint(self) -> None:
        """Test health check endpoint."""
        result = TestResult("Health endpoint")
        if self._skip_if_easyauth(result):
            return
        try:
            start = time.time()
            response = self.authed_client.get(f"{self.base_url}/health")
            result.response_time = time.time() - start

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert "status" in data, "Missing 'status' in response"
            assert data["status"] == "healthy", f"Service not healthy: {data['status']}"

            result.passed = True
        except Exception as e:
            result.error = str(e)
        self.results.append(result)

    def test_docs_endpoint(self) -> None:
        """Test API documentation is accessible."""
        result = TestResult("API docs endpoint")
        if self._skip_if_easyauth(result):
            return
        try:
            start = time.time()
            response = self.authed_client.get(f"{self.base_url}/docs")
            result.response_time = time.time() - start

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            assert "text/html" in response.headers.get("content-type", ""), (
                "Docs should return HTML"
            )

            result.passed = True
        except Exception as e:
            result.error = str(e)
        self.results.append(result)

    def test_admin_health_endpoint(self) -> None:
        """Test admin health endpoint."""
        result = TestResult("Admin health endpoint")
        if self._skip_if_easyauth(result):
            return
        try:
            start = time.time()
            response = self.authed_client.get(f"{self.base_url}/api/v1/admin/health")
            result.response_time = time.time() - start

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert "status" in data, "Missing 'status' in response"
            assert "schemas_count" in data, "Missing 'schemas_count' in response"
            assert "skills_count" in data, "Missing 'skills_count' in response"

            result.passed = True
        except Exception as e:
            result.error = str(e)
        self.results.append(result)

    def test_webhook_reload(self) -> None:
        """Test webhook reload endpoint."""
        result = TestResult("Webhook reload endpoint")
        if self._skip_if_easyauth(result):
            return
        try:
            start = time.time()
            response = self.authed_client.post(f"{self.base_url}/api/v1/webhooks/reload")
            result.response_time = time.time() - start

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert "status" in data, "Missing 'status' in response"

            result.passed = True
        except Exception as e:
            result.error = str(e)
        self.results.append(result)

    def test_webhook_events(self) -> None:
        """Test webhook events endpoint."""
        result = TestResult("Webhook events endpoint")
        if self._skip_if_easyauth(result):
            return
        try:
            start = time.time()
            response = self.authed_client.get(f"{self.base_url}/api/v1/webhooks/events")
            result.response_time = time.time() - start

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert isinstance(data, list), "Events should return a list"

            result.passed = True
        except Exception as e:
            result.error = str(e)
        self.results.append(result)

    def test_skills_list(self) -> None:
        """Test skills list endpoint with auth."""
        result = TestResult("Skills list (authed)")
        if self._skip_if_easyauth(result):
            return
        try:
            start = time.time()
            response = self.authed_client.get(f"{self.base_url}/api/v1/skills")
            result.response_time = time.time() - start

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert "skills" in data, "Missing 'skills' in response"
            assert "total" in data, "Missing 'total' in response"
            assert isinstance(data["skills"], list), "skills field should be a list"

            result.passed = True
        except Exception as e:
            result.error = str(e)
        self.results.append(result)

    def test_schemas_list(self) -> None:
        """Test schemas list endpoint with auth."""
        result = TestResult("Schemas list (authed)")
        if self._skip_if_easyauth(result):
            return
        try:
            start = time.time()
            response = self.authed_client.get(f"{self.base_url}/api/v1/schemas")
            result.response_time = time.time() - start

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert "schemas" in data, "Missing 'schemas' in response"
            assert "total" in data, "Missing 'total' in response"
            assert isinstance(data["schemas"], list), "schemas field should be a list"

            result.passed = True
        except Exception as e:
            result.error = str(e)
        self.results.append(result)

    # ---- Unauthenticated tests (should be rejected when auth is enabled) ----

    def _skip_if_no_auth(self, result: TestResult) -> bool:
        """Skip anon rejection test if neither EasyAuth nor app auth is enabled."""
        if not self.easyauth_enabled and not self.app_auth_enabled:
            result.skipped = True
            result.error = "Auth disabled on deployment (REQUIRE_API_KEY=false)"
            self.results.append(result)
            return True
        return False

    def test_skills_endpoint_rejects_anon(self) -> None:
        """Test skills endpoint rejects unauthenticated requests."""
        result = TestResult("Skills rejects anon")
        if self._skip_if_no_auth(result):
            return
        try:
            start = time.time()
            response = self.anon_client.get(f"{self.base_url}/api/v1/skills")
            result.response_time = time.time() - start

            assert response.status_code == 401, f"Expected 401, got {response.status_code}"

            result.passed = True
        except Exception as e:
            result.error = str(e)
        self.results.append(result)

    def test_schemas_endpoint_rejects_anon(self) -> None:
        """Test schemas endpoint rejects unauthenticated requests."""
        result = TestResult("Schemas rejects anon")
        if self._skip_if_no_auth(result):
            return
        try:
            start = time.time()
            response = self.anon_client.get(f"{self.base_url}/api/v1/schemas")
            result.response_time = time.time() - start

            assert response.status_code == 401, f"Expected 401, got {response.status_code}"

            result.passed = True
        except Exception as e:
            result.error = str(e)
        self.results.append(result)

    def test_execute_endpoint_rejects_anon(self) -> None:
        """Test execute endpoint rejects unauthenticated requests."""
        result = TestResult("Execute rejects anon")
        if self._skip_if_no_auth(result):
            return
        try:
            start = time.time()
            response = self.anon_client.post(
                f"{self.base_url}/api/v1/execute",
                json={"document": "test", "skill_name": "test"},
            )
            result.response_time = time.time() - start

            assert response.status_code == 401, f"Expected 401, got {response.status_code}"

            result.passed = True
        except Exception as e:
            result.error = str(e)
        self.results.append(result)

    # ---- Results ----

    def print_results(self) -> bool:
        """Print test results summary."""
        print("\n" + "=" * 70)
        print("TEST RESULTS")
        print("=" * 70 + "\n")

        for result in self.results:
            print(result)

        passed = sum(1 for r in self.results if r.passed)
        skipped = sum(1 for r in self.results if r.skipped)
        failed = sum(1 for r in self.results if not r.passed and not r.skipped)
        total = len(self.results)

        print("\n" + "=" * 70)
        print(f"SUMMARY: {passed} passed, {skipped} skipped, {failed} failed (total: {total})")

        if failed == 0:
            if skipped > 0:
                print("All reachable tests passed! (some skipped due to Azure EasyAuth)")
            else:
                print("All tests passed!")
        else:
            print(f"{failed} test(s) failed")
        print("=" * 70 + "\n")

        return failed == 0


def main() -> None:
    """Run integration tests."""
    tester = AzureIntegrationTests(BASE_URL, API_KEY, BEARER_TOKEN)
    success = tester.run_all()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
