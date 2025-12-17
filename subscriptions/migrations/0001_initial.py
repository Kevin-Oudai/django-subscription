from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SubscriptionPlan",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.SlugField(unique=True)),
                ("name", models.CharField(max_length=150)),
                ("description", models.TextField(blank=True)),
                ("price_ttd", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "billing_period",
                    models.CharField(
                        choices=[("monthly", "Monthly"), ("yearly", "Yearly")], max_length=20
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("max_active_listings", models.IntegerField(blank=True, null=True)),
                ("featured_credits_per_period", models.PositiveIntegerField(default=0)),
                ("badge_label", models.CharField(blank=True, max_length=150)),
                ("priority_support", models.BooleanField(default=False)),
                ("can_add_multiple_staff", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="UserSubscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("expired", "Expired"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("started_at", models.DateTimeField()),
                ("current_period_start", models.DateTimeField()),
                ("current_period_end", models.DateTimeField(db_index=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("last_paid_order_reference", models.CharField(blank=True, db_index=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="user_subscriptions",
                        to="subscriptions.subscriptionplan",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscriptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-current_period_end", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SubscriptionProduct",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sku", models.CharField(max_length=150, unique=True)),
                ("period_days", models.PositiveIntegerField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="products",
                        to="subscriptions.subscriptionplan",
                    ),
                ),
            ],
            options={
                "ordering": ["sku"],
            },
        ),
        migrations.CreateModel(
            name="ProcessedSubscriptionOrder",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("order_reference", models.CharField(max_length=255, unique=True)),
                ("processed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="processed_orders",
                        to="subscriptions.subscriptionplan",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="processed_subscription_orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-processed_at"],
            },
        ),
        migrations.CreateModel(
            name="SubscriptionCreditLedger",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "credit_type",
                    models.CharField(
                        choices=[("featured", "Featured")], max_length=50
                    ),
                ),
                ("change", models.IntegerField()),
                ("reason", models.CharField(max_length=255)),
                ("related_order_reference", models.CharField(blank=True, max_length=255, null=True)),
                ("related_listing_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="credit_entries",
                        to="subscriptions.usersubscription",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription_credit_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="usersubscription",
            constraint=models.UniqueConstraint(
                condition=models.Q(status="active"),
                fields=("user",),
                name="unique_active_subscription_per_user",
            ),
        ),
    ]
