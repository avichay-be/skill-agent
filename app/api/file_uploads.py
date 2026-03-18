"""Shared helpers for multipart file upload endpoints."""

import logging
import os

from fastapi import HTTPException, UploadFile, status

logger = logging.getLogger(__name__)


async def read_uploaded_text_file(
    file: UploadFile,
    *,
    allowed_file_extensions: list[str],
    max_upload_size_mb: int,
) -> str:
    """Validate and decode an uploaded text-like file."""
    filename = file.filename or ""
    _, file_ext = os.path.splitext(filename)
    file_ext_lower = file_ext.lower()

    if not file_ext_lower or file_ext_lower not in allowed_file_extensions:
        allowed = ", ".join(allowed_file_extensions)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"File type '{file_ext_lower or '(none)'}' is not supported. "
                f"Allowed file extensions: {allowed}"
            ),
        )

    content_bytes = await file.read()
    max_size_bytes = max_upload_size_mb * 1024 * 1024
    if len(content_bytes) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds the maximum allowed size of {max_upload_size_mb} MB.",
        )

    try:
        return content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
            try:
                logger.info("Successfully decoded file using %s encoding", encoding)
                return content_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error reading file: {str(exc)}",
        ) from exc

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "Unable to decode file. Unsupported encoding. "
            "Please upload a text file or convert to UTF-8."
        ),
    )
