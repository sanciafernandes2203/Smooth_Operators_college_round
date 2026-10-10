"""
Audit API Routes

POST /api/audits - Create a new audit
GET  /api/audits - List audit history
GET  /api/audits/{audit_id} - Get audit details

Per PROJECT_BIBLE.md §12 API Contract.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_db_session
from app.db.repositories import DatabaseError
from app.schemas.audit import (
    AuditCreateRequest,
    AuditCreateResponse,
    AuditDetailResponse,
    AuditListItem,
    AuditListResponse,
)
from app.schemas.errors import ErrorCodes, create_error_response
from app.services.audit_service import AuditService
from app.utils.file_validation import (
    FileValidationError,
    validate_upload_file,
)
from fastapi import Query
from fastapi.responses import PlainTextResponse

router = APIRouter()


async def get_audit_service(session: AsyncSession = Depends(get_db_session)) -> AuditService:
    """Dependency to get AuditService with database session."""
    return AuditService(session)


@router.post(
    "/audits",
    response_model=AuditCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new audit",
    description="Submit an AI-generated answer and optional source text/files for auditing. Returns an audit ID and initial processing status.",
    responses={
        201: {"description": "Audit created successfully", "model": AuditCreateResponse},
        400: {"description": "Invalid input", "model": create_error_response.__annotations__["return"]},
        413: {"description": "Input too large", "model": create_error_response.__annotations__["return"]},
        415: {"description": "Unsupported file type", "model": create_error_response.__annotations__["return"]},
        500: {"description": "Database error", "model": create_error_response.__annotations__["return"]},
    },
)
async def create_audit(
    answer: str = Form(..., description="The AI-generated answer to audit"),
    source_text: Optional[str] = Form(None, description="Pasted source text to audit against"),
    files: list[UploadFile] = File(default_factory=list, description="Uploaded source files (PDF, TXT, JPG, PNG)"),
    audit_service: AuditService = Depends(get_audit_service),
    settings=Depends(get_settings),
) -> AuditCreateResponse:
    """
    Create a new audit submission.

    Accepts:
    - answer: Required AI-generated answer text
    - source_text: Optional pasted source text
    - files: Optional uploaded files (PDF, TXT, JPG, JPEG, PNG)

    Returns:
    - audit_id: Unique identifier for the audit
    - status: Initial processing status (PROCESSING)
    - created_at: Timestamp of creation
    """
    # Validate required fields
    if not answer or not answer.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code=ErrorCodes.INVALID_INPUT,
                message="Answer is required and cannot be empty",
            ).model_dump(),
        )

    # Validate at least one source is provided
    has_source_text = source_text and source_text.strip()
    has_files = files and any(f.filename for f in files)

    if not has_source_text and not has_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code=ErrorCodes.INVALID_INPUT,
                message="At least one source must be provided (source_text or files)",
            ).model_dump(),
        )

    # Validate input sizes
    max_upload_size = settings.max_upload_size_bytes
    if len(answer.encode("utf-8")) > max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=create_error_response(
                code=ErrorCodes.FILE_TOO_LARGE,
                message=f"Answer exceeds maximum size of {settings.max_upload_size_mb} MB",
            ).model_dump(),
        )

    if source_text and len(source_text.encode("utf-8")) > max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=create_error_response(
                code=ErrorCodes.FILE_TOO_LARGE,
                message=f"Source text exceeds maximum size of {settings.max_upload_size_mb} MB",
            ).model_dump(),
        )

    # Validate and read files
    processed_files = []
    for file in files:
        if not file.filename:
            continue

        try:
            content, safe_filename = await validate_upload_file(file, max_size_mb=settings.max_upload_size_mb)
            processed_files.append((content, safe_filename, file.content_type or "application/octet-stream"))
        except FileValidationError as e:
            raise HTTPException(
                status_code=(
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
                    if e.code == ErrorCodes.UNSUPPORTED_FILE_TYPE
                    else status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                ),
                detail=create_error_response(
                    code=e.code,
                    message=e.message,
                ).model_dump(),
            )

    # Re-validate at least one source after file validation
    if not has_source_text and not processed_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code=ErrorCodes.INVALID_INPUT,
                message="At least one source must be provided (source_text or files)",
            ).model_dump(),
        )

    try:
        # Create audit with file processing
        result = await audit_service.create_audit_with_files(
            answer=answer.strip(),
            source_text=source_text.strip() if source_text else None,
            files=processed_files,
        )
        return result

    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                code=e.code,
                message=f"Database error: {e.message}",
            ).model_dump(),
        )
    except Exception as e:
        # Don't expose internal errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                code=ErrorCodes.INTERNAL_SERVER_ERROR,
                message="Failed to create audit",
            ).model_dump(),
        )


@router.get(
    "/audits",
    response_model=AuditListResponse,
    summary="List audit history",
    description="Retrieve a paginated list of previous audits.",
    responses={
        200: {"description": "List of audits", "model": AuditListResponse},
        500: {"description": "Database error", "model": create_error_response.__annotations__["return"]},
    },
)
async def list_audits(
    limit: int = 50,
    offset: int = 0,
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditListResponse:
    """
    List audit history with pagination.

    Query parameters:
    - limit: Maximum number of audits to return (default 50, max 100)
    - offset: Number of audits to skip (default 0)
    """
    # Clamp limit
    limit = min(max(1, limit), 100)
    offset = max(0, offset)

    try:
        audits = await audit_service.list_audits(limit=limit, offset=offset)
        items = [
            AuditListItem(
                audit_id=audit.id,
                status=audit.status,
                total_claims=audit.total_claims,
                created_at=audit.created_at,
            )
            for audit in audits
        ]
        return AuditListResponse(items=items)

    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                code=e.code,
                message=f"Database error: {e.message}",
            ).model_dump(),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                code=ErrorCodes.INTERNAL_SERVER_ERROR,
                message="Failed to retrieve audit history",
            ).model_dump(),
        )


@router.get(
    "/audits/{audit_id}",
    response_model=AuditDetailResponse,
    summary="Get audit details",
    description="Retrieve the full audit result including claims, verdicts, and evidence.",
    responses={
        200: {"description": "Audit details", "model": AuditDetailResponse},
        404: {"description": "Audit not found", "model": create_error_response.__annotations__["return"]},
        500: {"description": "Database error", "model": create_error_response.__annotations__["return"]},
    },
)
async def get_audit(
    audit_id: UUID,
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditDetailResponse:
    """
    Get a single audit by ID with full details.

    Returns 404 if audit does not exist.
    """
    try:
        audit = await audit_service.get_audit(audit_id)
        if audit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=create_error_response(
                    code=ErrorCodes.AUDIT_NOT_FOUND,
                    message=f"Audit with ID {audit_id} not found",
                ).model_dump(),
            )

        # Build response from audit data
        # Note: For Stage 3, claims and evidence will be empty since processing
        # is not yet implemented. This structure supports later stages.
        claims_response = []
        for claim in audit.claims:
            evidence_response = []
            for ev in claim.evidence:
                doc_name = ev.document.file_name if ev.document else "unknown"
                evidence_response.append(
                    EvidenceResponse(
                        document_id=ev.document_id or UUID("00000000-0000-0000-0000-000000000000"),
                        document_name=doc_name,
                        page_number=ev.page_number,
                        quote=ev.passage_text,
                        relationship=ev.relationship,
                        validated=ev.validated,
                    )
                )
            claims_response.append(
                ClaimResponse(
                    claim_id=claim.id,
                    claim_text=claim.claim_text,
                    verdict=claim.verdict,
                    explanation=claim.explanation,
                    evidence_strength=claim.evidence_strength,
                    evidence=evidence_response,
                    requires_review=claim.requires_review,
                )
            )

        # Calculate summary counts
        verdict_counts = {
            "supported": 0,
            "contradicted": 0,
            "unsupported": 0,
            "ambiguous": 0,
            "potentially_unsafe": 0,
            "unable_to_assess": 0,
        }
        for claim in audit.claims:
            verdict_key = claim.verdict.lower()
            if verdict_key in verdict_counts:
                verdict_counts[verdict_key] += 1

        summary = AuditSummaryResponse(
            total_claims=audit.total_claims,
            **verdict_counts,
        )

        return AuditDetailResponse(
            audit_id=audit.id,
            status=audit.status,
            summary=summary,
            claims=claims_response,
            created_at=audit.created_at,
        )

    except HTTPException:
        raise
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                code=e.code,
                message=f"Database error: {e.message}",
            ).model_dump(),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                code=ErrorCodes.INTERNAL_SERVER_ERROR,
                message="Failed to retrieve audit",
            ).model_dump(),
        )


@router.post(
    "/audits/{audit_id}/process",
    response_model=dict,
    summary="Process a full audit",
    description="Trigger the full audit pipeline: claim extraction, evidence retrieval, verification, and validation.",
    responses={
        200: {"description": "Audit processed successfully"},
        404: {"description": "Audit not found", "model": create_error_response.__annotations__["return"]},
        500: {"description": "Processing error", "model": create_error_response.__annotations__["return"]},
    },
)
async def process_audit(
    audit_id: UUID,
    audit_service: AuditService = Depends(get_audit_service),
) -> dict:
    """
    Process a full audit pipeline.

    This endpoint triggers the complete audit pipeline:
    1. Extract claims from the answer
    2. Retrieve evidence for each claim
    3. Verify each claim against evidence
    4. Validate evidence quotations and references

    Returns the processing results.
    """
    try:
        result = await audit_service.process_full_audit(audit_id)
        return result
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                code=e.code,
                message=f"Database error: {e.message}",
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                code=ErrorCodes.INTERNAL_SERVER_ERROR,
                message=f"Failed to process audit: {str(e)}",
            ).model_dump(),
        )


@router.get(
    "/audits/{audit_id}/report",
    summary="Get audit report",
    description="Generate and retrieve the audit report in the specified format.",
    responses={
        200: {"description": "Audit report", "content": {"text/markdown": {}, "application/json": {}}},
        404: {"description": "Audit not found", "model": create_error_response.__annotations__["return"]},
        500: {"description": "Report generation error", "model": create_error_response.__annotations__["return"]},
    },
)
async def get_audit_report(
    audit_id: UUID,
    format: str = Query(default="markdown", description="Report format: 'markdown' or 'json'"),
    audit_service: AuditService = Depends(get_audit_service),
) -> PlainTextResponse:
    """
    Generate and retrieve the audit report in the specified format.

    Supported formats:
    - markdown (default): Human-readable Markdown report
    - json: Structured JSON report

    Returns the report as plain text with appropriate content type.
    """
    try:
        audit = await audit_service.get_audit(audit_id)
        if audit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=create_error_response(
                    code=ErrorCodes.AUDIT_NOT_FOUND,
                    message=f"Audit with ID {audit_id} not found",
                ).model_dump(),
            )

        # Generate report
        format_lower = format.lower()
        if format_lower not in ("markdown", "json"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=create_error_response(
                    code=ErrorCodes.INVALID_INPUT,
                    message=f"Unsupported format: {format}. Supported formats: markdown, json",
                ).model_dump(),
            )

        report = audit_service.generate_report(audit, format_lower)

        media_type = "text/markdown" if format_lower == "markdown" else "application/json"
        return PlainTextResponse(content=report, media_type=media_type)

    except HTTPException:
        raise
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                code=e.code,
                message=f"Database error: {e.message}",
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                code=ErrorCodes.INTERNAL_SERVER_ERROR,
                message=f"Failed to generate report: {str(e)}",
            ).model_dump(),
        )