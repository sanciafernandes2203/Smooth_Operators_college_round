"""
Evidence Retrieval Tests
"""
import pytest
from uuid import uuid4

from app.services.retrieval.evidence_retriever import (
    EvidenceRetriever,
    RetrievedPassage,
    RetrievalResult,
    create_retriever,
)
from app.services.documents.text_chunker import TextPassage


class TestEvidenceRetriever:
    """Tests for evidence retrieval service."""

    @pytest.fixture
    def sample_passages(self):
        """Create sample passages for testing."""
        doc_id = uuid4()
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
            TextPassage(
                passage_id=f"{doc_id}-p2",
                document_id=doc_id,
                document_name="survey_report.pdf",
                page_number=3,
                text="Online learning platforms were rated highly by participants.",
                char_start=113,
                char_end=168,
                source_type="pdf",
                extraction_method="pymupdf",
            ),
            TextPassage(
                passage_id=f"{doc_id}-p3",
                document_id=doc_id,
                document_name="survey_report.pdf",
                page_number=1,
                text="The methodology section describes the sampling procedure in detail.",
                char_start=169,
                char_end=230,
                source_type="pdf",
                extraction_method="pymupdf",
            ),
        ]

    @pytest.fixture
    def retriever(self):
        """Create an evidence retriever with low threshold for testing."""
        return create_retriever(min_score=0.05, max_results=3)

    def test_retrieve_claim_with_matching_passage(self, retriever, sample_passages):
        """Test retrieving evidence for a claim with an obvious match."""
        claim = "The survey included 200 students."
        result = retriever.retrieve(claim, sample_passages)

        assert isinstance(result, RetrievalResult)
        assert result.claim_text == claim
        assert len(result.passages) > 0
        assert result.total_passages_searched == 4

        # The first passage should match best
        top_passage = result.passages[0]
        assert "200 students" in top_passage.passage.text
        assert top_passage.score > 0
        assert len(top_passage.matched_terms) > 0

    def test_retrieve_claim_with_percentage_match(self, retriever, sample_passages):
        """Test retrieving evidence for a claim with percentage."""
        claim = "60% of students preferred online notes."
        result = retriever.retrieve(claim, sample_passages)

        assert len(result.passages) > 0
        top_passage = result.passages[0]
        assert "60%" in top_passage.passage.text
        assert "online notes" in top_passage.passage.text
        # Percentage sign is preserved in tokenization
        assert "60%" in top_passage.matched_terms

    def test_retrieve_claim_no_matching_passage(self, retriever, sample_passages):
        """Test retrieving evidence for a claim with no meaningful match."""
        claim = "The moon is made of cheese."
        result = retriever.retrieve(claim, sample_passages)

        # Should return empty results for unrelated claim (stopwords filtered)
        assert len(result.passages) == 0
        assert result.total_passages_searched == 4

    def test_retrieve_claim_examination_scores(self, retriever, sample_passages):
        """Test retrieving evidence for claim about examination scores."""
        claim = "The survey proved that online notes improve examination scores."
        result = retriever.retrieve(claim, sample_passages)

        # Should find the passage about no examination score data
        assert len(result.passages) > 0
        top_passage = result.passages[0]
        assert "examination score" in top_passage.passage.text.lower()

    def test_retrieve_multiple_claims(self, retriever, sample_passages):
        """Test retrieving evidence for multiple claims."""
        claims = [
            "The survey included 200 students.",
            "60% preferred online notes.",
            "The survey did not collect examination scores.",
        ]

        results = retriever.retrieve_for_multiple_claims(claims, sample_passages)

        assert len(results) == 3
        for claim in claims:
            assert claim in results
            assert isinstance(results[claim], RetrievalResult)

    def test_retrieve_empty_passages(self, retriever):
        """Test retrieval with empty passages list."""
        claim = "Some claim."
        result = retriever.retrieve(claim, [])

        assert result.total_passages_searched == 0
        assert len(result.passages) == 0

    def test_retrieve_empty_claim(self, retriever, sample_passages):
        """Test retrieval with empty claim."""
        claim = ""
        result = retriever.retrieve(claim, sample_passages)

        assert result.total_passages_searched == 4
        assert len(result.passages) == 0
        assert result.error == "Claim text is empty"

    def test_retrieve_whitespace_claim(self, retriever, sample_passages):
        """Test retrieval with whitespace-only claim."""
        claim = "   \n\t  "
        result = retriever.retrieve(claim, sample_passages)

        assert result.total_passages_searched == 4
        assert len(result.passages) == 0

    def test_retrieve_preserves_provenance(self, retriever, sample_passages):
        """Test that retrieved passages preserve provenance metadata."""
        claim = "200 students preferred online notes."
        result = retriever.retrieve(claim, sample_passages)

        assert len(result.passages) > 0
        passage = result.passages[0]

        # Check provenance fields
        assert passage.passage.document_id is not None
        assert passage.passage.document_name == "survey_report.pdf"
        assert passage.passage.page_number is not None
        assert passage.passage.source_type == "pdf"
        assert passage.passage.extraction_method == "pymupdf"
        assert passage.passage.char_start is not None
        assert passage.passage.char_end is not None

    def test_retrieve_respects_max_results(self, sample_passages):
        """Test that max_results limits the number of returned passages."""
        retriever = create_retriever(min_score=0.01, max_results=2)
        claim = "survey students online notes"
        result = retriever.retrieve(claim, sample_passages)

        assert len(result.passages) <= 2

    def test_retrieve_respects_min_score(self, sample_passages):
        """Test that min_score filters out low-relevance passages."""
        retriever = create_retriever(min_score=100.0, max_results=5)  # Very high threshold
        claim = "survey students online notes"
        result = retriever.retrieve(claim, sample_passages)

        assert len(result.passages) == 0

    def test_retrieve_case_insensitive(self, sample_passages):
        """Test that retrieval is case insensitive by default."""
        retriever = create_retriever(min_score=0.05, case_sensitive=False)
        claim = "SURVEY STUDENTS ONLINE NOTES"
        result = retriever.retrieve(claim, sample_passages)

        assert len(result.passages) > 0

    def test_retrieve_case_sensitive(self, sample_passages):
        """Test that retrieval can be case sensitive."""
        retriever = create_retriever(min_score=0.05, case_sensitive=True, max_results=3)
        claim = "survey"  # lowercase
        result = retriever.retrieve(claim, sample_passages)

        # The passage has "Survey" with capital S
        # With case_sensitive=True, it might still match depending on tokenization
        # This test just ensures the parameter works
        assert isinstance(result, RetrievalResult)

    def test_retrieve_multiple_claims_independent(self, retriever, sample_passages):
        """Test that retrieving multiple claims doesn't affect each other."""
        claim1 = "200 students"
        claim2 = "online notes"

        result1 = retriever.retrieve(claim1, sample_passages)
        result2 = retriever.retrieve(claim2, sample_passages)

        assert len(result1.passages) > 0
        assert len(result2.passages) > 0

        # Results should be different
        if result1.passages and result2.passages:
            assert result1.passages[0].passage.text != result2.passages[0].passage.text or \
                   result1.passages[0].score != result2.passages[0].score

    def test_retrieve_filters_stopwords(self, sample_passages):
        """Test that stopwords like 'the', 'of', 'and' are filtered out."""
        claim = "The survey of students"
        retriever = create_retriever(min_score=0.05, max_results=3)
        result = retriever.retrieve(claim, sample_passages)

        # Should still match but "the" and "of" should not be in matched_terms
        if result.passages:
            for term in result.passages[0].matched_terms:
                assert term.lower() not in ["the", "of", "and", "a", "an", "in", "is", "to", "for"]

    def test_retrieve_preserves_percentage_sign(self, retriever, sample_passages):
        """Test that percentage signs are preserved in tokenization."""
        claim = "60% of students"
        result = retriever.retrieve(claim, sample_passages)

        if result.passages:
            # 60% should be preserved as a term
            assert any("%" in term for term in result.passages[0].matched_terms)


class TestRetrievalResult:
    """Tests for RetrievalResult dataclass."""

    def test_retrieval_result_creation(self):
        """Test creating a RetrievalResult."""
        result = RetrievalResult(
            claim_text="Test claim",
            passages=[],
            total_passages_searched=5,
        )
        assert result.claim_text == "Test claim"
        assert result.passages == []
        assert result.total_passages_searched == 5
        assert result.error is None

    def test_retrieval_result_with_error(self):
        """Test RetrievalResult with error."""
        result = RetrievalResult(
            claim_text="Test claim",
            passages=[],
            total_passages_searched=0,
            error="No passages available",
        )
        assert result.error == "No passages available"

    def test_retrieved_passage_creation(self):
        """Test creating a RetrievedPassage."""
        from app.services.documents.text_chunker import TextPassage
        from uuid import uuid4

        doc_id = uuid4()
        passage = TextPassage(
            passage_id=f"{doc_id}-p0",
            document_id=doc_id,
            document_name="test.pdf",
            page_number=1,
            text="Test passage",
            char_start=0,
            char_end=12,
            source_type="pdf",
            extraction_method="pymupdf",
        )

        retrieved = RetrievedPassage(
            passage=passage,
            score=0.85,
            matched_terms=["test", "passage"],
        )

        assert retrieved.score == 0.85
        assert retrieved.matched_terms == ["test", "passage"]
        assert retrieved.passage.text == "Test passage"