"""
Standard Error Response Schemas

Defines the consistent error format used across all API endpoints.
Per PROJECT_BIBLE.md §12.7.
"""
from typing import Optional, Any
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Standard error detail object."""
    code: str = Field(
        ...,
        description="Machine-readable error code",
        examples=["INVALID_INPUT", "LLM_PROVIDER_ERROR", "AUDIT_NOT_FOUND"],
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        examples=["Provide an answer and at least one source."],
    )
    details: Optional[Any] = Field(
        default=None,
        description="Optional additional error context (validation errors, etc.)",
    )


class ErrorResponse(BaseModel):
    """Standard error response wrapper."""
    error: ErrorDetail


# -----------------------------------------------------------------------------
# Pre-defined Error Codes (from PROJECT_BIBLE.md §12.7)
# -----------------------------------------------------------------------------
class ErrorCodes:
    """Standard error codes used across the API."""
    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    DOCUMENT_EXTRACTION_FAILED = "DOCUMENT_EXTRACTION_FAILED"
    OCR_FAILED = "OCR_FAILED"
    LLM_PROVIDER_ERROR = "LLM_PROVIDER_ERROR"
    INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"
    EVIDENCE_VALIDATION_FAILED = "EVIDENCE_VALIDATION_FAILED"
    DATABASE_ERROR = "DATABASE_ERROR"
    AUDIT_NOT_FOUND = "AUDIT_NOT_FOUND"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


def create_error_response(
    code: str,
    message: str,
    details: Optional[Any] = None,
) -> ErrorResponse:
    """Create a standardized error response."""
    return ErrorResponse(error=ErrorDetail(code=code, message=message, details=details))