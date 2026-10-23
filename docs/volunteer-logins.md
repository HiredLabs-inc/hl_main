# Volunteer Logins (IDEA-005)

Branch `feature/volunteer-logins` (from `develop` at 20bc6a0), worktree `.claude/worktrees/volunteer-logins`.

> **Status:** draft, 2026-10-22. Jeff answered the first round of questions (§6); §3 is updated to match. The new open questions are in §7. Nothing is built yet.

## 1. Context
IDEA-005 in `docs/backlog.md`: let volunteers log in with a limited role. It comes from the signup/login redesign ("no volunteer login yet") and from `docs/cold-apply-staff-redesign.md` §5.5 and §7.

**Today the only role is `is_staff`.** Apart from veteran review, nothing finer-grained exists:

| Gate | Where | What it covers |
|---|---|---|
| `staff_required` / `StaffRequiredMixin` (`userprofile/guards.py:53,93`) | 18 function views + 6 CBVs | `/staff/` dashboard, board, flows, every pipeline action, People, Stuck signups, cold_apply reference-data edits |
| cold_apply `owned_by` / `can_access_participant` (`cold_apply/guards.py:7-18`) | about 30 views | Staff see every participant's jobs, experience and resumes; everyone else sees only their own |
| `can_review_veteran_status` (`guards.py:71`) | DD214 download, veteran status edit, admin `service_doc` | `is_staff` **and** `userprofile.review_veteran_status` (the "Veteran reviewers" group) |
| `app_permission_required(app)` (`guards.py:100`) | releases, rates, and hlagents (on its branch) | Any permission in the app. **Does not need `is_staff`.** |
| Assignee rules | `pipeline/dashboard.py:127` `staff_users()`, `pipeline/services.py:61,106` | Only active `is_staff` users can be assigned |
| Django admin | default | Any `is_staff` user can reach `/admin/` and sees the models they hold permissions on |

**Everyone who isn't staff is treated as a participant:**
- They're listed in People (`userprofile/people.py:38`).
- Onboarding reminders go to them (`userprofile/reminders.py:41`), and the legacy purge can pick them up (`userprofile/purge.py:17`).
- At login they're sent to onboarding (`userprofile/views.py:61-67`). Finishing onboarding creates a `Participant` and starts Intake (`userprofile/models.py:61-68`).

**hlagents tie-in:** hlagents is merged into develop (deca18d). Every `/agents/` page uses `app_permission_required("hlagents")`, and migration `hlagents/0004_agents_group` creates an **Agents** group (view agents and runs, start runs, view/add/change leads) holding all active staff. A volunteer added to Agents can use `/agents/` with no code change. The Funding and Outreach **boards** are tabs on the `/staff/` dashboard, behind `staff_required`, so volunteers can't see them yet (`hlagents.md` H4, "Access"). The first volunteers will use hlagents, so that's where this starts.

## 2. Goals
1. Volunteers log in with their own account and land somewhere useful, not in participant onboarding.
2. What a volunteer can do is set by **groups in Django admin**. Over time a volunteer can do anything a staff member can, one permission at a time.
3. **First use: hlagents** (finding funders and partner orgs to fill boot camp seats). There's no onboarding, triage or job search work at first.
4. When volunteers do get participant work, they see **only the people assigned to them**.
5. **No DD214 or veteran-review access**, whatever groups a volunteer is in.
6. **One login can be both** a participant and a volunteer, for example an alum who comes back to help. Neither role leaks into the other: a volunteer never sees, works or is assigned their own record.
7. Volunteer actions show up in the Activity log like staff actions.

## 3. Design

### 3.1 What a volunteer is
- A normal `User` with **`is_staff=False`**, in a **Volunteers** group. The group is created by a data migration, the same way `userprofile/migrations/0022_review_veteran_status.py` creates Veteran reviewers. Volunteers holds no permissions of its own; it marks the role. Access comes from the other groups a volunteer is in (Agents to start with).
- Why not `is_staff`: it opens `/admin/`, every `staff_required` view, and full cold_apply access in one go. Volunteers get **no Django admin** (§6); groups are managed in admin by superusers, as now.
- Add a helper `is_volunteer(user)` to `userprofile/guards.py` (group membership, cached on the user). Routing, filters and the badge use it; access checks don't.
- DD214s stay safe without new code: `can_review_veteran_status` requires `is_staff`, and `is_staff` stays employee-only after the Staff group move (§3.5). A test pins this, so a volunteer who is somehow given the permission still gets a 403.

### 3.2 Who is a participant
- **A participant is a user whose `Profile.is_onboarded` is true** (§6). Helper `is_participant(user)` in `userprofile/guards.py`.
- A volunteer who started onboarding but never finished is **not** a participant.
- Where non-staff currently means participant:
  - **People** (`people.py:38`) shows non-staff users with a profile or an enrollment, which includes unfinished signups. Change: leave out volunteers who aren't onboarded.
  - **Onboarding reminders** (`reminders.py:41` `unfinished_users`) leave out volunteers, so a volunteer is never nagged to finish onboarding.
  - **Legacy purge** (`purge.py:17`) leaves out volunteers.
- Volunteer accounts are created through the invite (§3.4), so they never go through onboarding or get a `Participant` or an Intake enrollment.

### 3.3 Phase V1: hlagents volunteers
- **Landing:** `user_home` (`userprofile/views.py:57`) checks `is_staff`, then `is_volunteer`, then onboarding. A volunteer lands on a **small volunteer home** (§6), `/volunteer/`: a heading, a card for each tool they have permissions for (Agents; the Funding and Outreach boards), and "My profile" if they're also a participant.
- **Agents:** the invite adds new volunteers to **Agents**. `/agents/` then works with no code change.
- **Lead boards:** volunteers see **every** Funding and Outreach enrollment and who it's assigned to, other volunteers included (§6). The People tabs (My people, Everyone, triage, the person panel) stay staff-only.
  - New permission `pipeline.view_lead_flows`, added to Agents. Staff keep seeing everything through `is_staff` until V2.
  - A volunteer opening `/staff/` gets the dashboard with only the Funding and Outreach tabs. Alternatively, the same views can be served at a `/volunteer/leads/` URL; decide during the build.
  - What volunteers can **do** on those boards (move cards, assign, end) is an open question (§7 Q1).
- **Layout:** volunteers use `staff_base.html` with a nav built from permissions: Agents and Leads yes; People, Stuck signups, Flows, Admin and release notes no (§3.7).
- **Badge:** a "Volunteer" badge next to the name in the timeline actor, the assignee list and board cards, and on People rows for participant-volunteers (§6).

### 3.4 Volunteer invite (V1)
Jeff chose a **staff invite** (§6). It's a staff page, `/staff/volunteers/`:
- **List:** current volunteers (name, email, groups, last login, active), plus pending invites with Resend and Revoke.
- **Invite:** email, first and last name. Sending creates a `VolunteerInvite` (email, name, `invited_by`, `created_at`, `accepted_at`, `user`) and emails a link.
- **Token:** reuse the `make_token`/`read_token` pattern from `userprofile/signup.py` with its own salt (`userprofile.volunteer_invite`) and the same `LINK_MAX_AGE`. It uses its own model, not `PendingSignup`, so signup reminders and expiry (`reminders.py`) never touch invites.
- **Accepting:**
  - **New email:** the page asks for a password, then creates the user with a verified `EmailAddress`, adds Volunteers and Agents, logs them in, and sends them to `/volunteer/`. No onboarding.
  - **Email already has an account** (e.g. a former participant): the link asks them to log in as that account, then adds the groups. Their participant data is untouched (§3.6).
  - **Expired or used:** "ask staff for a new invite", the same way the signup link handles it.
- **Who can invite:** any staff in V1 (`staff_required`). In V2 this becomes a permission, `userprofile.invite_volunteers`, held by the Staff group.
- Other groups (anything past Agents) are added in Django admin.

### 3.5 Phase V2: Staff group and participant work (later)
Only when volunteers get enrollment work.
- **Staff group** (§6): a data migration creates **Staff** with permissions for every staff power and adds every active `is_staff` user. Sketch of the permissions: `pipeline.work_enrollments`, `pipeline.view_lead_flows`, `pipeline.manage_flows`, `userprofile.view_people`, `userprofile.invite_volunteers`, `cold_apply.view_all_participants`, plus the existing Agents group.
  - Every `staff_required` gate becomes a check of one of those permissions (`perm_required(perm)`, a sibling of `app_permission_required`). `StaffRequiredMixin` does the same.
  - `is_staff` then means only "an employee who can reach `/admin/`". The DD214 check keeps requiring it.
  - **New staff** need to join Staff as well as get `is_staff`. To catch anyone missed, `/staff/` can warn on login for `is_staff` users with no Staff group.
- **Assigned-only for people:** a volunteer with `work_enrollments` sees only **person** enrollments assigned to them. Lead enrollments stay fully visible (§3.3).
  - Dashboard and board querysets add `assignee=request.user` for person flows.
  - The quick view, person page and timeline 404 unless the volunteer has an open enrollment for that person assigned to them.
  - In cold_apply, `owned_by` / `can_access_participant` gain a third branch, "assigned to me", and staff go through `cold_apply.view_all_participants` instead of `is_staff`.
- **Assignee choices:** `staff_users()` (`pipeline/dashboard.py:127`) becomes "active users with `work_enrollments`". The checks in `enroll()` and `assign()` (`pipeline/services.py:61,106`) change to match.
- **What volunteers can't do on person enrollments** (unless Jeff says otherwise): reassign to someone else, unassign themselves, or see unassigned enrollments.

### 3.6 Dual role (participant + volunteer)
- One login can be both (§6). A participant-volunteer keeps their participant pages (`welcome`, their resume tools), and the volunteer home links to "My profile".
- **Self-exclusion** (V2):
  - `assign()` and `enroll()` refuse `assignee == enrollment.person`;
  - assignee choices leave out the enrollment's own person;
  - the volunteer visibility filters (§3.5) never show their own record as a staff record. They still see their own data through the normal participant pages.

### 3.7 Navigation and UI
- `staff_base.html` (lines 16, 37) and `base_app.html` (lines 56-67) check `is_staff`. Links should use `perms.<app>` instead. This also fixes BUG-042 (release notes).
- The volunteer home: §3.3.

### 3.8 Audit
- `pipeline.Activity.actor` already records who did what. hlagents leads log to Activity as well (`hlagents.md` §3.6). Volunteer actions need no change, apart from the badge (§3.3).

### 3.9 Offboarding
- **Deactivate** (`is_active=False`) in admin (§6). Login and assignment stop, and the history stays. Enrollments still assigned to them show on the dashboard as "assigned to inactive user", so staff can reassign them.
- A participant-volunteer would lose their participant access too. In that case remove the Volunteers and Agents groups instead.
- Later, a Deactivate button on `/staff/volunteers/`.

## 4. Implementation notes
**V1 files:**
- `userprofile/guards.py`: `is_volunteer`, `is_participant`.
- `userprofile/models.py`: `VolunteerInvite`. Migrations: the Volunteers group, `VolunteerInvite`, and `pipeline.view_lead_flows` on Agents.
- `userprofile/volunteers.py` (new): invite list/send/resend/revoke, accept, and the volunteer home. Templates and invite email under `templates/userprofile/volunteers/` and `templates/account/email/`.
- `userprofile/views.py`: `user_home`.
- `userprofile/people.py`, `reminders.py`, `purge.py`: leave out volunteers who aren't participants.
- `pipeline/views.py`: lead tabs and boards for `view_lead_flows`; People tabs stay `is_staff`.
- `templates/staff_base.html`, `base_app.html`: nav from permissions; volunteer badge partial.

**V2 files:**
- Staff group migration.
- `userprofile/guards.py`: `perm_required`.
- `pipeline/views.py`, `actions.py`, `dashboard.py`, `services.py`: gates, visibility, choices and checks.
- `userprofile/people.py`, `cold_apply/guards.py`, and the cold_apply `StaffRequiredMixin` views.

**Tests:** follow the current pattern (`force_login`, assert 403/404/redirect). Add a `volunteer()` helper next to `reviewer()` (`userprofile/tests/test_service_doc.py:19`). Then:
- invites: send, accept for a new email and for an existing account, expired, reused and revoked links, and no onboarding after accepting;
- `user_home` sends a volunteer to `/volunteer/`, and a 403 for a volunteer on every `staff_required` view except the lead tabs;
- lead tabs show every lead enrollment and its assignee, but not person enrollments;
- the DD214 view gives a 403 for a volunteer, even with the reviewer permission;
- People, reminders and purge leave out volunteers who aren't onboarded, but keep onboarded participant-volunteers;
- V2: a participant-volunteer can't see or be assigned their own enrollment.

Run the tests in docker compose (`-p hl-volunteer`).

## 5. Plan
- **V1, hlagents volunteers:** the Volunteers group, `is_volunteer` / `is_participant`, the invite flow, `user_home` and the volunteer home, lead boards for volunteers, People/reminders/purge filters, the permission-based nav, the badge, and the DD214 guard test. hlagents is already on develop, so this can start once develop is merged into the branch.
- **V2, Staff group and enrollment work:** the Staff group migration, permission gates in place of `is_staff`, assigned-only visibility for people, assignee choices, and self-exclusion. Only when volunteers need it.

## 6. Decisions
| Date | Decision | Why |
|---|---|---|
| 2026-10-22 | Volunteers can do anything staff can, as granted through groups in Django admin | Jeff: permissions differ mostly by group |
| 2026-10-22 | The first volunteer work is hlagents (funders, partner orgs), with no onboarding or job search | Jeff |
| 2026-10-22 | With participant work, volunteers see only people assigned to them by staff | Jeff |
| 2026-10-22 | One login can be both participant and volunteer | Jeff |
| 2026-10-22 | Accounts are created through a staff invite (§3.4), in V1 | Jeff |
| 2026-10-22 | Volunteers land on a small volunteer home | Jeff |
| 2026-10-22 | Volunteers see every lead and lead enrollment, and who it's assigned to, including other volunteers | Jeff: leads are orgs and public contacts |
| 2026-10-22 | No Django admin for volunteers | Jeff |
| 2026-10-22 | Staff powers move into a Staff group too (V2); `is_staff` stays for admin access | Jeff |
| 2026-10-22 | Offboarding is deactivate (remove groups for participant-volunteers) | Jeff |
| 2026-10-22 | A participant is a user who finished onboarding | Jeff |
| 2026-10-22 | Staff see a Volunteer badge | Jeff |
| 2026-10-22 | No volunteer agreement for now | Jeff |

## 7. Open questions
1. **Lead boards:** what can a volunteer do on the Funding and Outreach boards? View only; move cards and add notes; also assign leads to themselves; or everything staff can (assign to anyone, end enrollments)?
2. **Invite groups:** does the invite always add Volunteers + Agents, or should the inviter tick groups on the invite form?
3. **Volunteer to participant:** can a volunteer start onboarding from their volunteer home (for example, a volunteer who wants job search help), or does staff decide that?
4. **Lead board URL:** volunteers see a trimmed `/staff/` dashboard, or a separate `/volunteer/leads/`? Leaning `/staff/` with tabs filtered by permission, because it's less code and V2 needs the same filtering anyway.

## 8. Found along the way
Logged in `docs/bug-log.md` (2026-10-22):
- **BUG-040:** `/resume/resumes/<pk>` has no login check and always returns a 500.
- **BUG-041:** `ConfirmApplicationView` is dead code.
- **BUG-042:** release-notes links show to staff who can't open them. The V1 nav work (§3.7) can fix this.
