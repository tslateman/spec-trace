"""Integration tests for document pipeline.

Demonstrates:
- Multi-requirement tests (linking to multiple requirements)
- End-to-end workflow tests
- Cross-subsystem integration
"""

import asyncio

import pytest

from conftest import MockDocument

# =============================================================================
# End-to-End Pipeline Tests
# =============================================================================


@pytest.mark.requirement("DOC-001", "DOC-ING-001", "DOC-TRF-001", "DOC-STR-001")
def test_full_pipeline_pdf_document(processor, storage, sample_pdf):
    """Full pipeline processing for PDF document.

    Tests the complete flow: ingest -> transform -> store
    Linked to root requirement and all subsystem parents.
    """
    # Step 1: Validate file type (Ingest)
    validation = processor.validate_file_type(sample_pdf)
    assert validation.success is True, "PDF should pass validation"

    # Step 2: Extract metadata (Ingest)
    metadata = processor.extract_metadata(sample_pdf)
    assert metadata.success is True, "Metadata extraction should succeed"
    assert metadata.metadata["title"] == "Sample PDF"

    # Step 3: PDF conversion not needed (Transform)
    conversion = processor.convert_to_pdf(sample_pdf)
    assert conversion.success is True
    assert conversion.document_id == "pdf_already"

    # Step 4: Encrypt document (Storage)
    encryption = processor.encrypt_document(sample_pdf)
    assert encryption.success is True
    assert encryption.metadata["algorithm"] == "AES-256-GCM"

    # Step 5: Store document (Storage)
    stored = storage.store(encryption.document_id, sample_pdf.content)
    assert stored is True


@pytest.mark.requirement("DOC-001", "DOC-ING-001", "DOC-TRF-001", "DOC-TRF-002", "DOC-STR-001")
def test_full_pipeline_docx_document(processor, storage, sample_docx):
    """Full pipeline processing for DOCX document.

    Tests conversion from DOCX to PDF in addition to standard flow.
    """
    # Validate
    validation = processor.validate_file_type(sample_docx)
    assert validation.success is True

    # Extract metadata
    metadata = processor.extract_metadata(sample_docx)
    assert metadata.success is True

    # Convert to PDF
    conversion = processor.convert_to_pdf(sample_docx)
    assert conversion.success is True
    assert conversion.document_id == "pdf_converted"

    # Encrypt and store
    encryption = processor.encrypt_document(sample_docx)
    assert encryption.success is True

    stored = storage.store(encryption.document_id, sample_docx.content)
    assert stored is True


@pytest.mark.requirement("DOC-001", "DOC-ING-001", "DOC-TRF-001", "DOC-TRF-003", "DOC-STR-001")
def test_full_pipeline_image_document(processor, storage, sample_image):
    """Full pipeline processing for image document.

    Tests image optimization in addition to standard flow.
    """
    # Validate
    validation = processor.validate_file_type(sample_image)
    assert validation.success is True

    # Extract metadata
    metadata = processor.extract_metadata(sample_image)
    assert metadata.success is True
    assert metadata.metadata["width"] == 1920

    # Optimize for web
    optimization = processor.optimize_image(sample_image, 800)
    assert optimization.success is True
    assert optimization.metadata["format"] == "webp"

    # Convert to PDF
    conversion = processor.convert_to_pdf(sample_image)
    assert conversion.success is True

    # Encrypt and store
    encryption = processor.encrypt_document(sample_image)
    stored = storage.store(encryption.document_id, sample_image.content)
    assert stored is True


# =============================================================================
# Error Handling Integration Tests
# =============================================================================


@pytest.mark.requirement("DOC-001", "DOC-ING-002")
def test_pipeline_rejects_malicious_file(processor, malicious_exe):
    """Pipeline properly rejects malicious files at ingestion.

    Demonstrates security-focused integration testing.
    """
    validation = processor.validate_file_type(malicious_exe)
    assert validation.success is False
    assert ".exe" in validation.error or "not allowed" in validation.error


@pytest.mark.requirement("DOC-001", "DOC-ING-002")
def test_pipeline_rejects_oversized_file(processor, oversized_file):
    """Pipeline rejects files exceeding size limits."""
    validation = processor.validate_file_type(oversized_file)
    assert validation.success is False
    assert "100MB" in validation.error


# =============================================================================
# Batch Processing Tests
# =============================================================================


@pytest.mark.requirement("DOC-001", "DOC-ING-001", "DOC-TRF-001")
def test_batch_document_processing(processor, storage):
    """Process multiple documents in batch.

    Demonstrates bulk processing capability.
    """
    documents = [
        MockDocument("batch_1.pdf", b"pdf content", "application/pdf", 1024),
        MockDocument("batch_2.png", b"png content", "image/png", 2048),
        MockDocument(
            "batch_3.docx",
            b"docx content",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            3072,
        ),
    ]

    results = []
    for doc in documents:
        # Validate
        validation = processor.validate_file_type(doc)
        if not validation.success:
            results.append({"doc": doc.filename, "success": False, "stage": "validation"})
            continue

        # Transform (convert to PDF)
        conversion = processor.convert_to_pdf(doc)
        if not conversion.success:
            results.append({"doc": doc.filename, "success": False, "stage": "conversion"})
            continue

        # Store
        encryption = processor.encrypt_document(doc)
        stored = storage.store(encryption.document_id, doc.content)

        results.append({"doc": doc.filename, "success": stored, "stage": "complete"})

    # All documents should complete successfully
    assert all(r["success"] for r in results)
    assert all(r["stage"] == "complete" for r in results)


@pytest.mark.requirement("DOC-001")
@pytest.mark.asyncio
async def test_concurrent_pipeline_processing(processor, storage):
    """Process multiple documents concurrently.

    Demonstrates async pipeline processing capability.
    """

    async def process_document(doc: MockDocument) -> dict:
        """Process a single document through the pipeline."""
        await asyncio.sleep(0.01)  # Simulate async I/O

        validation = processor.validate_file_type(doc)
        if not validation.success:
            return {"doc": doc.filename, "success": False}

        processor.convert_to_pdf(doc)
        encryption = processor.encrypt_document(doc)
        storage.store(encryption.document_id, doc.content)

        return {"doc": doc.filename, "success": True}

    documents = [
        MockDocument(f"concurrent_{i}.pdf", b"content", "application/pdf", 1024) for i in range(10)
    ]

    results = await asyncio.gather(*[process_document(doc) for doc in documents])

    assert len(results) == 10
    assert all(r["success"] for r in results)


# =============================================================================
# Delivery Subsystem Tests
# =============================================================================


@pytest.mark.requirement("DOC-DEL-001")
def test_delivery_subsystem_basic(storage, sample_pdf):
    """Basic delivery test - document can be retrieved for delivery.

    Note: Full CDN integration (DOC-DEL-002) requires in-app validation.
    """
    document_id = "delivery_test_doc"
    storage.store(document_id, sample_pdf.content)

    # Simulate delivery by retrieving document
    content = storage.retrieve(document_id)
    assert content is not None
    assert content == sample_pdf.content
