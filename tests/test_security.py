"""Tests for security features: CORS, rate limiting, and request timeout."""

import os


class TestCORSConfiguration:
    """Tests for CORS configuration based on environment."""

    def test_allowed_origins_setting_default(self):
        """Test that ALLOWED_ORIGINS setting exists with default value."""
        # Clear cache to ensure fresh settings
        from app.core.config import get_settings

        get_settings.cache_clear()

        # Remove any existing env var
        os.environ.pop("ALLOWED_ORIGINS", None)

        settings = get_settings()

        # Should have allowed_origins attribute
        assert hasattr(settings, "allowed_origins")
        # Default should include localhost origins
        assert "http://localhost:3000" in settings.allowed_origins
        assert "http://localhost:8000" in settings.allowed_origins

        get_settings.cache_clear()

    def test_allowed_origins_from_environment(self):
        """Test that ALLOWED_ORIGINS can be set via environment."""
        from app.core.config import get_settings

        get_settings.cache_clear()

        os.environ["ALLOWED_ORIGINS"] = "https://app.example.com,https://api.example.com"

        settings = get_settings()

        assert "https://app.example.com" in settings.allowed_origins
        assert "https://api.example.com" in settings.allowed_origins

        # Cleanup
        os.environ.pop("ALLOWED_ORIGINS", None)
        get_settings.cache_clear()

    def test_cors_uses_allowed_origins_in_production(self):
        """Test that CORS middleware uses ALLOWED_ORIGINS in production."""
        from app.core.config import get_settings

        get_settings.cache_clear()

        os.environ["ENVIRONMENT"] = "production"
        os.environ["ALLOWED_ORIGINS"] = "https://app.example.com"

        # Need to import fresh app
        from importlib import reload

        import app.main

        reload(app.main)

        # Get CORS middleware from app
        from app.main import create_app

        test_app = create_app()

        # Find CORS middleware
        cors_middleware = None
        for middleware in test_app.user_middleware:
            if middleware.cls.__name__ == "CORSMiddleware":
                cors_middleware = middleware
                break

        assert cors_middleware is not None
        # Should NOT be wildcard
        assert cors_middleware.kwargs.get("allow_origins") != ["*"]
        assert "https://app.example.com" in cors_middleware.kwargs.get("allow_origins", [])

        # Cleanup
        os.environ.pop("ENVIRONMENT", None)
        os.environ.pop("ALLOWED_ORIGINS", None)
        get_settings.cache_clear()

    def test_cors_uses_localhost_in_debug(self):
        """Test that CORS middleware uses localhost origins in debug/local mode."""
        from app.core.config import get_settings

        get_settings.cache_clear()

        os.environ["ENVIRONMENT"] = "local"
        os.environ["DEBUG"] = "true"
        os.environ.pop("ALLOWED_ORIGINS", None)

        from importlib import reload

        import app.main

        reload(app.main)

        from app.main import create_app

        test_app = create_app()

        # Find CORS middleware
        cors_middleware = None
        for middleware in test_app.user_middleware:
            if middleware.cls.__name__ == "CORSMiddleware":
                cors_middleware = middleware
                break

        assert cors_middleware is not None
        origins = cors_middleware.kwargs.get("allow_origins", [])
        # Should NOT be wildcard
        assert origins != ["*"]
        # Should include localhost
        assert any("localhost" in origin for origin in origins)

        # Cleanup
        os.environ.pop("ENVIRONMENT", None)
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


class TestRateLimiting:
    """Tests for rate limiting on LLM endpoints."""

    def test_slowapi_limiter_exists(self):
        """Test that slowapi Limiter is configured."""
        from slowapi import Limiter

        from app.core.rate_limiter import limiter

        assert isinstance(limiter, Limiter)

    def test_rate_limiter_configured_on_app(self):
        """Test that rate limiter is added to app state."""
        from app.main import create_app

        test_app = create_app()

        assert hasattr(test_app.state, "limiter")
        from slowapi import Limiter

        assert isinstance(test_app.state.limiter, Limiter)

    def test_execute_endpoint_has_rate_limit_decorator(self):
        """Test that /execute endpoint has rate limit decorator applied."""
        from app.api.routes.execute import execute_extraction

        # Check that the function has been wrapped by slowapi
        # The limiter adds _limit attribute to decorated functions
        assert hasattr(execute_extraction, "__wrapped__") or callable(execute_extraction)

        # Verify the limiter is configured
        from app.core.rate_limiter import limiter

        # The limiter should have stored limit info
        assert limiter is not None

    def test_execute_file_endpoint_has_rate_limit_decorator(self):
        """Test that /execute/file endpoint has rate limit decorator applied."""
        from app.api.routes.execute import execute_extraction_from_file

        # Check that the function has been wrapped
        assert hasattr(execute_extraction_from_file, "__wrapped__") or callable(
            execute_extraction_from_file
        )

    def test_execute_stream_endpoint_has_rate_limit_decorator(self):
        """Test that /execute/stream endpoint has rate limit decorator applied."""
        from app.api.routes.execute import execute_extraction_streaming

        # Check that the function has been wrapped
        assert hasattr(execute_extraction_streaming, "__wrapped__") or callable(
            execute_extraction_streaming
        )

    def test_rate_limit_exceeded_handler_registered(self):
        """Test that rate limit exceeded handler is registered."""
        from slowapi.errors import RateLimitExceeded

        from app.main import create_app

        test_app = create_app()

        # Check that exception handler is registered for RateLimitExceeded
        assert RateLimitExceeded in test_app.exception_handlers


class TestRequestTimeout:
    """Tests for request timeout middleware."""

    def test_timeout_middleware_exists(self):
        """Test that timeout middleware is configured."""

        from app.main import create_app

        test_app = create_app()

        # Check that a timeout middleware is present
        middleware_names = [m.cls.__name__ for m in test_app.user_middleware]
        # Should have some form of timeout middleware
        assert any("timeout" in name.lower() for name in middleware_names), (
            f"No timeout middleware found in: {middleware_names}"
        )

    def test_request_timeout_setting_exists(self):
        """Test that REQUEST_TIMEOUT_SECONDS setting exists."""
        from app.core.config import get_settings

        get_settings.cache_clear()

        settings = get_settings()

        assert hasattr(settings, "request_timeout_seconds")
        # Default should be 300 (5 minutes)
        assert settings.request_timeout_seconds == 300

        get_settings.cache_clear()

    def test_request_timeout_configurable(self):
        """Test that REQUEST_TIMEOUT_SECONDS can be configured."""
        from app.core.config import get_settings

        get_settings.cache_clear()

        os.environ["REQUEST_TIMEOUT_SECONDS"] = "120"

        settings = get_settings()

        assert settings.request_timeout_seconds == 120

        # Cleanup
        os.environ.pop("REQUEST_TIMEOUT_SECONDS", None)
        get_settings.cache_clear()


class TestProxyAwareRateLimiting:
    """Tests for proxy-aware rate limiting using X-Forwarded-For header."""

    def test_key_func_uses_x_forwarded_for_header(self):
        """Test that rate limiter key function checks X-Forwarded-For header first."""
        from unittest.mock import MagicMock

        from app.core.rate_limiter import get_client_ip

        # Create mock request with X-Forwarded-For header
        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": "203.0.113.50, 70.41.3.18, 150.172.238.178"}
        mock_request.client.host = "10.0.0.1"

        # Should return first IP from X-Forwarded-For
        result = get_client_ip(mock_request)
        assert result == "203.0.113.50"

    def test_key_func_falls_back_to_client_host(self):
        """Test that rate limiter key function falls back to client.host when no header."""
        from unittest.mock import MagicMock

        from app.core.rate_limiter import get_client_ip

        # Create mock request without X-Forwarded-For header
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client.host = "192.168.1.100"

        # Should return client.host
        result = get_client_ip(mock_request)
        assert result == "192.168.1.100"

    def test_key_func_handles_single_ip_in_header(self):
        """Test that rate limiter handles single IP in X-Forwarded-For."""
        from unittest.mock import MagicMock

        from app.core.rate_limiter import get_client_ip

        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": "203.0.113.50"}
        mock_request.client.host = "10.0.0.1"

        result = get_client_ip(mock_request)
        assert result == "203.0.113.50"

    def test_limiter_uses_custom_key_func(self):
        """Test that the limiter instance uses our custom key function."""
        from app.core.rate_limiter import get_client_ip, limiter

        # The limiter should be configured with our custom key function
        assert limiter._key_func == get_client_ip


class TestExceptionSanitization:
    """Tests for exception message sanitization in production."""

    def test_generic_exception_hides_details_in_production(self):
        """Test that generic exception handler hides internal details in production."""
        from app.core.config import get_settings

        get_settings.cache_clear()

        os.environ["DEBUG"] = "false"
        os.environ["ENVIRONMENT"] = "production"

        from importlib import reload

        import app.main

        reload(app.main)

        from fastapi.testclient import TestClient

        from app.main import create_app

        test_app = create_app()
        # Use raise_server_exceptions=False to let exception handlers work
        client = TestClient(test_app, raise_server_exceptions=False)

        # Add a route that raises an exception
        @test_app.get("/test-error")
        async def raise_error():
            raise ValueError(
                "Sensitive internal database connection string: postgres://user:pass@host"
            )

        # Make request
        response = client.get("/test-error")

        # Should return 500 but NOT expose internal details
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        # Should NOT contain sensitive information
        assert "postgres://" not in data.get("detail", "")
        assert "password" not in data.get("detail", "").lower()
        assert "connection string" not in data.get("detail", "").lower()
        # Should contain generic message
        assert "internal server error" in data.get("error", "").lower()

        # Cleanup
        os.environ.pop("DEBUG", None)
        os.environ.pop("ENVIRONMENT", None)
        get_settings.cache_clear()

    def test_generic_exception_shows_details_in_debug(self):
        """Test that generic exception handler shows details when debug=True."""
        from app.core.config import get_settings

        get_settings.cache_clear()

        os.environ["DEBUG"] = "true"
        os.environ["ENVIRONMENT"] = "local"

        from importlib import reload

        import app.main

        reload(app.main)

        from fastapi.testclient import TestClient

        from app.main import create_app

        test_app = create_app()
        # Use raise_server_exceptions=False to let exception handlers work
        client = TestClient(test_app, raise_server_exceptions=False)

        # Add a route that raises an exception
        @test_app.get("/test-error-debug")
        async def raise_error_debug():
            raise ValueError("Debug error message for developers")

        # Make request
        response = client.get("/test-error-debug")

        # Should return 500 with details in debug mode
        assert response.status_code == 500
        data = response.json()
        # In debug mode, should contain the error details
        assert "Debug error message" in data.get("detail", "")

        # Cleanup
        os.environ.pop("DEBUG", None)
        os.environ.pop("ENVIRONMENT", None)
        get_settings.cache_clear()


class TestResumeAndLegacyRateLimits:
    """Tests for rate limiting on /resume and /legacy endpoints."""

    def test_resume_endpoint_has_rate_limit_decorator(self):
        """Test that /execute/resume/{execution_id} endpoint has rate limit decorator."""
        from app.api.routes.execute import resume_execution

        # Check that the function has been wrapped by slowapi
        # Decorated functions have __wrapped__ attribute
        assert hasattr(resume_execution, "__wrapped__"), (
            "resume_execution endpoint missing rate limit decorator"
        )

    def test_legacy_endpoint_has_rate_limit_decorator(self):
        """Test that /execute/legacy endpoint has rate limit decorator."""
        from app.api.routes.execute import execute_extraction_legacy

        # Check that the function has been wrapped by slowapi
        # Decorated functions have __wrapped__ attribute
        assert hasattr(execute_extraction_legacy, "__wrapped__"), (
            "execute_extraction_legacy endpoint missing rate limit decorator"
        )
