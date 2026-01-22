"""Tests for document storage subsystem.

Demonstrates:
- Storage backend tests (DOC-STR-001)
- Encryption tests (DOC-STR-002)
- Fixture usage for storage backend
"""

import pytest
from conftest import MockDocument, MockDocumentProcessor, MockStorageBackend


# =============================================================================
# DOC-STR-001: Storage Subsystem
# =============================================================================


@pytest.mark.requirement("DOC-STR-001")
def test_storage_subsystem_initialized(storage):
    """Verify storage subsystem is properly configured."""
    assert storage is not None
    assert hasattr(storage, "store")
    assert hasattr(storage, "retrieve")
    assert hasattr(storage, "delete")


@pytest.mark.requirement("DOC-STR-001")
def test_document_storage_roundtrip(storage, sample_pdf):
    """Documents can be stored and retrieved."""
    document_id = "doc_roundtrip_test"
    content = sample_pdf.content

    # Store document
    stored = storage.store(document_id, content)
    assert stored is True

    # Retrieve document
    retrieved = storage.retrieve(document_id)
    assert retrieved == content


@pytest.mark.requirement("DOC-STR-001")
def test_document_deletion(storage, sample_pdf):
    """Documents can be deleted from storage."""
    document_id = "doc_deletion_test"

    # Store then delete
    storage.store(document_id, sample_pdf.content)
    deleted = storage.delete(document_id)
    assert deleted is True

    # Verify deleted
    retrieved = storage.retrieve(document_id)
    assert retrieved is None


@pytest.mark.requirement("DOC-STR-001")
def test_retrieve_nonexistent_document(storage):
    """Retrieving non-existent document returns None."""
    retrieved = storage.retrieve("nonexistent_doc_id")
    assert retrieved is None


@pytest.mark.requirement("DOC-STR-001")
def test_delete_nonexistent_document(storage):
    """Deleting non-existent document returns False."""
    deleted = storage.delete("nonexistent_doc_id")
    assert deleted is False


# =============================================================================
# DOC-STR-002: Encryption at Rest
# =============================================================================


@pytest.mark.requirement("DOC-STR-002")
def test_document_encryption(processor, sample_pdf):
    """Documents are encrypted before storage."""
    result = processor.encrypt_document(sample_pdf)
    assert result.success is True
    assert result.metadata["algorithm"] == "AES-256-GCM"


@pytest.mark.requirement("DOC-STR-002")
def test_encryption_key_assigned(processor, sample_pdf):
    """Encrypted documents have key IDs assigned."""
    result = processor.encrypt_document(sample_pdf)
    assert result.success is True
    assert "key_id" in result.metadata
    assert result.metadata["key_id"].startswith("key_")


@pytest.mark.requirement("DOC-STR-002")
def test_encryption_different_document_types(processor, sample_pdf, sample_image, sample_docx):
    """All document types can be encrypted."""
    for doc in [sample_pdf, sample_image, sample_docx]:
        result = processor.encrypt_document(doc)
        assert result.success is True
        assert result.metadata["algorithm"] == "AES-256-GCM"


@pytest.mark.requirement("DOC-STR-001", "DOC-STR-002")
def test_encrypted_storage_workflow(processor, storage, sample_pdf):
    """Full workflow: encrypt then store document.

    This test links to multiple requirements to demonstrate
    cross-cutting functionality.
    """
    # Encrypt document
    encrypt_result = processor.encrypt_document(sample_pdf)
    assert encrypt_result.success is True

    # Store encrypted content (simulated)
    document_id = encrypt_result.document_id
    stored = storage.store(document_id, sample_pdf.content)
    assert stored is True

    # Verify retrieval
    retrieved = storage.retrieve(document_id)
    assert retrieved is not None
