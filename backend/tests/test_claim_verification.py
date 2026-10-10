"""
Claim Verification Tests (Stage 8)
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from app.schemas.claim import ExtractedClaim
from app.services.verification.claim_verifier import ClaimVerifier, VerificationResult
from app.services.llm.llm_client import LLMResponse, LLMError, LLMProvider


class TestClaimVerifier:
    """Tests for claim verification service."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        client = AsyncMock()
        client.complete = AsyncMock()
        return client

    @pytest.fixture
    def claim_verifier(self, mock_llm_client):
        """Create claim verifier with mock client."""
        return ClaimVerifier(llm_client=mock_llm_client)

    @pytest.fixture
    def sample_passages(self):
        """Create sample passages for testing."""
        from uuid import uuid4
        from app.services.documents.text_chunker import TextPassage
        from app.services.retrieval.evidence_retriever import RetrievedPassage

        doc_id = uuid4()
        passages = [
            RetrievedPassage(
                passage=TextPassage(
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
                score=0.85,
                matched_terms=["200", "students", "60%", "preferred", "online", "notes"],
            ),
            RetrievedPassage(
                passage=TextPassage(
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
                score=0.75,
                matched_terms=["survey", "examination", "score", "data"],
            ),
        ]
        return passages

    @pytest.mark.asyncio
    async def test_verify_supported_claim(self, claim_verifier, mock_llm_client, sample_passages):
        """Test verifying a claim that is supported by evidence."""
        mock_llm_client.complete.return_value = LLMResponse(
            content=json.dumps({
                "verdict": "SUPPORTED",
                "explanation": "The source states 60% of students preferred online notes, matching the claim.",
                "evidence_strength": "strong",
                "evidence": [
                    {
                        "document_id": str(sample_passages[0].passage.document_id),
                        "document_name": "survey_report.pdf",
                        "page_number": 1,
                        "quote": "60% preferred online notes",
                        "relationship": "supports",
                        "validated": False
                    }
                ],
                "requires_review": False
            }),
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            request_id="test-1",
        )

        claim = ExtractedClaim(
            claim_text="60% of students preferred online notes.",
            is_checkable=True,
            reason_not_checkable=None,
        )

        result = await claim_verifier.verify_claim(claim, sample_passages)

        assert result.verdict == "SUPPORTED"
        assert result.error is None
        assert "60%" in result.explanation
        assert result.evidence_strength == "strong"
        assert len(result.evidence) == 1
        assert result.evidence[0]["relationship"] == "supports"

    @pytest.mark.asyncio
    async def test_verify_contradicted_claim(self, claim_verifier, mock_llm_client, sample_passages):
        """Test verifying a claim that is contradicted by evidence."""
        mock_llm_client.complete.return_value = LLMResponse(
            content=json.dumps({
                "verdict": "CONTRADICTED",
                "explanation": "The source states 200 students, not 500.",
                "evidence_strength": "strong",
                "evidence": [
                    {
                        "document_id": str(sample_passages[0].passage.document_id),
                        "document_name": "survey_report.pdf",
                        "page_number": 1,
                        "quote": "A survey of 200 students",
                        "relationship": "contradicts",
                        "validated": False
                    }
                ],
                "requires_review": False
            }),
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            request_id="test-2",
        )

        claim = ExtractedClaim(
            claim_text="The survey included 500 students.",
            is_checkable=True,
            reason_not_checkable=None,
        )

        result = await claim_verifier.verify_claim(claim, sample_passages)

        assert result.verdict == "CONTRADICTED"
        assert result.error is None
        assert "200" in result.explanation
        assert result.evidence[0]["relationship"] == "contradicts"

    @pytest.mark.asyncio
    async def test_verify_unsupported_claim(self, claim_verifier, mock_llm_client, sample_passages):
        """Test verifying a claim that is unsupported by evidence."""
        mock_llm_client.complete.return_value = LLMResponse(
            content=json.dumps({
                "verdict": "UNSUPPORTED",
                "explanation": "The source states examination score data was not collected, so the claim about proving improvement cannot be supported.",
                "evidence_strength": "weak",
                "evidence": [
                    {
                        "document_id": str(sample_passages[1].passage.document_id),
                        "document_name": "survey_report.pdf",
                        "page_number": 2,
                        "quote": "The survey did not collect examination score data",
                        "relationship": "insufficient",
                        "validated": False
                    }
                ],
                "requires_review": False
            }),
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            request_id="test-3",
        )

        claim = ExtractedClaim(
            claim_text="The survey proved that online notes improve examination scores.",
            is_checkable=True,
            reason_not_checkable=None,
        )

        result = await claim_verifier.verify_claim(claim, sample_passages)

        assert result.verdict == "UNSUPPORTED"
        assert result.error is None
        assert "not collected" in result.explanation.lower() or "insufficient" in result.explanation.lower()
        assert result.evidence[0]["relationship"] in ("insufficient", "context")

    @pytest.mark.asyncio
    async def test_verify_ambiguous_claim(self, claim_verifier, mock_llm_client, sample_passages):
        """Test verifying a claim that is ambiguous."""
        mock_llm_client.complete.return_value = LLMResponse(
            content=json.dumps({
                "verdict": "AMBIGUOUS",
                "explanation": "The claim mentions student preferences but the evidence doesn't clearly support or contradict the specific claim about 'proved improvement'.",
                "evidence_strength": "weak",
                "evidence": [
                    {
                        "document_id": str(sample_passages[0].passage.document_id),
                        "document_name": "survey_report.pdf",
                        "page_number": 1,
                        "quote": "60% preferred online notes",
                        "relationship": "context",
                        "validated": False
                    }
                ],
                "requires_review": True
            }),
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            request_id="test-4",
        )

        claim = ExtractedClaim(
            claim_text="Students prefer online notes because they improve learning outcomes.",
            is_checkable=True,
            reason_not_checkable=None,
        )

        result = await claim_verifier.verify_claim(claim, sample_passages)

        assert result.verdict == "AMBIGUOUS"
        assert result.error is None
        assert result.requires_review is True

    @pytest.mark.asyncio
    async def test_verify_empty_claim(self, claim_verifier):
        """Test verifying a claim with only whitespace."""
        # ExtractedClaim validates min_length=1, so we test the verifier's internal check
        # by creating a claim with whitespace only
        claim = ExtractedClaim(
            claim_text="   ",
            is_checkable=True,
        )

        result = await claim_verifier.verify_claim(claim, [])

        assert result.verdict == "UNABLE_TO_ASSESS"
        assert result.error is not None
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_verify_non_checkable_claim(self, claim_verifier):
        """Test verifying a non-checkable claim."""
        claim = ExtractedClaim(
            claim_text="This is the best method ever.",
            is_checkable=False,
            reason_not_checkable="opinion",
        )

        result = await claim_verifier.verify_claim(claim, [])

        assert result.verdict == "UNABLE_TO_ASSESS"
        assert result.error is None
        assert "opinion" in result.explanation.lower()
        assert result.requires_review is True

    @pytest.mark.asyncio
    async def test_verify_no_evidence_passages(self, claim_verifier, mock_llm_client):
        """Test verifying a claim with no retrieved evidence."""
        mock_llm_client.complete.return_value = LLMResponse(
            content=json.dumps({
                "verdict": "UNSUPPORTED",
                "explanation": "No relevant evidence found in the source material.",
                "evidence_strength": "weak",
                "evidence": [],
                "requires_review": False
            }),
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 50, "output_tokens": 20, "total_tokens": 70},
            request_id="test-no-evidence",
        )

        claim = ExtractedClaim(
            claim_text="The moon is made of cheese.",
            is_checkable=True,
        )

        result = await claim_verifier.verify_claim(claim, [])

        # Should still process the claim, even with no evidence
        assert result.verdict in ("UNSUPPORTED", "UNABLE_TO_ASSESS")

    @pytest.mark.asyncio
    async def test_verify_malformed_json(self, claim_verifier, mock_llm_client):
        """Test handling of malformed JSON response."""
        mock_llm_client.complete.return_value = LLMResponse(
            content="This is not valid JSON",
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            request_id="test-malformed",
        )

        claim = ExtractedClaim(
            claim_text="Some claim.",
            is_checkable=True,
        )

        result = await claim_verifier.verify_claim(claim, [])

        assert result.verdict == "UNABLE_TO_ASSESS"
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_verify_invalid_verdict(self, claim_verifier, mock_llm_client):
        """Test handling of invalid verdict value."""
        mock_llm_client.complete.return_value = LLMResponse(
            content=json.dumps({
                "verdict": "INVALID_VERDICT",
                "explanation": "Some explanation",
                "evidence": []
            }),
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            request_id="test-invalid-verdict",
        )

        claim = ExtractedClaim(
            claim_text="Some claim.",
            is_checkable=True,
        )

        result = await claim_verifier.verify_claim(claim, [])

        assert result.verdict == "UNABLE_TO_ASSESS"
        assert result.error is not None
        assert "invalid verdict" in result.error.lower()

    @pytest.mark.asyncio
    async def test_verify_llm_error(self, claim_verifier, mock_llm_client):
        """Test handling of LLM errors."""
        from app.services.llm.llm_client import LLMError, LLMProvider
        mock_llm_client.complete.side_effect = LLMError(
            message="Rate limit exceeded",
            code="RATE_LIMIT",
            provider=LLMProvider.OPENAI,
            status_code=429,
            retryable=True,
        )

        claim = ExtractedClaim(
            claim_text="Some claim.",
            is_checkable=True,
        )

        result = await claim_verifier.verify_claim(claim, [])

        assert result.verdict == "UNABLE_TO_ASSESS"
        assert result.error is not None
        assert "rate limit" in result.error.lower()

    @pytest.mark.asyncio
    async def test_verify_preserves_claim_text(self, claim_verifier, mock_llm_client, sample_passages):
        """Test that original claim text is preserved."""
        original_claim = "The survey included 500 students."

        mock_llm_client.complete.return_value = LLMResponse(
            content=json.dumps({
                "verdict": "CONTRADICTED",
                "explanation": "The source says 200 students.",
                "evidence": []
            }),
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
            request_id="test-preserve",
        )

        claim = ExtractedClaim(
            claim_text=original_claim,
            is_checkable=True,
        )

        result = await claim_verifier.verify_claim(claim, sample_passages)

        # The verifier should receive the exact claim text
        call_args = mock_llm_client.complete.call_args
        user_prompt = call_args[1]["user_prompt"]
        assert original_claim in user_prompt


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_verification_result_creation(self):
        """Test creating a VerificationResult."""
        result = VerificationResult(
            verdict="SUPPORTED",
            explanation="Evidence supports the claim",
            evidence_strength="strong",
            evidence=[{"quote": "test", "relationship": "supports"}],
            requires_review=False,
        )
        assert result.verdict == "SUPPORTED"
        assert result.evidence_strength == "strong"
        assert len(result.evidence) == 1

    def test_verification_result_with_error(self):
        """Test VerificationResult with error."""
        result = VerificationResult(
            verdict="UNABLE_TO_ASSESS",
            explanation="Error occurred",
            evidence_strength=None,
            evidence=[],
            error="LLM error",
        )
        assert result.error == "LLM error"
        assert result.verdict == "UNABLE_TO_ASSESS"