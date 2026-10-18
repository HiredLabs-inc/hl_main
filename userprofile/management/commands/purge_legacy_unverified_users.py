import csv
import smtplib
import sys
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from userprofile import purge


class Command(BaseCommand):
    help = (
        "Delete legacy accounts from the old signup flow: non-staff, no password, "
        "unverified email, onboarding not finished, joined before --before."
    )

    def add_arguments(self, parser):
        parser.add_argument("--before", required=True, help="Cutover date YYYY-MM-DD; only accounts joined earlier are touched.")
        parser.add_argument("--dry-run", action="store_true", help="List the accounts; change nothing.")
        parser.add_argument("--export", metavar="FILE", help="Write the accounts to a CSV file first ('-' for stdout).")
        parser.add_argument("--invite", action="store_true", help="Email each person a new signup link before deleting.")
        parser.add_argument("--batch-size", type=int, metavar="N", help="Handle at most N accounts this run.")

    def handle(self, *args, before, dry_run, export, invite, batch_size, **options):
        try:
            cutover = timezone.make_aware(datetime.strptime(before, "%Y-%m-%d"))
        except ValueError:
            raise CommandError("--before must be YYYY-MM-DD")
        users = purge.legacy_unverified_users(cutover)
        total = users.count()
        if batch_size:
            users = users[:batch_size]
        users = list(users)

        if export:
            self.export(users, export)
        self.stdout.write(f"{total} legacy account(s) joined before {before}; handling {len(users)} this run.")
        if dry_run:
            for user in users:
                self.stdout.write(f"would {'invite and ' if invite else ''}delete {user.email} (joined {user.date_joined:%Y-%m-%d})")
            return

        failed = []
        for user in users:
            if invite:
                try:
                    purge.invite_and_delete(user)
                except (smtplib.SMTPException, OSError) as e:
                    self.stderr.write(f"invite to {user.email} failed, account kept: {e!r}")
                    failed.append(user.email)
            else:
                user.delete()
        self.stdout.write(f"deleted {len(users) - len(failed)}, kept {len(failed)} after send errors")
        if failed:
            raise CommandError(f"Invites failed for: {', '.join(failed)}")

    def export(self, users, path):
        out = sys.stdout if path == "-" else open(path, "w", newline="")
        try:
            writer = csv.writer(out)
            writer.writerow(["id", "email", "date_joined", "last_login"])
            for user in users:
                writer.writerow([user.pk, user.email, user.date_joined.isoformat(), user.last_login.isoformat() if user.last_login else ""])
        finally:
            if out is not sys.stdout:
                out.close()
