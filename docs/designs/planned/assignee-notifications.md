# Assignee Notifications (IDEA-001)

Branch `feature/idea-001-assignee-notifications` (from `develop`), not started.

> **Status:** drafted 2026-10-29. Proposals in §5 are recommendations and still need Jeff's agreement. Open items in §7.

## 1. Context
IDEA-001: "email a staff member when an enrollment is assigned to them, and when one of their enrollments has sat in the same step longer than N days." It was left out of the staff redesign (`docs/designs/completed/cold-apply-staff-redesign.md` §5.5). Today nobody is told about either. Assignees find out from the dashboard's *My people* tab or the "In step over 14 days" header count.

What's already in place:
- `pipeline.Enrollment` has `assignee` (FK to User, nullable), `status`, `step_entered_at` and `ended_at`. `days_in_step` is a property.
- `pipeline.services.assign()` and `enroll(..., assignee=...)` are the only places an assignee is set. Both run in a transaction and write an `ASSIGNEE_CHANGE` Activity. `assign()` returns early when the assignee doesn't change.
- `pipeline.dashboard.DEFAULT_STALE_DAYS = 14` drives the "In step over 14 days" count, the amber day count in table rows, and the board card badge. The dashboard filters already support `?tab=mine&days=14` and, for lead flows, `?tab=<flow slug>&assignee=me&days=14`.
- Who can be assigned (`pipeline.guards.can_be_assigned`): active staff in any flow, plus active users with `pipeline.work_lead_flows` (volunteers in the Agents group) in the lead flows, Funding and Outreach.
- The daily `send_signup_reminders` command (`userprofile/reminders.py`) runs as the `signup-reminders` Cloud Run Job, started by `google_cloud_scheduler_job.signup_reminders` (`infra/terraform/modules/hl-env/main.tf`). It sends with allauth's `get_adapter().send_mail`, builds links with `userprofile.signup.absolute_url` (falls back to `PUBLIC_BASE_URL` outside a request), logs and collects SMTP failures, and supports `--dry-run`.
- Email templates are plain text, extending `templates/account/email/base_message.txt`.

## 2. Goals
- **Assigned email:** when someone else assigns an enrollment to you, you get an email right away with who it is, the flow and step, who assigned it, and a link.
- **Stuck digest:** once a day, each assignee with enrollments that have just passed N days in their step gets **one** email listing them, with a link to the filtered dashboard.
- Each enrollment is reported as stuck **once per step**. Moving it to a new step resets that.
- No email when you assign something to yourself, to an inactive user, or to a user without an email address.
- Works for person flows and lead flows alike.

**Not goals:** in-app notifications or a bell. Emails to participants or leads. Per-user notification settings beyond a single opt-out (see §7). Notifying the previous assignee when an enrollment is taken away.

## 3. Design

### 3.1 Assigned email
- New `pipeline/notifications.py` with `send_assigned(enrollment, actor)`.
- `services.assign()` and `services.enroll()` call it through `transaction.on_commit`, so a rolled-back change sends nothing and the send happens outside the row lock. It's skipped when `assignee is None`, `assignee == actor`, the assignee is inactive, or has no email.
- A send failure is logged (`logger.exception`) and swallowed: the assignment itself has already succeeded and the user sees the normal toast.
- Content (`pipeline/templates/pipeline/email/assigned_subject.txt` / `_message.txt`, extending `account/email/base_message.txt`):
  - Subject: `You've been assigned {{ label }} ({{ flow }})`
  - Body: who, flow, current step and days in it, who assigned it, and a link to the dashboard filtered to that flow and `assignee=me` (person flows link to `?tab=mine`).
- **Bulk assigns:** there's no bulk-assign action today (`complete_triage` enrolls without an assignee). If one is added, each `on_commit` would send its own email, so it should batch them into one.

### 3.2 Stuck digest
- New field `Enrollment.stuck_notified_at` (DateTimeField, null). An enrollment is **due** when:
  - `ended_at` is null and `status == ACTIVE` (paused, rejected and no-show are waiting on someone else, so they're left out),
  - `assignee` is set, active, and has an email,
  - `step_entered_at < now - N days`,
  - and `stuck_notified_at` is null or earlier than `step_entered_at` (not yet reported for this step).
- `notifications.stuck_due(now=None)` returns the due enrollments grouped by assignee. `send_stuck_digest(assignee, enrollments)` sends one email and sets `stuck_notified_at = now` on those enrollments with a single `update()`.
- `move_to_step` already sets `step_entered_at`, so a new step makes the enrollment eligible again with no extra code. `stuck_notified_at` isn't cleared by reassignment: the new assignee got the assigned email, which shows days in step.
- Content (`stuck_digest_subject.txt` / `_message.txt`):
  - Subject: `{{ count }} of your enrollments have been in the same step over {{ days }} days`
  - Body: one line per enrollment (`label — flow: step, N days`), then a link to `?tab=mine&days=N` and, if any lead flows are listed, one link per lead flow with `assignee=me&days=N`.
- **N** is a new setting `ASSIGNEE_STUCK_DAYS`, defaulting to `pipeline.dashboard.DEFAULT_STALE_DAYS` (14) so the email and the dashboard agree. One value for every flow for now (see §7).

### 3.3 Command and job
- New `pipeline/management/commands/send_assignee_reminders.py`, shaped like `send_signup_reminders`: `--dry-run` lists who would get what; failures are logged, collected, and raise `CommandError` at the end so the Cloud Run execution shows as failed.
- Terraform: add `assignee-reminders = ["python", "manage.py", "send_assignee_reminders"]` to the `google_cloud_run_v2_job.jobs` map, and a second scheduler job beside `signup_reminders` with its own `assignee_reminders_schedule` variable (null = off). Suggested schedule `0 7 * * 1-5` (weekday mornings, Pacific), so a digest lands at the start of the working day and nothing goes out at weekends. Weekend crossings are picked up on Monday because "due" is a state, not an event.
- The new command lives in `pipeline` and imports nothing from `cold_apply`. Reusing `userprofile.signup.absolute_url` is fine (`pipeline` already imports `userprofile.guards` and `userprofile.bootcamp`); if that's unwanted, move `absolute_url` to `hl_main`.

### 3.4 Timeline
Neither email writes an Activity row. They're internal nudges to staff, not contact with the person, and would clutter the timeline. The command's output and logs are the record.

## 4. Stages (one branch, `feature/idea-001-assignee-notifications`)
- **N1 — Assigned email.** `notifications.py`, `send_assigned`, the `on_commit` hooks in `assign()` and `enroll()`, templates, tests.
- **N2 — Stuck digest.** Migration for `stuck_notified_at`, `ASSIGNEE_STUCK_DAYS`, `stuck_due`, `send_stuck_digest`, the command, templates, tests.
- **N3 — Infra.** Cloud Run job and scheduler in Terraform, variable set for each environment, a dry run against prod data before turning the schedule on.

## 5. Proposed decisions (need agreement)
1. Assigned emails go out immediately; stuck emails go out as one daily digest per assignee.
2. Each enrollment is reported stuck once per step, not every day it stays stuck.
3. Only `active` enrollments count as stuck.
4. N is one setting shared with the dashboard's stale count (14 days).
5. A separate command and Cloud Run Job, not folded into `send_signup_reminders`.
6. No Activity rows for these emails.

## 6. Verification
- `python manage.py test pipeline` passes, with new tests in `pipeline/tests/test_notifications.py`:
  - assigning someone else sends one email (`mail.outbox`); assigning yourself, unassigning, re-assigning the same person, or assigning an inactive / email-less user sends none;
  - an assign that fails validation or rolls back sends none (`captureOnCommitCallbacks`);
  - `stuck_due` includes an enrollment at N+1 days and excludes N−1 days, ended, paused, unassigned, and already-notified-for-this-step enrollments; moving it to a new step makes it due again after N days;
  - the digest groups by assignee, sends one email each, and sets `stuck_notified_at`; a second run the same day sends nothing;
  - `--dry-run` sends nothing and changes nothing; an SMTP failure for one assignee doesn't stop the others and ends in `CommandError`.
- Locally, with the console email backend: assign an enrollment to another staff user from the dashboard and see the email in the runserver output; backdate a `step_entered_at` in the shell and run `python manage.py send_assignee_reminders --dry-run`, then without `--dry-run`.
- Before turning the schedule on in prod: run the job once with `--dry-run` and check the count. Prod likely has many enrollments already over 14 days, so the **first** digest could be long (see §7).

## 7. Open items
- **First run backlog:** enrollments already stuck when this ships would all land in the first digest. Options: send it anyway (it's a useful clean-up list), or a data migration that sets `stuck_notified_at = now` on everything currently stuck so only new crossings are reported. Recommendation: send it, after the dry-run count is checked.
- **Repeat reminders:** whether an enrollment still stuck after another N days should be reported again (e.g. at 14, 28, 42 days). The design above reports once per step.
- **Opt-out:** whether staff need a way to turn these off. Staff users may not have a `Profile`, so it would be a new small model or a field on a staff settings page. Left out of the first version unless asked for.
- **Per-flow N:** some steps (e.g. waiting for a boot camp session) are expected to be long. A `Step.stuck_after_days` override could come later; for now Boot Camp waitlist enrollments would show up as stuck.
- **Volunteers:** lead-flow volunteers get these emails too. Confirm that's wanted.
