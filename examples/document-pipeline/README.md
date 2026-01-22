# Document Processing Pipeline Example

This example demonstrates spec-trace's full capabilities using a realistic document processing pipeline scenario.

## Overview

The document processing pipeline handles user-uploaded documents through four stages:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Ingest    │ -> │  Transform  │ -> │   Storage   │ -> │  Delivery   │
│             │    │             │    │             │    │             │
│ • Validate  │    │ • PDF Conv. │    │ • Encrypt   │    │ • CDN       │
│ • Scan      │    │ • Optimize  │    │ • Replicate │    │ • Signed    │
│ • Extract   │    │ • OCR       │    │ • Tier      │    │   URLs      │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## Quick Start

```bash
# Run the demo script
python scripts/demo_pipeline.py

# Or step-by-step:
cd spectrace

# 1. Import specs
python manage.py parse_specs ../examples/document-pipeline/specs/ --clear

# 2. Import SLOs
python manage.py import_slos ../examples/document-pipeline/slos/

# 3. Run tests with JUnit output
pytest ../examples/document-pipeline/tests/ --junitxml=../test-results.xml -v

# 4. Import test results
python manage.py import_tests ../test-results.xml

# 5. View in dashboard
python manage.py runserver
# Visit http://localhost:8000/admin
```

## Directory Structure

```
document-pipeline/
├── README.md                    # This file
├── specs/
│   └── pipeline/
│       ├── DOC-001-overview.md  # Root requirement
│       ├── ingest/
│       │   ├── DOC-ING-001.md   # Ingestion subsystem
│       │   ├── DOC-ING-002.md   # File validation
│       │   ├── DOC-ING-003.md   # Virus scanning (inapp)
│       │   └── DOC-ING-004.md   # Metadata extraction
│       ├── transform/
│       │   ├── DOC-TRF-001.md   # Transform subsystem
│       │   ├── DOC-TRF-002.md   # PDF conversion
│       │   ├── DOC-TRF-003.md   # Image optimization
│       │   └── DOC-TRF-004.md   # OCR processing (skipped)
│       ├── storage/
│       │   ├── DOC-STR-001.md   # Storage subsystem
│       │   └── DOC-STR-002.md   # Encryption at rest
│       └── delivery/
│           ├── DOC-DEL-001.md   # Delivery subsystem
│           └── DOC-DEL-002.md   # CDN integration (inapp)
├── slos/
│   ├── api-availability.yaml    # 99.9% uptime SLO
│   └── processing-latency.yaml  # p99 < 5s latency SLO
├── tests/
│   ├── conftest.py              # Shared fixtures
│   ├── test_ingestion.py        # Ingest tests
│   ├── test_transform.py        # Transform tests
│   ├── test_storage.py          # Storage tests
│   └── test_integration.py      # Cross-cutting tests
└── ci/
    └── github-actions.yml       # Example CI workflow
```

## Requirements Hierarchy

```
DOC-001: Document Processing Pipeline (verification_method: both)
├── DOC-ING-001: Ingestion Subsystem
│   ├── DOC-ING-002: File Validation ............... test     ✓ passing
│   ├── DOC-ING-003: Virus Scanning ................ inapp    ? pending
│   └── DOC-ING-004: Metadata Extraction ........... test     ✗ failing
├── DOC-TRF-001: Transform Subsystem
│   ├── DOC-TRF-002: PDF Conversion ................ test     ✓ passing
│   ├── DOC-TRF-003: Image Optimization ............ test     ✓ passing
│   └── DOC-TRF-004: OCR Processing ................ test     - untested
├── DOC-STR-001: Storage Subsystem
│   └── DOC-STR-002: Encryption at Rest ............ test     ✓ passing
└── DOC-DEL-001: Delivery Subsystem
    └── DOC-DEL-002: CDN Integration ............... inapp    ? pending
```

## Feature Demonstrations

### 1. Nested Requirement Hierarchy

Requirements are organized in a three-level hierarchy using the `parent` field:

```yaml
# specs/pipeline/ingest/DOC-ING-002.md
---
id: DOC-ING-002
title: File Type Validation
parent: DOC-ING-001       # Links to parent requirement
verification_method: test
---
```

### 2. Verification Methods

Different requirements use different verification approaches:

| Method | Used For | Example |
|--------|----------|---------|
| `test` | Automated tests cover this requirement | DOC-ING-002 (File Validation) |
| `inapp` | Requires in-app validation or manual verification | DOC-ING-003 (Virus Scanning) |
| `both` | Must pass both tests AND in-app validation | DOC-001 (Root) |

### 3. Test Patterns

The test suite demonstrates various pytest patterns:

**Parametrized Tests** (`test_ingestion.py`):
```python
@pytest.mark.requirement("DOC-ING-002")
@pytest.mark.parametrize("extension,mime_type,expected", [
    (".pdf", "application/pdf", True),
    (".exe", "application/x-msdownload", False),
])
def test_file_type_validation(processor, extension, mime_type, expected):
    ...
```

**Class-Based Tests** (`test_transform.py`):
```python
@pytest.mark.requirement("DOC-TRF-002")
class TestPDFConversion:
    def test_docx_to_pdf_conversion(self, processor, sample_docx):
        ...
```

**xfail Tests** (`test_ingestion.py`):
```python
@pytest.mark.requirement("DOC-ING-004")
@pytest.mark.xfail(reason="Known issue with GPS coordinate extraction")
def test_gps_extraction_from_exif(processor, sample_jpeg):
    ...
```

**Async Tests** (`test_ingestion.py`):
```python
@pytest.mark.requirement("DOC-ING-001", "DOC-ING-002")
@pytest.mark.asyncio
async def test_concurrent_file_validation(processor):
    ...
```

**Multi-Requirement Tests** (`test_integration.py`):
```python
@pytest.mark.requirement("DOC-001", "DOC-ING-001", "DOC-TRF-001", "DOC-STR-001")
def test_full_pipeline_pdf_document(processor, storage, sample_pdf):
    ...
```

### 4. Test Status Variety

| Status | How Demonstrated |
|--------|------------------|
| Passing | Most tests (DOC-ING-002, DOC-TRF-002, etc.) |
| Failing | `test_corrupted_exif_data_handling` in DOC-ING-004 |
| Skipped | All OCR tests in DOC-TRF-004 |
| xfail | `test_gps_extraction_from_exif` in DOC-ING-004 |

### 5. SLO Integration

Two OpenSLO-format SLOs demonstrate operational requirements tracking:

**api-availability.yaml**:
```yaml
apiVersion: openslo/v1
kind: SLO
metadata:
  name: document-pipeline-availability
  labels:
    requirement: DOC-001
spec:
  objectives:
    - target: 0.999    # 99.9% availability
      timeWindow:
        duration: 30d
```

**processing-latency.yaml**:
```yaml
apiVersion: openslo/v1
kind: SLO
metadata:
  name: document-processing-latency
  labels:
    requirements: DOC-001, DOC-TRF-001
spec:
  objectives:
    - target: 0.99    # 99% of requests under target
      timeWindow:
        duration: 7d
```

### 6. CI/CD Integration

The `ci/github-actions.yml` file shows how to integrate spec-trace:

1. **Test Job**: Runs pytest with JUnit XML output
2. **Traceability Job**: Imports specs, SLOs, and test results
3. **Quality Gate Job**: Checks for failing/untested requirements

## Expected Test Results

When you run the tests, expect:

```
tests/test_ingestion.py
  ✓ test_ingestion_subsystem_initialized
  ✓ test_file_type_validation[pdf-allowed]
  ✓ test_file_type_validation[docx-allowed]
  ... (all file types pass)
  ✓ test_zero_byte_file_rejected
  ✓ test_oversized_file_rejected
  ✓ test_mime_type_mismatch_rejected
  ✓ test_pdf_metadata_extraction
  ✓ test_image_metadata_extraction
  ✗ test_corrupted_exif_data_handling          # Intentional failure
  x test_gps_extraction_from_exif              # xfail (expected failure)
  ✓ test_concurrent_file_validation

tests/test_transform.py
  ✓ TestPDFConversion::test_docx_to_pdf_conversion
  ... (all PDF tests pass)
  ✓ test_image_optimization_variants[thumbnail-150px]
  ... (all optimization tests pass)
  s test_scanned_pdf_ocr                       # Skipped
  s test_ocr_language_detection                # Skipped
  s test_ocr_confidence_scores                 # Skipped
  s test_rotated_document_handling             # Skipped

tests/test_storage.py
  ✓ All tests pass

tests/test_integration.py
  ✓ All tests pass
```

## Using This as a Template

To use this example as a template for your own project:

1. **Copy the structure**:
   ```bash
   cp -r examples/document-pipeline my-project/requirements/
   ```

2. **Modify specs** for your domain:
   - Update requirement IDs (e.g., `MYPROJ-XXX`)
   - Define your own hierarchy
   - Set appropriate `verification_method` for each

3. **Create tests** that link to your requirements:
   ```python
   @pytest.mark.requirement("MYPROJ-001")
   def test_my_feature():
       ...
   ```

4. **Define SLOs** for operational requirements:
   - Create OpenSLO YAML files
   - Link to requirements via `metadata.labels.requirement`

5. **Integrate with CI/CD**:
   - Adapt `ci/github-actions.yml` for your pipeline
   - Configure quality gates based on your standards
