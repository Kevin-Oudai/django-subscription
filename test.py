"""
Run the mroudai-django-subscriptions test suite.

Usage:
    python test django-subscriptions
    # or simply:
    python test
"""
import os
import sys

import django
from django.core.management import call_command


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "subscriptions.tests.settings")
    django.setup()

    # Accept optional app label; default to "subscriptions"
    app_label = sys.argv[1] if len(sys.argv) > 1 else "subscriptions"
    if app_label in {"django-subscriptions", "mroudai-django-subscriptions"}:
        app_label = "subscriptions"
    call_command("test", app_label)


if __name__ == "__main__":
    main()
