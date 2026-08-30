"""Guard the Unfold sidebar against features that ship unreachable.

``show_all_applications`` is False, so a registered ModelAdmin the sidebar omits
has no navigation path at all. Every omission belongs in ``SIDEBAR_EXEMPT`` with
the reason it stays out.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import reverse

KNOWN_GAP = "Known gap: unlinked since before the 2026-08-29 IA audit."

SIDEBAR_EXEMPT = {
    "Agent": KNOWN_GAP,
    "AgentSprint": KNOWN_GAP,
    "AgentTask": KNOWN_GAP,
    "AgentTaskHistory": KNOWN_GAP,
    "AgentTaskReview": KNOWN_GAP,
    "ConflictLog": KNOWN_GAP,
    "InAppValidation": KNOWN_GAP,
    "InAppValidationResult": KNOWN_GAP,
    "InAppValidationRun": KNOWN_GAP,
    "SLO": KNOWN_GAP,
    "TestRequirementLink": KNOWN_GAP,
    "TestResult": KNOWN_GAP,
    "VerificationFlow": KNOWN_GAP,
}


def _sidebar_links():
    return {
        str(item["link"])
        for group in settings.UNFOLD["SIDEBAR"]["navigation"]
        for item in group["items"]
    }


def _registered_models():
    return {
        model.__name__: model
        for model in admin.site._registry
        if model._meta.app_label == "requirements"
    }


def _changelist_url(model):
    meta = model._meta
    return reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist")


def test_sidebar_navigation__links_every_registered_model():
    links = _sidebar_links()
    missing = sorted(
        name
        for name, model in _registered_models().items()
        if name not in SIDEBAR_EXEMPT and _changelist_url(model) not in links
    )
    assert not missing, (
        f"Registered in admin but absent from the sidebar: {missing}. "
        "Add an entry to UNFOLD['SIDEBAR']['navigation'] in settings.py, "
        "or record the reason in SIDEBAR_EXEMPT."
    )


def test_sidebar_exempt__names_only_unlinked_registered_models():
    registered = _registered_models()
    links = _sidebar_links()

    unregistered = sorted(set(SIDEBAR_EXEMPT) - set(registered))
    assert not unregistered, (
        f"SIDEBAR_EXEMPT names models no longer registered in admin: {unregistered}. "
        "Drop them from the list."
    )

    now_linked = sorted(
        name for name in SIDEBAR_EXEMPT if _changelist_url(registered[name]) in links
    )
    assert not now_linked, (
        f"SIDEBAR_EXEMPT names models the sidebar now links: {now_linked}. Drop them from the list."
    )


def test_sidebar_navigation__every_link_resolves():
    for group in settings.UNFOLD["SIDEBAR"]["navigation"]:
        for item in group["items"]:
            assert str(item["link"]).startswith("/"), (
                f"Sidebar item {item['title']!r} does not resolve to a URL path."
            )
