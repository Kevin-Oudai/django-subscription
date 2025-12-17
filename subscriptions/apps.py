from django.apps import AppConfig


class SubscriptionsConfig(AppConfig):
    name = "subscriptions"
    verbose_name = "Subscriptions"

    def ready(self):
        from . import signals  # noqa: F401
