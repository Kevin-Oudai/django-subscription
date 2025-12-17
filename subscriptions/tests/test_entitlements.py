from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from subscriptions.entitlements import (
    consume_featured_credit,
    get_active_subscription,
    get_entitlements,
)
from subscriptions.models import SubscriptionPlan, SubscriptionProduct
from subscriptions.services import activate_or_renew_subscription_from_order_item


class DummyOrder:
    def __init__(self, reference, user):
        self.reference = reference
        self.user = user


class DummyItem:
    def __init__(self, sku):
        self.sku = sku


class EntitlementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="dealer", password="pass")
        self.plan = SubscriptionPlan.objects.create(
            key="dealer_plus",
            name="Dealer Plus",
            description="",
            price_ttd=Decimal("299.00"),
            billing_period="monthly",
            featured_credits_per_period=2,
            badge_label="Dealer",
            priority_support=True,
            max_active_listings=100,
        )
        self.product = SubscriptionProduct.objects.create(
            sku="BUS_SUB_MONTH_PLUS",
            plan=self.plan,
            period_days=30,
        )
        order = DummyOrder(reference="ORDER-ENT", user=self.user)
        item = DummyItem(sku=self.product.sku)
        activate_or_renew_subscription_from_order_item(order, None, item, self.user)

    def test_entitlements_match_plan(self):
        entitlements = get_entitlements(self.user)

        self.assertEqual(entitlements["max_active_listings"], self.plan.max_active_listings)
        self.assertEqual(entitlements["badge_label"], self.plan.badge_label)
        self.assertTrue(entitlements["priority_support"])
        self.assertEqual(entitlements["featured_credits_balance"], self.plan.featured_credits_per_period)

    def test_consume_featured_credit_until_depleted(self):
        subscription = get_active_subscription(self.user)

        self.assertTrue(consume_featured_credit(self.user, listing_id=None, reason="test"))
        self.assertTrue(consume_featured_credit(self.user, listing_id=None, reason="test"))
        # third attempt should fail because balance hit zero
        self.assertFalse(consume_featured_credit(self.user, listing_id=None, reason="test"))
