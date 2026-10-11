"""
File validation utilities for document uploads.

Validates file extensions, MIME types, sizes, and content.
"""
import os
from typing import Optional
from uuid import uuid4

from fastapi import UploadFile

from app.config import get_settings
from app.schemas.errors import ErrorCodes


# Supported file types
SUPPORTED_MIME_TYPES = {
    # Text files
    "text/plain": [".txt"],
    # PDF files
    "application/pdf": [".pdf"],
    # Image files
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
}

# Allowed extensions (lowercase)
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".jpg", ".jpeg", ".png"}

# Maximum file size (15 MB default, configurable via settings)
MAX_FILE_SIZE_MB = 15


class FileValidationError(Exception):
    """Raised when file validation fails."""

    def __init__(self, message: str, code: str = ErrorCodes.UNSUPPORTED_FILE_TYPE):
        self.message = message
        self.code = code
        super().__init__(message)


def get_file_extension(filename: str) -> str:
    """Extract and return the file extension in lowercase."""
    return os.path.splitext(filename)[1].lower()


def is_allowed_extension(filename: str) -> bool:
    """Check if file extension is allowed."""
    ext = get_file_extension(filename)
    return ext in ALLOWED_EXTENSIONS


def is_allowed_mime_type(mime_type: Optional[str]) -> bool:
    """Check if MIME type is allowed."""
    if not mime_type:
        return False
    return mime_type in SUPPORTED_MIME_TYPES


def validate_file_extension(filename: str) -> None:
    """Validate file extension. Raises FileValidationError if invalid."""
    if not filename:
        raise FileValidationError("File has no name", ErrorCodes.INVALID_INPUT)

    if not is_allowed_extension(filename):
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise FileValidationError(
            f"Unsupported file type: '{filename}'. Allowed: {allowed}",
            ErrorCodes.UNSUPPORTED_FILE_TYPE,
        )


def validate_mime_type(mime_type: Optional[str], filename: str) -> None:
    """Validate MIME type matches extension. Raises FileValidationError if invalid."""
    if not mime_type:
        # If no MIME type provided, infer from extension
        return

    if not is_allowed_mime_type(mime_type):
        allowed_mimes = ", ".join(SUPPORTED_MIME_TYPES.keys())
        raise FileValidationError(
            f"Unsupported MIME type: '{mime_type}'. Allowed: {allowed_mimes}",
            ErrorCodes.UNSUPPORTED_FILE_TYPE,
        )

    # Check extension matches MIME type
    ext = get_file_extension(filename)
    expected_extensions = SUPPORTED_MIME_TYPES.get(mime_type, [])
    if ext not in expected_extensions:
        raise FileValidationError(
            f"File extension '{ext}' does not match MIME type '{mime_type}'",
            ErrorCodes.UNSUPPORTED_FILE_TYPE,
        )


def validate_file_size(file_size: int, max_size_mb: Optional[int] = None) -> None:
    """Validate file size. Raises FileValidationError if too large."""
    limit_mb = max_size_mb or MAX_FILE_SIZE_MB
    limit_bytes = limit_mb * 1024 * 1024

    if file_size > limit_bytes:
        raise FileValidationError(
            f"File size ({file_size / (1024*1024):.1f} MB) exceeds limit of {limit_mb} MB",
            ErrorCodes.FILE_TOO_LARGE,
        )


async def validate_upload_file(
    file: UploadFile,
    max_size_mb: Optional[int] = None,
) -> tuple[bytes, str]:
    """
    Validate an uploaded file and return its content and a safe filename.

    Returns:
        Tuple of (file_content, safe_filename)

    Raises:
        FileValidationError: If validation fails
    """
    # Validate filename
    if not file.filename:
        raise FileValidationError("File has no filename", ErrorCodes.INVALID_INPUT)

    original_filename = file.filename
    validate_file_extension(original_filename)

    # Read file content
    content = await file.read()

    # Validate size
    validate_file_size(len(content), max_size_mb)

    # Validate MIME type
    validate_mime_type(file.content_type, original_filename)

    # Generate safe filename (preserve extension, use UUID for name)
    ext = get_file_extension(original_filename)
    safe_filename = f"{uuid4()}{ext}"

    return content, safe_filename


def get_file_type_category(mime_type: Optional[str], filename: str) -> str:
    """
    Determine the file type category for processing.

    Returns one of: 'text', 'pdf', 'image'
    """
    if not mime_type:
        mime_type = ""

    if mime_type == "text/plain" or get_file_extension(filename) == ".txt":
        return "text"
    elif mime_type == "application/pdf" or get_file_extension(filename) == ".pdf":
        return "pdf"
    elif mime_type in ("image/jpeg", "image/png") or get_file_extension(filename) in (
        ".jpg",
        ".jpeg",
        ".png",
    ):
        return "image"

    return "unknown"