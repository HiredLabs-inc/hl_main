# Nurture Flow (IDEA-006)

Branch `feature/idea-006-nurture-flow` (from `develop`), not started.

> **Status:** drafted 2026-10-29. Proposals in §5 are recommendations and still need Jeff's agreement. Open items in §7.

## 1. Context
IDEA-006: "decide what Nurture means for people who have finished or paused other flows (boot camp alumni, past job-search participants), and give it real steps." The staff redesign made Nurture its own flow but left it undefined (`docs/designs/completed/cold-apply-staff-redesign.md` §7, "Nurture as a flow?").

What's there today:
- Flow `nurture` (seeded in `pipeline/migrations/0002_seed_flows.py`), description "Steps to be defined (IDEA-006)". One phase, *Nurture*, with two steps: *Boot Camp Alumni* and *Nurture* (the old *Monthly Newsletter*, renamed because there is no newsletter).
- Prod (2026-10-19): 121 people on *Nurture*, almost nobody on *Boot Camp Alumni*. They came over from the old cold_apply phases with no record of why they're there. Most have had no contact in a long time.
- Nurture has no `completes_flow` step, so `services.ending_options` only allows **Withdrawn** (BUG-037, `pipeline/migrations/0004_enrollment_endings.py`). That fits a flow with no end.
- Nobody enters Nurture automatically. Staff can choose it at triage (`services.complete_triage`) or with *Enroll in more flows* (`actions.enroll_view`). Ending a Resume & Job Search or Boot Camp enrollment doesn't suggest it.
- `Profile.dnc` marks do-not-contact. Nothing in `pipeline` checks it.
- Staff record contact by hand as Activity rows (`email`, `phone`, `in_person`, `note`). The only emails the site sends to participants are signup ones (`userprofile/reminders.py`, `templates/account/email/`).
- The dashboard already shows days in step, an "In step over 14 days" count and a `?days=` filter (`pipeline/dashboard.py`, `DEFAULT_STALE_DAYS`). The board has one-line cards past 30 per column because of Nurture's 121 (`docs/designs/completed/kanban-board.md`).

## 2. Goals
Nurture is **low-touch, long-running contact with people Hired Labs isn't actively serving**: alumni of Boot Camp and Resume & Job Search, and people who paused, withdrew or weren't taken on. It exists to:
1. **Learn outcomes.** Did they get a job, where, doing what? This is what funders ask for, and today nobody records it.
2. **Bring people back** when they need help again (a new job search, the next boot camp cycle).
3. **Find helpers:** alumni who would volunteer, mentor, refer others or give a testimonial.
4. **Keep the list clean:** people who don't want contact are withdrawn (or marked DNC), not left on a step forever.

Concretely:
- Real steps that say what staff should do next, replacing the placeholders.
- A check-in every N days, which shows up as **due** on the dashboard rather than staff having to remember.
- A one-click templated check-in email that records itself on the timeline and moves the step.
- People enter Nurture when another flow ends, with staff confirming it.
- A one-time re-permission pass for the 121 people migrated in, so the flow starts with people who actually want to hear from us.

**Not goals:** a newsletter or bulk mail tool (if one is wanted, export the list to a mail service, see §7). A participant-facing check-in form (that belongs to the self-service portal, IDEA-004). Automatic moves between steps on a timer. Changes to lead flows.

## 3. Design

### 3.1 Steps
One flow, two phases. Owners in brackets.

| Phase | Step | Owner | Meaning |
|---|---|---|---|
| Start | **Welcome** | Hired Labs | Just entered. Send the welcome email (what Nurture is, how to reach us, "reply if you'd rather not hear from us"). |
| Keep in Touch | **Check In** | Hired Labs | A check-in is due. Email or call, ask how things are going and about work. |
| Keep in Touch | **Awaiting Reply** | Participant | Check-in sent. Waiting for an answer. |
| Keep in Touch | **Between Check-ins** | Hired Labs | Resting step. Due again after N days (§3.2). |

- The cycle is Check In → Awaiting Reply → Between Check-ins → (N days later) Check In. `move_to_step` already allows moving back to an earlier step, so no model change is needed for the loop.
- A reply moves them to Between Check-ins, with the answer recorded as a note or contact. No reply after M days (Awaiting Reply is also "due") means staff try once more or withdraw them (§5 item 6).
- **Boot Camp Alumni** goes. Where someone came from is already in their ended enrollments, so the dashboard shows it as a chip (§3.4) instead of a step.
- Ending: **Withdrawn** with a reason ("asked to stop", "no reply", "email bounced"). If they ask never to be contacted, staff also set `Profile.dnc`.

### 3.2 When a step is due
New nullable field `Step.due_after_days`. An enrollment is due when it's `active` and `days_in_step >= current_step.due_after_days`.

| Step | `due_after_days` (proposed) |
|---|---|
| Welcome | 0 (due as soon as they arrive) |
| Check In | 0 |
| Awaiting Reply | 21 |
| Between Check-ins | 90 |

- Steps without a value behave as today (only the global 14-day stale count applies). For Nurture steps the per-step value **replaces** the 14-day count, so 121 people resting for 90 days don't all show as stale.
- The dashboard's Nurture tab gets a **Due** filter and count, beside the existing filters, and due rows and cards get the amber badge.
- This is the same thing as IDEA-001's open item "Per-flow N" (`docs/designs/planned/assignee-notifications.md` §7). Whichever ships first adds the field, and the assignee stuck digest then uses it, so a Nurture assignee is reminded about due check-ins with no extra code.

### 3.3 Entering and leaving Nurture
- **When another flow ends.** The end-status dialog (completed, withdrawn, dropped) for a person-flow enrollment gets a checkbox *Move to Nurture*, ticked by default when the person isn't DNC and has no other open person-flow enrollment. Ticking it calls `services.enroll(person, nurture, actor)` in the same request. No automatic enrollment in `services`: staff know when someone shouldn't be contacted again.
- **At triage** nothing changes: Nurture is already one of the choices (e.g. someone not taken on now but worth keeping in touch with).
- **When they come back.** Enrolling in another flow leaves the Nurture enrollment open. While they have another open, active person-flow enrollment, Nurture rows show an *In another flow* chip and are **never due**. When that flow ends they're due again by the normal rules. This avoids extra pause/resume logic in `services`.
- **DNC.** `services.enroll` refuses Nurture for people with `Profile.dnc` (a small `ENROLL_RULES` hook like `STATUS_RULES`, registered by `userprofile`, so `pipeline` still doesn't import `userprofile.models`). Setting DNC on a profile doesn't change enrollments today; see §7.

### 3.4 Dashboard
On the Nurture tab only:
- Chips for where they came from: *Boot Camp alumni* (completed Boot Camp), *Boot Camp, didn't finish* (withdrawn or dropped), *Job search alumni* (ended Resume & Job Search), *Triaged here* (came straight from Intake). Derived in `dashboard.py` from the person's ended enrollments in one extra query for the page.
- *In another flow* chip (§3.3).
- **Due** count in the header and a `?due=1` filter. The board view groups by step as usual.

### 3.5 Check-in emails
- A new **Send check-in** action on Nurture rows (Welcome, Check In and Awaiting Reply steps), next to the existing inline actions in `pipeline/actions.py`. It:
  1. sends a templated email from the site's address with `Reply-To` set to the staff member (or the shared staff mailbox, see §7),
  2. records an `email` Activity with the subject, as staff do by hand now,
  3. moves the enrollment to Awaiting Reply (Welcome moves to Between Check-ins instead: the welcome isn't a question).
- It refuses DNC people and users without an email, and shows the normal toast on success. A send failure leaves the step unchanged.
- Templates in `pipeline/templates/pipeline/email/`, plain text, extending `account/email/base_message.txt`:
  - `nurture_welcome_*`: what Nurture is, that we'll check in a few times a year, how to ask for help, how to opt out (reply "stop").
  - `nurture_check_in_*`: how are things, are you working (where, doing what), would you like help again, would you like to help others (volunteer, mentor, refer).
- Replies arrive in a human inbox. Staff paste the useful part into a note and move the step. Reading replies into the site is out of scope.

### 3.6 Outcomes (optional, see §5 item 7)
Check-ins collect employment outcomes, which today would end up as free text in notes. A small structured record makes them reportable:
- New model `pipeline.Outcome`: `person`, `recorded_at`, `kind` (employed full time, employed part time, self-employed, in school or training, looking, not looking), optional `organization` and `position` (FKs to `resume.Organization` / `resume.Position`, using the case-insensitive matching from BUG-030), `note`, `actor`. Recording one writes an Activity row.
- A small form in the person panel and the participant workspace. A **Latest outcome** column on the Nurture tab.
- A CSV export of outcomes for funder reports.
`pipeline` would import from `resume` here; if that's unwanted, the model can live in `cold_apply` instead.

### 3.7 Migrating the people already there
Data migration (stage NF1):
- Create the new phases and steps, set `due_after_days`.
- Move everyone on *Nurture* and *Boot Camp Alumni* to **Check In**, keeping `step_entered_at` so the timeline is honest, and write a `step_change` Activity ("Nurture flow defined (IDEA-006)").
- Withdraw any Nurture enrollment whose profile has `dnc=True`, with reason "Do not contact".
- Delete the two old steps once empty. The migration stops with an error if any enrollment is still on them.
- Update the flow description.

Then a one-time **re-permission pass** (stage NF4): a management command `send_nurture_welcome` (`--dry-run`, same shape as `send_signup_reminders`) sends the welcome email to everyone on Check In who has never had a Nurture email, records the Activity, and moves them to Awaiting Reply. After 21 days the non-responders show as due, and staff withdraw them with "no reply" (or try once more). Run once by hand, not scheduled.

## 4. Stages (one branch, `feature/idea-006-nurture-flow`)
- **NF1 — Steps and due.** `Step.due_after_days` (unless IDEA-001 added it first), data migration (§3.7), dashboard Due count, filter and badge, tests.
- **NF2 — Entering and leaving.** *Move to Nurture* in the end-status dialog, DNC enroll rule, *In another flow* and came-from chips, tests.
- **NF3 — Check-in emails.** Send check-in action, templates, Activity and step move, tests.
- **NF4 — Re-permission pass.** `send_nurture_welcome` command, dry run on prod data, then the real run.
- **NF5 — Outcomes** (only if §5 item 7 is agreed). Model, form, column, CSV export.

## 5. Proposed decisions (need agreement)
1. Nurture is for keeping in touch with people not actively being served, with the four aims in §2 (outcomes, return, helpers, clean list).
2. Steps: Welcome → Check In → Awaiting Reply → Between Check-ins, looping. *Boot Camp Alumni* becomes a chip, not a step.
3. Check-ins every **90 days**, and a reply is chased after **21 days**, using a per-step `due_after_days` shared with IDEA-001.
4. Staff confirm entry to Nurture when another flow ends (pre-ticked checkbox), rather than automatic enrollment.
5. A Nurture enrollment stays open while the person is in another flow, and is never due during it.
6. People who don't reply to the re-permission email within 21 days are withdrawn with reason "no reply". Later, two unanswered check-ins in a row lead to withdrawal.
7. Outcomes (§3.6) are recorded as structured data, in stage NF5.
8. No newsletter is built.

## 6. Verification
- `python manage.py test pipeline userprofile` passes, with new tests:
  - migration: people on the old steps end up on Check In with `step_entered_at` unchanged and a `step_change` Activity; DNC people are withdrawn; the old steps are gone; a leftover enrollment stops the migration (`pipeline/tests/test_seed_flows.py` style);
  - due: an enrollment on Between Check-ins is due at 90 days and not at 89; Welcome and Check In are due at once; paused or ended enrollments are never due; someone with another open active person-flow enrollment is never due; steps without `due_after_days` keep the 14-day behaviour;
  - entry: ending Boot Camp with *Move to Nurture* ticked creates one Nurture enrollment; unticked creates none; already in Nurture is a no-op; DNC is refused;
  - check-in: the action sends one email (`mail.outbox`) with the right `Reply-To`, writes an `email` Activity and moves the step; DNC, no email, wrong step and a send failure send nothing and leave the step unchanged;
  - `send_nurture_welcome --dry-run` sends and changes nothing; a second real run sends nothing new.
- Locally with `load_dev_data`: end a Boot Camp enrollment and move them to Nurture, send a welcome and a check-in (console email backend), backdate `step_entered_at` in the shell and see the Due count change.
- Before NF4 in prod: dry-run count, and Jeff reads the welcome email text.

## 7. Open items
- **Who answers replies:** `Reply-To` the staff member who sent it, or one shared Hired Labs inbox? A shared inbox survives staff changes. Recommendation: shared inbox, set as a setting.
- **Assignee:** should Nurture enrollments have an assignee (one person owns all check-ins), or be worked as a pool? With IDEA-001, an assignee would get a digest of due check-ins.
- **Cadence:** is 90 days right, and should it slow down over time (e.g. 3, 6, 12 months, then yearly)? A slowing cadence needs a check-in count per enrollment; the design above uses a flat 90 days.
- **DNC everywhere:** setting `Profile.dnc` doesn't end anyone's enrollments. Should it withdraw all open person-flow enrollments? That's wider than Nurture and could be its own bug or idea.
- **Bulk list:** if an occasional announcement to all Nurture people is wanted (e.g. "next boot camp cycle is open"), a CSV export of non-DNC Nurture emails for a mail service is a small add-on. Sending bulk email from the site would need unsubscribe handling and isn't proposed.
- **Who else belongs here:** people triaged but not taken on, and Intake rejections that never responded. Should they be offered Nurture at triage by default?
- **Prod numbers:** the 121 is from 2026-10-19. Recount before NF4.
