"""Scheduled subscription monitoring: expire overdue rows and send reminders.

Run daily from cron, Windows Task Scheduler or any job runner::

    python manage.py monitor_subscriptions

Use ``--now`` (ISO datetime) to replay a specific moment in tests or backfills.
The command is safe to run repeatedly: every reminder is unique per
subscription, kind and expiry cycle.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from subscriptions.services import run_monitor


class Command(BaseCommand):
    help = "Expire overdue subscriptions and send duplicate-free reminders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--now",
            help="Override the current time (ISO 8601, e.g. 2026-01-31T09:00:00).",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        if options.get("now"):
            parsed = parse_datetime(options["now"])
            if parsed is None:
                raise CommandError("--now must be a valid ISO 8601 datetime.")
            now = (
                timezone.make_aware(parsed)
                if timezone.is_naive(parsed)
                else parsed
            )

        result = run_monitor(now)
        expired = len(result["expired"])
        reminders = len(result["reminders"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Subscription monitor complete: {expired} expired, "
                f"{reminders} reminder(s) sent."
            )
        )
