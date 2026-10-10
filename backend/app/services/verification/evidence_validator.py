"""
Evidence Validation Service (Stage 9)

Validates that evidence returned by the verifier genuinely exists in the supplied
source material and that the reported source references are accurate.
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional, List
from uuid import UUID

from app.services.documents.text_chunker import TextPassage
from app.schemas.audit import EvidenceResponse

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Represents a validation issue found during evidence validation."""
    severity: str  # "error", "warning", "info"
    code: str  # e.g., "QUOTE_NOT_FOUND", "PAGE_MISMATCH", "DOCUMENT_NOT_FOUND"
    message: str
    evidence_index: int  # Index of the evidence item in the claim's evidence list


@dataclass
class EvidenceValidationResult:
    """Result of evidence validation for a single evidence item."""
    validated: bool
    issues: List[ValidationIssue]
    matched_passage: Optional[str] = None  # The matched text from source
    matched_char_start: Optional[int] = None
    matched_char_end: Optional[int] = None


@dataclass
class ClaimValidationResult:
    """Result of validation for all evidence of a single claim."""
    claim_id: UUID
    claim_text: str
    verdict: str
    evidence_validations: List[EvidenceValidationResult]
    has_errors: bool = False
    has_warnings: bool = False


class EvidenceValidator:
    """
    Validates evidence quotations and source references against actual source material.
    """

    def __init__(
        self,
        normalize_whitespace: bool = True,
        allow_partial_match: bool = True,
        min_match_ratio: float = 0.9,
    ):
        """
        Initialize the evidence validator.

        Args:
            normalize_whitespace: Whether to normalize whitespace for comparison
            allow_partial_match: Whether to allow partial matching for near matches
            min_match_ratio: Minimum similarity ratio for a match to be considered valid (0-1)
        """
        self.normalize_whitespace = normalize_whitespace
        self.allow_partial_match = allow_partial_match
        self.min_match_ratio = min_match_ratio

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        if self.normalize_whitespace:
            text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _find_quote_in_source(
        self,
        quote: str,
        source_text: str,
    ) -> tuple[Optional[int], Optional[int], float]:
        """
        Find a quote in source text.

        Returns:
            Tuple of (start_index, end_index, match_ratio)
            Returns (None, None, 0.0) if not found
        """
        norm_quote = self._normalize_text(quote)
        norm_source = self._normalize_text(source_text)

        if not norm_quote or not norm_source:
            return None, None, 0.0

        # Try exact match first
        idx = norm_source.find(norm_quote)
        if idx != -1:
            return idx, idx + len(norm_quote), 1.0

        # Try partial match if enabled
        if self.allow_partial_match and len(norm_quote) > 20:
            # Try to find the longest matching substring
            best_ratio = 0.0
            best_start = None
            best_end = None

            # Try matching from start of quote
            for length in range(len(norm_quote), max(20, len(norm_quote) // 2), -10):
                sub = norm_quote[:length]
                idx = norm_source.find(sub)
                if idx != -1:
                    ratio = len(sub) / len(norm_quote)
                    if ratio >= self.min_match_ratio:
                        return idx, idx + len(sub), ratio
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_start = idx
                        best_end = idx + len(sub)

                # Try matching from end of quote
                for length in range(len(norm_quote), max(20, len(norm_quote) // 2), -10):
                    sub = norm_quote[-length:]
                    idx = norm_source.find(sub)
                    if idx != -1:
                        ratio = len(sub) / len(norm_quote)
                        if ratio >= self.min_match_ratio:
                            return idx, idx + len(sub), ratio
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_start = idx
                            best_end = idx + len(sub)

            if best_start is not None:
                return best_start, best_end, best_ratio

        return None, None, 0.0

    def validate_evidence(
        self,
        evidence: EvidenceResponse,
        source_passages: List[TextPassage],
        source_documents: dict[UUID, SourceDocument],
    ) -> EvidenceValidationResult:
        """
        Validate a single evidence item against source material.

        Args:
            evidence: The evidence item to validate
            source_passages: List of all available source passages
            source_documents: Dict of source documents by ID

        Returns:
            EvidenceValidationResult with validation status and issues
        """
        issues = []

        # 1. Validate document ID exists
        doc_id = evidence.document_id
        if doc_id not in source_documents:
            issues.append(ValidationIssue(
                severity="error",
                code="DOCUMENT_NOT_FOUND",
                message=f"Document ID {doc_id} not found in source documents",
                evidence_index=0,
            ))
            return EvidenceValidationResult(validated=False, issues=issues)

        doc = source_documents[doc_id]

        # 2. Validate document name matches
        if evidence.document_name != doc.file_name:
            issues.append(ValidationIssue(
                severity="warning",
                code="DOCUMENT_NAME_MISMATCH",
                message=f"Document name '{evidence.document_name}' does not match stored filename '{doc.file_name}'",
                evidence_index=0,
            ))

        # 3. Validate page number if provided
        if evidence.page_number is not None:
            # Check if page number is valid for this document
            if doc.page_count is not None and evidence.page_number > doc.page_count:
                issues.append(ValidationIssue(
                    severity="error",
                    code="PAGE_NUMBER_OUT_OF_RANGE",
                    message=f"Page number {evidence.page_number} exceeds document page count {doc.page_count}",
                    evidence_index=0,
                ))
            elif doc.page_count is None:
                issues.append(ValidationIssue(
                    severity="warning",
                    code="PAGE_NUMBER_UNVERIFIABLE",
                    message=f"Page number {evidence.page_number} cannot be verified (document page count unknown)",
                    evidence_index=0,
                ))

        # 4. Validate quotation exists in source
        quote = evidence.quote
        if not quote or not quote.strip():
            issues.append(ValidationIssue(
                severity="error",
                code="EMPTY_QUOTE",
                message="Evidence quote is empty",
                evidence_index=0,
            ))
            return EvidenceValidationResult(validated=False, issues=issues)

        # Find the relevant passage(s) for this document
        doc_passages = [p for p in source_passages if p.document_id == doc_id]

        if not doc_passages:
            issues.append(ValidationIssue(
                severity="error",
                code="NO_SOURCE_TEXT",
                message=f"No source text available for document {doc.file_name}",
                evidence_index=0,
            ))
            return EvidenceValidationResult(validated=False, issues=issues)

        # Combine all text from this document's passages
        combined_text = "\n\n".join(p.text for p in doc_passages)

        # Find the quote in the source
        start_idx, end_idx, match_ratio = self._find_quote_in_source(quote, combined_text)

        if start_idx is None:
            issues.append(ValidationIssue(
                severity="error",
                code="QUOTE_NOT_FOUND",
                message=f"Quotation not found in source document: '{quote[:100]}...'",
                evidence_index=0,
            ))
            return EvidenceValidationResult(validated=False, issues=issues)

        if match_ratio < 1.0:
            issues.append(ValidationIssue(
                severity="warning",
                code="PARTIAL_QUOTE_MATCH",
                message=f"Quotation partially matches source (match ratio: {match_ratio:.2f}). Original: '{quote[:100]}...'",
                evidence_index=0,
            ))

        # 5. Validate evidence is associated with correct claim (this is done at claim level)
        # 6. Validate evidence traceability
        if doc.storage_path is None and doc.mime_type != "text/plain":
            issues.append(ValidationIssue(
                severity="info",
                code="SOURCE_NOT_RETAINED",
                message=f"Original source file not retained (storage_path is None)",
                evidence_index=0,
            ))

        # Return validation result
        validated = not any(i.severity == "error" for i in issues)
        matched_text = combined_text[start_idx:end_idx] if start_idx is not None else None

        return EvidenceValidationResult(
            validated=validated,
            issues=issues,
            matched_passage=matched_text,
            matched_char_start=start_idx,
            matched_char_end=end_idx,
        )

    def validate_claim_evidence(
        self,
        claim_id: UUID,
        claim_text: str,
        verdict: str,
        evidence_list: List[EvidenceResponse],
        source_passages: List[TextPassage],
        source_documents: dict[UUID, SourceDocument],
    ) -> ClaimValidationResult:
        """
        Validate all evidence for a single claim.

        Args:
            claim_id: The claim's UUID
            claim_text: The claim text
            verdict: The claim's verdict
            evidence_list: List of evidence items for this claim
            source_passages: All available source passages
            source_documents: Dict of source documents by ID

        Returns:
            ClaimValidationResult with validation for each evidence item
        """
        evidence_validations = []
        has_errors = False
        has_warnings = False

        for i, evidence in enumerate(evidence_list):
            validation = self.validate_evidence(evidence, source_passages, source_documents)
            evidence_validations.append(validation)

            if not validation.validated:
                has_errors = True
            if any(i.severity == "warning" for i in validation.issues):
                has_warnings = True

        return ClaimValidationResult(
            claim_id=claim_id,
            claim_text=claim_text,
            verdict=verdict,
            evidence_validations=evidence_validations,
            has_errors=has_errors,
            has_warnings=has_warnings,
        )

    def validate_audit_evidence(
        self,
        audit: "Audit",  # Forward reference, will import at runtime
        claims: List["Claim"],
        source_passages: List[TextPassage],
    ) -> List[ClaimValidationResult]:
        """
        Validate all evidence for all claims in an audit.

        Args:
            audit: The audit object with source_documents relationship loaded
            claims: List of claims with evidence relationships loaded
            source_passages: All available source passages

        Returns:
            List of ClaimValidationResult for each claim
        """
        # Build source documents dict
        source_documents = {doc.id: doc for doc in audit.source_documents}

        results = []
        for claim in claims:
            # Convert claim evidence to EvidenceResponse format
            evidence_list = []
            for ev in claim.evidence:
                evidence_list.append(EvidenceResponse(
                    document_id=ev.document_id,
                    document_name=ev.document.file_name if ev.document else "unknown",
                    page_number=ev.page_number,
                    quote=ev.passage_text,
                    relationship=ev.relationship_type,
                    validated=ev.validated,
                ))

            result = self.validate_claim_evidence(
                claim_id=claim.id,
                claim_text=claim.claim_text,
                verdict=claim.verdict,
                evidence_list=evidence_list,
                source_passages=source_passages,
                source_documents=source_documents,
            )
            results.append(result)

        return results


def create_evidence_validator(
    normalize_whitespace: bool = True,
    allow_partial_match: bool = True,
    min_match_ratio: float = 0.9,
) -> EvidenceValidator:
    """Create an evidence validator with default settings."""
    return EvidenceValidator(
        normalize_whitespace=normalize_whitespace,
        allow_partial_match=allow_partial_match,
        min_match_ratio=min_match_ratio,
    )