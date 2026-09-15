"""Regression test for concurrent duplicate GitHub webhook deliveries."""

import json

import pytest
from django.db.models import QuerySet
from django.test import RequestFactory

from requirements import webhooks
from requirements.models import WebhookEvent, WebhookEventStatus

WORKFLOW_RUN_PAYLOAD = {
    "action": "requested",
    "repository": {"full_name": "acme/widgets"},
    "sender": {"login": "octocat"},
}


@pytest.mark.django_db
def test_duplicate_delivery_race_does_not_500(settings, monkeypatch):
    """A delivery_id that wins the idempotency check but loses the create race must not 500.

    GitHub retries deliveries with the same X-GitHub-Delivery id on
    timeout/5xx, so two requests for the same delivery_id can race each
    other between the idempotency check and the insert. This reproduces
    that race deterministically: the idempotency check reports "not seen
    yet" (as it would for the loser of a real race, since the winner's row
    lands after the check ran) while a row for the delivery_id already
    exists by the time the request tries to persist it. The request must
    still return 200 with a duplicate response, not an unhandled
    IntegrityError.
    """
    settings.GITHUB_ALLOWED_REPOS = []
    delivery_id = "dup-delivery-race"

    original_exists = QuerySet.exists

    def stale_exists(self):
        if self.model is WebhookEvent:
            return False
        return original_exists(self)

    monkeypatch.setattr(QuerySet, "exists", stale_exists)

    WebhookEvent.objects.create(
        delivery_id=delivery_id,
        event_type="workflow_run",
        action="requested",
        repository="acme/widgets",
        sender="octocat",
        status=WebhookEventStatus.RECEIVED,
    )

    request = RequestFactory().post(
        "/api/webhooks/github/",
        data=json.dumps(WORKFLOW_RUN_PAYLOAD).encode(),
        content_type="application/json",
        HTTP_X_GITHUB_DELIVERY=delivery_id,
        HTTP_X_GITHUB_EVENT="workflow_run",
    )

    response = webhooks.github_webhook(request)

    assert response.status_code == 200
    assert json.loads(response.content) == {"status": "duplicate", "delivery_id": delivery_id}
    assert WebhookEvent.objects.filter(delivery_id=delivery_id).count() == 1
