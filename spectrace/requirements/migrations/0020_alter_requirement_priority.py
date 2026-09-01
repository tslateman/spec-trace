"""Publish the priority strings the database already stores.

`Requirement.priority` named its levels in help text alone, so
`generate_contract` had nothing to publish and a consumer reading the database
coupled to values SpecTrace declared nowhere. Attaching choices names those
values in the contract snapshot, where a rename shows up as a diff.

The declared set covers every value the code produces: the spec parser stores
whatever frontmatter carries (`critical` through `low` in the shipped example
corpus) and the Linear importer maps issue priority 1 to `urgent`. The field
stays blank-able, so an unset priority keeps storing the empty string.

The stored strings stay exactly as they are. Every live row already holds a
declared value, so this migration rewrites no data.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("requirements", "0019_alter_requirement_status_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="requirement",
            name="priority",
            field=models.CharField(
                blank=True,
                choices=[
                    ("urgent", "Urgent"),
                    ("critical", "Critical"),
                    ("high", "High"),
                    ("medium", "Medium"),
                    ("low", "Low"),
                ],
                help_text="Priority level (urgent, critical, high, medium, low)",
                max_length=20,
            ),
        ),
    ]
