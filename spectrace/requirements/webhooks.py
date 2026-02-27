"""GitHub webhook endpoints for CI/CD integration."""

import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from .models import WebhookEvent, WebhookEventStatus
from .services.github_app import (
    get_installation_id_from_payload,
    parse_workflow_run_event,
    verify_webhook_signature,
)

logger = logging.getLogger(__name__)

# Rate limit for webhooks (generous, as they come from GitHub)
RATE_LIMIT_WEBHOOK = "300/m"


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key="ip", rate=RATE_LIMIT_WEBHOOK, block=True)
def github_webhook(request):
    """Receive GitHub webhook events.

    Handles workflow_run.completed events to trigger test result imports.

    Security:
    - HMAC-SHA256 signature verification via X-Hub-Signature-256 header
    - Timestamp validation to prevent replay attacks
    - Repository allowlist support

    Returns:
        200: Event processed or acknowledged
        400: Invalid request
        401: Signature verification failed
        403: Repository not allowed
    """
    # Get headers
    signature = request.headers.get("X-Hub-Signature-256", "")
    event_type = request.headers.get("X-GitHub-Event", "")
    delivery_id = request.headers.get("X-GitHub-Delivery", "")

    if not delivery_id:
        return JsonResponse({"error": "Missing X-GitHub-Delivery header"}, status=400)

    if not event_type:
        return JsonResponse({"error": "Missing X-GitHub-Event header"}, status=400)

    # Verify signature
    if not verify_webhook_signature(request.body, signature):
        logger.warning("Webhook signature verification failed for delivery %s", delivery_id)
        return JsonResponse({"error": "Invalid signature"}, status=401)

    # Parse payload
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError as e:
        logger.warning("Invalid JSON in webhook payload: %s", e)
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    # Extract basic info for audit log
    repository = payload.get("repository", {}).get("full_name", "unknown")
    action = payload.get("action", "")
    sender = payload.get("sender", {}).get("login", "")

    # Check repository allowlist
    allowed_repos = getattr(settings, "GITHUB_ALLOWED_REPOS", [])
    if allowed_repos and repository not in allowed_repos:
        logger.info("Webhook from non-allowed repository: %s", repository)
        return JsonResponse({"error": f"Repository {repository} not in allowlist"}, status=403)

    # Check for duplicate delivery (idempotency)
    if WebhookEvent.objects.filter(delivery_id=delivery_id).exists():
        logger.info("Duplicate webhook delivery: %s", delivery_id)
        return JsonResponse({"status": "duplicate", "delivery_id": delivery_id})

    # Create audit log entry
    webhook_event = WebhookEvent.objects.create(
        delivery_id=delivery_id,
        event_type=event_type,
        action=action,
        repository=repository,
        sender=sender,
        payload=_sanitize_payload(payload),
        status=WebhookEventStatus.RECEIVED,
    )

    # Only process workflow_run.completed events
    if event_type != "workflow_run":
        webhook_event.status = WebhookEventStatus.SKIPPED
        webhook_event.error_message = f"Ignoring event type: {event_type}"
        webhook_event.processed_at = timezone.now()
        webhook_event.save()
        return JsonResponse(
            {
                "status": "skipped",
                "reason": f"Event type {event_type} not processed",
                "delivery_id": delivery_id,
            }
        )

    # Parse workflow run event
    workflow_run = parse_workflow_run_event(payload)
    if not workflow_run:
        webhook_event.status = WebhookEventStatus.SKIPPED
        webhook_event.error_message = f"Ignoring workflow_run action: {action}"
        webhook_event.processed_at = timezone.now()
        webhook_event.save()
        return JsonResponse(
            {
                "status": "skipped",
                "reason": f"Action {action} not processed (only 'completed')",
                "delivery_id": delivery_id,
            }
        )

    # Get installation ID for API access
    installation_id = get_installation_id_from_payload(payload)
    if not installation_id:
        webhook_event.status = WebhookEventStatus.FAILED
        webhook_event.error_message = "Missing installation ID in payload"
        webhook_event.processed_at = timezone.now()
        webhook_event.save()
        return JsonResponse(
            {"error": "Missing installation ID", "delivery_id": delivery_id},
            status=400,
        )

    # Mark as processing
    webhook_event.status = WebhookEventStatus.PROCESSING
    webhook_event.save()

    # Process the webhook (will be implemented in Phase 26)
    try:
        from .services.github_webhook_handler import process_workflow_run

        test_run = process_workflow_run(
            workflow_run=workflow_run,
            installation_id=installation_id,
            webhook_event=webhook_event,
        )

        webhook_event.status = WebhookEventStatus.SUCCESS
        webhook_event.test_run = test_run
        webhook_event.processed_at = timezone.now()
        webhook_event.save()

        return JsonResponse(
            {
                "status": "success",
                "delivery_id": delivery_id,
                "test_run_id": test_run.id if test_run else None,
            }
        )

    except ImportError:
        # Handler not implemented yet (Phase 26)
        webhook_event.status = WebhookEventStatus.RECEIVED
        webhook_event.error_message = "Handler not yet implemented"
        webhook_event.processed_at = timezone.now()
        webhook_event.save()

        return JsonResponse(
            {
                "status": "received",
                "delivery_id": delivery_id,
                "message": "Webhook recorded, processing not yet implemented",
            }
        )

    except Exception as e:
        logger.exception("Error processing webhook %s: %s", delivery_id, e)
        webhook_event.status = WebhookEventStatus.FAILED
        webhook_event.error_message = str(e)[:1000]  # Truncate long errors
        webhook_event.processed_at = timezone.now()
        webhook_event.save()

        return JsonResponse(
            {
                "status": "error",
                "delivery_id": delivery_id,
                "error": "Processing failed",
            },
            status=500,
        )


def _sanitize_payload(payload: dict) -> dict:
    """Remove sensitive data from payload before storing.

    Args:
        payload: Raw webhook payload.

    Returns:
        Sanitized payload safe for storage.
    """
    # Create a copy to avoid modifying original
    sanitized = payload.copy()

    # Remove potentially sensitive nested data
    # Keep structure but remove large or sensitive fields
    if "installation" in sanitized:
        # Keep only the ID
        sanitized["installation"] = {"id": sanitized["installation"].get("id")}

    # Truncate large fields
    if "workflow_run" in sanitized:
        wr = sanitized["workflow_run"]
        # Remove logs_url and jobs_url (can be reconstructed from run_id)
        for key in ["logs_url", "jobs_url", "check_suite_url"]:
            wr.pop(key, None)

    return sanitized
