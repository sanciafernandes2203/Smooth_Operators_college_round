"""
Claim Extraction Service

Extracts individual checkable claims from an AI-generated answer using an LLM.
"""
import json
import logging
from typing import Optional

from app.schemas.claim import (
    ExtractedClaim,
    ClaimExtractionRequest,
    ClaimExtractionResponse,
)
from app.services.llm.llm_client import BaseLLMClient, LLMError, get_llm_client

logger = logging.getLogger(__name__)


# Claim extraction system prompt
CLAIM_EXTRACTION_SYSTEM_PROMPT = """You are a precise claim extraction system. Your task is to analyze an AI-generated answer and break it down into individual, checkable factual claims.

Rules:
1. Extract ONLY claims that are explicitly stated in the answer. Do not infer or add claims.
2. Preserve the original wording of each claim as closely as possible.
3. Each claim should be a single, self-contained factual statement that can be verified against source material.
4. Do NOT combine unrelated claims into one. Split compound sentences that make multiple independent claims.
5. Identify non-checkable content (opinions, vague statements, predictions, subjective assessments) and mark them appropriately.
6. Claims must be specific enough to be verified - they should contain checkable facts (numbers, dates, names, comparisons, causal claims, etc.).
7. Do not rewrite claims to make them stronger or weaker. Keep the original meaning and qualifiers (e.g., "may", "suggests", "proves", "indicates").
8. Return structured JSON output only.

Output format:
{
  "claims": [
    {
      "claim_text": "Exact claim text from the answer",
      "is_checkable": true,
      "reason_not_checkable": null
    }
  ]
}

For non-checkable claims, set is_checkable to false and provide a reason (e.g., "opinion", "vague", "prediction", "subjective")."""


CLAIM_EXTRACTION_USER_PROMPT_TEMPLATE = """Extract the individual checkable claims from this AI-generated answer:

---
{answer}
---

Return the claims in the specified JSON format."""


class ClaimExtractor:
    """
    Service for extracting claims from AI-generated answers using an LLM.
    """

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        """
        Initialize the claim extractor.

        Args:
            llm_client: LLM client to use. If None, uses the global client.
        """
        self._llm_client = llm_client

    def _get_client(self) -> BaseLLMClient:
        """Get the LLM client, using global if not provided."""
        if self._llm_client is not None:
            return self._llm_client
        return get_llm_client()

    async def extract_claims(
        self,
        answer: str,
    ) -> ClaimExtractionResponse:
        """
        Extract claims from an AI-generated answer.

        Args:
            answer: The AI-generated answer text

        Returns:
            ClaimExtractionResponse with extracted claims
        """
        if not answer or not answer.strip():
            return ClaimExtractionResponse(
                claims=[],
                total_claims=0,
                error="Answer is empty",
            )

        client = self._get_client()

        user_prompt = CLAIM_EXTRACTION_USER_PROMPT_TEMPLATE.format(answer=answer.strip())

        try:
            # Use structured output if supported (JSON mode)
            response = await client.complete(
                user_prompt=user_prompt,
                system_prompt=CLAIM_EXTRACTION_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            # Parse the JSON response
            content = response.content.strip()
            logger.debug(f"LLM claim extraction response: {content}")

            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                # Try to extract JSON from the response
                data = self._try_extract_json(content)
                if data is None:
                    return ClaimExtractionResponse(
                        claims=[],
                        total_claims=0,
                        error=f"Failed to parse LLM response: {e}",
                    )

            # Validate and convert to ExtractedClaim objects
            claims = []
            raw_claims = data.get("claims", [])

            for i, claim_data in enumerate(raw_claims):
                if not isinstance(claim_data, dict):
                    logger.warning(f"Skipping invalid claim at index {i}: not a dict")
                    continue

                claim_text = claim_data.get("claim_text", "").strip()
                if not claim_text:
                    logger.warning(f"Skipping claim at index {i}: empty claim_text")
                    continue

                is_checkable = claim_data.get("is_checkable", True)
                reason_not_checkable = claim_data.get("reason_not_checkable")

                if not is_checkable and reason_not_checkable is None:
                    reason_not_checkable = "not specified"

                claims.append(ExtractedClaim(
                    claim_text=claim_text,
                    is_checkable=is_checkable,
                    reason_not_checkable=reason_not_checkable,
                ))

            logger.info(f"Extracted {len(claims)} claims from answer")
            return ClaimExtractionResponse(
                claims=claims,
                total_claims=len(claims),
            )

        except LLMError as e:
            logger.error(f"LLM error during claim extraction: {e}")
            return ClaimExtractionResponse(
                claims=[],
                total_claims=0,
                error=f"LLM error: {e.message}",
            )
        except Exception as e:
            logger.exception("Unexpected error during claim extraction")
            return ClaimExtractionResponse(
                claims=[],
                total_claims=0,
                error=f"Unexpected error: {e}",
            )

    def _try_extract_json(self, text: str) -> Optional[dict]:
        """
        Try to extract JSON from text that might have extra content.
        """
        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass
        return None