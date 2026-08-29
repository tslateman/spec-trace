"""Add the per-standard enforcement posture and rehash the versions that predate it.

Enforcement joins the content hash, so every version stored before this migration
has a hash computed over a payload that lacked the key. Every one of them was
advisory — the concept did not exist — so recomputing with `enforcement:
advisory` reproduces exactly what those versions always meant, and re-parsing the
same corpus file reports the version unchanged instead of conflicting.
"""

from django.db import migrations, models

from requirements.services.corpus_parser import compute_content_hash, version_payload


def rehash_versions_with_enforcement(apps, schema_editor):
    CorpusEntryVersion = apps.get_model("requirements", "CorpusEntryVersion")
    for version in CorpusEntryVersion.objects.select_related("entry"):
        version.content_hash = compute_content_hash(
            version_payload(
                kind=version.entry.kind,
                title=version.entry.title,
                body=version.body,
                applies_to=version.applies_to,
                checks=version.checks,
                enforcement=version.enforcement,
                effective=version.effective_date,
            )
        )
        version.save(update_fields=["content_hash"])


def rehash_versions_without_enforcement(apps, schema_editor):
    CorpusEntryVersion = apps.get_model("requirements", "CorpusEntryVersion")
    for version in CorpusEntryVersion.objects.select_related("entry"):
        version.content_hash = compute_content_hash(
            {
                "kind": version.entry.kind,
                "title": version.entry.title,
                "body": version.body,
                "applies_to": version.applies_to,
                "checks": version.checks,
                "effective": version.effective_date,
            }
        )
        version.save(update_fields=["content_hash"])


class Migration(migrations.Migration):
    dependencies = [
        ("requirements", "0016_corpusentry_corpusentryversion_corpussnapshot_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="corpusentryversion",
            name="enforcement",
            field=models.CharField(
                choices=[("advisory", "Advisory"), ("blocking", "Blocking")],
                db_index=True,
                default="advisory",
                help_text="Posture the owner set for this version (advisory, blocking)",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="reviewcoverage",
            name="enforcement",
            field=models.CharField(
                choices=[("advisory", "Advisory"), ("blocking", "Blocking")],
                db_index=True,
                default="advisory",
                help_text="Posture the entry version carried when this review ran",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="reviewfinding",
            name="enforcement",
            field=models.CharField(
                choices=[("advisory", "Advisory"), ("blocking", "Blocking")],
                db_index=True,
                default="advisory",
                help_text="Posture the entry version carried when this review ran",
                max_length=20,
            ),
        ),
        migrations.RunPython(
            rehash_versions_with_enforcement, rehash_versions_without_enforcement, elidable=False
        ),
    ]
