"""Tests for file upload validation: size limits and file type restrictions."""

import io
import os

from fastapi.testclient import TestClient


def _reset_limiter_and_settings():
    """Reset rate limiter storage and settings cache between tests."""
    from app.core.config import get_settings
    from app.core.rate_limiter import limiter

    get_settings.cache_clear()
    # Reset slowapi in-memory storage to avoid rate limiting in tests
    if hasattr(limiter, "_storage") and hasattr(limiter._storage, "storage"):
        limiter._storage.storage.clear()


def _make_client():
    """Create a fresh test client with reset state."""
    _reset_limiter_and_settings()
    from app.main import create_app

    test_app = create_app()
    return TestClient(test_app, raise_server_exceptions=False)


class TestFileUploadSettings:
    """Tests for file upload validation settings in config.py."""

    def test_max_upload_size_mb_setting_exists(self):
        """Test that MAX_UPLOAD_SIZE_MB setting exists with default value of 10."""
        from app.core.config import get_settings

        get_settings.cache_clear()
        os.environ.pop("MAX_UPLOAD_SIZE_MB", None)

        settings = get_settings()

        assert hasattr(settings, "max_upload_size_mb")
        assert settings.max_upload_size_mb == 10

        get_settings.cache_clear()

    def test_max_upload_size_mb_configurable(self):
        """Test that MAX_UPLOAD_SIZE_MB can be configured via environment."""
        from app.core.config import get_settings

        get_settings.cache_clear()
        os.environ["MAX_UPLOAD_SIZE_MB"] = "25"

        settings = get_settings()

        assert settings.max_upload_size_mb == 25

        os.environ.pop("MAX_UPLOAD_SIZE_MB", None)
        get_settings.cache_clear()

    def test_allowed_file_extensions_setting_exists(self):
        """Test that ALLOWED_FILE_EXTENSIONS setting exists with default value."""
        from app.core.config import get_settings

        get_settings.cache_clear()
        os.environ.pop("ALLOWED_FILE_EXTENSIONS", None)

        settings = get_settings()

        assert hasattr(settings, "allowed_file_extensions")
        # Should be a list parsed from comma-separated string
        assert isinstance(settings.allowed_file_extensions, list)
        assert ".txt" in settings.allowed_file_extensions
        assert ".md" in settings.allowed_file_extensions
        assert ".json" in settings.allowed_file_extensions
        assert ".csv" in settings.allowed_file_extensions
        assert ".xml" in settings.allowed_file_extensions
        assert ".html" in settings.allowed_file_extensions
        assert ".pdf" in settings.allowed_file_extensions

        get_settings.cache_clear()

    def test_allowed_file_extensions_configurable(self):
        """Test that ALLOWED_FILE_EXTENSIONS can be configured via environment."""
        from app.core.config import get_settings

        get_settings.cache_clear()
        os.environ["ALLOWED_FILE_EXTENSIONS"] = ".txt,.csv,.docx"

        settings = get_settings()

        assert ".txt" in settings.allowed_file_extensions
        assert ".csv" in settings.allowed_file_extensions
        assert ".docx" in settings.allowed_file_extensions
        # Should NOT have defaults that weren't specified
        assert ".json" not in settings.allowed_file_extensions

        os.environ.pop("ALLOWED_FILE_EXTENSIONS", None)
        get_settings.cache_clear()


class TestFileSizeValidation:
    """Tests for file size validation on the /execute/file endpoint."""

    def test_file_too_large_returns_413(self):
        """Test that uploading a file exceeding MAX_UPLOAD_SIZE_MB returns 413."""
        os.environ["MAX_UPLOAD_SIZE_MB"] = "1"
        os.environ.pop("REQUIRE_API_KEY", None)
        client = _make_client()

        # Create a file that exceeds 1 MB
        large_content = "x" * (1 * 1024 * 1024 + 1)  # 1 MB + 1 byte
        files = {"file": ("large_file.txt", io.BytesIO(large_content.encode()), "text/plain")}
        data = {"skill_name": "test_skill"}

        response = client.post("/api/v1/execute/file", files=files, data=data)

        assert response.status_code == 413, (
            f"Expected 413 for oversized file, got {response.status_code}: {response.text}"
        )

        os.environ.pop("MAX_UPLOAD_SIZE_MB", None)
        _reset_limiter_and_settings()

    def test_file_within_size_limit_passes_validation(self):
        """Test that a file within the size limit is not rejected for size."""
        os.environ["MAX_UPLOAD_SIZE_MB"] = "10"
        os.environ.pop("REQUIRE_API_KEY", None)
        client = _make_client()

        # Create a small file (well within 10 MB)
        small_content = "Hello, this is a test document."
        files = {"file": ("small_file.txt", io.BytesIO(small_content.encode()), "text/plain")}
        data = {"skill_name": "test_skill"}

        response = client.post("/api/v1/execute/file", files=files, data=data)

        # Should NOT be 413 - may be 404 (skill not found) or other, but NOT 413
        assert response.status_code != 413, "Small file should not be rejected for size"

        os.environ.pop("MAX_UPLOAD_SIZE_MB", None)
        _reset_limiter_and_settings()

    def test_file_exactly_at_limit_passes(self):
        """Test that a file exactly at the size limit passes validation."""
        os.environ["MAX_UPLOAD_SIZE_MB"] = "1"
        os.environ.pop("REQUIRE_API_KEY", None)
        client = _make_client()

        # Create a file exactly at 1 MB (not exceeding)
        exact_content = "x" * (1 * 1024 * 1024)  # exactly 1 MB
        files = {"file": ("exact_file.txt", io.BytesIO(exact_content.encode()), "text/plain")}
        data = {"skill_name": "test_skill"}

        response = client.post("/api/v1/execute/file", files=files, data=data)

        # Should NOT be 413 - exactly at limit is OK
        assert response.status_code != 413, "File exactly at limit should not be rejected"

        os.environ.pop("MAX_UPLOAD_SIZE_MB", None)
        _reset_limiter_and_settings()


class TestFileTypeValidation:
    """Tests for file type/extension validation on the /execute/file endpoint."""

    def test_disallowed_extension_returns_415(self):
        """Test that uploading a file with disallowed extension returns 415."""
        os.environ["ALLOWED_FILE_EXTENSIONS"] = ".txt,.md,.json"
        os.environ.pop("REQUIRE_API_KEY", None)
        client = _make_client()

        # Upload a .exe file (not in allowed list)
        content = "fake executable content"
        files = {"file": ("malware.exe", io.BytesIO(content.encode()), "application/octet-stream")}
        data = {"skill_name": "test_skill"}

        response = client.post("/api/v1/execute/file", files=files, data=data)

        assert response.status_code == 415, (
            f"Expected 415 for disallowed extension .exe, got {response.status_code}: {response.text}"
        )

        os.environ.pop("ALLOWED_FILE_EXTENSIONS", None)
        _reset_limiter_and_settings()

    def test_allowed_extension_passes_validation(self):
        """Test that uploading a file with allowed extension is not rejected for type."""
        os.environ["ALLOWED_FILE_EXTENSIONS"] = ".txt,.md,.json"
        os.environ.pop("REQUIRE_API_KEY", None)
        client = _make_client()

        content = "This is valid text content."
        files = {"file": ("document.txt", io.BytesIO(content.encode()), "text/plain")}
        data = {"skill_name": "test_skill"}

        response = client.post("/api/v1/execute/file", files=files, data=data)

        # Should NOT be 415 - may be other error (skill not found), but NOT 415
        assert response.status_code != 415, "Allowed extension .txt should not be rejected"

        os.environ.pop("ALLOWED_FILE_EXTENSIONS", None)
        _reset_limiter_and_settings()

    def test_case_insensitive_extension_check(self):
        """Test that extension validation is case-insensitive (.TXT == .txt)."""
        os.environ["ALLOWED_FILE_EXTENSIONS"] = ".txt,.md,.json"
        os.environ.pop("REQUIRE_API_KEY", None)
        client = _make_client()

        content = "This is valid text content."
        files = {"file": ("document.TXT", io.BytesIO(content.encode()), "text/plain")}
        data = {"skill_name": "test_skill"}

        response = client.post("/api/v1/execute/file", files=files, data=data)

        # Should NOT be 415 - .TXT should match .txt
        assert response.status_code != 415, "Case-insensitive .TXT should match .txt"

        os.environ.pop("ALLOWED_FILE_EXTENSIONS", None)
        _reset_limiter_and_settings()

    def test_no_filename_rejected(self):
        """Test that uploading a file with no/empty filename is rejected.

        FastAPI may reject empty filenames at the framework level (422) before
        reaching our validation. Either 415 or 422 is an acceptable rejection.
        """
        os.environ["ALLOWED_FILE_EXTENSIONS"] = ".txt,.md,.json"
        os.environ.pop("REQUIRE_API_KEY", None)
        client = _make_client()

        content = "content without filename"
        # FastAPI UploadFile with empty filename
        files = {"file": ("", io.BytesIO(content.encode()), "text/plain")}
        data = {"skill_name": "test_skill"}

        response = client.post("/api/v1/execute/file", files=files, data=data)

        # File with no filename should be rejected - 415 (our validation) or 422 (FastAPI)
        assert response.status_code in (415, 422), (
            f"Expected 415 or 422 for file with no filename, got {response.status_code}"
        )

        os.environ.pop("ALLOWED_FILE_EXTENSIONS", None)
        _reset_limiter_and_settings()

    def test_no_extension_returns_415(self):
        """Test that uploading a file with no extension returns 415."""
        os.environ["ALLOWED_FILE_EXTENSIONS"] = ".txt,.md,.json"
        os.environ.pop("REQUIRE_API_KEY", None)
        client = _make_client()

        content = "content without extension"
        files = {"file": ("Makefile", io.BytesIO(content.encode()), "text/plain")}
        data = {"skill_name": "test_skill"}

        response = client.post("/api/v1/execute/file", files=files, data=data)

        # No extension means we cannot validate - should reject
        assert response.status_code == 415, (
            f"Expected 415 for file with no extension, got {response.status_code}: {response.text}"
        )

        os.environ.pop("ALLOWED_FILE_EXTENSIONS", None)
        _reset_limiter_and_settings()

    def test_validation_happens_before_file_read(self):
        """Test that type validation occurs BEFORE reading file content.

        A disallowed file type gets rejected even when content is valid text.
        """
        os.environ["ALLOWED_FILE_EXTENSIONS"] = ".txt"
        os.environ["MAX_UPLOAD_SIZE_MB"] = "10"
        os.environ.pop("REQUIRE_API_KEY", None)
        client = _make_client()

        # Upload .exe with valid text content
        content = "perfectly valid UTF-8 text content"
        files = {"file": ("script.exe", io.BytesIO(content.encode()), "application/octet-stream")}
        data = {"skill_name": "test_skill"}

        response = client.post("/api/v1/execute/file", files=files, data=data)

        # Should be rejected for type (415) before any content processing
        assert response.status_code == 415, (
            f"Expected 415 for .exe file, got {response.status_code}: {response.text}"
        )

        os.environ.pop("ALLOWED_FILE_EXTENSIONS", None)
        os.environ.pop("MAX_UPLOAD_SIZE_MB", None)
        _reset_limiter_and_settings()


class TestFileUploadErrorMessages:
    """Tests for clear error messages in file upload validation."""

    def test_size_error_includes_limit(self):
        """Test that size validation error message includes the configured limit."""
        os.environ["MAX_UPLOAD_SIZE_MB"] = "1"
        os.environ.pop("REQUIRE_API_KEY", None)
        client = _make_client()

        large_content = "x" * (1 * 1024 * 1024 + 1)
        files = {"file": ("large.txt", io.BytesIO(large_content.encode()), "text/plain")}
        data = {"skill_name": "test_skill"}

        response = client.post("/api/v1/execute/file", files=files, data=data)

        assert response.status_code == 413, (
            f"Expected 413, got {response.status_code}: {response.text}"
        )
        detail = response.json().get("detail", "")
        # Error message should mention the limit
        assert "1" in detail or "MB" in detail.upper(), (
            f"Error message should mention size limit, got: {detail}"
        )

        os.environ.pop("MAX_UPLOAD_SIZE_MB", None)
        _reset_limiter_and_settings()

    def test_type_error_includes_allowed_extensions(self):
        """Test that type validation error message includes allowed extensions."""
        os.environ["ALLOWED_FILE_EXTENSIONS"] = ".txt,.md,.json"
        os.environ.pop("REQUIRE_API_KEY", None)
        client = _make_client()

        content = "fake content"
        files = {"file": ("file.exe", io.BytesIO(content.encode()), "application/octet-stream")}
        data = {"skill_name": "test_skill"}

        response = client.post("/api/v1/execute/file", files=files, data=data)

        assert response.status_code == 415, (
            f"Expected 415, got {response.status_code}: {response.text}"
        )
        detail = response.json().get("detail", "")
        # Error message should mention allowed extensions
        assert ".txt" in detail or "txt" in detail, (
            f"Error message should mention allowed extensions, got: {detail}"
        )

        os.environ.pop("ALLOWED_FILE_EXTENSIONS", None)
        _reset_limiter_and_settings()
