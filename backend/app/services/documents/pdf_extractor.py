"""
PDF text extraction using PyMuPDF (fitz).

Extracts text page by page, preserving page-level provenance.
Detects scanned/image-only pages that may need OCR.
"""
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from app.utils.file_validation import get_file_type_category

logger = logging.getLogger(__name__)


@dataclass
class PageExtractionResult:
    """Result of extracting text from a single PDF page."""

    page_number: int  # 1-based page number
    text: str
    char_count: int
    has_text: bool
    is_likely_scanned: bool
    extraction_method: str = "pymupdf"


@dataclass
class PDFExtractionResult:
    """Result of extracting text from a PDF document."""

    file_path: str
    page_count: int
    pages: list[PageExtractionResult]
    total_char_count: int
    extraction_method: str = "pymupdf"
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class PDFExtractor:
    """Extracts text from PDF documents using PyMuPDF."""

    # Minimum characters per page to consider it as having extractable text
    MIN_CHARS_PER_PAGE = 50

    def __init__(self, max_pages: Optional[int] = None):
        """
        Initialize PDF extractor.

        Args:
            max_pages: Maximum number of pages to process (None for no limit)
        """
        self.max_pages = max_pages

    def extract(self, file_content: bytes, filename: str) -> PDFExtractionResult:
        """
        Extract text from a PDF file.

        Args:
            file_content: Raw PDF file bytes
            filename: Original filename for logging

        Returns:
            PDFExtractionResult with page-by-page extraction results
        """
        # Write to temporary file for PyMuPDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        try:
            return self._extract_from_path(tmp_path, filename)
        finally:
            # Clean up temp file
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to delete temp file {tmp_path}: {e}")

    def _extract_from_path(self, file_path: str, filename: str) -> PDFExtractionResult:
        """Extract text from PDF at given path."""
        errors = []
        pages = []

        try:
            doc = fitz.open(file_path)
        except Exception as e:
            errors.append(f"Failed to open PDF: {e}")
            return PDFExtractionResult(
                file_path=filename,
                page_count=0,
                pages=[],
                total_char_count=0,
                errors=errors,
            )

        page_count = len(doc)

        if self.max_pages and page_count > self.max_pages:
            errors.append(
                f"PDF has {page_count} pages, exceeds limit of {self.max_pages}. "
                f"Only first {self.max_pages} pages processed."
            )
            page_count = self.max_pages

        total_chars = 0

        for page_num in range(page_count):
            try:
                page = doc[page_num]
                text = page.get_text("text")

                char_count = len(text)
                has_text = char_count >= self.MIN_CHARS_PER_PAGE
                is_likely_scanned = not has_text

                # Additional heuristic: check for images on page
                if not is_likely_scanned:
                    images = page.get_images(full=True)
                    # If page has large images but little text, might be scanned
                    if images and char_count < 200:
                        # Check image sizes - if they cover most of the page
                        page_rect = page.rect
                        page_area = page_rect.width * page_rect.height
                        for img in images:
                            # img format: (xref, smask, width, height, ...)
                            if len(img) >= 4:
                                img_width, img_height = img[2], img[3]
                                img_area = img_width * img_height
                                if img_area > page_area * 0.5:
                                    is_likely_scanned = True
                                    break

                page_result = PageExtractionResult(
                    page_number=page_num + 1,  # 1-based
                    text=text,
                    char_count=char_count,
                    has_text=has_text,
                    is_likely_scanned=is_likely_scanned,
                    extraction_method="pymupdf",
                )
                pages.append(page_result)
                total_chars += char_count

            except Exception as e:
                errors.append(f"Failed to extract page {page_num + 1}: {e}")
                pages.append(
                    PageExtractionResult(
                        page_number=page_num + 1,
                        text="",
                        char_count=0,
                        has_text=False,
                        is_likely_scanned=True,
                        extraction_method="pymupdf",
                    )
                )

        # Save page count before closing
        final_page_count = len(doc)
        doc.close()

        return PDFExtractionResult(
            file_path=filename,
            page_count=final_page_count,
            pages=pages,
            total_char_count=total_chars,
            extraction_method="pymupdf",
            errors=errors,
        )

    @staticmethod
    def is_encrypted(file_content: bytes) -> bool:
        """Check if a PDF is encrypted/password protected."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        try:
            doc = fitz.open(tmp_path)
            encrypted = bool(doc.needs_pass)
            doc.close()
            return encrypted
        except Exception:
            return False
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


def extract_pdf_text(
    file_content: bytes,
    filename: str,
    max_pages: Optional[int] = None,
) -> PDFExtractionResult:
    """
    Convenience function to extract text from PDF.

    Args:
        file_content: Raw PDF file bytes
        filename: Original filename
        max_pages: Maximum pages to process

    Returns:
        PDFExtractionResult
    """
    extractor = PDFExtractor(max_pages=max_pages)
    return extractor.extract(file_content, filename)