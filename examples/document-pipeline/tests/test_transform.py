"""Tests for document transform subsystem.

Demonstrates:
- Class-based tests (TestPDFConversion)
- Passing tests (DOC-TRF-002, DOC-TRF-003)
- Skipped tests (DOC-TRF-004 - OCR pending)
- Parametrized image optimization tests
"""

import pytest
from conftest import MockDocument, MockDocumentProcessor


# =============================================================================
# DOC-TRF-001: Transform Subsystem (parent requirement)
# =============================================================================


@pytest.mark.requirement("DOC-TRF-001")
def test_transform_subsystem_initialized(processor):
    """Verify transform subsystem is properly configured."""
    assert processor is not None
    assert hasattr(processor, "convert_to_pdf")
    assert hasattr(processor, "optimize_image")


# =============================================================================
# DOC-TRF-002: PDF Conversion (class-based tests)
# =============================================================================


@pytest.mark.requirement("DOC-TRF-002")
class TestPDFConversion:
    """Class-based tests for PDF conversion functionality."""

    def test_docx_to_pdf_conversion(self, processor, sample_docx):
        """DOCX files convert to PDF successfully."""
        result = processor.convert_to_pdf(sample_docx)
        assert result.success is True
        assert result.document_id == "pdf_converted"

    def test_image_to_pdf_conversion(self, processor, sample_image):
        """Image files convert to single-page PDFs."""
        result = processor.convert_to_pdf(sample_image)
        assert result.success is True
        assert result.document_id == "pdf_converted"

    def test_pdf_passthrough(self, processor, sample_pdf):
        """PDF files are passed through without conversion."""
        result = processor.convert_to_pdf(sample_pdf)
        assert result.success is True
        assert result.document_id == "pdf_already"

    def test_tiff_to_pdf_conversion(self, processor):
        """Multi-page TIFF converts to multi-page PDF."""
        tiff_doc = MockDocument(
            filename="multipage.tiff",
            content=b"II*\x00 tiff content",
            mime_type="image/tiff",
            size=10240,
        )
        result = processor.convert_to_pdf(tiff_doc)
        assert result.success is True

    def test_unsupported_format_fails(self, processor, malicious_exe):
        """Unsupported formats cannot be converted."""
        result = processor.convert_to_pdf(malicious_exe)
        assert result.success is False
        assert "Cannot convert" in result.error


# =============================================================================
# DOC-TRF-003: Image Optimization
# =============================================================================


@pytest.mark.requirement("DOC-TRF-003")
@pytest.mark.parametrize(
    "target_width,variant_name",
    [
        (150, "thumbnail"),
        (800, "preview"),
        (1920, "full-size"),
    ],
    ids=["thumbnail-150px", "preview-800px", "full-1920px"],
)
def test_image_optimization_variants(processor, sample_image, target_width, variant_name):
    """Generate optimized image variants at different sizes."""
    result = processor.optimize_image(sample_image, target_width)
    assert result.success is True
    assert result.metadata["width"] == target_width
    assert result.metadata["format"] == "webp"


@pytest.mark.requirement("DOC-TRF-003")
def test_webp_conversion(processor, sample_jpeg):
    """Images are converted to WebP format."""
    result = processor.optimize_image(sample_jpeg, 800)
    assert result.success is True
    assert result.metadata["format"] == "webp"


@pytest.mark.requirement("DOC-TRF-003")
def test_non_image_optimization_fails(processor, sample_pdf):
    """Non-image files cannot be optimized."""
    result = processor.optimize_image(sample_pdf, 800)
    assert result.success is False
    assert "Not an image" in result.error


# =============================================================================
# DOC-TRF-004: OCR Processing (skipped - pending new provider)
# =============================================================================


@pytest.mark.requirement("DOC-TRF-004")
@pytest.mark.skip(reason="OCR integration pending - switching to new provider")
def test_scanned_pdf_ocr():
    """Scanned PDFs undergo OCR to enable text search.

    This test is skipped pending integration with the new OCR
    service provider. Expected completion: Q2 2025.
    """
    # OCR implementation pending
    pass


@pytest.mark.requirement("DOC-TRF-004")
@pytest.mark.skip(reason="OCR integration pending - switching to new provider")
def test_ocr_language_detection():
    """OCR automatically detects document language.

    Skipped while OCR provider integration is in progress.
    """
    pass


@pytest.mark.requirement("DOC-TRF-004")
@pytest.mark.skip(reason="OCR integration pending - switching to new provider")
def test_ocr_confidence_scores():
    """OCR provides confidence scores for extracted text.

    Skipped while OCR provider integration is in progress.
    """
    pass


@pytest.mark.requirement("DOC-TRF-004")
@pytest.mark.skip(reason="OCR integration pending - switching to new provider")
def test_rotated_document_handling():
    """OCR handles rotated and skewed documents.

    Skipped while OCR provider integration is in progress.
    """
    pass
