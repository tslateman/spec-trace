"""Shared fixtures for document pipeline tests.

This conftest.py demonstrates pytest fixtures that might be used
in a real document processing pipeline test suite.
"""

import pytest
from pathlib import Path
from dataclasses import dataclass


@dataclass
class MockDocument:
    """Represents a document for testing."""

    filename: str
    content: bytes
    mime_type: str
    size: int

    @property
    def extension(self) -> str:
        return Path(self.filename).suffix.lower()


@dataclass
class ProcessingResult:
    """Result of document processing."""

    success: bool
    document_id: str | None = None
    error: str | None = None
    metadata: dict | None = None


class MockDocumentProcessor:
    """Mock document processor for testing."""

    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tiff"}
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image/png",
        "image/jpeg",
        "image/tiff",
    }
    MAX_SIZE = 100 * 1024 * 1024  # 100MB

    def validate_file_type(self, doc: MockDocument) -> ProcessingResult:
        """Validate document file type."""
        if doc.size == 0:
            return ProcessingResult(success=False, error="Zero-byte file rejected")

        if doc.size > self.MAX_SIZE:
            return ProcessingResult(success=False, error="File exceeds 100MB limit")

        if doc.extension not in self.ALLOWED_EXTENSIONS:
            return ProcessingResult(
                success=False, error=f"File type {doc.extension} not allowed"
            )

        if doc.mime_type not in self.ALLOWED_MIME_TYPES:
            return ProcessingResult(
                success=False, error=f"MIME type {doc.mime_type} not allowed"
            )

        return ProcessingResult(success=True, document_id="doc_123")

    def extract_metadata(self, doc: MockDocument) -> ProcessingResult:
        """Extract metadata from document."""
        metadata = {
            "filename": doc.filename,
            "size": doc.size,
            "mime_type": doc.mime_type,
        }

        # Simulate metadata extraction based on file type
        if doc.extension == ".pdf":
            metadata.update({"title": "Sample PDF", "author": "Test Author", "pages": 1})
        elif doc.extension in {".png", ".jpg", ".jpeg", ".tiff"}:
            metadata.update({"width": 1920, "height": 1080, "format": doc.extension[1:]})

        return ProcessingResult(success=True, metadata=metadata)

    def convert_to_pdf(self, doc: MockDocument) -> ProcessingResult:
        """Convert document to PDF format."""
        if doc.extension == ".pdf":
            return ProcessingResult(success=True, document_id="pdf_already")

        if doc.extension in self.ALLOWED_EXTENSIONS:
            return ProcessingResult(success=True, document_id="pdf_converted")

        return ProcessingResult(success=False, error="Cannot convert file type")

    def optimize_image(self, doc: MockDocument, target_width: int) -> ProcessingResult:
        """Optimize image for web delivery."""
        if doc.extension not in {".png", ".jpg", ".jpeg", ".tiff"}:
            return ProcessingResult(success=False, error="Not an image file")

        return ProcessingResult(
            success=True,
            document_id=f"optimized_{target_width}",
            metadata={"width": target_width, "format": "webp"},
        )

    def encrypt_document(self, doc: MockDocument) -> ProcessingResult:
        """Encrypt document for storage."""
        return ProcessingResult(
            success=True,
            document_id="encrypted_doc",
            metadata={"algorithm": "AES-256-GCM", "key_id": "key_abc123"},
        )


class MockStorageBackend:
    """Mock storage backend for testing."""

    def __init__(self):
        self._storage: dict[str, bytes] = {}

    def store(self, document_id: str, content: bytes) -> bool:
        """Store document content."""
        self._storage[document_id] = content
        return True

    def retrieve(self, document_id: str) -> bytes | None:
        """Retrieve document content."""
        return self._storage.get(document_id)

    def delete(self, document_id: str) -> bool:
        """Delete document."""
        if document_id in self._storage:
            del self._storage[document_id]
            return True
        return False


@pytest.fixture
def processor() -> MockDocumentProcessor:
    """Provide a mock document processor."""
    return MockDocumentProcessor()


@pytest.fixture
def storage() -> MockStorageBackend:
    """Provide a mock storage backend."""
    return MockStorageBackend()


@pytest.fixture
def sample_pdf() -> MockDocument:
    """Provide a sample PDF document."""
    return MockDocument(
        filename="sample.pdf",
        content=b"%PDF-1.4 sample content",
        mime_type="application/pdf",
        size=1024,
    )


@pytest.fixture
def sample_docx() -> MockDocument:
    """Provide a sample DOCX document."""
    return MockDocument(
        filename="sample.docx",
        content=b"PK\x03\x04 docx content",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size=2048,
    )


@pytest.fixture
def sample_image() -> MockDocument:
    """Provide a sample PNG image."""
    return MockDocument(
        filename="sample.png",
        content=b"\x89PNG\r\n\x1a\n image content",
        mime_type="image/png",
        size=4096,
    )


@pytest.fixture
def sample_jpeg() -> MockDocument:
    """Provide a sample JPEG image."""
    return MockDocument(
        filename="photo.jpg",
        content=b"\xff\xd8\xff\xe0 jpeg content",
        mime_type="image/jpeg",
        size=8192,
    )


@pytest.fixture
def malicious_exe() -> MockDocument:
    """Provide a malicious executable (should be rejected)."""
    return MockDocument(
        filename="malware.exe",
        content=b"MZ executable content",
        mime_type="application/x-msdownload",
        size=1024,
    )


@pytest.fixture
def zero_byte_file() -> MockDocument:
    """Provide a zero-byte file (should be rejected)."""
    return MockDocument(
        filename="empty.pdf",
        content=b"",
        mime_type="application/pdf",
        size=0,
    )


@pytest.fixture
def oversized_file() -> MockDocument:
    """Provide an oversized file (should be rejected)."""
    return MockDocument(
        filename="huge.pdf",
        content=b"x" * 1000,  # Content is symbolic, size field matters
        mime_type="application/pdf",
        size=150 * 1024 * 1024,  # 150MB
    )
