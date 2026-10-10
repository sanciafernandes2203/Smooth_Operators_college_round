"""
Claim Extraction Tests
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.claim import (
    ExtractedClaim,
    ClaimExtractionRequest,
    ClaimExtractionResponse,
)
from app.services.llm.claim_extractor import ClaimExtractor, CLAIM_EXTRACTION_SYSTEM_PROMPT
from app.services.llm.llm_client import LLMResponse, LLMError, LLMProvider


class TestClaimExtraction:
    """Tests for claim extraction service."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        client = AsyncMock()
        client.complete = AsyncMock()
        return client

    @pytest.fixture
    def claim_extractor(self, mock_llm_client):
        """Create claim extractor with mock client."""
        return ClaimExtractor(llm_client=mock_llm_client)

    @pytest.mark.asyncio
    async def test_extract_claims_multiple_factual(self, claim_extractor, mock_llm_client):
        """Test extracting multiple factual claims from an answer."""
        mock_llm_client.complete.return_value = LLMResponse(
            content=json.dumps({
                "claims": [
                    {"claim_text": "The survey included 500 students.", "is_checkable": True, "reason_not_checkable": None},
                    {"claim_text": "60% of the surveyed students preferred online notes.", "is_checkable": True, "reason_not_checkable": None},
                    {"claim_text": "The survey proves that online notes improve examination scores.", "is_checkable": True, "reason_not_checkable": None},
                ]
            }),
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            request_id="test-123",
        )

        answer = """A survey of 500 students found that 60% preferred online notes. 
        The survey proved that online notes improve examination scores."""
        result = await claim_extractor.extract_claims(answer)

        assert result.error is None
        assert result.total_claims == 3
        assert len(result.claims) == 3
        assert result.claims[0].claim_text == "The survey included 500 students."
        assert result.claims[0].is_checkable is True
        assert result.claims[1].claim_text == "60% of the surveyed students preferred online notes."
        assert result.claims[2].claim_text == "The survey proves that online notes improve examination scores."

    @pytest.mark.asyncio
    async def test_extract_claims_with_non_checkable(self, claim_extractor, mock_llm_client):
        """Test extracting claims including non-checkable content."""
        mock_llm_client.complete.return_value = LLMResponse(
            content=json.dumps({
                "claims": [
                    {"claim_text": "The study included 200 participants.", "is_checkable": True, "reason_not_checkable": None},
                    {"claim_text": "This is the best method ever.", "is_checkable": False, "reason_not_checkable": "opinion"},
                    {"claim_text": "Results may vary depending on conditions.", "is_checkable": False, "reason_not_checkable": "vague"},
                ]
            }),
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 80, "output_tokens": 40, "total_tokens": 120},
            request_id="test-456",
        )

        answer = "The study included 200 participants. This is the best method ever. Results may vary depending on conditions."
        result = await claim_extractor.extract_claims(answer)

        assert result.error is None
        assert result.total_claims == 3
        assert result.claims[0].is_checkable is True
        assert result.claims[1].is_checkable is False
        assert result.claims[1].reason_not_checkable == "opinion"
        assert result.claims[2].is_checkable is False
        assert result.claims[2].reason_not_checkable == "vague"

    @pytest.mark.asyncio
    async def test_extract_claims_single_claim(self, claim_extractor, mock_llm_client):
        """Test extracting a single claim."""
        mock_llm_client.complete.return_value = LLMResponse(
            content=json.dumps({
                "claims": [
                    {"claim_text": "The temperature reached 35 degrees Celsius.", "is_checkable": True, "reason_not_checkable": None}
                ]
            }),
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 50, "output_tokens": 20, "total_tokens": 70},
            request_id="test-789",
        )

        answer = "The temperature reached 35 degrees Celsius."
        result = await claim_extractor.extract_claims(answer)

        assert result.error is None
        assert result.total_claims == 1
        assert result.claims[0].claim_text == "The temperature reached 35 degrees Celsius."

    @pytest.mark.asyncio
    async def test_extract_claims_empty_answer(self, claim_extractor):
        """Test extracting claims from empty answer."""
        result = await claim_extractor.extract_claims("")
        assert result.error == "Answer is empty"
        assert result.total_claims == 0
        assert result.claims == []

    @pytest.mark.asyncio
    async def test_extract_claims_whitespace_only(self, claim_extractor):
        """Test extracting claims from whitespace-only answer."""
        result = await claim_extractor.extract_claims("   \n\t  ")
        assert result.error == "Answer is empty"
        assert result.total_claims == 0

    @pytest.mark.asyncio
    async def test_extract_claims_malformed_json(self, claim_extractor, mock_llm_client):
        """Test handling of malformed LLM JSON response."""
        mock_llm_client.complete.return_value = LLMResponse(
            content="This is not valid JSON",
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            request_id="test-malformed",
        )

        result = await claim_extractor.extract_claims("Some answer")

        assert result.error is not None
        assert "Failed to parse LLM response" in result.error or "JSON" in result.error

    @pytest.mark.asyncio
    async def test_extract_claims_llm_error(self, claim_extractor, mock_llm_client):
        """Test handling of LLM errors."""
        mock_llm_client.complete.side_effect = LLMError(
            message="Rate limit exceeded",
            code="RATE_LIMIT",
            provider=LLMProvider.OPENAI,
            status_code=429,
            retryable=True,
        )

        result = await claim_extractor.extract_claims("Some answer")

        assert result.error is not None
        assert "LLM error" in result.error
        assert "Rate limit" in result.error

    @pytest.mark.asyncio
    async def test_extract_claims_llm_error_non_retryable(self, claim_extractor, mock_llm_client):
        """Test handling of non-retryable LLM errors."""
        mock_llm_client.complete.side_effect = LLMError(
            message="Invalid API key",
            code="AUTHENTICATION_ERROR",
            provider=LLMProvider.OPENAI,
            status_code=401,
            retryable=False,
        )

        result = await claim_extractor.extract_claims("Some answer")

        assert result.error is not None
        assert "LLM error" in result.error
        assert "Invalid API key" in result.error

    @pytest.mark.asyncio
    async def test_extract_claims_empty_claims_list(self, claim_extractor, mock_llm_client):
        """Test handling when LLM returns empty claims list."""
        mock_llm_client.complete.return_value = LLMResponse(
            content=json.dumps({"claims": []}),
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            request_id="test-empty",
        )

        result = await claim_extractor.extract_claims("An opinion piece without factual claims.")

        assert result.error is None
        assert result.total_claims == 0
        assert result.claims == []

    @pytest.mark.asyncio
    async def test_extract_claims_skips_invalid_items(self, claim_extractor, mock_llm_client):
        """Test that invalid claim items are skipped."""
        mock_llm_client.complete.return_value = LLMResponse(
            content=json.dumps({
                "claims": [
                    {"claim_text": "Valid claim.", "is_checkable": True, "reason_not_checkable": None},
                    "not a dict",
                    {"claim_text": "", "is_checkable": True, "reason_not_checkable": None},
                    {"claim_text": "Another valid claim.", "is_checkable": True, "reason_not_checkable": None},
                ]
            }),
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            request_id="test-invalid",
        )

        result = await claim_extractor.extract_claims("Test answer")

        assert result.error is None
        # Should skip the invalid items
        assert result.total_claims == 2
        assert result.claims[0].claim_text == "Valid claim."
        assert result.claims[1].claim_text == "Another valid claim."


class TestClaimExtractionSchemas:
    """Tests for claim extraction schemas."""

    def test_extracted_claim_valid(self):
        """Test creating a valid ExtractedClaim."""
        claim = ExtractedClaim(
            claim_text="The survey included 200 students.",
            is_checkable=True,
            reason_not_checkable=None,
        )
        assert claim.claim_text == "The survey included 200 students."
        assert claim.is_checkable is True
        assert claim.reason_not_checkable is None

    def test_extracted_claim_non_checkable(self):
        """Test creating a non-checkable ExtractedClaim."""
        claim = ExtractedClaim(
            claim_text="This is the best approach.",
            is_checkable=False,
            reason_not_checkable="opinion",
        )
        assert claim.is_checkable is False
        assert claim.reason_not_checkable == "opinion"

    def test_claim_extraction_request_valid(self):
        """Test valid claim extraction request."""
        req = ClaimExtractionRequest(answer="The survey included 200 students.")
        assert req.answer == "The survey included 200 students."

    def test_claim_extraction_request_empty_fails(self):
        """Test that empty answer fails validation."""
        with pytest.raises(ValueError):
            ClaimExtractionRequest(answer="   ")

    def test_claim_extraction_response(self):
        """Test ClaimExtractionResponse creation."""
        claims = [
            ExtractedClaim(claim_text="Claim 1", is_checkable=True),
            ExtractedClaim(claim_text="Claim 2", is_checkable=False, reason_not_checkable="opinion"),
        ]
        resp = ClaimExtractionResponse(claims=claims, total_claims=2)
        assert resp.total_claims == 2
        assert len(resp.claims) == 2

    def test_claim_extraction_response_with_error(self):
        """Test ClaimExtractionResponse with error."""
        resp = ClaimExtractionResponse(
            claims=[],
            total_claims=0,
            error="LLM error occurred",
        )
        assert resp.error == "LLM error occurred"
        assert resp.total_claims == 0