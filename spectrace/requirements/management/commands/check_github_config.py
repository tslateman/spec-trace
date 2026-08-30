"""Management command to verify GitHub webhook configuration."""

import json
import sys

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import get_resolver


class Command(BaseCommand):
    """Verify GitHub App and webhook configuration."""

    help = "Check GitHub webhook integration configuration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--test-jwt",
            action="store_true",
            help="Test JWT generation (requires valid private key)",
        )

    def handle(self, *args, **options):
        output_format = options["format"]
        test_jwt = options["test_jwt"]

        checks = {
            "dependencies": self._check_dependencies(),
            "settings": self._check_settings(),
            "private_key_format": self._check_private_key_format(),
            "url_registered": self._check_url_registered(),
        }

        if test_jwt:
            checks["jwt_generation"] = self._check_jwt_generation()

        if output_format == "json":
            self._output_json(checks)
        else:
            self._output_text(checks)

        # Exit with error if any check failed
        if not all(c["ok"] for c in checks.values()):
            sys.exit(1)

    def _check_dependencies(self):
        """Check if PyJWT and cryptography are installed."""
        missing = []

        try:
            import jwt  # noqa: F401
        except ImportError:
            missing.append("PyJWT")

        try:
            import cryptography  # noqa: F401
        except ImportError:
            missing.append("cryptography")

        if missing:
            return {
                "ok": False,
                "message": f"Missing: {', '.join(missing)}",
                "hint": "Install with: pip install spectrace[github]",
            }

        return {
            "ok": True,
            "message": "PyJWT and cryptography installed",
        }

    def _check_settings(self):
        """Check if required settings are configured."""
        missing = []

        if not getattr(settings, "GITHUB_APP_ID", ""):
            missing.append("GITHUB_APP_ID")

        if not getattr(settings, "GITHUB_PRIVATE_KEY", ""):
            missing.append("GITHUB_PRIVATE_KEY")

        if not getattr(settings, "GITHUB_WEBHOOK_SECRET", ""):
            missing.append("GITHUB_WEBHOOK_SECRET")

        if missing:
            return {
                "ok": False,
                "message": f"Missing: {', '.join(missing)}",
                "hint": "Set environment variables or Django settings",
            }

        return {
            "ok": True,
            "message": "GITHUB_APP_ID, GITHUB_PRIVATE_KEY, GITHUB_WEBHOOK_SECRET set",
        }

    def _check_private_key_format(self):
        """Check if private key appears to be valid PEM format."""
        private_key = getattr(settings, "GITHUB_PRIVATE_KEY", "")

        if not private_key:
            return {
                "ok": False,
                "message": "No private key configured",
            }

        # Handle escaped newlines
        key = private_key.replace("\\n", "\n")

        if not key.startswith("-----BEGIN"):
            return {
                "ok": False,
                "message": "Private key does not start with PEM header",
                "hint": "Key should start with '-----BEGIN RSA PRIVATE KEY-----'",
            }

        if "-----END" not in key:
            return {
                "ok": False,
                "message": "Private key missing PEM footer",
                "hint": "Key should end with '-----END RSA PRIVATE KEY-----'",
            }

        return {
            "ok": True,
            "message": "Valid PEM format",
        }

    def _check_url_registered(self):
        """Check if webhook URL is registered."""
        try:
            resolver = get_resolver()
            patterns = resolver.url_patterns

            # Recursively search for the webhook URL
            def find_pattern(patterns, name):
                for pattern in patterns:
                    if hasattr(pattern, "name") and pattern.name == name:
                        return pattern
                    if hasattr(pattern, "url_patterns"):
                        found = find_pattern(pattern.url_patterns, name)
                        if found:
                            return found
                return None

            webhook_pattern = find_pattern(patterns, "api-v1-integrations-webhooks-github")

            if webhook_pattern:
                return {
                    "ok": True,
                    "message": "/api/v1/integrations/webhooks/github/",
                }
            else:
                return {
                    "ok": False,
                    "message": "Webhook URL not registered",
                    "hint": "Check dependencies and GITHUB_WEBHOOK_SECRET setting",
                }
        except Exception as e:
            return {
                "ok": False,
                "message": f"Error checking URLs: {e}",
            }

    def _check_jwt_generation(self):
        """Test JWT generation with configured credentials."""
        try:
            from requirements.services.github_app import GitHubClient

            client = GitHubClient()
            jwt_token = client._generate_jwt()

            # Basic validation - JWT should have 3 parts
            parts = jwt_token.split(".")
            if len(parts) != 3:
                return {
                    "ok": False,
                    "message": "Generated JWT has invalid format",
                }

            return {
                "ok": True,
                "message": "JWT generation successful",
            }

        except ImportError as e:
            return {
                "ok": False,
                "message": str(e),
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"JWT generation failed: {e}",
            }

    def _output_text(self, checks):
        """Output results in human-readable format."""
        self.stdout.write("")
        self.stdout.write("GitHub Webhook Configuration")
        self.stdout.write("=" * 28)

        all_passed = True
        for name, result in checks.items():
            if result["ok"]:
                symbol = self.style.SUCCESS("✓")
            else:
                symbol = self.style.ERROR("✗")
                all_passed = False

            self.stdout.write(f"{symbol} {name}: {result['message']}")

            if not result["ok"] and "hint" in result:
                self.stdout.write(f"  └─ {result['hint']}")

        self.stdout.write("")
        if all_passed:
            self.stdout.write(self.style.SUCCESS("All checks passed!"))
        else:
            self.stdout.write(self.style.ERROR("Some checks failed."))

    def _output_json(self, checks):
        """Output results in JSON format for CI pipelines."""
        output = {
            "checks": checks,
            "all_passed": all(c["ok"] for c in checks.values()),
        }
        self.stdout.write(json.dumps(output, indent=2))
