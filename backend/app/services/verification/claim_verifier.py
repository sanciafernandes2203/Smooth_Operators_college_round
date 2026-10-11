"""
Claim Verification Service (Stage 8)

Assesses each extracted claim against the relevant evidence retrieved from the source material.
Uses the existing LLM client and follows the project's verdict taxonomy.
"""
import json
import logging
from dataclasses import dataclass
from typing import Optional, List
from uuid import UUID

from app.schemas.claim import ExtractedClaim
from app.schemas.audit import EvidenceResponse
from app.services.llm.llm_client import BaseLLMClient, LLMError, get_llm_client
from app.services.retrieval.evidence_retriever import RetrievedPassage
from app.schemas.audit import ClaimResponse

logger = logging.getLogger(__name__)


# Claim verification system prompt
CLAIM_VERIFICATION_SYSTEM_PROMPT = """You are a precise claim verification system. Your task is to assess a claim against the supplied source evidence and determine the verdict.

VERDICT TAXONOMY (use exactly these strings):
- SUPPORTED: The supplied evidence directly supports the claim. Quote the supporting passage.
- CONTRADICTED: The supplied evidence directly conflicts with the claim. Quote the contradicting passage.
- UNSUPPORTED: The supplied source material does not provide sufficient evidence to establish the claim. Do NOT call it false. Explain what evidence is missing.
- AMBIGUOUS: The evidence is unclear, conflicting, incomplete, or supports multiple reasonable interpretations. Explain the ambiguity.

RULES:
1. Assess the claim ONLY against the supplied source evidence. Do NOT use outside knowledge or web searches.
2. Distinguish direct contradiction from absence of evidence. No retrieved evidence must not be treated as contradiction.
3. If evidence directly conflicts with a claim, CONTRADICTED is appropriate.
4. If the source does not discuss the claim, use UNSUPPORTED when the source was processed adequately.
5. If the source is unreadable or the process failed, use UNABLE_TO_ASSESS rather than making a factual judgement.
6. Do NOT invent evidence, quotations, page numbers, or source references.
7. Quote ONLY from the supplied passages.
8. Preserve the original claim wording.
8. Explain the verdict briefly using the available evidence.
9. Do not overstate certainty.
10. Return structured JSON output only.

Output format:
{
  "verdict": "SUPPORTED|CONTRADICTED|UNSUPPORTED|AMBIGUOUS",
  "explanation": "Brief explanation citing the evidence",
  "evidence_strength": "strong|moderate|weak|null",
  "evidence": [
    {
      "document_id": "uuid",
      "document_name": "filename",
      "page_number": 1,
      "quote": "Exact quotation from source",
      "relationship": "supports|contradicts|context|insufficient",
      "validated": false
    }
  ],
  "requires_review": false
}

For UNSUPPORTED: Set evidence_strength to "weak" or null, explain what evidence is missing.
For CONTRADICTED: Quote the contradicting passage, set relationship to "contradicts".
For SUPPORTED: Quote the supporting passage, set relationship to "supports".
For AMBIGUOUS: Explain the ambiguity, quote relevant passages with relationship "context" or "insufficient"."""


CLAIM_VERIFICATION_USER_PROMPT_TEMPLATE = """Assess this claim against the supplied source evidence.

CLAIM:
---
{claim_text}
---

SOURCE EVIDENCE:
---
{evidence_text}
---

Return the verdict in the specified JSON format."""


@dataclass
class VerificationResult:
    """Result of claim verification."""
    verdict: str
    explanation: str
    evidence_strength: Optional[str]
    evidence: List[dict]  # List of evidence dicts matching EvidenceResponse structure
    requires_review: bool = False
    error: Optional[str] = None


class ClaimVerifier:
    """
    Service for verifying claims against retrieved evidence using an LLM.
    """

    VALID_VERDICTS = {"SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "AMBIGUOUS", "POTENTIALLY_UNSAFE", "UNABLE_TO_ASSESS"}

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        """
        Initialize the claim verifier.

        Args:
            llm_client: LLM client to use. If None, uses the global client.
        """
        self._llm_client = llm_client

    def _get_client(self) -> BaseLLMClient:
        """Get the LLM client, using global if not provided."""
        if self._llm_client is not None:
            return self._llm_client
        return get_llm_client()

    def _format_evidence(self, passages: list) -> str:
        """Format retrieved passages for the LLM prompt."""
        if not passages:
            return "No relevant evidence found in the source material."

        lines = []
        for i, p in enumerate(passages):
            doc_name = p.passage.document_name if hasattr(p, 'passage') else p.document_name
            page_num = p.passage.page_number if hasattr(p, 'passage') else p.page_number
            text = p.passage.text if hasattr(p, 'passage') else p.text
            doc_id = str(p.passage.document_id) if hasattr(p, 'passage') else p.document_id

            lines.append(f"--- Passage {i+1} ---")
            lines.append(f"Document: {doc_name} (ID: {doc_id})")
            if page_num is not None:
                lines.append(f"Page: {page_num}")
            lines.append(f"Text: {text}")
            lines.append("")

        return "\n".join(lines)

    async def verify_claim(
        self,
        claim: ExtractedClaim,
        evidence_passages: list,
    ) -> VerificationResult:
        """
        Verify a claim against retrieved evidence passages.

        Args:
            claim: The extracted claim to verify
            evidence_passages: List of retrieved passages (RetrievedPassage or similar)

        Returns:
            VerificationResult with verdict, explanation, and evidence references
        """
        if not claim or not claim.claim_text.strip():
            return VerificationResult(
                verdict="UNABLE_TO_ASSESS",
                explanation="Claim text is empty",
                evidence_strength=None,
                evidence=[],
                error="Empty claim text",
            )

        if not claim.is_checkable:
            return VerificationResult(
                verdict="UNABLE_TO_ASSESS",
                explanation=f"Claim is not checkable: {claim.reason_not_checkable or 'not specified'}",
                evidence_strength=None,
                evidence=[],
                requires_review=True,
            )

        client = self._get_client()

        # Format evidence for prompt
        evidence_text = self._format_evidence(evidence_passages)

        user_prompt = CLAIM_VERIFICATION_USER_PROMPT_TEMPLATE.format(
            claim_text=claim.claim_text.strip(),
            evidence_text=evidence_text,
        )

        try:
            # Use structured output if supported (JSON mode)
            response = await client.complete(
                user_prompt=user_prompt,
                system_prompt=CLAIM_VERIFICATION_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            # Parse the JSON response
            content = response.content.strip()
            logger.debug(f"LLM claim verification response: {content}")

            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM verification response as JSON: {e}")
                # Try to extract JSON from the response
                data = self._try_extract_json(content)
                if data is None:
                    return VerificationResult(
                        verdict="UNABLE_TO_ASSESS",
                        explanation="Failed to parse verification response",
                        evidence_strength=None,
                        evidence=[],
                        error=f"Failed to parse LLM response: {e}",
                    )

            # Validate and extract verdict
            verdict = data.get("verdict", "").strip().upper()
            if verdict not in self.VALID_VERDICTS:
                logger.warning(f"Invalid verdict from LLM: {verdict}")
                return VerificationResult(
                    verdict="UNABLE_TO_ASSESS",
                    explanation=f"Invalid verdict returned by verifier: {verdict}",
                    evidence_strength=None,
                    evidence=[],
                    error=f"Invalid verdict: {verdict}",
                )

            explanation = data.get("explanation", "").strip()
            if not explanation:
                explanation = f"Verifier returned verdict {verdict} without explanation"

            evidence_strength = data.get("evidence_strength")
            raw_evidence = data.get("evidence", [])

            # Validate and format evidence
            formatted_evidence = []
            for i, ev in enumerate(raw_evidence):
                if not isinstance(ev, dict):
                    logger.warning(f"Skipping invalid evidence at index {i}: not a dict")
                    continue

                # Validate required fields
                quote = ev.get("quote", "").strip()
                if not quote:
                    logger.warning(f"Skipping evidence at index {i}: empty quote")
                    continue

                relationship = ev.get("relationship", "").strip().lower()
                valid_relationships = {"supports", "contradicts", "context", "insufficient"}
                if relationship not in valid_relationships:
                    relationship = "context"

                formatted_evidence.append({
                    "document_id": ev.get("document_id"),
                    "document_name": ev.get("document_name", ""),
                    "page_number": ev.get("page_number"),
                    "quote": quote,
                    "relationship": relationship,
                    "validated": False,  # Will be validated in Stage 9
                })

            requires_review = data.get("requires_review", False)

            logger.info(f"Verified claim: {verdict} (strength: {evidence_strength})")

            return VerificationResult(
                verdict=verdict,
                explanation=explanation,
                evidence_strength=evidence_strength,
                evidence=formatted_evidence,
                requires_review=requires_review,
            )

        except LLMError as e:
            logger.error(f"LLM error during claim verification: {e}")
            return VerificationResult(
                verdict="UNABLE_TO_ASSESS",
                explanation="LLM verification failed",
                evidence_strength=None,
                evidence=[],
                error=f"LLM error: {e.message}",
            )
        except Exception as e:
            logger.exception("Unexpected error during claim verification")
            return VerificationResult(
                verdict="UNABLE_TO_ASSESS",
                explanation="Unexpected error during verification",
                evidence_strength=None,
                evidence=[],
                error=f"Unexpected error: {e}",
            )

    def _try_extract_json(self, text: str) -> Optional[dict]:
        """Try to extract JSON from text that might have extra content."""
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass
        return None

    async def verify_claims_batch(
        self,
        claims: List[ExtractedClaim],
        passages_by_claim: dict[str, list],
    ) -> List[VerificationResult]:
        """
        Verify multiple claims in batch.

        Args:
            claims: List of extracted claims
            passages_by_claim: Dict mapping claim text to retrieved passages

        Returns:
            List of VerificationResult objects
        """
        results = []
        for claim in claims:
            passages = passages_by_claim.get(claim.claim_text, [])
            result = await self.verify_claim(claim, passages)
            results.append(result)
        return results