import smtplib

from django.core.management.base import BaseCommand, CommandError

from userprofile import reminders


class Command(BaseCommand):
    help = (
        "Email reminders to people who stalled during signup or onboarding, and delete "
        "signups never completed within 30 days (run daily)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="List who would get a reminder; send nothing.")

    def handle(self, *args, dry_run=False, **options):
        jobs = [(p.email, reminders.send_pending_reminder, p) for p in reminders.pending_due()]
        jobs += [(u.email, reminders.send_onboarding_reminder, u) for u in reminders.users_due()]
        failed = []
        for email, send, target in jobs:
            if dry_run:
                self.stdout.write(f"would remind {email} ({send.__name__})")
                continue
            try:
                send(target)
            except (smtplib.SMTPException, OSError):
                reminders.logger.exception("Reminder to %s failed", email)
                failed.append(email)
        self.stdout.write(f"{len(jobs) - len(failed)} reminder(s) {'due' if dry_run else 'sent'}, {len(failed)} failed")
        expired = reminders.expired_pending()
        if dry_run:
            self.stdout.write(f"would delete {expired.count()} expired pending signup(s)")
        else:
            deleted, _ = expired.delete()
            self.stdout.write(f"deleted {deleted} expired pending signup(s)")
        if failed:
            raise CommandError(f"Reminders failed for: {', '.join(failed)}")
