from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from subscriptions.models import SubscriptionPlan, SubscriptionProduct, SubscriptionStatus, UserSubscription
from subscriptions.selectors import get_featured_credit_balance
from subscriptions.services import activate_or_renew_subscription_from_order_item


class DummyOrder:
    def __init__(self, reference, user):
        self.reference = reference
        self.user = user


class DummyItem:
    def __init__(self, sku):
        self.sku = sku


class RenewalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="dealer", password="pass")
        self.basic = SubscriptionPlan.objects.create(
            key="business_basic",
            name="Business Basic",
            description="",
            price_ttd=Decimal("199.00"),
            billing_period="monthly",
            featured_credits_per_period=2,
        )
        self.pro = SubscriptionPlan.objects.create(
            key="dealer_pro",
            name="Dealer Pro",
            description="",
            price_ttd=Decimal("399.00"),
            billing_period="monthly",
            featured_credits_per_period=5,
        )
        self.basic_product = SubscriptionProduct.objects.create(
            sku="BUS_SUB_MONTH_BASIC",
            plan=self.basic,
            period_days=30,
        )
        self.pro_product = SubscriptionProduct.objects.create(
            sku="BUS_SUB_MONTH_PRO",
            plan=self.pro,
            period_days=30,
        )

    def _activate(self, reference: str, product: SubscriptionProduct) -> UserSubscription:
        order = DummyOrder(reference=reference, user=self.user)
        item = DummyItem(sku=product.sku)
        return activate_or_renew_subscription_from_order_item(order, None, item, self.user)

    def test_renewal_extends_existing_subscription(self):
        first = self._activate("ORDER-RENEW-1", self.basic_product)
        initial_end = first.current_period_end

        renewed = self._activate("ORDER-RENEW-2", self.basic_product)
        renewed.refresh_from_db()

        self.assertEqual(renewed.plan, self.basic)
        self.assertEqual(renewed.current_period_start, initial_end)
        self.assertEqual(
            renewed.current_period_end, initial_end + timedelta(days=self.basic_product.period_days)
        )

    def test_plan_change_replaces_active_subscription(self):
        first = self._activate("ORDER-CHANGE-1", self.basic_product)
        _ = self._activate("ORDER-CHANGE-2", self.pro_product)

        first.refresh_from_db()
        replacement = UserSubscription.objects.get(user=self.user, status=SubscriptionStatus.ACTIVE)

        self.assertEqual(first.status, SubscriptionStatus.EXPIRED)
        self.assertEqual(replacement.plan, self.pro)
        self.assertNotEqual(replacement.id, first.id)

    def test_idempotent_processing_of_same_order(self):
        subscription = self._activate("ORDER-IDEMPOTENT", self.basic_product)
        initial_end = subscription.current_period_end

        again = self._activate("ORDER-IDEMPOTENT", self.basic_product)
        subscription.refresh_from_db()

        self.assertEqual(subscription.current_period_end, initial_end)
        self.assertEqual(get_featured_credit_balance(subscription), self.basic.featured_credits_per_period)
        self.assertEqual(subscription.id, again.id)
