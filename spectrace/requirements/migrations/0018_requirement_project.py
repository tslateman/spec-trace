"""Give every requirement the project that owns it.

Requirements already stored belong to the project this installation was set up
to trace, so they adopt `settings.SPECTRACE_PROJECT` — the same name a re-parse
would give them. No re-parse is needed to keep an existing database working.

The check constraint is the guard the incident wanted: a requirement with no
project cannot be written at all, so no import can drop rows into a shared
namespace and have coverage count them as this project's own.
"""

from django.db import migrations, models

import requirements.projects


class Migration(migrations.Migration):
    dependencies = [
        ("requirements", "0017_corpus_enforcement_posture"),
    ]

    operations = [
        migrations.AddField(
            model_name="requirement",
            name="project",
            field=models.CharField(
                db_index=True,
                default=requirements.projects.default_project,
                help_text="Project that owns this requirement (e.g., spectrace)",
                max_length=100,
            ),
        ),
        migrations.AddConstraint(
            model_name="requirement",
            constraint=models.CheckConstraint(
                condition=models.Q(("project", ""), _negated=True),
                name="requirement_project_is_named",
            ),
        ),
    ]
