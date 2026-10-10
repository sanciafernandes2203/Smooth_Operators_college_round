"""
OCR service using Tesseract (via pytesseract).

Processes images and scanned PDF pages to extract text.
"""
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytesseract
from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Result of OCR processing on a single image/page."""

    page_number: int
    text: str
    char_count: int
    confidence: Optional[float] = None
    language: str = "eng"
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    @property
    def has_text(self) -> bool:
        return bool(self.text.strip())


class OCRService:
    """OCR service using Tesseract."""

    def __init__(
        self,
        language: str = "eng",
        tesseract_cmd: Optional[str] = None,
        config: str = "",
    ):
        """
        Initialize OCR service.

        Args:
            language: Tesseract language code(s), e.g., "eng", "eng+fra"
            tesseract_cmd: Path to tesseract executable (None = use PATH or config)
            config: Additional tesseract config options
        """
        self.language = language
        self.config = config

        # Configure tesseract command path
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        else:
            settings = get_settings()
            if settings.tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

        # Verify tesseract is available
        self._verify_tesseract()

    def _verify_tesseract(self) -> None:
        """Verify Tesseract is installed and accessible."""
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract version: {version}")
        except pytesseract.TesseractNotFoundError:
            logger.error(
                "Tesseract executable not found. "
                "Install Tesseract OCR and ensure it's in PATH, "
                "or set TESSERACT_CMD in .env"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to verify Tesseract: {e}")
            raise

    def process_image(
        self,
        image_content: bytes,
        page_number: int = 1,
        filename: str = "image",
    ) -> OCRResult:
        """
        Process an image file with OCR.

        Args:
            image_content: Raw image file bytes
            page_number: Page number for provenance (1-based)
            filename: Original filename for logging

        Returns:
            OCRResult with extracted text
        """
        errors = []

        # Write to temporary file
        with tempfile.NamedTemporaryFile(suffix=self._get_suffix(filename), delete=False) as tmp:
            tmp.write(image_content)
            tmp_path = tmp.name

        try:
            return self._process_image_file(tmp_path, page_number, filename)
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to delete temp file {tmp_path}: {e}")

    def _get_suffix(self, filename: str) -> str:
        """Get appropriate suffix for temp file based on filename."""
        ext = Path(filename).suffix.lower()
        if ext in (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"):
            return ext
        return ".png"

    def _process_image_file(
        self,
        image_path: str,
        page_number: int,
        filename: str,
    ) -> OCRResult:
        """Process image file at given path."""
        errors = []

        try:
            image = Image.open(image_path)
        except Exception as e:
            errors.append(f"Failed to open image: {e}")
            return OCRResult(
                page_number=page_number,
                text="",
                char_count=0,
                errors=errors,
            )

        try:
            # Run OCR with detailed output
            ocr_data = pytesseract.image_to_data(
                image,
                lang=self.language,
                config=self.config,
                output_type=pytesseract.Output.DICT,
            )

            # Extract text from OCR data
            text_parts = []
            confidences = []

            for i, word in enumerate(ocr_data.get("text", [])):
                if word.strip():
                    text_parts.append(word)
                    conf = ocr_data.get("conf", [])[i]
                    if conf != "-1":  # -1 means no confidence data
                        try:
                            confidences.append(float(conf))
                        except (ValueError, TypeError):
                            pass

            text = " ".join(text_parts)
            char_count = len(text)
            avg_confidence = sum(confidences) / len(confidences) if confidences else None

            return OCRResult(
                page_number=page_number,
                text=text,
                char_count=char_count,
                confidence=avg_confidence,
                language=self.language,
                errors=errors,
            )

        except pytesseract.TesseractError as e:
            errors.append(f"Tesseract error: {e}")
            return OCRResult(
                page_number=page_number,
                text="",
                char_count=0,
                errors=errors,
            )
        except Exception as e:
            errors.append(f"OCR processing failed: {e}")
            return OCRResult(
                page_number=page_number,
                text="",
                char_count=0,
                errors=errors,
            )

    def process_pdf_page(
        self,
        pdf_content: bytes,
        page_number: int,
        filename: str = "document.pdf",
    ) -> OCRResult:
        """
        Process a single PDF page with OCR by rendering it as an image.

        Args:
            pdf_content: Raw PDF file bytes
            page_number: 1-based page number to process
            filename: Original filename for logging

        Returns:
            OCRResult with extracted text
        """
        import fitz  # PyMuPDF

        errors = []

        # Write PDF to temp file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_content)
            tmp_path = tmp.name

        try:
            doc = fitz.open(tmp_path)

            # Convert to 0-based index
            page_idx = page_number - 1
            if page_idx < 0 or page_idx >= len(doc):
                errors.append(f"Page {page_number} out of range (1-{len(doc)})")
                return OCRResult(
                    page_number=page_number,
                    text="",
                    char_count=0,
                    errors=errors,
                )

            page = doc[page_idx]

            # Render page as high-resolution image (300 DPI)
            mat = fitz.Matrix(300 / 72, 300 / 72)  # 300 DPI
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pix.tobytes("png")
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Run OCR on the rendered image
            try:
                ocr_data = pytesseract.image_to_data(
                    image,
                    lang=self.language,
                    config=self.config,
                    output_type=pytesseract.Output.DICT,
                )

                text_parts = []
                confidences = []

                for i, word in enumerate(ocr_data.get("text", [])):
                    if word.strip():
                        text_parts.append(word)
                        conf = ocr_data.get("conf", [])[i]
                        if conf != "-1":
                            try:
                                confidences.append(float(conf))
                            except (ValueError, TypeError):
                                pass

                text = " ".join(text_parts)
                char_count = len(text)
                avg_confidence = sum(confidences) / len(confidences) if confidences else None

                return OCRResult(
                    page_number=page_number,
                    text=text,
                    char_count=char_count,
                    confidence=avg_confidence,
                    language=self.language,
                    errors=errors,
                )

            except pytesseract.TesseractError as e:
                errors.append(f"Tesseract error: {e}")
                return OCRResult(
                    page_number=page_number,
                    text="",
                    char_count=0,
                    errors=errors,
                )
            except Exception as e:
                errors.append(f"OCR processing failed: {e}")
                return OCRResult(
                    page_number=page_number,
                    text="",
                    char_count=0,
                    errors=errors,
                )

        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


def create_ocr_service(
    language: str = "eng",
    tesseract_cmd: Optional[str] = None,
) -> OCRService:
    """Create OCR service with configuration from settings."""
    return OCRService(language=language, tesseract_cmd=tesseract_cmd)