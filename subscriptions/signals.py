from __future__ import annotations

from django.dispatch import receiver, Signal

from .models import SubscriptionProduct
from .services import activate_or_renew_subscription_from_order_item

try:
    from payments.signals import order_paid  # type: ignore
except Exception:  # pragma: no cover - fallback when payments app is absent
    order_paid = Signal()


def _sku_from_item(item):
    if isinstance(item, dict):
        return item.get("sku") or item.get("product_sku")
    return getattr(item, "sku", None) or getattr(item, "product_sku", None)


def _items_from_order(order):
    if order is None:
        return []
    for attr in ("items", "order_items", "lines"):
        value = getattr(order, attr, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if value is not None:
            return value
    return []


@receiver(order_paid)
def on_order_paid(sender, order=None, transaction=None, **kwargs):
    user = getattr(order, "user", None) or kwargs.get("user")
    items = kwargs.get("items") or _items_from_order(order)
    if not user or not items:
        return

    for item in items:
        sku = _sku_from_item(item)
        if not sku:
            continue
        if not SubscriptionProduct.objects.filter(sku=sku, is_active=True).exists():
            continue
        activate_or_renew_subscription_from_order_item(order, transaction, item, user)
