#!/usr/bin/env python3
"""Integration tests for Azure deployed application.

This script tests the live Azure Container Apps deployment.
"""

import sys
import time

import httpx

# Azure deployment URL
BASE_URL = "https://skill-agent-app.livelycliff-37840c5f.eastus.azurecontainerapps.io"
TIMEOUT = 30.0


class TestResult:
    """Test result container."""

    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error = None
        self.response_time = 0.0

    def __repr__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        time_str = f"({self.response_time:.2f}s)"
        error_str = f" - {self.error}" if self.error else ""
        return f"{status} {self.name} {time_str}{error_str}"


class AzureIntegrationTests:
    """Integration tests for Azure deployment."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.Client(timeout=TIMEOUT)
        self.results = []

    def run_all(self):
        """Run all integration tests."""
        print(f"🚀 Running integration tests against: {self.base_url}\n")

        # Basic connectivity tests
        self.test_root_endpoint()
        self.test_health_endpoint()
        self.test_docs_endpoint()

        # API endpoint tests (without auth)
        self.test_admin_health_endpoint()
        self.test_skills_endpoint_requires_auth()
        self.test_schemas_endpoint_requires_auth()
        self.test_execute_endpoint_requires_auth()

        # Webhook tests
        self.test_webhook_reload()
        self.test_webhook_events()

        # Display results
        self.print_results()

    def test_root_endpoint(self):
        """Test root endpoint returns service info."""
        result = TestResult("Root endpoint")
        try:
            start = time.time()
            response = self.client.get(f"{self.base_url}/")
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

    def test_health_endpoint(self):
        """Test health check endpoint."""
        result = TestResult("Health endpoint")
        try:
            start = time.time()
            response = self.client.get(f"{self.base_url}/health")
            result.response_time = time.time() - start

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert "status" in data, "Missing 'status' in response"
            assert data["status"] == "healthy", f"Service not healthy: {data['status']}"

            result.passed = True
        except Exception as e:
            result.error = str(e)

        self.results.append(result)

    def test_docs_endpoint(self):
        """Test API documentation is accessible."""
        result = TestResult("API docs endpoint")
        try:
            start = time.time()
            response = self.client.get(f"{self.base_url}/docs")
            result.response_time = time.time() - start

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            assert "text/html" in response.headers.get("content-type", ""), "Docs should return HTML"

            result.passed = True
        except Exception as e:
            result.error = str(e)

        self.results.append(result)

    def test_admin_health_endpoint(self):
        """Test admin health endpoint."""
        result = TestResult("Admin health endpoint")
        try:
            start = time.time()
            response = self.client.get(f"{self.base_url}/api/v1/admin/health")
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

    def test_skills_endpoint_requires_auth(self):
        """Test skills endpoint requires authentication."""
        result = TestResult("Skills endpoint auth check")
        try:
            start = time.time()
            response = self.client.get(f"{self.base_url}/api/v1/skills")
            result.response_time = time.time() - start

            assert response.status_code == 401, f"Expected 401 (unauthorized), got {response.status_code}"

            result.passed = True
        except Exception as e:
            result.error = str(e)

        self.results.append(result)

    def test_schemas_endpoint_requires_auth(self):
        """Test schemas endpoint requires authentication."""
        result = TestResult("Schemas endpoint auth check")
        try:
            start = time.time()
            response = self.client.get(f"{self.base_url}/api/v1/schemas")
            result.response_time = time.time() - start

            assert response.status_code == 401, f"Expected 401 (unauthorized), got {response.status_code}"

            result.passed = True
        except Exception as e:
            result.error = str(e)

        self.results.append(result)

    def test_execute_endpoint_requires_auth(self):
        """Test execute endpoint requires authentication."""
        result = TestResult("Execute endpoint auth check")
        try:
            start = time.time()
            response = self.client.post(
                f"{self.base_url}/api/v1/execute",
                json={"document": "test", "schema_id": "test"}
            )
            result.response_time = time.time() - start

            assert response.status_code == 401, f"Expected 401 (unauthorized), got {response.status_code}"

            result.passed = True
        except Exception as e:
            result.error = str(e)

        self.results.append(result)

    def test_webhook_reload(self):
        """Test webhook reload endpoint."""
        result = TestResult("Webhook reload endpoint")
        try:
            start = time.time()
            response = self.client.post(f"{self.base_url}/api/v1/webhooks/reload")
            result.response_time = time.time() - start

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert "status" in data, "Missing 'status' in response"

            result.passed = True
        except Exception as e:
            result.error = str(e)

        self.results.append(result)

    def test_webhook_events(self):
        """Test webhook events endpoint."""
        result = TestResult("Webhook events endpoint")
        try:
            start = time.time()
            response = self.client.get(f"{self.base_url}/api/v1/webhooks/events")
            result.response_time = time.time() - start

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert isinstance(data, list), "Events should return a list"

            result.passed = True
        except Exception as e:
            result.error = str(e)

        self.results.append(result)

    def print_results(self):
        """Print test results summary."""
        print("\n" + "=" * 70)
        print("TEST RESULTS")
        print("=" * 70 + "\n")

        for result in self.results:
            print(result)

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        print("\n" + "=" * 70)
        print(f"SUMMARY: {passed}/{total} tests passed")

        if passed == total:
            print("🎉 All tests passed!")
        else:
            print(f"⚠️  {total - passed} test(s) failed")
        print("=" * 70 + "\n")

        return passed == total


def main():
    """Run integration tests."""
    tester = AzureIntegrationTests(BASE_URL)
    success = tester.run_all()

    # Exit with proper code for CI/CD
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
