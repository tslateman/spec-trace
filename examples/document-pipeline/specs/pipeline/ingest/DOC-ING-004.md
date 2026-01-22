---
id: DOC-ING-004
title: Metadata Extraction
tags: [pipeline, ingest, metadata]
priority: medium
status: active
parent: DOC-ING-001
verification_method: test
---

Document metadata is extracted during ingestion for indexing and search.

## Overview

This requirement has a known failing test for edge cases with corrupted EXIF data.

## Acceptance Criteria

- Extracts document title, author, and creation date when available
- Extracts image EXIF data (dimensions, camera, GPS if present)
- Handles missing or corrupted metadata gracefully
- Stores extracted metadata in searchable index
- Supports custom metadata fields defined by organization
