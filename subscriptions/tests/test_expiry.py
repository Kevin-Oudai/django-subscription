from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from subscriptions.entitlements import has_active_subscription
from subscriptions.models import SubscriptionPlan, SubscriptionProduct, SubscriptionStatus, UserSubscription
from subscriptions.services import expire_due_subscriptions


class ExpiryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="dealer", password="pass")
        self.plan = SubscriptionPlan.objects.create(
            key="business_basic",
            name="Business Basic",
            description="",
            price_ttd=Decimal("199.00"),
            billing_period="monthly",
        )
        self.product = SubscriptionProduct.objects.create(
            sku="BUS_SUB_MONTH_BASIC",
            plan=self.plan,
            period_days=30,
        )

    def test_expiry_marks_due_subscriptions(self):
        now = timezone.now()
        subscription = UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            started_at=now - timedelta(days=40),
            current_period_start=now - timedelta(days=40),
            current_period_end=now - timedelta(days=10),
        )

        expire_due_subscriptions(now=now)
        subscription.refresh_from_db()

        self.assertEqual(subscription.status, SubscriptionStatus.EXPIRED)
        self.assertFalse(has_active_subscription(self.user))
