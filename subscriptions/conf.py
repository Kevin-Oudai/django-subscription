from __future__ import annotations

from django.conf import settings

DEFAULTS = {
    "SUBSCRIPTIONS_TENANT_MODEL": None,
    "SUBSCRIPTIONS_USER_MODEL": None,
    "SUBSCRIPTIONS_DEFAULT_PLAN_SLUG": "free",
    "SUBSCRIPTIONS_TRIAL_DAYS_DEFAULT": 14,
    "SUBSCRIPTIONS_GRACE_DAYS_DEFAULT": 7,
    "SUBSCRIPTIONS_ENABLE_OVERRIDES": True,
    "SUBSCRIPTIONS_ENABLE_USAGE": True,
}


def get_setting(name: str):
    """Return subscriptions setting with fallback to defaults."""
    return getattr(settings, name, DEFAULTS.get(name))


def tenant_model_label() -> str | None:
    return get_setting("SUBSCRIPTIONS_TENANT_MODEL")


def user_model_label() -> str:
    configured = get_setting("SUBSCRIPTIONS_USER_MODEL")
    return configured or settings.AUTH_USER_MODEL


def trial_days_default() -> int:
    return int(get_setting("SUBSCRIPTIONS_TRIAL_DAYS_DEFAULT") or 0)


def grace_days_default() -> int:
    return int(get_setting("SUBSCRIPTIONS_GRACE_DAYS_DEFAULT") or 0)


def overrides_enabled() -> bool:
    return bool(get_setting("SUBSCRIPTIONS_ENABLE_OVERRIDES"))


def usage_enabled() -> bool:
    return bool(get_setting("SUBSCRIPTIONS_ENABLE_USAGE"))
