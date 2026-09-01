"""Publish the status strings the database already stores.

`Requirement.status` and `TestRequirementLink.last_status` listed their legal
values in help text alone, so `generate_contract` had nothing to publish and a
consumer reading the database — Praxis queries `WHERE r.status != 'draft'` —
coupled to a value SpecTrace declared nowhere. Attaching choices names those
values in the contract snapshot, where a rename shows up as a diff.

The stored strings stay exactly as they are. Every live row already holds a
declared value, so this migration rewrites no data.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("requirements", "0018_requirement_project"),
    ]

    operations = [
        migrations.AlterField(
            model_name="requirement",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("active", "Active"),
                    ("deprecated", "Deprecated"),
                ],
                default="draft",
                help_text="Requirement status (draft, active, deprecated)",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="testrequirementlink",
            name="last_status",
            field=models.CharField(
                choices=[
                    ("passed", "Passed"),
                    ("failed", "Failed"),
                    ("error", "Error"),
                    ("skipped", "Skipped"),
                    ("unknown", "Unknown"),
                ],
                default="unknown",
                help_text="Status from last test run (passed, failed, error, skipped, unknown)",
                max_length=20,
            ),
        ),
    ]
