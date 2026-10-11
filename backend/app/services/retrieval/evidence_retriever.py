"""
Evidence Retrieval Service

Retrieves relevant source passages for a given claim using keyword-based search (BM25-style).
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from app.services.documents.text_chunker import TextPassage

logger = logging.getLogger(__name__)

# Common English stopwords to filter out
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
    "to", "was", "were", "will", "with", "this", "that", "these",
    "those", "have", "had", "has", "been", "be", "being", "do", "does",
    "did", "but", "or", "if", "then", "than", "when", "where", "why",
    "how", "what", "which", "who", "whom", "whose", "can", "could",
    "should", "would", "may", "might", "must", "shall", "will", "would"
}


@dataclass
class RetrievedPassage:
    """A passage retrieved as evidence for a claim."""

    passage: TextPassage
    score: float  # Relevance score (higher = more relevant)
    matched_terms: list[str]  # Terms that matched


@dataclass
class RetrievalResult:
    """Result of evidence retrieval for a single claim."""

    claim_text: str
    passages: list[RetrievedPassage]
    total_passages_searched: int
    error: Optional[str] = None


class EvidenceRetriever:
    """
    Retrieves relevant source passages for claims using keyword-based search.

    Uses a simple TF-IDF / BM25-inspired scoring approach on the chunked passages
    from the document service.
    """

    def __init__(
        self,
        min_score: float = 0.15,
        max_results: int = 5,
        case_sensitive: bool = False,
    ):
        """
        Initialize the evidence retriever.

        Args:
            min_score: Minimum relevance score to include a passage
            max_results: Maximum number of passages to return per claim
            case_sensitive: Whether search is case sensitive
        """
        self.min_score = min_score
        self.max_results = max_results
        self.case_sensitive = case_sensitive

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        if not self.case_sensitive:
            text = text.lower()
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into search terms."""
        text = self._normalize_text(text)
        # Split on non-alphanumeric characters (keep % for percentages)
        # Also keep hyphenated words together
        tokens = re.findall(r"[a-zA-Z0-9%]+(?:-[a-zA-Z0-9%]+)*", text)
        # Filter out stopwords and short tokens
        filtered = [
            t for t in tokens
            if len(t) >= 2 and t.lower() not in STOPWORDS
        ]
        return filtered

    def _compute_tf(self, term: str, passage_text: str) -> float:
        """Compute term frequency in passage."""
        passage_norm = self._normalize_text(passage_text)
        term_norm = self._normalize_text(term)
        if not passage_norm:
            return 0.0
        # Count occurrences
        count = passage_norm.count(term_norm)
        return count / len(passage_norm.split())

    def _compute_idf(self, term: str, all_passages: list[TextPassage]) -> float:
        """Compute inverse document frequency for a term."""
        import math
        term_norm = self._normalize_text(term)
        if not term_norm:
            return 0.0
        total = len(all_passages)
        if total == 0:
            return 0.0
        doc_count = sum(
            1 for p in all_passages
            if term_norm in self._normalize_text(p.text)
        )
        if doc_count == 0:
            return 0.0
        return math.log((total - doc_count + 0.5) / (doc_count + 0.5) + 1.0)

    def _score_passage(self, claim_terms: list[str], passage: TextPassage, all_passages: list[TextPassage]) -> tuple[float, list[str]]:
        """
        Score a passage against claim terms using TF-IDF inspired scoring.

        Returns:
            Tuple of (score, matched_terms)
        """
        if not claim_terms:
            return 0.0, []

        matched_terms = []
        total_score = 0.0

        for term in claim_terms:
            tf = self._compute_tf(term, passage.text)
            if tf > 0:
                idf = self._compute_idf(term, all_passages)
                total_score += tf * idf
                matched_terms.append(term)

        return total_score, matched_terms

    def retrieve(
        self,
        claim_text: str,
        passages: list[TextPassage],
    ) -> RetrievalResult:
        """
        Retrieve the most relevant passages for a claim.

        Args:
            claim_text: The claim to find evidence for
            passages: List of all available source passages

        Returns:
            RetrievalResult with ranked passages
        """
        if not passages:
            return RetrievalResult(
                claim_text=claim_text,
                passages=[],
                total_passages_searched=0,
            )

        if not claim_text or not claim_text.strip():
            return RetrievalResult(
                claim_text=claim_text,
                passages=[],
                total_passages_searched=len(passages),
                error="Claim text is empty",
            )

        # Tokenize claim
        claim_terms = self._tokenize(claim_text)

        if not claim_terms:
            return RetrievalResult(
                claim_text=claim_text,
                passages=[],
                total_passages_searched=len(passages),
            )

        # Score all passages
        scored_passages = []
        for passage in passages:
            score, matched_terms = self._score_passage(claim_terms, passage, passages)
            if score >= self.min_score and matched_terms:
                scored_passages.append(RetrievedPassage(
                    passage=passage,
                    score=score,
                    matched_terms=matched_terms,
                ))

        # Sort by score descending
        scored_passages.sort(key=lambda x: x.score, reverse=True)

        # Limit results
        top_passages = scored_passages[:self.max_results]

        logger.info(
            f"Retrieved {len(top_passages)} passages for claim "
            f"(searched {len(passages)} total, terms: {claim_terms[:5]})"
        )

        return RetrievalResult(
            claim_text=claim_text,
            passages=top_passages,
            total_passages_searched=len(passages),
        )

    def retrieve_for_multiple_claims(
        self,
        claims: list[str],
        passages: list[TextPassage],
    ) -> dict[str, RetrievalResult]:
        """
        Retrieve evidence for multiple claims.

        Args:
            claims: List of claim texts
            passages: List of all available source passages

        Returns:
            Dict mapping claim text to RetrievalResult
        """
        results = {}
        for claim in claims:
            results[claim] = self.retrieve(claim, passages)
        return results


def create_retriever(
    min_score: float = 0.15,
    max_results: int = 5,
    case_sensitive: bool = False,
) -> EvidenceRetriever:
    """Create an evidence retriever with default settings."""
    return EvidenceRetriever(min_score=min_score, max_results=max_results, case_sensitive=case_sensitive)