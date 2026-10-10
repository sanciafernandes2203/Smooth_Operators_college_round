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

router = APIRouter()


async def get_audit_service(session: AsyncSession = Depends(get_db_session)) -> AuditService:
    """Dependency to get AuditService with database session."""
    return AuditService(session)


@router.post(
    "/audits",
    response_model=AuditCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new audit",
    description="Submit an AI-generated answer and optional source text for auditing. Returns an audit ID and initial processing status.",
    responses={
        201: {"description": "Audit created successfully", "model": AuditCreateResponse},
        400: {"description": "Invalid input", "model": create_error_response.__annotations__["return"]},
        413: {"description": "Input too large", "model": create_error_response.__annotations__["return"]},
        500: {"description": "Database error", "model": create_error_response.__annotations__["return"]},
    },
)
async def create_audit(
    answer: str = Form(..., description="The AI-generated answer to audit"),
    source_text: Optional[str] = Form(None, description="Pasted source text to audit against"),
    files: list[UploadFile] = File(default_factory=list, description="Uploaded source files (not processed in Stage 3)"),
    audit_service: AuditService = Depends(get_audit_service),
    settings=Depends(get_settings),
) -> AuditCreateResponse:
    """
    Create a new audit submission.

    Accepts:
    - answer: Required AI-generated answer text
    - source_text: Optional pasted source text
    - files: Optional uploaded files (stored but not processed in Stage 3)

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
    max_answer_size = settings.max_upload_size_bytes  # Reuse upload limit for answer
    if len(answer.encode("utf-8")) > max_answer_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=create_error_response(
                code=ErrorCodes.FILE_TOO_LARGE,
                message=f"Answer exceeds maximum size of {settings.max_upload_size_mb} MB",
            ).model_dump(),
        )

    if source_text and len(source_text.encode("utf-8")) > max_answer_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=create_error_response(
                code=ErrorCodes.FILE_TOO_LARGE,
                message=f"Source text exceeds maximum size of {settings.max_upload_size_mb} MB",
            ).model_dump(),
        )

    # Validate file sizes and types (basic validation for Stage 3)
    for file in files:
        if file.filename:
            content = await file.read()
            if len(content) > max_answer_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=create_error_response(
                        code=ErrorCodes.FILE_TOO_LARGE,
                        message=f"File '{file.filename}' exceeds maximum size of {settings.max_upload_size_mb} MB",
                    ).model_dump(),
                )
            # Reset file position for potential future processing
            await file.seek(0)

    try:
        # Create audit with the service
        result = await audit_service.create_audit(
            answer=answer.strip(),
            source_text=source_text.strip() if source_text else None,
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