"""
Claim Extraction Schemas

Pydantic models for claim extraction input/output.
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ExtractedClaim(BaseModel):
    """A single claim extracted from an answer."""

    claim_text: str = Field(
        ...,
        description="The exact claim text as it appears in the answer",
        min_length=1,
    )
    is_checkable: bool = Field(
        default=True,
        description="Whether this claim can be verified against source material",
    )
    reason_not_checkable: Optional[str] = Field(
        default=None,
        description="Reason why the claim is not checkable (opinion, vague, etc.)",
    )


class ClaimExtractionRequest(BaseModel):
    """Request for claim extraction."""

    answer: str = Field(
        ...,
        description="The AI-generated answer to extract claims from",
        min_length=1,
    )

    @field_validator("answer")
    @classmethod
    def answer_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Answer cannot be empty or whitespace only")
        return v.strip()


class ClaimExtractionResponse(BaseModel):
    """Response from claim extraction."""

    claims: list[ExtractedClaim] = Field(
        default_factory=list,
        description="List of extracted claims",
    )
    total_claims: int = Field(
        default=0,
        description="Total number of claims extracted",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if extraction failed",
    )


class ClaimCreate(BaseModel):
    """Schema for creating a claim in the database."""

    audit_id: UUID
    claim_text: str
    verdict: str = "PENDING"
    explanation: str = ""
    evidence_strength: Optional[str] = None
    requires_review: bool = False