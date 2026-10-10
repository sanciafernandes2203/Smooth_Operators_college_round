"""
Audit Request/Response Schemas

Pydantic models for the audit API endpoints.
Per PROJECT_BIBLE.md §12 API Contract.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# -----------------------------------------------------------------------------
# Request Schemas
# -----------------------------------------------------------------------------

class AuditCreateRequest(BaseModel):
    """Request schema for creating an audit."""

    answer: str = Field(
        ...,
        description="The AI-generated answer to audit",
        min_length=1,
        max_length=50000,
    )
    source_text: Optional[str] = Field(
        default=None,
        description="Pasted source text to audit against",
        max_length=200000,
    )

    @field_validator("answer")
    @classmethod
    def answer_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Answer cannot be empty")
        return v.strip()

    @field_validator("source_text")
    @classmethod
    def source_text_not_whitespace(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            return None
        return v


# -----------------------------------------------------------------------------
# Response Schemas
# -----------------------------------------------------------------------------

class AuditCreateResponse(BaseModel):
    """Response schema for audit creation."""

    audit_id: UUID = Field(..., description="Unique identifier for the audit")
    status: str = Field(..., description="Current processing status: PROCESSING, COMPLETED, FAILED")
    created_at: datetime = Field(..., description="ISO 8601 timestamp of creation")


class AuditListItem(BaseModel):
    """Schema for audit list items in history."""

    audit_id: UUID = Field(..., description="Unique identifier for the audit")
    status: str = Field(..., description="Current processing status")
    total_claims: int = Field(..., description="Total number of claims in this audit")
    created_at: datetime = Field(..., description="ISO 8601 timestamp of creation")


class AuditListResponse(BaseModel):
    """Response schema for audit history list."""

    items: list[AuditListItem]


# -----------------------------------------------------------------------------
# Full Audit Response (for completed audits - from §12.4)
# -----------------------------------------------------------------------------

class EvidenceResponse(BaseModel):
    """Evidence passage in audit response."""

    document_id: UUID = Field(..., description="Source document identifier")
    document_name: str = Field(..., description="Source document filename")
    page_number: Optional[int] = Field(None, description="Page number if available")
    quote: str = Field(..., description="Exact quotation from source")
    relationship: str = Field(..., description="Relationship: supports, contradicts, context, insufficient")
    validated: bool = Field(..., description="Whether quotation was validated against source")


class ClaimResponse(BaseModel):
    """Claim with verdict and evidence in audit response."""

    claim_id: UUID = Field(..., description="Unique identifier for the claim")
    claim_text: str = Field(..., description="The claim text")
    verdict: str = Field(..., description="Verdict: SUPPORTED, CONTRADICTED, UNSUPPORTED, AMBIGUOUS, POTENTIALLY_UNSAFE, UNABLE_TO_ASSESS")
    explanation: str = Field(..., description="Explanation of the verdict")
    evidence_strength: Optional[str] = Field(None, description="Evidence strength: strong, moderate, weak")
    evidence: list[EvidenceResponse] = Field(default_factory=list, description="Supporting evidence passages")
    requires_review: bool = Field(False, description="Whether claim requires human review")


class AuditSummaryResponse(BaseModel):
    """Summary counts for audit response."""

    total_claims: int = Field(..., description="Total number of claims")
    supported: int = Field(0, description="Number of supported claims")
    contradicted: int = Field(0, description="Number of contradicted claims")
    unsupported: int = Field(0, description="Number of unsupported claims")
    ambiguous: int = Field(0, description="Number of ambiguous claims")
    potentially_unsafe: int = Field(0, description="Number of potentially unsafe claims")
    unable_to_assess: int = Field(0, description="Number of claims unable to assess")


class AuditDetailResponse(BaseModel):
    """Full audit detail response (for completed audits)."""

    audit_id: UUID
    status: str
    summary: AuditSummaryResponse
    claims: list[ClaimResponse]
    created_at: datetime