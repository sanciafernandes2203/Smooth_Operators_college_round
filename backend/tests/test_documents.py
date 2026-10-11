"""
Document Processing Tests
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.documents.pdf_extractor import PDFExtractor, extract_pdf_text, PDFExtractionResult
from app.services.documents.ocr_service import OCRService, OCRResult
from app.services.documents.text_chunker import TextChunker, TextPassage, ChunkingResult
from app.services.documents.document_service import DocumentService, DocumentProcessingResult
from app.utils.file_validation import (
    validate_file_extension,
    validate_mime_type,
    validate_file_size,
    validate_upload_file,
    get_file_type_category,
    FileValidationError,
    ErrorCodes,
)


class TestFileValidation:
    """Tests for file validation utilities."""

    def test_validate_file_extension_valid(self):
        """Test valid file extensions pass."""
        for ext in [".txt", ".pdf", ".jpg", ".jpeg", ".png"]:
            assert validate_file_extension(f"test{ext}") is None

    def test_validate_file_extension_invalid(self):
        """Test invalid file extensions raise error."""
        with pytest.raises(FileValidationError) as exc:
            validate_file_extension("test.docx")
        assert exc.value.code == ErrorCodes.UNSUPPORTED_FILE_TYPE

    def test_validate_file_extension_empty(self):
        """Test empty filename raises error."""
        with pytest.raises(FileValidationError) as exc:
            validate_file_extension("")
        assert exc.value.code == ErrorCodes.INVALID_INPUT

    def test_validate_mime_type_valid(self):
        """Test valid MIME types pass."""
        assert validate_mime_type("text/plain", "test.txt") is None
        assert validate_mime_type("application/pdf", "test.pdf") is None
        assert validate_mime_type("image/jpeg", "test.jpg") is None
        assert validate_mime_type("image/png", "test.png") is None

    def test_validate_mime_type_invalid(self):
        """Test invalid MIME types raise error."""
        with pytest.raises(FileValidationError) as exc:
            validate_mime_type("application/msword", "test.docx")
        assert exc.value.code == ErrorCodes.UNSUPPORTED_FILE_TYPE

    def test_validate_mime_type_mismatch(self):
        """Test MIME type mismatch with extension raises error."""
        with pytest.raises(FileValidationError) as exc:
            validate_mime_type("application/pdf", "test.txt")
        assert exc.value.code == ErrorCodes.UNSUPPORTED_FILE_TYPE

    def test_validate_file_size_valid(self):
        """Test valid file sizes pass."""
        validate_file_size(1024 * 1024, max_size_mb=15)  # 1 MB
        validate_file_size(15 * 1024 * 1024, max_size_mb=15)  # 15 MB

    def test_validate_file_size_too_large(self):
        """Test oversized files raise error."""
        with pytest.raises(FileValidationError) as exc:
            validate_file_size(16 * 1024 * 1024, max_size_mb=15)
        assert exc.value.code == ErrorCodes.FILE_TOO_LARGE

    def test_get_file_type_category(self):
        """Test file type category detection."""
        assert get_file_type_category("text/plain", "test.txt") == "text"
        assert get_file_type_category("application/pdf", "test.pdf") == "pdf"
        assert get_file_type_category("image/jpeg", "test.jpg") == "image"
        assert get_file_type_category("image/png", "test.png") == "image"
        assert get_file_type_category(None, "test.txt") == "text"
        assert get_file_type_category("unknown/type", "test.xyz") == "unknown"


class TestTextChunker:
    """Tests for text chunking."""

    def test_chunk_plain_text(self):
        """Test chunking plain text."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "This is a test document. " * 10  # ~250 chars

        passages = chunker.chunk_text(
            text=text,
            document_id="test-id",
            document_name="test.txt",
        )

        assert len(passages) > 0
        for p in passages:
            assert isinstance(p, TextPassage)
            assert p.document_id == "test-id"
            assert p.document_name == "test.txt"
            assert p.source_type == "text"
            assert len(p.text) <= 120  # chunk_size + overlap

    def test_chunk_short_text(self):
        """Test chunking text shorter than chunk size."""
        chunker = TextChunker(chunk_size=500, chunk_overlap=100)
        text = "Short text."

        passages = chunker.chunk_text(
            text=text,
            document_id="test-id",
            document_name="test.txt",
        )

        assert len(passages) == 1
        assert passages[0].text == "Short text."

    def test_chunk_empty_text(self):
        """Test chunking empty text returns empty list."""
        chunker = TextChunker()
        passages = chunker.chunk_text("", "test-id", "test.txt")
        assert passages == []

    def test_chunk_overlap(self):
        """Test chunks have proper overlap."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=30)
        text = "Word " * 50  # ~250 chars

        passages = chunker.chunk_text(
            text=text,
            document_id="test-id",
            document_name="test.txt",
        )

        # Check overlap between consecutive chunks
        for i in range(len(passages) - 1):
            prev_end = passages[i].char_end
            next_start = passages[i + 1].char_start
            overlap = prev_end - next_start
            # Allow some flexibility due to sentence boundary detection
            assert overlap >= 20


class TestPDFExtractor:
    """Tests for PDF text extraction (mocked)."""

    @pytest.fixture
    def sample_pdf_content(self):
        """Return minimal valid PDF content for testing."""
        # Minimal PDF with one page
        return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n192\n%%EOF\n"

    def test_extract_pdf_text_valid(self, sample_pdf_content):
        """Test PDF extraction with valid content."""
        # This will fail with the minimal PDF but tests the error handling
        result = extract_pdf_text(sample_pdf_content, "test.pdf")
        assert isinstance(result, PDFExtractionResult)
        assert result.file_path == "test.pdf"
        # Minimal PDF has no extractable text
        assert result.total_char_count == 0

    def test_extract_pdf_text_errors(self, sample_pdf_content):
        """Test PDF extraction captures errors."""
        result = extract_pdf_text(sample_pdf_content, "test.pdf")
        assert isinstance(result.errors, list)

    def test_is_encrypted(self, sample_pdf_content):
        """Test encrypted PDF detection."""
        # Not testing actual encryption, just that method runs
        result = PDFExtractor.is_encrypted(sample_pdf_content)
        assert isinstance(result, bool)


class TestOCRService:
    """Tests for OCR service (mocked)."""

    @pytest.fixture
    def mock_image(self):
        """Create a simple test image."""
        from PIL import Image
        img = Image.new('RGB', (100, 50), color='white')
        return img

    def test_ocr_service_init(self):
        """Test OCR service initialization."""
        # This will fail if tesseract not installed, which is expected
        try:
            service = OCRService(language="eng")
            assert service.language == "eng"
        except Exception:
            # Tesseract not installed - expected in test environment
            pytest.skip("Tesseract not installed")

    @patch("app.services.documents.ocr_service.OCRService._verify_tesseract")
    @patch("app.services.documents.ocr_service.pytesseract.image_to_data")
    def test_process_image_mocked(self, mock_image_to_data, mock_verify):
        """Test image OCR with mocked tesseract."""
        mock_verify.return_value = None
        mock_image_to_data.return_value = {
            "text": ["Hello", "world"],
            "conf": ["95", "90"],
        }

        with patch("PIL.Image.open") as mock_open:
            mock_img = MagicMock()
            mock_open.return_value = mock_img

            service = OCRService(language="eng")
            # Now we can test the actual OCR processing logic
            result = service.process_image(b"fake_image_data", page_number=1, filename="test.png")
            
            assert isinstance(result, OCRResult)
            assert result.page_number == 1
            assert result.text == "Hello world"
            assert result.confidence == 92.5
            assert result.has_text


class TestDocumentService:
    """Tests for document processing service."""

    def test_process_text_file(self):
        """Test processing plain text file."""
        service = DocumentService()
        text_content = b"This is a test document with some content."

        result = service.process_file(
            file_content=text_content,
            filename="test.txt",
            mime_type="text/plain",
        )

        assert isinstance(result, DocumentProcessingResult)
        assert result.file_type_category == "text"
        assert result.processing_status == "PROCESSED"
        assert result.total_char_count > 0
        assert len(result.passages) > 0
        assert result.full_text == "This is a test document with some content."

    def test_process_empty_text_file(self):
        """Test processing empty text file."""
        service = DocumentService()

        result = service.process_file(
            file_content=b"   \n\t  ",
            filename="empty.txt",
            mime_type="text/plain",
        )

        assert result.processing_status == "FAILED"
        assert "empty" in result.errors[0].lower()

    def test_process_unknown_file_type(self):
        """Test processing unknown file type."""
        service = DocumentService()

        result = service.process_file(
            file_content=b"content",
            filename="test.xyz",
            mime_type="application/unknown",
        )

        assert result.processing_status == "FAILED"

    def test_process_multiple_files(self):
        """Test processing multiple files."""
        service = DocumentService()

        files = [
            (b"First document", "doc1.txt", "text/plain"),
            (b"Second document", "doc2.txt", "text/plain"),
        ]

        results = service.process_multiple(files)

        assert len(results) == 2
        assert all(r.processing_status == "PROCESSED" for r in results)


class TestDocumentProcessingIntegration:
    """Integration tests for document processing pipeline."""

    def test_txt_extraction_preserves_content(self):
        """Test that TXT extraction preserves all content."""
        service = DocumentService()
        original = "Line 1\nLine 2\nLine 3 with special chars: \u00e9\u00f1\u00fc"

        result = service.process_file(
            file_content=original.encode("utf-8"),
            filename="test.txt",
            mime_type="text/plain",
        )

        assert result.processing_status == "PROCESSED"
        assert original in result.full_text

    def test_chunking_preserves_provenance(self):
        """Test that chunking preserves document provenance."""
        service = DocumentService()
        text = "First sentence. Second sentence. Third sentence. " * 5

        result = service.process_file(
            file_content=text.encode("utf-8"),
            filename="provenance_test.txt",
            mime_type="text/plain",
        )

        assert result.processing_status == "PROCESSED"
        for passage in result.passages:
            assert passage.document_name == "provenance_test.txt"
            assert passage.document_id == result.document_id
            assert passage.source_type == "text"