from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from subscriptions.models import SubscriptionPlan, SubscriptionProduct
from subscriptions.selectors import get_featured_credit_balance
from subscriptions.services import activate_or_renew_subscription_from_order_item


class DummyOrder:
    def __init__(self, reference, user):
        self.reference = reference
        self.user = user


class DummyItem:
    def __init__(self, sku):
        self.sku = sku


class ActivationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="dealer", password="pass")
        self.plan = SubscriptionPlan.objects.create(
            key="business_basic",
            name="Business Basic",
            description="",
            price_ttd=Decimal("199.00"),
            billing_period="monthly",
            featured_credits_per_period=3,
            max_active_listings=25,
        )
        self.product = SubscriptionProduct.objects.create(
            sku="BUS_SUB_MONTH_BASIC",
            plan=self.plan,
            period_days=30,
        )

    def test_activation_creates_subscription_with_correct_period(self):
        order = DummyOrder(reference="ORDER-1", user=self.user)
        item = DummyItem(sku=self.product.sku)

        subscription = activate_or_renew_subscription_from_order_item(order, None, item, self.user)

        self.assertIsNotNone(subscription)
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.status, "active")
        self.assertEqual(
            subscription.current_period_end - subscription.current_period_start, timedelta(days=30)
        )

    def test_activation_grants_featured_credits(self):
        order = DummyOrder(reference="ORDER-2", user=self.user)
        item = DummyItem(sku=self.product.sku)

        subscription = activate_or_renew_subscription_from_order_item(order, None, item, self.user)
        balance = get_featured_credit_balance(subscription)

        self.assertEqual(balance, self.plan.featured_credits_per_period)
