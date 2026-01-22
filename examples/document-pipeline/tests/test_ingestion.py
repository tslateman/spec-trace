"""Tests for document ingestion subsystem.

Demonstrates:
- Parametrized tests with multiple file types
- Passing tests (DOC-ING-002)
- Failing tests (DOC-ING-004 - intentional failure)
- xfail for known edge cases
- Async tests for concurrent uploads
"""

import pytest
import asyncio
from conftest import MockDocument, MockDocumentProcessor


# =============================================================================
# DOC-ING-001: Ingestion Subsystem (parent requirement)
# =============================================================================


@pytest.mark.requirement("DOC-ING-001")
def test_ingestion_subsystem_initialized(processor):
    """Verify ingestion subsystem is properly configured."""
    assert processor is not None
    assert hasattr(processor, "validate_file_type")
    assert hasattr(processor, "extract_metadata")


# =============================================================================
# DOC-ING-002: File Type Validation
# =============================================================================


@pytest.mark.requirement("DOC-ING-002")
@pytest.mark.parametrize(
    "extension,mime_type,expected_valid",
    [
        (".pdf", "application/pdf", True),
        (
            ".docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            True,
        ),
        (".png", "image/png", True),
        (".jpg", "image/jpeg", True),
        (".jpeg", "image/jpeg", True),
        (".tiff", "image/tiff", True),
        (".exe", "application/x-msdownload", False),
        (".bat", "application/x-bat", False),
        (".sh", "application/x-sh", False),
    ],
    ids=[
        "pdf-allowed",
        "docx-allowed",
        "png-allowed",
        "jpg-allowed",
        "jpeg-allowed",
        "tiff-allowed",
        "exe-rejected",
        "bat-rejected",
        "sh-rejected",
    ],
)
def test_file_type_validation(processor, extension, mime_type, expected_valid):
    """Validate allowed and rejected file types."""
    doc = MockDocument(
        filename=f"test{extension}",
        content=b"test content",
        mime_type=mime_type,
        size=1024,
    )
    result = processor.validate_file_type(doc)
    assert result.success == expected_valid


@pytest.mark.requirement("DOC-ING-002")
def test_zero_byte_file_rejected(processor, zero_byte_file):
    """Zero-byte files should be rejected."""
    result = processor.validate_file_type(zero_byte_file)
    assert result.success is False
    assert "Zero-byte" in result.error


@pytest.mark.requirement("DOC-ING-002")
def test_oversized_file_rejected(processor, oversized_file):
    """Files over 100MB should be rejected."""
    result = processor.validate_file_type(oversized_file)
    assert result.success is False
    assert "100MB" in result.error


@pytest.mark.requirement("DOC-ING-002")
def test_mime_type_mismatch_rejected(processor):
    """Files with mismatched extension and MIME type should be rejected."""
    # PDF extension but executable MIME type
    doc = MockDocument(
        filename="fake.pdf",
        content=b"MZ executable",
        mime_type="application/x-msdownload",
        size=1024,
    )
    result = processor.validate_file_type(doc)
    assert result.success is False


# =============================================================================
# DOC-ING-004: Metadata Extraction (has intentional failing test)
# =============================================================================


@pytest.mark.requirement("DOC-ING-004")
def test_pdf_metadata_extraction(processor, sample_pdf):
    """Extract metadata from PDF documents."""
    result = processor.extract_metadata(sample_pdf)
    assert result.success is True
    assert result.metadata["title"] == "Sample PDF"
    assert result.metadata["author"] == "Test Author"


@pytest.mark.requirement("DOC-ING-004")
def test_image_metadata_extraction(processor, sample_image):
    """Extract metadata from image files."""
    result = processor.extract_metadata(sample_image)
    assert result.success is True
    assert result.metadata["width"] == 1920
    assert result.metadata["height"] == 1080


@pytest.mark.requirement("DOC-ING-004")
def test_corrupted_exif_data_handling(processor):
    """Handle corrupted EXIF data gracefully.

    This test intentionally fails to demonstrate a known bug
    with corrupted EXIF metadata in certain JPEG files.
    """
    doc = MockDocument(
        filename="corrupted_exif.jpg",
        content=b"\xff\xd8\xff\xe1\x00\x00 corrupted exif",
        mime_type="image/jpeg",
        size=2048,
    )
    result = processor.extract_metadata(doc)

    # This assertion intentionally fails - the processor doesn't
    # currently handle corrupted EXIF data properly
    assert result.metadata.get("exif_error") is not None, (
        "Corrupted EXIF should be flagged - known bug DOC-ING-004-BUG-001"
    )


@pytest.mark.requirement("DOC-ING-004")
@pytest.mark.xfail(reason="Known issue with GPS coordinate extraction from EXIF")
def test_gps_extraction_from_exif(processor, sample_jpeg):
    """Extract GPS coordinates from image EXIF data.

    This is an xfail test demonstrating a known limitation
    in the current metadata extraction implementation.
    """
    result = processor.extract_metadata(sample_jpeg)
    # GPS extraction not yet implemented
    assert "gps" in result.metadata
    assert result.metadata["gps"]["latitude"] is not None


# =============================================================================
# Async tests for concurrent upload validation
# =============================================================================


@pytest.mark.requirement("DOC-ING-001", "DOC-ING-002")
@pytest.mark.asyncio
async def test_concurrent_file_validation(processor):
    """Validate multiple files can be processed concurrently."""
    documents = [
        MockDocument(f"doc_{i}.pdf", b"content", "application/pdf", 1024)
        for i in range(5)
    ]

    async def validate_async(doc):
        # Simulate async processing
        await asyncio.sleep(0.01)
        return processor.validate_file_type(doc)

    results = await asyncio.gather(*[validate_async(doc) for doc in documents])

    assert all(r.success for r in results)
    assert len(results) == 5
