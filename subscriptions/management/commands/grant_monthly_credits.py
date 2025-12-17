from django.core.management.base import BaseCommand

from subscriptions.services import grant_periodic_credits


class Command(BaseCommand):
    help = "Grant monthly featured credits when a new billing period starts."

    def handle(self, *args, **options):
        created = grant_periodic_credits()
        self.stdout.write(self.style.SUCCESS(f"Granted credits to {created} subscription(s)."))
