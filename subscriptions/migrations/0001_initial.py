from django.conf import settings
from django.db import migrations, models

import subscriptions.conf as app_conf

TENANT_MODEL_LABEL = app_conf.tenant_model_label()
USER_MODEL_LABEL = app_conf.user_model_label()
HAS_TENANT = TENANT_MODEL_LABEL is not None


def subscription_fields():
    fields = [
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("status", models.CharField(choices=[("TRIAL", "Trial"), ("ACTIVE", "Active"), ("PAST_DUE", "Past due"), ("GRACE", "Grace"), ("CANCELLED", "Cancelled"), ("EXPIRED", "Expired")], default="ACTIVE", max_length=20)),
        ("starts_at", models.DateTimeField()),
        ("ends_at", models.DateTimeField(blank=True, null=True)),
        ("trial_ends_at", models.DateTimeField(blank=True, null=True)),
        ("grace_ends_at", models.DateTimeField(blank=True, null=True)),
        ("cancel_at_period_end", models.BooleanField(default=True)),
        ("external_reference", models.CharField(blank=True, max_length=255)),
        ("metadata", models.JSONField(blank=True, default=dict)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
        ("plan", models.ForeignKey(on_delete=models.PROTECT, related_name="subscriptions", to="subscriptions.plan")),
    ]
    if HAS_TENANT:
        fields.append(
            ("tenant", models.ForeignKey(blank=True, null=True, on_delete=models.CASCADE, related_name="subscription_subscriptions", to=TENANT_MODEL_LABEL)),
        )
    fields.append(
        ("user", models.ForeignKey(blank=True, null=True, on_delete=models.CASCADE, related_name="subscription_user_subscriptions", to=USER_MODEL_LABEL)),
    )
    return fields


def override_fields():
    fields = [
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("feature_key", models.CharField(max_length=150)),
        ("feature_enabled", models.BooleanField(null=True)),
        ("limit_key", models.CharField(blank=True, max_length=150)),
        ("limit_value", models.IntegerField(blank=True, null=True)),
        ("note", models.CharField(blank=True, max_length=255)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
    ]
    if HAS_TENANT:
        fields.append(
            ("tenant", models.ForeignKey(blank=True, null=True, on_delete=models.CASCADE, related_name="subscription_entitlement_overrides", to=TENANT_MODEL_LABEL)),
        )
    fields.append(
        ("user", models.ForeignKey(blank=True, null=True, on_delete=models.CASCADE, related_name="subscription_user_entitlement_overrides", to=USER_MODEL_LABEL)),
    )
    return fields


def usage_fields():
    fields = [
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("key", models.CharField(max_length=150)),
        ("period_start", models.DateField()),
        ("period_end", models.DateField()),
        ("used", models.PositiveIntegerField(default=0)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
    ]
    if HAS_TENANT:
        fields.append(
            ("tenant", models.ForeignKey(blank=True, null=True, on_delete=models.CASCADE, related_name="subscription_usage_counters", to=TENANT_MODEL_LABEL)),
        )
    fields.append(
        ("user", models.ForeignKey(blank=True, null=True, on_delete=models.CASCADE, related_name="subscription_user_usage_counters", to=USER_MODEL_LABEL)),
    )
    return fields


def override_constraints():
    constraints = [
        models.UniqueConstraint(fields=["user", "feature_key"], name="subscriptions_feature_override_user"),
        models.UniqueConstraint(fields=["user", "limit_key"], name="subscriptions_limit_override_user"),
    ]
    if HAS_TENANT:
        constraints.extend(
            [
                models.UniqueConstraint(fields=["tenant", "feature_key"], name="subscriptions_feature_override_tenant"),
                models.UniqueConstraint(fields=["tenant", "limit_key"], name="subscriptions_limit_override_tenant"),
            ]
        )
    return constraints


def usage_constraints():
    constraints = [
        models.UniqueConstraint(
            fields=["user", "key", "period_start", "period_end"],
            name="subscriptions_usage_user_period_key",
        )
    ]
    if HAS_TENANT:
        constraints.append(
            models.UniqueConstraint(
                fields=["tenant", "key", "period_start", "period_end"],
                name="subscriptions_usage_tenant_period_key",
            )
        )
    return constraints


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(USER_MODEL_LABEL),
    ]
    if HAS_TENANT:
        dependencies.append(migrations.swappable_dependency(TENANT_MODEL_LABEL))

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("slug", models.SlugField(unique=True)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_public", models.BooleanField(default=True)),
                ("sort_order", models.IntegerField(default=0)),
                ("features", models.JSONField(blank=True, default=dict)),
                ("limits", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["sort_order", "slug"]},
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=subscription_fields(),
            options={"ordering": ["-starts_at", "-created_at"], "indexes": [models.Index(fields=["status", "starts_at"], name="subscripti_status_1b082c_idx")]},
        ),
        migrations.CreateModel(
            name="EntitlementOverride",
            fields=override_fields(),
            options={"constraints": override_constraints()},
        ),
        migrations.CreateModel(
            name="UsageCounter",
            fields=usage_fields(),
            options={
                "ordering": ["-period_start", "-created_at"],
                "constraints": usage_constraints(),
            },
        ),
        migrations.AddIndex(
            model_name="plan",
            index=models.Index(fields=["is_active", "sort_order"], name="plan_is_acti_7a8923_idx"),
        ),
    ]
