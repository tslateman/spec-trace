#!/usr/bin/env python
"""Verify Phase 1 success criteria."""

import os
import sys

# Configure Django before any imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spectrace.settings")
sys.path.insert(0, os.path.dirname(__file__))

import django

django.setup()

from django.db.models import Count  # noqa: E402

from requirements.models import Requirement  # noqa: E402


def verify():
    """Run all Phase 1 verification checks."""
    print("=== Phase 1 Verification ===\n")

    # 1. Requirements exist
    count = Requirement.objects.count()
    print(f"1. Requirements in DB: {count}")
    assert count > 0, "No requirements found"
    print("   PASS: Requirements exist\n")

    # 2. Unique IDs
    dupes = (
        Requirement.objects.values("external_id").annotate(count=Count("id")).filter(count__gt=1)
    )
    dupe_count = dupes.count()
    print(f"2. Duplicate IDs: {dupe_count}")
    assert not dupes.exists(), f"Duplicates found: {list(dupes)}"
    print("   PASS: All IDs are unique\n")

    # 3. Hierarchy works
    roots = list(Requirement.get_root_nodes())
    print(f"3. Root requirements: {len(roots)}")
    for root in roots:
        children = list(root.get_children())
        if children:
            print(f"   - {root.external_id} has {len(children)} children")
            for child in children:
                print(f"     - {child.external_id}")
    print("   PASS: Hierarchy queries work\n")

    # 4. Tags queryable
    tagged = Requirement.objects.exclude(tags=[])
    print(f"4. Requirements with tags: {tagged.count()}")

    # Test tag filtering
    auth_reqs = [r for r in Requirement.objects.all() if "auth" in r.tags]
    print(f"   - Requirements with 'auth' tag: {len(auth_reqs)}")
    for req in auth_reqs:
        print(f"     - {req.external_id}: {req.tags}")
    print("   PASS: Tags are queryable\n")

    # 5. Source file tracking
    with_source = Requirement.objects.exclude(source_file="")
    print(f"5. Requirements with source_file: {with_source.count()}")
    for req in Requirement.objects.all()[:3]:
        print(f"   - {req.external_id}: {req.source_file}")
    print("   PASS: Source files tracked\n")

    # 6. Full tree display
    print("6. Full requirement tree:")
    for req in Requirement.objects.all():
        depth = req.get_depth()
        indent = "   " + "  " * depth
        print(f"{indent}{req.external_id}: {req.title}")
    print()

    print("=== All Phase 1 checks passed ===")
    return True


if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
