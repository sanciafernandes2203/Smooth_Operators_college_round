"""
Text chunking for evidence retrieval.

Splits extracted source text into passages while preserving
document and page provenance for citation.
"""
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from app.services.documents.pdf_extractor import PDFExtractionResult, PageExtractionResult
from app.services.documents.ocr_service import OCRResult


@dataclass
class TextPassage:
    """
    A chunk of text with full source provenance.

    Used for evidence retrieval and citation.
    """
    passage_id: str  # Unique identifier for this passage
    document_id: UUID
    document_name: str
    page_number: Optional[int]
    text: str
    char_start: int  # Character offset in original document
    char_end: int    # Character offset in original document
    source_type: str  # "text", "pdf", "ocr"
    extraction_method: str  # "pymupdf", "tesseract", "direct"


@dataclass
class ChunkingResult:
    """Result of chunking a document."""
    document_id: UUID
    document_name: str
    passages: list[TextPassage]
    total_chunks: int
    errors: list[str]

    def __init__(self, document_id: UUID, document_name: str):
        self.document_id = document_id
        self.document_name = document_name
        self.passages = []
        self.total_chunks = 0
        self.errors = []


class TextChunker:
    """
    Splits document text into overlapping passages for retrieval.

    Preserves page-level and document-level provenance for each chunk.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        min_chunk_size: int = 50,
    ):
        """
        Initialize text chunker.

        Args:
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Overlap between adjacent chunks in characters
            min_chunk_size: Minimum chunk size (smaller chunks are merged)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_text(
        self,
        text: str,
        document_id: UUID,
        document_name: str,
        page_number: Optional[int] = None,
        source_type: str = "text",
        extraction_method: str = "direct",
    ) -> list[TextPassage]:
        """
        Split text into overlapping chunks.

        Args:
            text: Source text to chunk
            document_id: Source document UUID
            document_name: Source document filename
            page_number: Page number (1-based) if applicable
            source_type: Type of source ("text", "pdf", "ocr")
            extraction_method: Method used ("direct", "pymupdf", "tesseract")

        Returns:
            List of TextPassage objects with provenance
        """
        if not text or not text.strip():
            return []

        # For very short texts, return as single chunk regardless of min_chunk_size
        if len(text.strip()) < self.min_chunk_size:
            return [TextPassage(
                passage_id=f"{document_id}-p0",
                document_id=document_id,
                document_name=document_name,
                page_number=page_number,
                text=text.strip(),
                char_start=0,
                char_end=len(text),
                source_type=source_type,
                extraction_method=extraction_method,
            )]

        passages = []
        text_len = len(text)
        start = 0
        chunk_index = 0

        while start < text_len:
            end = min(start + self.chunk_size, text_len)

            # Try to break at sentence boundary
            if end < text_len:
                # Look for sentence end within last 100 chars
                search_start = max(start, end - 100)
                for punct in [". ", "! ", "? ", "\n\n"]:
                    pos = text.rfind(punct, search_start, end)
                    if pos != -1:
                        end = pos + 1  # Include the punctuation
                        break

            chunk_text = text[start:end].strip()

            if len(chunk_text) >= self.min_chunk_size:
                passage = TextPassage(
                    passage_id=f"{document_id}-p{chunk_index}",
                    document_id=document_id,
                    document_name=document_name,
                    page_number=page_number,
                    text=chunk_text,
                    char_start=start,
                    char_end=end,
                    source_type=source_type,
                    extraction_method=extraction_method,
                )
                passages.append(passage)
                chunk_index += 1

            # Move start forward with overlap
            # If we're at the end of text, break to avoid infinite loop
            if end >= text_len:
                break
            start = end - self.chunk_overlap
            if start < 0:
                start = 0

            # Prevent infinite loop
            if start >= end:
                start = end

        return passages

    def chunk_pdf_extraction(
        self,
        result: PDFExtractionResult,
        document_id: UUID,
        document_name: str,
    ) -> ChunkingResult:
        """
        Chunk a PDF extraction result, preserving page-level provenance.

        Args:
            result: PDFExtractionResult from pdf_extractor
            document_id: Source document UUID
            document_name: Source document filename

        Returns:
            ChunkingResult with all passages
        """
        chunking_result = ChunkingResult(document_id, document_name)

        for page in result.pages:
            if page.has_text:
                passages = self.chunk_text(
                    text=page.text,
                    document_id=document_id,
                    document_name=document_name,
                    page_number=page.page_number,
                    source_type="pdf",
                    extraction_method=page.extraction_method,
                )
                chunking_result.passages.extend(passages)
            elif page.is_likely_scanned:
                chunking_result.errors.append(
                    f"Page {page.page_number}: Likely scanned/image-only (char_count={page.char_count})"
                )

        chunking_result.total_chunks = len(chunking_result.passages)
        chunking_result.errors.extend(result.errors)

        return chunking_result

    def chunk_ocr_results(
        self,
        ocr_results: list[OCRResult],
        document_id: UUID,
        document_name: str,
    ) -> ChunkingResult:
        """
        Chunk OCR results from multiple pages.

        Args:
            ocr_results: List of OCRResult objects
            document_id: Source document UUID
            document_name: Source document filename

        Returns:
            ChunkingResult with all passages
        """
        chunking_result = ChunkingResult(document_id, document_name)

        for ocr in ocr_results:
            if ocr.has_text:
                passages = self.chunk_text(
                    text=ocr.text,
                    document_id=document_id,
                    document_name=document_name,
                    page_number=ocr.page_number,
                    source_type="ocr",
                    extraction_method="tesseract",
                )
                chunking_result.passages.extend(passages)
            else:
                chunking_result.errors.append(
                    f"Page {ocr.page_number}: OCR produced no text"
                )

            chunking_result.errors.extend(ocr.errors)

        chunking_result.total_chunks = len(chunking_result.passages)
        return chunking_result

    def chunk_plain_text(
        self,
        text: str,
        document_id: UUID,
        document_name: str,
    ) -> ChunkingResult:
        """
        Chunk plain text (from pasted source or TXT file).

        Args:
            text: Source text
            document_id: Source document UUID
            document_name: Source document filename

        Returns:
            ChunkingResult with all passages
        """
        chunking_result = ChunkingResult(document_id, document_name)

        passages = self.chunk_text(
            text=text,
            document_id=document_id,
            document_name=document_name,
            page_number=None,
            source_type="text",
            extraction_method="direct",
        )
        chunking_result.passages.extend(passages)
        chunking_result.total_chunks = len(chunking_result.passages)

        return chunking_result