"""
Management command to analyze impact of spec changes on tests.
"""

import json
import sys

from django.core.management.base import BaseCommand, CommandError

from ...services.impact_analyzer import ImpactAnalyzer
from requirements.models import Requirement


class Command(BaseCommand):
    help = "Analyze impact of spec changes on tests between two git refs"

    def add_arguments(self, parser):
        parser.add_argument(
            "base_ref",
            type=str,
            help="Base git ref (commit, branch, tag)",
        )
        parser.add_argument(
            "head_ref",
            type=str,
            help="Head git ref to compare against base",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json", "md"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--include-hierarchy",
            action="store_true",
            default=True,
            help="Include tests from child requirements (default: true)",
        )
        parser.add_argument(
            "--no-hierarchy",
            action="store_true",
            help="Do not include tests from child requirements",
        )
        parser.add_argument(
            "--spec-dir",
            type=str,
            default="specs",
            help="Directory containing spec files (default: specs)",
        )

    def handle(self, *args, **options):
        base_ref = options["base_ref"]
        head_ref = options["head_ref"]
        output_format = options["format"]
        include_hierarchy = not options["no_hierarchy"]
        spec_dir = options["spec_dir"]

        analyzer = ImpactAnalyzer(spec_dir=spec_dir)

        try:
            result = analyzer.analyze(base_ref, head_ref, include_hierarchy=include_hierarchy)
        except ValueError as e:
            raise CommandError(str(e))

        if output_format == "json":
            self._output_json(result)
        elif output_format == "md":
            self._output_md(result, base_ref, head_ref)
        else:
            self._output_text(result, base_ref, head_ref)

        # Exit code 1 if tests are affected (for CI gates)
        if result.affected_tests:
            sys.exit(1)

    def _output_json(self, result):
        """Output structured JSON."""
        output = {
            "changed_requirements": result.changed_requirements,
            "affected_tests": result.affected_tests,
            "hierarchy_expansion": result.hierarchy_expansion,
            "dependency_expansion": result.dependency_expansion,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "summary": {
                "requirements_changed": len(result.changed_requirements),
                "tests_affected": len(result.affected_tests),
                "has_impact": len(result.affected_tests) > 0,
            },
        }
        self.stdout.write(json.dumps(output, indent=2))


    def _get_titles(self, req_ids):
        """Helper to fetch requirement titles."""
        reqs = Requirement.objects.filter(external_id__in=req_ids).values_list("external_id", "title")
        return {r[0]: r[1] for r in reqs}

    def _output_md(self, result, base_ref, head_ref):
        """Output Markdown for PR comments."""
        lines = []
        lines.append(f"## 🔍 SpecTrace Impact Analysis")
        lines.append(f"**Comparing:** `{base_ref}` → `{head_ref}`")
        lines.append("")
        
        if not result.changed_requirements:
            lines.append("✅ **No spec files changed.**")
            self.stdout.write("\n".join(lines) + "\n")
            return
            
        all_ids = set(result.changed_requirements)
        for child_ids in result.hierarchy_expansion.values():
            all_ids.update(child_ids)
        for dep_ids in result.dependency_expansion.values():
            all_ids.update(dep_ids)
            
        titles = self._get_titles(all_ids)
        
        lines.append(f"### 📝 Changed Requirements ({len(result.changed_requirements)})")
        for req_id in result.changed_requirements:
            title = titles.get(req_id, 'Unknown Title')
            lines.append(f"- **{req_id}**: {title}")
            
        if result.hierarchy_expansion:
            lines.append("")
            lines.append("### 🌳 Hierarchy Expansion")
            for parent_id, child_ids in result.hierarchy_expansion.items():
                lines.append(f"- **{parent_id}** children:")
                for cid in child_ids:
                    title = titles.get(cid, 'Unknown Title')
                    lines.append(f"  - {cid}: {title}")
                    
        if result.dependency_expansion:
            lines.append("")
            lines.append("### 🔗 Dependency Expansion")
            for req_id, dependent_ids in result.dependency_expansion.items():
                lines.append(f"- **{req_id}** is depended on by:")
                for did in dependent_ids:
                    title = titles.get(did, 'Unknown Title')
                    lines.append(f"  - {did}: {title}")
                    
        risk_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴"
        }.get(result.risk_level, "⚪")
        
        lines.append("")
        lines.append(f"### 🚦 Risk Assessment")
        lines.append(f"**Level:** {risk_emoji} {result.risk_level.upper()} *(Score: {result.risk_score:.2f})*")
        
        lines.append("")
        if result.affected_tests:
            lines.append(f"### 🧪 Affected Tests ({len(result.affected_tests)})")
            lines.append("The following tests should be executed to verify these changes:")
            lines.append("```bash")
            for test in sorted(result.affected_tests):
                lines.append(f"pytest {test}")
            lines.append("```")
        else:
            lines.append("✅ **No tests affected by these changes.**")
            
        self.stdout.write("\n".join(lines) + "\n")

    def _output_text(self, result, base_ref, head_ref):
        """Output human-readable text."""
        self.stdout.write(self.style.SUCCESS(f"🔍 Impact Analysis: {base_ref} → {head_ref}\n"))
        self.stdout.write("=" * 50 + "\n")

        if not result.changed_requirements:
            self.stdout.write(self.style.SUCCESS("\n✓ No spec files changed.\n"))
            return

        all_ids = set(result.changed_requirements)
        for child_ids in result.hierarchy_expansion.values():
            all_ids.update(child_ids)
        for dep_ids in result.dependency_expansion.values():
            all_ids.update(dep_ids)
            
        titles = self._get_titles(all_ids)

        # Changed requirements
        self.stdout.write(self.style.SUCCESS(f"\n📝 Changed Requirements ({len(result.changed_requirements)}):\n"))
        for req_id in result.changed_requirements:
            title = titles.get(req_id, 'Unknown Title')
            self.stdout.write(f"  • {self.style.SUCCESS(req_id)}: {title}\n")

        # Hierarchy expansion
        if result.hierarchy_expansion:
            self.stdout.write(self.style.SUCCESS("\n🌳 Hierarchy Expansion:\n"))
            for parent_id, child_ids in result.hierarchy_expansion.items():
                self.stdout.write(f"  {parent_id} children:\n")
                for cid in child_ids:
                    title = titles.get(cid, 'Unknown Title')
                    self.stdout.write(f"    ↳ {cid}: {title}\n")

        # Dependency expansion
        if result.dependency_expansion:
            self.stdout.write(self.style.SUCCESS("\n🔗 Dependency Expansion:\n"))
            for req_id, dependent_ids in result.dependency_expansion.items():
                self.stdout.write(f"  {req_id} is depended on by:\n")
                for did in dependent_ids:
                    title = titles.get(did, 'Unknown Title')
                    self.stdout.write(f"    ↳ {did}: {title}\n")

        # Risk assessment
        risk_styles = {
            "low": self.style.SUCCESS,
            "medium": self.style.WARNING,
            "high": self.style.WARNING,
            "critical": self.style.ERROR,
        }
        style_fn = risk_styles.get(result.risk_level, self.style.WARNING)
        self.stdout.write(
            style_fn(f"\n🚦 Risk: {result.risk_level.upper()} ({result.risk_score:.2f})\n")
        )

        # Affected tests
        if result.affected_tests:
            self.stdout.write(
                self.style.WARNING(f"\n🧪 Affected Tests ({len(result.affected_tests)}):\n")
            )
            for test in sorted(result.affected_tests):
                self.stdout.write(f"  ✗ {test}\n")
            self.stdout.write(
                self.style.WARNING("\nThese tests should be run to verify the changes.\n")
            )
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ No tests affected by these changes.\n"))
