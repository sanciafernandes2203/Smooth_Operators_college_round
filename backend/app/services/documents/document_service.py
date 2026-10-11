"""
Document processing service.

Orchestrates text extraction, OCR, and chunking for all supported file types.
"""
import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4

from app.config import get_settings
from app.services.documents.pdf_extractor import PDFExtractionResult, extract_pdf_text
from app.services.documents.ocr_service import OCRResult, OCRService
from app.services.documents.text_chunker import ChunkingResult, TextChunker
from app.utils.file_validation import get_file_type_category

logger = logging.getLogger(__name__)


@dataclass
class DocumentProcessingResult:
    """
    Complete result of processing a single document.

    Contains extracted text, chunked passages, and metadata
    needed for later pipeline stages.
    """
    document_id: UUID
    filename: str
    mime_type: str
    file_type_category: str  # "text", "pdf", "image"
    page_count: int
    total_char_count: int
    processing_status: str  # "PROCESSED", "FAILED", "PARTIAL"
    extraction_method: str
    full_text: str
    passages: list  # List of TextPassage from chunker
    errors: list[str]
    ocr_pages: list[int]  # Page numbers that used OCR

    def __init__(
        self,
        document_id: UUID,
        filename: str,
        mime_type: str,
        file_type_category: str,
    ):
        self.document_id = document_id
        self.filename = filename
        self.mime_type = mime_type
        self.file_type_category = file_type_category
        self.page_count = 0
        self.total_char_count = 0
        self.processing_status = "PENDING"
        self.extraction_method = ""
        self.full_text = ""
        self.passages = []
        self.errors = []
        self.ocr_pages = []

    def mark_processed(self, method: str = "direct") -> None:
        """Mark document as successfully processed."""
        self.processing_status = "PROCESSED"
        self.extraction_method = method

    def mark_partial(self, method: str = "partial") -> None:
        """Mark document as partially processed (some errors)."""
        self.processing_status = "PARTIAL"
        self.extraction_method = method

    def mark_failed(self, error: str) -> None:
        """Mark document as failed."""
        self.processing_status = "FAILED"
        self.errors.append(error)


class DocumentService:
    """
    Main document processing service.

    Handles TXT, PDF, and image files. For PDFs, extracts text page by page
    and applies OCR to scanned pages. For images, runs OCR directly.
    """

    def __init__(
        self,
        max_pages: Optional[int] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        ocr_language: str = "eng",
    ):
        """
        Initialize document service.

        Args:
            max_pages: Maximum pages to process per PDF (None = no limit)
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            ocr_language: Tesseract language code
        """
        self.max_pages = max_pages
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.ocr_language = ocr_language

        # Initialize sub-services
        self.ocr_service = None
        self.chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def _get_ocr_service(self) -> OCRService:
        """Lazy initialization of OCR service."""
        if self.ocr_service is None:
            settings = get_settings()
            self.ocr_service = OCRService(
                language=self.ocr_language,
                tesseract_cmd=settings.tesseract_cmd,
            )
        return self.ocr_service

    def process_file(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str,
        document_id: Optional[UUID] = None,
    ) -> DocumentProcessingResult:
        """
        Process a single uploaded file.

        Args:
            file_content: Raw file bytes
            filename: Original filename
            mime_type: MIME type from upload
            document_id: Optional UUID (generated if not provided)

        Returns:
            DocumentProcessingResult with extracted text and passages
        """
        if document_id is None:
            document_id = uuid4()

        file_category = get_file_type_category(mime_type, filename)

        result = DocumentProcessingResult(
            document_id=document_id,
            filename=filename,
            mime_type=mime_type,
            file_type_category=file_category,
        )

        try:
            if file_category == "text":
                self._process_text_file(file_content, result)
            elif file_category == "pdf":
                self._process_pdf_file(file_content, result)
            elif file_category == "image":
                self._process_image_file(file_content, result)
            else:
                result.mark_failed(f"Unknown file category: {file_category}")

        except Exception as e:
            logger.exception(f"Failed to process {filename}")
            result.mark_failed(f"Processing error: {e}")

        return result

    def _process_text_file(
        self,
        file_content: bytes,
        result: DocumentProcessingResult,
    ) -> None:
        """Process plain text file (TXT)."""
        try:
            # Try UTF-8 first
            try:
                text = file_content.decode("utf-8")
            except UnicodeDecodeError:
                # Fallback: try common encodings
                for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
                    try:
                        text = file_content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    result.mark_failed("Unable to decode text file with any supported encoding")
                    return

            if not text.strip():
                result.mark_failed("Text file is empty or contains only whitespace")
                return

            result.full_text = text
            result.total_char_count = len(text)
            result.page_count = 1
            result.mark_processed("direct")

            # Chunk the text
            chunk_result = self.chunker.chunk_plain_text(
                text=text,
                document_id=result.document_id,
                document_name=result.filename,
            )
            result.passages = chunk_result.passages
            result.errors.extend(chunk_result.errors)

        except Exception as e:
            result.mark_failed(f"Text extraction failed: {e}")

    def _process_pdf_file(
        self,
        file_content: bytes,
        result: DocumentProcessingResult,
    ) -> None:
        """Process PDF file with text extraction and OCR for scanned pages."""
        try:
            # Extract text using PyMuPDF
            pdf_result = extract_pdf_text(
                file_content,
                result.filename,
                max_pages=self.max_pages,
            )

            result.page_count = pdf_result.page_count

            # Collect text from all pages
            full_text_parts = []
            ocr_pages = []

            for page in pdf_result.pages:
                if page.has_text:
                    full_text_parts.append(page.text)
                elif page.is_likely_scanned:
                    # Mark for OCR
                    ocr_pages.append(page.page_number)

            # If we have scanned pages, run OCR on them
            if ocr_pages:
                ocr_service = self._get_ocr_service()
                for page_num in ocr_pages:
                    try:
                        ocr_result = ocr_service.process_pdf_page(
                            file_content,
                            page_num,
                            result.filename,
                        )
                        if ocr_result.has_text:
                            full_text_parts.append(ocr_result.text)
                            result.ocr_pages.append(page_num)
                            result.total_char_count += ocr_result.char_count
                            # Add OCR text as a pseudo-page
                            # We'll handle chunking separately
                    except Exception as e:
                        result.errors.append(f"OCR failed for page {page_num}: {e}")

            # Combine all extracted text
            result.full_text = "\n\n".join(full_text_parts)
            result.total_char_count = len(result.full_text)

            # Chunk the combined text with page provenance
            # For now, chunk the full text (later we could preserve page boundaries better)
            chunk_result = self.chunker.chunk_text(
                text=result.full_text,
                document_id=result.document_id,
                document_name=result.filename,
                page_number=None,  # Mixed pages
                source_type="pdf",
                extraction_method="pymupdf+ocr" if result.ocr_pages else "pymupdf",
            )
            result.passages = chunk_result.passages
            result.errors.extend(chunk_result.errors)
            result.errors.extend(pdf_result.errors)

            if result.total_char_count == 0:
                result.mark_failed("No text could be extracted from PDF")
            elif result.ocr_pages or result.errors:
                result.mark_partial("pymupdf+ocr")
            else:
                result.mark_processed("pymupdf")

        except Exception as e:
            logger.exception(f"PDF processing failed for {result.filename}")
            result.mark_failed(f"PDF processing error: {e}")

    def _process_image_file(
        self,
        file_content: bytes,
        result: DocumentProcessingResult,
    ) -> None:
        """Process image file with OCR."""
        try:
            ocr_service = self._get_ocr_service()
            ocr_result = ocr_service.process_image(
                file_content,
                page_number=1,
                filename=result.filename,
            )

            result.page_count = 1

            if ocr_result.has_text:
                result.full_text = ocr_result.text
                result.total_char_count = ocr_result.char_count
                result.ocr_pages = [1]
                result.mark_processed("tesseract")

                # Chunk the OCR text
                chunk_result = self.chunker.chunk_text(
                    text=ocr_result.text,
                    document_id=result.document_id,
                    document_name=result.filename,
                    page_number=1,
                    source_type="ocr",
                    extraction_method="tesseract",
                )
                result.passages = chunk_result.passages
                result.errors.extend(chunk_result.errors)
                result.errors.extend(ocr_result.errors)
            else:
                result.mark_failed("OCR produced no readable text")
                result.errors.extend(ocr_result.errors)

        except Exception as e:
            logger.exception(f"Image processing failed for {result.filename}")
            result.mark_failed(f"Image processing error: {e}")

    def process_multiple(
        self,
        files: list[tuple[bytes, str, str]],  # (content, filename, mime_type)
    ) -> list[DocumentProcessingResult]:
        """
        Process multiple files.

        Args:
            files: List of (content, filename, mime_type) tuples

        Returns:
            List of DocumentProcessingResult
        """
        results = []
        for content, filename, mime_type in files:
            result = self.process_file(content, filename, mime_type)
            results.append(result)
        return results