"""
Evidence Validation Tests (Stage 9)
"""
import pytest
from uuid import uuid4
from dataclasses import dataclass
from typing import Optional

from app.services.verification.evidence_validator import (
    EvidenceValidator,
    EvidenceValidationResult,
    ClaimValidationResult,
    ValidationIssue,
    create_evidence_validator,
)
from app.services.documents.text_chunker import TextPassage
from app.schemas.audit import EvidenceResponse


@dataclass
class MockSourceDocument:
    """Mock source document for testing."""
    id: UUID
    file_name: str
    mime_type: str = "application/pdf"
    storage_path: Optional[str] = "/tmp/test.pdf"
    page_count: Optional[int] = 2


class TestEvidenceValidator:
    """Tests for evidence validation service."""

    @pytest.fixture
    def validator(self):
        """Create an evidence validator."""
        return create_evidence_validator()

    @pytest.fixture
    def doc_id(self):
        """Create a shared document ID for tests."""
        return uuid4()

    @pytest.fixture
    def sample_source_documents(self, doc_id):
        """Create sample source documents for testing."""
        return {
            doc_id: MockSourceDocument(
                id=doc_id,
                file_name="survey_report.pdf",
                mime_type="application/pdf",
                storage_path="/tmp/survey_report.pdf",
                page_count=2,
            )
        }

    @pytest.fixture
    def sample_passages(self, doc_id):
        """Create sample passages for testing."""
        return [
            TextPassage(
                passage_id=f"{doc_id}-p0",
                document_id=doc_id,
                document_name="survey_report.pdf",
                page_number=1,
                text="A survey of 200 students found that 60% preferred online notes.",
                char_start=0,
                char_end=65,
                source_type="pdf",
                extraction_method="pymupdf",
            ),
            TextPassage(
                passage_id=f"{doc_id}-p1",
                document_id=doc_id,
                document_name="survey_report.pdf",
                page_number=2,
                text="The survey did not collect examination score data.",
                char_start=66,
                char_end=112,
                source_type="pdf",
                extraction_method="pymupdf",
            ),
        ]

    def test_validate_exact_quote_match(self, validator, sample_passages, sample_source_documents):
        """Test validating an exact quotation that exists in the source."""
        doc_id = list(sample_source_documents.keys())[0]

        evidence = EvidenceResponse(
            document_id=doc_id,
            document_name="survey_report.pdf",
            page_number=1,
            quote="A survey of 200 students found that 60% preferred online notes.",
            relationship="supports",
            validated=False,
        )

        result = validator.validate_evidence(evidence, sample_passages, sample_source_documents)

        assert result.validated is True
        assert result.matched_passage == "A survey of 200 students found that 60% preferred online notes."
        assert len([i for i in result.issues if i.severity == "error"]) == 0

    def test_validate_quote_not_in_source(self, validator, sample_passages, sample_source_documents):
        """Test validating a quotation that does not exist in the source."""
        doc_id = list(sample_source_documents.keys())[0]

        evidence = EvidenceResponse(
            document_id=doc_id,
            document_name="survey_report.pdf",
            page_number=1,
            quote="The survey included 500 students.",
            relationship="contradicts",
            validated=False,
        )

        result = validator.validate_evidence(evidence, sample_passages, sample_source_documents)

        assert result.validated is False
        assert any(i.code == "QUOTE_NOT_FOUND" for i in result.issues)

    def test_validate_wrong_document(self, validator, sample_passages, sample_source_documents):
        """Test validating a quotation associated with the wrong document."""
        doc_id = uuid4()  # Different document ID

        evidence = EvidenceResponse(
            document_id=doc_id,
            document_name="survey_report.pdf",
            page_number=1,
            quote="A survey of 200 students found that 60% preferred online notes.",
            relationship="supports",
            validated=False,
        )

        result = validator.validate_evidence(evidence, sample_passages, sample_source_documents)

        assert result.validated is False
        assert any(i.code == "DOCUMENT_NOT_FOUND" for i in result.issues)

    def test_validate_incorrect_page_number(self, validator, sample_passages, sample_source_documents):
        """Test validating with an incorrect page number."""
        doc_id = list(sample_source_documents.keys())[0]

        evidence = EvidenceResponse(
            document_id=doc_id,
            document_name="survey_report.pdf",
            page_number=999,  # Page doesn't exist
            quote="A survey of 200 students found that 60% preferred online notes.",
            relationship="supports",
            validated=False,
        )

        result = validator.validate_evidence(evidence, sample_passages, sample_source_documents)

        assert any(i.code == "PAGE_NUMBER_OUT_OF_RANGE" for i in result.issues)

    def test_validate_empty_quote(self, validator, sample_passages, sample_source_documents):
        """Test validating an empty quotation."""
        doc_id = list(sample_source_documents.keys())[0]

        evidence = EvidenceResponse(
            document_id=doc_id,
            document_name="survey_report.pdf",
            page_number=1,
            quote="",
            relationship="supports",
            validated=False,
        )

        result = validator.validate_evidence(evidence, sample_passages, sample_source_documents)

        assert result.validated is False
        assert any(i.code == "EMPTY_QUOTE" for i in result.issues)

    def test_validate_empty_source_passages(self, validator, sample_source_documents):
        """Test validating when no source passages are available."""
        doc_id = list(sample_source_documents.keys())[0]

        evidence = EvidenceResponse(
            document_id=doc_id,
            document_name="survey_report.pdf",
            page_number=1,
            quote="Some quote",
            relationship="supports",
            validated=False,
        )

        result = validator.validate_evidence(evidence, [], sample_source_documents)

        assert result.validated is False
        assert any(i.code == "NO_SOURCE_TEXT" for i in result.issues)

    def test_validate_preserves_percentage_sign(self, validator, sample_passages, sample_source_documents):
        """Test that percentage signs are preserved in validation."""
        doc_id = list(sample_source_documents.keys())[0]

        evidence = EvidenceResponse(
            document_id=doc_id,
            document_name="survey_report.pdf",
            page_number=1,
            quote="60% preferred online notes",
            relationship="supports",
            validated=False,
        )

        result = validator.validate_evidence(evidence, sample_passages, sample_source_documents)

        # Should find the 60% in the source
        assert result.validated is True
        assert "60%" in result.matched_passage

    def test_validate_whitespace_normalization(self, validator, sample_passages, sample_source_documents):
        """Test that whitespace normalization works for validation."""
        doc_id = list(sample_source_documents.keys())[0]

        # Quote with different whitespace
        evidence = EvidenceResponse(
            document_id=doc_id,
            document_name="survey_report.pdf",
            page_number=1,
            quote="A  survey  of  200  students  found  that  60%  preferred  online  notes.",
            relationship="supports",
            validated=False,
        )

        result = validator.validate_evidence(evidence, sample_passages, sample_source_documents)

        # Should still match after whitespace normalization
        assert result.validated is True

    def test_validate_document_name_mismatch(self, validator, sample_passages, sample_source_documents):
        """Test warning when document name doesn't match."""
        doc_id = list(sample_source_documents.keys())[0]

        evidence = EvidenceResponse(
            document_id=doc_id,
            document_name="wrong_name.pdf",  # Mismatch
            page_number=1,
            quote="A survey of 200 students found that 60% preferred online notes.",
            relationship="supports",
            validated=False,
        )

        result = validator.validate_evidence(evidence, sample_passages, sample_source_documents)

        assert any(i.code == "DOCUMENT_NAME_MISMATCH" for i in result.issues)

    def test_validate_partial_match_warning(self, validator, sample_passages, sample_source_documents):
        """Test warning when quote partially matches (not fully found)."""
        doc_id = list(sample_source_documents.keys())[0]

        # Partial quote - only the first part, cut off mid-sentence
        evidence = EvidenceResponse(
            document_id=doc_id,
            document_name="survey_report.pdf",
            page_number=1,
            quote="A survey of 200 students found that 60% preferred online notes. The survey also found",
            relationship="supports",
            validated=False,
        )

        result = validator.validate_evidence(evidence, sample_passages, sample_source_documents)

        # Should still validate but with warning about partial match (quote extends beyond source)
        assert result.validated is True
        assert any(i.code == "PARTIAL_QUOTE_MATCH" for i in result.issues)


class TestClaimValidation:
    """Tests for claim-level validation."""

    @pytest.fixture
    def validator(self):
        return create_evidence_validator()

    @pytest.fixture
    def doc_id(self):
        """Create a shared document ID for tests."""
        return uuid4()

    @pytest.fixture
    def sample_source_documents(self, doc_id):
        return {
            doc_id: MockSourceDocument(
                id=doc_id,
                file_name="survey_report.pdf",
                mime_type="application/pdf",
                page_count=2,
            )
        }

    @pytest.fixture
    def sample_passages(self, doc_id):
        return [
            TextPassage(
                passage_id=f"{doc_id}-p0",
                document_id=doc_id,
                document_name="survey_report.pdf",
                page_number=1,
                text="A survey of 200 students found that 60% preferred online notes.",
                char_start=0,
                char_end=65,
                source_type="pdf",
                extraction_method="pymupdf",
            ),
            TextPassage(
                passage_id=f"{doc_id}-p1",
                document_id=doc_id,
                document_name="survey_report.pdf",
                page_number=2,
                text="The survey did not collect examination score data.",
                char_start=66,
                char_end=112,
                source_type="pdf",
                extraction_method="pymupdf",
            ),
        ]

    def test_validate_claim_with_valid_evidence(self, validator, sample_passages, sample_source_documents):
        """Test validating a claim with all valid evidence."""
        doc_id = list(sample_source_documents.keys())[0]

        evidence_list = [
            EvidenceResponse(
                document_id=doc_id,
                document_name="survey_report.pdf",
                page_number=1,
                quote="A survey of 200 students found that 60% preferred online notes.",
                relationship="supports",
                validated=False,
            )
        ]

        result = validator.validate_claim_evidence(
            claim_id=uuid4(),
            claim_text="The survey included 200 students.",
            verdict="SUPPORTED",
            evidence_list=evidence_list,
            source_passages=sample_passages,
            source_documents=sample_source_documents,
        )

        assert result.claim_text == "The survey included 200 students."
        assert result.verdict == "SUPPORTED"
        assert len(result.evidence_validations) == 1
        assert result.evidence_validations[0].validated is True
        assert result.has_errors is False

    def test_validate_claim_with_invalid_evidence(self, validator, sample_passages, sample_source_documents):
        """Test validating a claim with invalid evidence."""
        doc_id = list(sample_source_documents.keys())[0]

        evidence_list = [
            EvidenceResponse(
                document_id=doc_id,
                document_name="survey_report.pdf",
                page_number=1,
                quote="The survey included 500 students.",  # Not in source
                relationship="contradicts",
                validated=False,
            )
        ]

        result = validator.validate_claim_evidence(
            claim_id=uuid4(),
            claim_text="The survey included 500 students.",
            verdict="CONTRADICTED",
            evidence_list=evidence_list,
            source_passages=sample_passages,
            source_documents=sample_source_documents,
        )

        assert result.has_errors is True
        assert len(result.evidence_validations) == 1
        assert result.evidence_validations[0].validated is False

    def test_validate_claim_with_no_evidence(self, validator, sample_passages, sample_source_documents):
        """Test validating a claim with no evidence."""
        result = validator.validate_claim_evidence(
            claim_id=uuid4(),
            claim_text="The moon is made of cheese.",
            verdict="UNSUPPORTED",
            evidence_list=[],
            source_passages=sample_passages,
            source_documents=sample_source_documents,
        )

        assert result.has_errors is False
        assert len(result.evidence_validations) == 0


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_validation_issue_creation(self):
        """Test creating a ValidationIssue."""
        issue = ValidationIssue(
            severity="error",
            code="QUOTE_NOT_FOUND",
            message="Quote not found in source",
            evidence_index=0,
        )
        assert issue.severity == "error"
        assert issue.code == "QUOTE_NOT_FOUND"
        assert issue.evidence_index == 0


class TestEvidenceValidationResult:
    """Tests for EvidenceValidationResult dataclass."""

    def test_evidence_validation_result_creation(self):
        """Test creating an EvidenceValidationResult."""
        result = EvidenceValidationResult(
            validated=True,
            issues=[],
            matched_passage="Test passage",
            matched_char_start=0,
            matched_char_end=14,
        )
        assert result.validated is True
        assert result.matched_passage == "Test passage"

    def test_evidence_validation_result_with_error(self):
        """Test EvidenceValidationResult with error."""
        issue = ValidationIssue(
            severity="error",
            code="QUOTE_NOT_FOUND",
            message="Quote not found",
            evidence_index=0,
        )
        result = EvidenceValidationResult(
            validated=False,
            issues=[issue],
        )
        assert result.validated is False
        assert len(result.issues) == 1


class TestClaimValidationResult:
    """Tests for ClaimValidationResult dataclass."""

    def test_claim_validation_result_creation(self):
        """Test creating a ClaimValidationResult."""
        result = ClaimValidationResult(
            claim_id=uuid4(),
            claim_text="Test claim",
            verdict="SUPPORTED",
            evidence_validations=[],
            has_errors=False,
            has_warnings=False,
        )
        assert result.claim_text == "Test claim"
        assert result.verdict == "SUPPORTED"
        assert result.has_errors is False

    def test_claim_validation_result_with_errors(self):
        """Test ClaimValidationResult with errors."""
        from app.services.verification.evidence_validator import ValidationIssue, EvidenceValidationResult

        issue = ValidationIssue(
            severity="error",
            code="QUOTE_NOT_FOUND",
            message="Quote not found",
            evidence_index=0,
        )
        ev_result = EvidenceValidationResult(validated=False, issues=[issue])

        result = ClaimValidationResult(
            claim_id=uuid4(),
            claim_text="Test claim",
            verdict="CONTRADICTED",
            evidence_validations=[ev_result],
            has_errors=True,
            has_warnings=False,
        )
        assert result.has_errors is True
        assert result.has_warnings is False