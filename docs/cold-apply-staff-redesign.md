# Cold Apply Staff Redesign

Branch `feature/cold-apply-staff-redesign` (from `develop`), worktree `.claude/worktrees/cold-apply-staff-redesign`.

> **How to use this doc:** sections marked **TODO (Jeff)** are for you to fill in. Section 4 is Claude's review of the current code. Strike, keep or move items into Section 5 as you decide on them.

## 1. Context
**DONE (Jeff):** why now, and what prompted it.
It was never finished. The pipeline was a rough draft put up for people to interact with and provide feedback. Some feedback has come, and it needs to be integrated.
The hiredlabs project continues to evolve, and I'm going to need a clean, reusable admin interface to use for different things that are very similar
to what cold apply does.

## 2. Who uses the staff side, and for what
**DONE (Jeff):** the main staff jobs, in order of frequency. For example: triage new signups, move people through phases, find and add jobs, build tailored resumes, log contact.
Nothing is very frequent - there are few users/participants. Staff need to do all that you listed in roughly equal proportions.
This is the general flow, and some of the pain (your table was cumbersome):

1. START -> Someone applies through our site
2. They're profile lands in the "applicants", and an approved administrator reviews their veteran status. Only a certain set of admins will have permissions to review veteran status,
and only they should be able to access DD214s. Other staff should only be able to see the applicant's veteran status. 
3. The profile is then sent to either the boot camp interested section or straight to the resume and job search. This is clunky, becuase we don't always have a boot camp session 
scheduled, but can do resume services whenever. The current setup can leave people in the bootcamp section, and they miss the resume services that they might want.
4. Staff must triage participants, and move them through the phases of whichever process they are in. Ideally, participants should be able to be in two flows at once. 

# 3. Your list
**DONE (Jeff):** the things you already know need doing.

1. There needs to be a way for staff to interact with participant records to move them through the pipeline, both triage and each process flow, without leaving the dashboard.
Currently staff has to open each participant record to do anything with them
2. Only certain staff should be able to access DD214s. They should specific permission, and no one without that reviewer permission should be able to access them at all.
3. There needs to be assignees for each participant, so we can track who's responsible at any given moment.

## 4. Review of what's there (Claude's suggestions)

### 4.1 Current staff surface
- **Pipeline** `cold_apply:index` (`ParticipantListView`, `participant_list.html`): every participant, grouped into one table per Phase. Active phases on top, inactive below.
- **Process** `cold_apply:process` (`PhaseListView`, `process.html`): read-only text describing the Phases and Steps.
- **Participant detail** `participant_detail.html`: profile summary, veteran status, resume link, and New / Open / Closed job lists. Staff and the participant both see this page, with `{% if user.is_staff %}` blocks for staff extras.
- **Update participant** (`ParticipantUpdateView`): a form whose only field is `current_step`.
- **Experience / Education / Bullets / Overviews / Jobs / tailored resume**: shared by staff and participants through `OwnedObjectMixin` / `ParticipantAccessMixin`.
- **Reference data**: Locations (list, detail, create, update), and create/update for Companies, Titles, Concentrations and Positions. There are no list pages for Companies or Titles, and none of them can be deleted.
- **Staff home** `/staff/` and **Stuck signups** `/staff/stuck-signups/`, both outside cold_apply.
- **Django admin only**: Interaction, Application, Phase, Step, Skill, State.

### 4.2 Workflow gaps
1. **No list controls on the pipeline.** It has no search, filter, sort or pagination. Every participant is loaded and rendered, and each phase loops over the whole participant list (`participant_list.html`), which is O(phases × participants).
2. **Participants with no `current_step` never appear on the pipeline.** Every table filters by `participant.current_step.phase == phase`, and the model allows `current_step=None`. `Participant.active` isn't shown or used either.
3. **Moving someone along is slow.** Changing a step means opening a separate page with a dropdown. You can't change it inline from the pipeline, move several people at once, or see when someone entered their current step or how long they've been there.
4. **No contact log.** The `Interaction` model exists (type and notes per participant, recorded by a staff user), but it only appears in admin. The views have `TODO View interactions` comments. Suggestion: a notes/activity timeline on the participant page.
5. **No application tracking.** `Application` (Submitted → Interview → Offer / Rejected / Withdrawn) is also admin-only. `Job.status` and `status_reason` overlap with it. Decide on one model for "where is this application" before building UI.
6. **No staff assignment.** Nothing records which staff member or volunteer owns a participant, so there's no "my participants" view.
7. **No dashboard numbers.** For example: counts per phase, new signups this week, people stuck in a step longer than N days, open jobs per participant. The Impact page might reuse some of these.
8. **Phases and Steps can only be managed in admin.** The pipeline also hardcodes phase titles (`'Boot Camp On-boarding'`, `'Boot Camp Wait List'`) to decide whether to show the Bootcamp Interest column. Better: a flag on Phase, or always show the column.
9. **Reference data is hard to manage.** There's no list, merge or delete for Companies, Titles or Locations. Job imports will create duplicates over time.

### 4.3 Bugs and rough edges spotted (logged as BUG-021 to BUG-030 in `docs/bug-log.md`)
- `participant_detail.html`: the Do Not Contact / Contactable badge checks `object.user.is_staff` (whether the **participant** is staff), so staff viewers never see it. It should probably check `user.is_staff`.
- `participant_detail.html`: `{{ object.phone }}` and `{{ object.email }}` aren't fields on `Participant`, so they always render blank. They should come from `object.user` / `object.user.profile`.
- `participant_detail.html`: "Highest Education" shows `Education...first()` with no ordering, so it isn't really the highest.
- `participant_detail.html`: the navigation block calls `new bootstrap.Collapse(...)` on `#jobs-panel-new-jobs`, which no longer exists now that the panels are `<details>`. That code is dead.
- The "Update Participant Veteran Status" button shows only for superusers, but the view uses `staff_required`. Decide which one is right.
- `participant_list.html`: the date format `"F j, Y: H:m:s T"` uses `m` (month) where it should use `i` (minutes).
- `ParticipantListView.model = Phase`, but it lists Participants. This works only because `queryset` is set.
- `ParticipantDetailView.get_context_data` fetches the participant again (`Participant.objects.get`) and runs separate queries for experience and education. Use `self.object`.
- 23 cold_apply templates extend `staff.html`, but every one of them overrides `block content`, so staff.html's Bootstrap navbar never renders. staff.html is effectively just `base_app.html`. `staff.html` and `process.html` still use Bootstrap markup (`navbar`, `dropdown-item`, `btn btn-primary`) on a Tailwind base.
- `cold_apply/index.html` is a leftover CRUD to-do list and isn't routed anywhere.
- The URL `companiies/<pk>/update/` is misspelled. There are also many `confirm_*` routes that all point to one generic `ConfirmCreateView`. Redirecting back with a Django message would remove most of them.
- `OrganizationCreateView`, `TitleCreateView`, `PositionCreateView`, `ConcentrationCreateView` and `LocationCreateView` are only `LoginRequired`, so any participant can create shared reference data. That may be intended because participants pick titles and companies, but confirm it.
- `LocationDetailView` and `LocationListView` are `LoginRequired`, not staff-only.

### 4.4 Structural suggestions
- **Split the staff and participant views of a participant.** One template full of `is_staff` branches is hard to redesign. A staff "participant workspace" (summary, phase/step, notes timeline, jobs, resume tools, actions) could live under `cold_apply/staff/...` and reuse partials from the participant pages.
- **Use one staff layout.** Make a real `staff_base.html`: Tailwind, staff nav (Pipeline, Participants, Stuck signups, Jobs, Reference data, Process, Admin), and Django messages in place of the confirm pages.
- **Do list pages with htmx.** Search, filter and sort as GET params, with htmx swaps of the table body (the codebase already uses `HtmxViewMixin`). Paginate.
- **Add a kanban option for the pipeline.** Columns per Phase, cards per participant, and a step change through a small POST. This is optional and depends on how many participants are active.
- **Add tests as you go** in `cold_apply/tests/test_views.py` / `test_access.py`. Staff-only access should be covered for every new staff view.

## 5. Proposed design
**DRAFT (Claude), 2026-10-19:** for Jeff to review. It's built from §2 and §3. Choices that need your call are marked **[decide]** and also listed in §7.

### 5.0 Core idea
Today a participant has a single `current_step`, so they can be in only one place. Phases also mix process stages ("Phase 2") with statuses ("Nurture", "Do Not Contact"). The design separates three things:

1. **Person.** Who they are: the `User`, `Profile` and veteran status. This is shared across all programs.
2. **Flow.** A process someone can go through, for example **Intake**, **Resume & Job Search** (today's cold apply) or **Boot Camp**. A flow is data (phases and steps), not code, so a future program becomes a new flow rather than a new app. This is the reusable admin interface from §1.
3. **Enrollment.** One person in one flow. It records the current step, assignee, status and dates. A person can have several active enrollments at once (§2.4), for example Boot Camp (waitlisted) and Resume & Job Search (in progress).

```
Person (User + Profile)
 ├─ Enrollment: Intake               step: Verify Vet Status  assignee: —        status: active
 ├─ Enrollment: Boot Camp            step: Waitlist           assignee: Sam      status: active
 └─ Enrollment: Resume & Job Search  step: Write bullets      assignee: Alex     status: active
Activity timeline (notes + every step/assignee/status change, who and when)
```

### 5.1 Information architecture / navigation
A new `staff_base.html` (Tailwind, Django messages, staff-only nav) replaces `staff.html` for every staff page:

- **Dashboard.** The home for staff work (§5.2).
- **People.** Search everyone: participants, applicants and people who have finished.
- **Stuck signups.** Existing page; it moves under the new nav.
- **Flows.** Read-only process description (today's `process` page), one section per flow.
- **Reference data.** Companies, titles, locations (§5.6).
- **Admin.** Superusers only.

The participant-facing pages (their own profile, jobs, experience and resume tools) stay on `base_app.html` and are not part of this redesign. Staff stop sharing the participant's detail template (§5.3).

### 5.2 Dashboard (your list #1: work without leaving the page)
One page at `/staff/`, with tabs:

- **Intake.** New applicants, grouped by intake step: *Verify Veteran Status → Triage* (from the prod Applicants phase).
- **One tab per active flow.** Enrollments grouped by phase, then step.
- **My people.** Every enrollment assigned to me, across flows.

Each row shows: name, flow step, assignee, veteran status badge, DNC badge, **days in step**, last activity. Filters are GET params, so views can be bookmarked: assignee (me / unassigned / anyone), phase, status, "in step > N days", and name/email search. At current volumes there is no pagination; add it later if needed.

**Inline actions (htmx, no page change):**
- **Step:** a dropdown on the row. A POST saves the change, logs an Activity entry and swaps the row.
- **Assignee:** a dropdown of staff users. It is logged the same way.
- **Note:** opens a small inline form and adds a timeline entry.
- **More…** Pause / complete / withdraw the enrollment, or **enroll in another flow**.
- **Triage (Intake tab):** an "Enroll in…" control with checkboxes for Boot Camp and Resume & Job Search (both allowed). Saving it creates those enrollments and completes the Intake enrollment. This fixes §2.3: nobody is left stuck in the boot camp section without resume services.
- **Quick view:** clicking a name opens a **side drawer** (an htmx partial) with the profile summary, all enrollments and the timeline. The full workspace (§5.3) is one click further, for heavier work.

A small header strip shows counts: awaiting veteran review, awaiting triage, unassigned, and in step > N days. These counts link to the matching filters.

A kanban board (columns per phase, drag between steps) is an optional second view of a flow tab later. The table comes first because it does filters and inline dropdowns well.

### 5.3 Participant workspace (staff)
A new staff-only page (`cold_apply/staff/people/<pk>/`) replaces the staff use of `participant_detail.html`:

- **Header:** name, email, phone, city/state, DNC badge, veteran status badge (shown to all staff) and each enrollment's assignee.
- **Enrollments:** one card per flow with the same step/assignee/status controls as the dashboard, plus an "Enroll in another flow" button.
- **Veteran status panel:** visible to all staff as read-only status. **Only reviewers** (§5.4) get the DD214 link and the verify/unverify controls.
- **Activity timeline:** notes and system events, newest first, with an "Add note" form.
- **Work tools:** links to the existing jobs, experience/education, bullets and tailored resume pages. These keep working as they do now.
- **Profile details:** special training, skills, job links, work preferences, uploaded resume.

### 5.4 Veteran status and DD214 access (your list #2, BUG-021)
- New permission `userprofile.review_veteran_status`, granted through a **"Veteran reviewers"** group.
- **Reviewers only:** open the DD214, and change `veteran_verified` / `is_veteran`. Everyone else, including other staff, sees only the badge (Verified / Not verified / Not a veteran).
- **One door to the file:** a view `GET /staff/people/<pk>/service-doc/` checks the permission, logs an Activity entry ("Alex opened the DD214"), and redirects to a ~10-minute signed URL. Pages never contain a signed URL for someone without the permission.
- **Django admin:** remove `service_doc` from `ProfileAdmin` and `VeteranProfileAdmin` for anyone without the permission (`get_exclude`). Otherwise admin's GCS link is a 24-hour signed URL that any staff member with Profile access can open.
- **Storage:** move new DD214 uploads to their own prefix (`service_docs/`) instead of the shared `uploads/`. Also confirm the GCS bucket has no public access (§7).
- **Intake:** the *Verify Veteran Status* step can only be completed by a reviewer. The step model gets an optional `required_permission`, and the dashboard hides or disables that step change for other staff.
- **Superusers:** have access to everything, including DD214s (normal `has_perm` behaviour). At launch the reviewer group is empty, because Jeff is a superuser. Yes - superusers will be a small, trusted group, and should have full access to everything.

### 5.5 Assignees (your list #3)
- **Default: the assignee is on the Enrollment.** "Who's responsible right now" can differ per flow, for example a boot camp lead versus a resume writer. The participant header shows all of them.
- Assignee choices: active users with `is_staff`. Volunteers aren't users yet (signup redesign decision), so this can expand later.
- Every change is logged as an Activity entry, so the history of who was responsible when is kept.
- Unassigned enrollments are counted on the dashboard header and can be filtered.
- Optional later: email an assignee when something is assigned to them, or when an enrollment sits in a step longer than N days. This reuses the daily reminders command from the signup redesign.

### 5.6 Notes, activity and reference data
- **Activity** replaces `Interaction` (which is admin-only today, with no views). Each entry has: person, optional enrollment, kind (note, email, phone, in person, step change, assignee change, status change, DD214 opened), text, `from`/`to` values, who, when. Existing `Interaction` rows are migrated over as notes.
- **Flows, phases and steps:** stay managed in Django admin for now, since they rarely change. The "Flows" page is read-only.
- **Companies / titles / locations:** out of scope for the first pass. Later: list, merge duplicates, delete. BUG-030 (participants creating reference data) needs a call first.
- **Jobs and applications:** out of scope, except that the unused `Application` model is dropped. `Job.status` / `status_reason` stay. Agreed with recommendation

### 5.7 Data model changes
| Change | Notes |
|---|---|
| New `Flow` (name, slug, description, active, order) | Seeded: Intake, Resume & Job Search, Boot Camp |
| `Phase.flow` FK | Existing phases go under Resume & Job Search |
| `Step.required_permission` (optional char) | For the Intake *Verify Veteran Status* step |
| New `Enrollment` (person→User, flow, current_step, assignee→User, status: active/paused/rejected/no_show/completed/withdrawn, started_at, step_entered_at, ended_at) | Only one non-ended enrollment per (person, flow) |
| New `Activity` (person, enrollment?, kind, text, from/to, actor, created_at) | Replaces `Interaction` |
| Permission `userprofile.review_veteran_status` + "Veteran reviewers" group | Data migration creates the group |
| Retire `Participant.current_step` | Data migration following the Step 3 mapping (built from prod rows) |

**Where the code lives (decided: new app):** put the cod in a new pipeline app this proposal puts Flow/Enrollment/Activity in a **new small app (`pipeline`)** keyed on `User`, with no imports from cold_apply. The dashboard, row partials and `staff_base.html` go there too. Cold apply then becomes the Resume & Job Search flow plus its job and resume tools, and a future program needs only new flow data and its own tools. The alternative is to keep everything inside `cold_apply`. That's faster to start but not reusable.

`Participant` stays for now, because jobs, bullets, experience and the other tools point at it. It can be folded into `User`/`Profile` later.

## 6. Decisions
| Date | Decision | Why |
|---|---|---|
| 2026-10-19 | Staff move people through triage and flows from the dashboard, without opening each record | §3.1 |
| 2026-10-19 | DD214s are visible only to holders of a veteran-reviewer permission; other staff see status only | §3.2 |
| 2026-10-19 | Each participant has a tracked assignee | §3.3 |
| 2026-10-19 | A participant can be in more than one flow at once (e.g. Boot Camp and resume services) | §2.4 |
| 2026-10-19 | One assignee per enrollment | Responsibility differs per flow |
| 2026-10-19 | Intake is a flow; programs are modelled as flows | Uniform and reusable |
| 2026-10-19 | New `pipeline` app keyed on `User`; dashboard at `/staff/` | Reusable admin interface (§1) |
| 2026-10-19 | Boot Camp enrollments link to a `BootCampSession`; no session means waitlist | Boot camp sessions aren't always scheduled |
| 2026-10-19 | Superusers get everything, including DD214s; reviewer group starts empty | Jeff is the only reviewer today |
| 2026-10-19 | Drop `Application` | Unused |
| 2026-10-19 | Participants keep create rights on reference data (BUG-030) for now | Needed for adding experience; revisit with the self-service portal |

## 7. Open questions
- **Where is the assignee recorded?** The draft puts one assignee on each enrollment; the alternative is one per participant.
**Answer** One assignee on each enrollment.
- **Should Intake be a flow?** The draft models intake (Applied → Veteran review → Triage) as a flow, rather than as status fields on the profile.
**Answer** Yes, Intake should be a flow, and flows in general are a good idea
- **New app or inside cold_apply?** The draft proposes a new `pipeline` app keyed on `User`.
**Answer** New app like the draft proposes
- **URL for the dashboard:** `/staff/` or `/cold_apply/staff/`?
**Answer** `/staff/`
- **Boot Camp and cohorts:** should a Boot Camp enrollment link to a `BootCampSession` once one is scheduled, with "Waitlist" meaning no session yet?
**Answer** Yes
- **DD214 access for superusers:** should superusers get DD214 access automatically, or only through the reviewer group (a custom check rather than `has_perm`)?
**Answer** Superusers should have access to all things, including DD214
- **Who is in the "Veteran reviewers" group** at launch?
**Clarifying question with possible answer** Do you mean which user(s) by name? Honestly, it's just me now, but there will be others in the future.
**Reply (Claude):** yes, by name. You're a superuser, so the group can start empty and people are added in admin later.
- **Is the GCS media bucket private?** If any public access exists, fixing it comes before anything else here.
**Answer** Not sure - can you check?
**Checked (Claude, 2026-10-19):** both are private. `hiredlabs-prod-media` and `hiredlabs-stage-media` have public access prevention `enforced` and uniform bucket-level access, with no `allUsers` or `allAuthenticatedUsers` bindings. The only bucket grant is `objectAdmin` to the app's service account. Project owners and editors (read and write) and project viewers (read) also have access through the default legacy bucket roles, and Jeff is the only project owner on prod. This matches Terraform (`infra/terraform/modules/hl-env/main.tf`).
- **Who counts as staff:** only `is_staff`, or volunteers later? The signup redesign decided "no volunteer login yet".
**Answer** There will be volunteers, but any time really soon.
- **`Application` model:** drop it as unused, or replace `Job.status`/`status_reason` with it?
**Answer** Drop `Application`
- **Shared reference data:** should participants be able to create Companies, Titles and Locations (BUG-030), or only staff?
Participants can now, because that's how experience is added - manually - and the intent is to eventually have particapants access certain tools through a self-service portal.
That portal and access level don't exist yet, and only staff does any of the creation of those items now.  

### New questions from the prod data (2026-10-19)
- **Nurture as a flow?** 121 people are in Nurture → Monthly Newsletter, and Boot Camp Alumni is there too. The draft makes Nurture its own flow, so staff can filter and act on it like any other. The alternative is a paused status on another enrollment.
**Answer (Jeff):** Nurture is its own flow, but it isn't defined yet. "Monthly Newsletter" is a placeholder; there is no newsletter.
- **Do Not Contact:** 81 people are on *Do nothing*, but only 1 profile has `dnc=True`. Should the migration set `dnc=True` for all 81, and drop the Do Not Contact phase?
**Answer (Jeff):** yes. Mark them do not contact, and drop the phase.
- **"Send Rejection Message"** appears in both Phase 4 and Boot Camp On-boarding, and Phase 4 also has **"No Show"**. These are copied as they are. Should they become enrollment outcomes (status *withdrawn* / *completed* with a reason) instead of steps? The draft copies them now and leaves that for later.
**Answer (Jeff):** "Send Rejection Message" is a step today because someone has to act, and the rejection isn't final. Applicants sometimes upload the wrong service document or an unclear DD214, and the soft rejection lets them fix it. It could be an outcome that leaves people in "rejected" until they respond. "No Show" can be an outcome too.
**Resulting design (Claude):** two new enrollment statuses. **`rejected`** is a soft rejection that can be undone: the enrollment keeps its step, and staff set it back to `active` when the participant responds. **`no_show`** is the other. Setting `rejected` from the dashboard prompts for a reason (e.g. "unclear DD214"), which is saved to the Activity timeline. Sending the message itself stays a manual task for now. The "Send Rejection Message" and "No Show" steps are not copied.

## 8. Plan
**DRAFT (Claude), 2026-10-19.** Each step ends with passing tests and can be merged to develop on its own. Step 1 doesn't depend on the rest and goes first. Ask before each commit.

### Step 0 — Working environment
- Tests run in Docker under their own compose project:
  - `docker compose -p hl-cold-apply build django`
  - `docker compose -p hl-cold-apply run --rm frontend sh -c "npm ci && npm run build"`
  - `docker compose -p hl-cold-apply run --rm django python manage.py test`
- Baseline on `develop` (7aa936b, 2026-10-19): 114 tests, all passing.
- **Prod Phase and Step rows: done 2026-10-19.** Read-only `manage.py shell` query run through the `hl-prod-manage` Cloud Run job (execution `hl-prod-manage-xl84x`), with Jeff's approval. Only counts were read, no personal data. Step 3's mapping comes from these rows, not from the dev seed.

**Prod phases and steps (2026-10-19).** Step ids in brackets; *n* = participants on that step now.

| Phase (id, order) | Steps in order |
|---|---|
| Applicants (10, 0) | Verify Veteran Status [14] |
| Phase 1 (1, 0) | Send Initial Email [1] · Fill out intake form [2] (Participant) · Intake Call [3] · Conduct Intake Call [4] |
| Phase 2 (2, 1) | Create Initial Job List [5] *n=2* · Analyze keywords in job posts [6] · Write tailored bullets and overview [7] |
| Phase 3 (3, 2) | Send Initial Job and Resume Set [8] *n=1* · Offer Resume & Job Search [25] · Give Feedback on Initial Packet [9] (Participant) · Review for Resume Service [22] |
| Phase 4 (4, 3) | Apply to Jobs [10] · No Show [32] *n=1* · Send Rejection Message [23] |
| Phase 5 (5, 4) | Send End-of-Process Comms [11] |
| Boot Camp On-boarding (8, 3) | Send Commitment Form [15] *n=1* · Send Rejection Message [17] · Send Waitlist 1 Message [18] · Send Waitlist 2 Message [24] · Fill out Commitment Form [20] *n=1* · Send Enrollment Confirmation [19] · Send Calendar Invite [28] · Send pre-course survey [26] · Send Instructor Intro [21] · Active Student [27] |
| Boot Camp Wait List (9, 4) | Priority Enrollment - Next Cycle [31] · Never Committed [29] · Make Way for Enlisted [16] *n=5* |
| Nurture (6, 0, inactive) | Boot Camp Alumni [30] · Monthly Newsletter [12] *n=121* |
| Do Not Contact (7, 1, inactive) | Do nothing [13] *n=81* |

Other facts from the query:
- 213 participants, and every one has a step (BUG-024 doesn't occur in prod today).
- 0 `Interaction` rows and 0 `Application` rows.
- 0 `BootCampSession` rows.
- 182 profiles have `bootcamp=True`.
- Only **1** profile has `dnc=True`, although 81 participants are on *Do nothing*.
- Several phases and steps share an `order` value (for example, three phases have order 0). That ambiguity is BUG-031.

### Step 1 — Lock down DD214s (fixes BUG-021, BUG-027, BUG-028) — done 2026-10-19, not yet deployed
- Add the permission `review_veteran_status` to `Profile.Meta.permissions`. A data migration creates an empty **"Veteran reviewers"** group that holds it. Jeff is a superuser, so `has_perm` already passes for him. Others are added to the group in admin as they join.
- New view `service_doc` (`/staff/people/<user_pk>/service-doc/`, in `hl_main/urls.py` beside the stuck-signups pages):
  - Users without the permission get a 403. For reviewers, it logs who opened which document (to the `hl_main.audit` logger, kept at INFO in `cloud.py`; it moves to Activity in Step 7) and redirects to a signed URL that lasts about 10 minutes.
  - In DEBUG it streams the local file instead, so dev no longer links straight to `/media/`.
- `update_veteran_status_view` requires the permission. The page and the participant page link to the file only through the new view. The participant page shows the update button only to holders of the permission (BUG-027).
- Admin: `get_exclude` hides `service_doc` on `ProfileAdmin` and `VeteranProfileAdmin` for anyone without the permission. Fix `ProfileAdmin.search_fields` / `list_filter` (BUG-028).
- New uploads go to `service_docs/` (change `upload_to`; existing files stay where they are).
- **Tests:** staff without the permission get 403 on the view and the page, and see no file field in admin. Reviewers and superusers get a redirect. The participant page shows the button only to the right users.

### Step 2 — `pipeline` app: models and services — done 2026-10-19
- New app `pipeline`. It imports nothing from `cold_apply`.
- **Models:**
  - `Flow`.
  - `Phase` and `Step`: new copies in `pipeline`, not moved, so the old cold_apply tables keep working until Step 9. `Step` gains `required_permission`.
  - `Enrollment`: person, flow, current_step, assignee, status, started_at, step_entered_at, ended_at. A conditional `UniqueConstraint` allows one non-ended enrollment per (person, flow).
  - `Activity`.
  - All of them registered in admin.
- **`pipeline/services.py`:** `enroll`, `move_to_step`, `assign`, `set_status`, `add_note`, `complete_triage`, plus `record_document_opened` for Step 7. Each one runs in a transaction, writes its Activity row and checks `required_permission`. Every UI path calls these functions; no view writes enrollments directly.
- **Tests:** each service function, the uniqueness constraint, the permission-gated step, and an Activity row written for every change.

### Step 3 — Seed flows and migrate existing data (fixes BUG-024) — done 2026-10-19
- **The data migration builds the flows from the prod rows in Step 0.** It copies phase and step titles, descriptions, owners and order. Steps that share an order value are ordered by id and renumbered.

| New flow | Built from (prod phase → steps) | Added |
|---|---|---|
| **Intake** | Applicants → Verify Veteran Status (gets `required_permission`) | A final **Triage** step |
| **Resume & Job Search** | Phases 1–5 and all their steps | — |
| **Boot Camp** | Boot Camp On-boarding (10 steps) and Boot Camp Wait List (3 steps), as two phases | — |
| **Nurture** | Nurture → Boot Camp Alumni. *Monthly Newsletter* is a placeholder, so it becomes a generic **Nurture** step until the flow is defined (IDEA-006) | — |

- **Existing participants:**
  - Each one gets one enrollment in the flow that now holds their current step, on the copied step. Phases 1–5 go to Resume & Job Search, the boot camp phases go to Boot Camp, and Nurture goes to the Nurture flow.
  - **Do Not Contact / Do nothing (81 people):** no enrollment. Their `Profile.dnc` is set to `True` (Jeff, 2026-10-19), and the phase is dropped.
  - **Rejection and No Show steps:** these steps are not copied (no one is on a rejection step today). The 1 participant on *No Show* gets a Resume & Job Search enrollment at *Apply to Jobs* with status `no_show`.
  - Participants with no step (BUG-024; none in prod today) get an Intake enrollment at Triage, so staff would see them.
  - `step_entered_at` starts as `Participant.updated_at`, the best value available.
- `Interaction` rows become Activity notes. Prod has none, but the code path stays for dev and stage data.
- **Tests:** run the migration on factory data that covers every mapping case, including the DNC case and tied order values. Before the prod deploy, also run it on a copy of stage data. Then rerun the Step 0 query on prod to confirm no phases or steps were added since 2026-10-19.
- **As built** (`pipeline/migrations/0002_seed_flows.py`):
  - Old phases are matched to flows by title: *Applicants* → Intake, *Phase N* → Resume & Job Search, *Boot Camp …* → Boot Camp, *Nurture* → Nurture, *Do Not Contact* → `dnc`. **Any other phase title stops the migration** with an error naming it, rather than guessing. Because deploys auto-migrate, the prod recheck matters: a new phase would fail the deploy.
  - People on *No Show* or *Send Rejection Message* stay on the copied step before it in the same phase, with status `no_show` or `rejected`. That puts the prod No Show participant on *Apply to Jobs*, as agreed.
  - Each migrated enrollment gets an `enrolled` Activity ("Moved from the old Cold Apply steps") with no actor, plus a `status_change` entry for no show or rejected. DNC people get a note instead. The enrollment's `created_at` is the participant's `created_at`.
  - `Participant.active` is ignored: it is only shown in admin and nothing else reads it.
  - On a fresh database (tests, new dev setups) there are no old phases, so Intake gets *Applicants: Verify Veteran Status, Triage* and each other flow gets a single placeholder step named after it.
  - Reversing the migration deletes all pipeline rows. It leaves `Profile.dnc` alone, since one profile was already marked before.
  - `load_dev_data` still creates only old cold_apply phases, so dev participants have no enrollments until Step 4 or 5 updates it.

### Step 4 — New signups enter Intake — done 2026-10-19
- `Profile.handle_onboard_complete` still creates the `Participant`, which the job and resume tools need. It no longer picks "the first step" (BUG-031: ties can drop new signups into Nurture). It creates an Intake enrollment at *Verify Veteran Status*. A non-veteran goes straight to *Triage*.
- Verifying a veteran (Step 1 page) offers "Verified, move to Triage", which calls `move_to_step`.
- **Tests:** onboarding creates exactly one Intake enrollment, and running it again doesn't duplicate it (keep the BUG-003 behaviour).
- **As built** (`userprofile/intake.py`):
  - Onboarding enrolls the person in Intake only if they have **no enrollment in any flow**. Running onboarding again, or onboarding someone already moved into another flow by Step 3, adds nothing.
  - The start step is the first Intake step. For non-veterans (`is_veteran=False`), a first step gated by the veteran review permission is skipped. Steps are found by flow and permission, not by title, so renaming them in admin doesn't break this.
  - The person is recorded as the actor on their own `enrolled` entry.
  - If the Intake flow is missing, onboarding still completes and an error is logged.
  - `Participant.current_step` is still set for the old staff pages, which are removed in Step 9. It now uses the old *Verify Veteran Status* step if one exists, instead of "the first step" (BUG-031).
  - On the veteran status page, the button is labelled with the next step ("Verified, move to Triage"). It appears only while the person's Intake enrollment is on the gated step. It sets `veteran_verified` and calls `move_to_step` in one transaction.
  - `Step.next_step()` was added to the pipeline model.

### Step 5 — Staff layout and read-only dashboard at `/staff/` — done 2026-10-19
- Add `staff_base.html`: Tailwind, staff nav (§5.1) and Django messages. Today's `/staff/` app list (`staff_home.html`) moves into the nav.
- `/staff/` shows tabs for Intake, each active flow, and My people. Filters (assignee, phase, status, in step > N days, search) are GET params, and the table body is swapped with htmx. The count strip links to filters. Rows come from a single partial, which Step 6 reuses.
- Old `cold_apply:index` redirects to `/staff/`.
- **Tests:** staff-only access, each filter, and a fixed query count with 50 enrollments.
- **As built:**
  - **Layout:** `templates/staff_base.html` has a navy staff bar with Dashboard, Stuck signups and Flows, plus a menu with tools (World Rates, public site, release notes per app), Admin for superusers, and account links. `staff.html` now just extends it, so the veteran status, stuck signups and World Rates pages get the new nav. On phones the links move to a second row.
  - The old `staff_home.html` app list and `userprofile.views.staff` are gone.
  - **Dashboard** (`pipeline/views.py`, `pipeline/dashboard.py`):
    - Tabs: Intake, each other active flow, My people, and **Everyone**. Everyone was added so the "Unassigned" and "In step over 14 days" counts have a cross-flow view to link to.
    - The count strip has one card per Intake step (e.g. "In Verify Veteran Status"), then Unassigned and "In step over 14 days".
    - Filters: search (every word must match name or email), assignee, phase (flow tabs only), step, status (blank = all open), and days in step. They are a Django form read from GET params. The form fires htmx on `input` with a 300 ms delay and pushes the URL.
    - Rows are grouped by step on flow tabs and by flow on My people and Everyone. Each row comes from `pipeline/partials/enrollment_row.html` (`id="enrollment-<pk>"`) for Step 6.
    - Veteran reviewers get a "Review veteran status" link on gated rows.
    - Names link to the old participant page until Step 7.
  - **Flows page** at `/staff/flows/`: each active flow's phases and steps, with open counts linking to the dashboard. It replaces the old `process` page in the nav; that page still exists.
  - `cold_apply:index` redirects to `/staff/`, and the old `participant_list.html` is deleted.
  - `load_dev_data` now enrolls its 5 participants across the flows.
  - **Gotcha:** `Meta.ordering` doesn't apply to GROUP BY queries, so the annotated step queries order explicitly.
  - Tailwind now scans `pipeline/` templates and `.py` files.

### Step 6 — Inline actions and quick view — done 2026-10-19
- **Row controls:**
  - Step dropdown, assignee dropdown, note, and pause/complete/withdraw: each is an htmx POST to a small view that calls the service function and returns the updated row.
  - Steps the user lacks permission for are disabled.
- **"Enroll in…":** on any row, plus the triage form on the Intake tab, with checkboxes for Boot Camp and Resume & Job Search.
- **Side panel:** quick view with profile summary, enrollments and timeline, opened from the name.
- **Tests:** each action, including permission refusal, a CSRF-protected POST and a 404 for a missing enrollment. One Playwright smoke test of triage from the dashboard.
- **As built** (`pipeline/actions.py`, URLs under `/staff/` in `pipeline/urls.py`):
  - The step and assignee are dropdowns in their cells. The step dropdown is disabled when the user can't leave the current step, and its tooltip says why.
  - "⋯" opens an actions row under the person, not a dropdown menu, because a menu would be clipped by the table's scroll container. The actions row has:
    - a note form, with kind note, email, phone or in person;
    - status buttons: Make active, Pause, No show, Reject with a required reason, and Complete or Withdraw, which ask for confirmation because they can't be undone;
    - **Triage** on Intake rows, and **Enroll in…** on other rows.
  - Intake rows don't offer "Enroll in…", so nobody can skip veteran review that way. Rows on Verify Veteran Status say "Triage opens once veteran status is reviewed."
  - Each action returns the updated row. It also sends an htmx `enrollment-changed` event, which makes the table (with the current filters) and the count strip reload, so moved or ended rows land in the right place.
  - Refusals (validation or permission) return 200 with `HX-Reswap: none` and an error toast through the existing toaster. The page doesn't change.
  - **Side panel:** clicking a name opens a drawer with profile badges and details, all enrollments, the last 50 timeline entries and a note form. Escape, the backdrop or Close shuts it. It links to the old participant page ("Open full page") until Step 7.
  - **Gotcha:** `hx-include` is inherited. The table container includes the filter form for its refresh, so it sets `hx-disinherit="*"`. Otherwise every row control also posts the filters' empty `step`.
  - On phones the table scrolls sideways, and the actions row stays pinned on screen.

### Step 7 — Staff participant workspace and People search
- `/staff/people/` (search) and `/staff/people/<pk>/` (§5.3): header, enrollment cards, veteran panel (DD214 link only with the permission), timeline, profile details, and links to the existing work tools.
- DD214 opens are now logged as Activity.
- Staff links to `participant_detail` point to the workspace. The staff-only blocks are removed from `participant_detail.html`, which becomes participant-only. This fixes BUG-022, BUG-023 and BUG-025 by replacing the code that has them.
- **Tests:** access, every panel renders with missing profile data, and the DD214 link is hidden without the permission.

### Step 8 — Boot camp sessions
- Link Boot Camp enrollments to `BootCampSession` on the userprofile side (`BootCampSession.enrollments`, at most one session per enrollment), so `pipeline` stays generic. An enrollment with no session is on the waitlist.
- Assign a session from the row or the side panel, which moves the enrollment to *Session assigned*. The Boot Camp tab gets a session filter.
- **Tests:** assigning a session, the waitlist filter, and one session per enrollment.

### Step 9 — Cleanup (fixes BUG-026, BUG-029)
- Remove `Participant.current_step` and cold_apply `Phase`, `Step`, `Interaction` and `Application` (dropped, §7). Remove `ParticipantListView`, `PhaseListView`, `participant_list.html`, `process.html`, `staff.html`, `cold_apply/index.html`, `ParticipantUpdateView` and its form.
- Old URLs redirect. `process` becomes the read-only Flows page.
- Fix the `companiies` URL typo.
- Update `load_dev_data`, `dev_seed.json` and `cold_apply/tests/factories.py` for flows and enrollments.
- **Tests:** full suite; no references left to the removed models (`grep`).

### Step 10 — Rollout
- Deploy to stage (`git push origin develop:staging`, done by Jeff). Check the Step 3 migration against stage data, then go through the dashboard as a staff user without the permission and as a superuser.
- **Prod checklist:** rerun the Step 0 query and confirm the mapping still holds, take a database backup before deploying (deploys run migrations automatically), and add any reviewers to the group.
- Update the bug log entries to `Fixed` with their commits.

### Not in this plan
Tracked in `docs/backlog.md`: IDEA-001 assignee notifications, IDEA-002 kanban view, IDEA-003 reference data management, IDEA-004 self-service participant portal (and BUG-030), IDEA-005 volunteer logins.

## 9. Status
- 2026-10-19: worktree and doc created; review in Section 4.
- 2026-10-19: §1–3 filled in by Jeff; bugs logged (BUG-021–030); §5 drafted for review.
- 2026-10-19: §7 answered by Jeff; bucket checked (private); §5 updated to match; §8 drafted for review.
- 2026-10-19: prod phases/steps read (Step 0); Step 3 mapping built from them; new questions added to §7; BUG-031 logged; left-out items moved to `docs/backlog.md`.
- 2026-10-19: Jeff answered the prod-data questions (Nurture flow, DNC, soft rejection / no show as statuses); Step 1 started.
- 2026-10-19: Step 1 implemented: 129 tests passing (15 new in `userprofile/tests/test_service_doc.py`); migration `userprofile/0022` checked both ways.
- 2026-10-19: Step 1 merged into develop (fcca49a); it reaches prod with the next release, not 3.2.3.
- 2026-10-19: Step 2 implemented: `pipeline` app (Flow, Phase, Step, Enrollment, Activity; migration `pipeline/0001`), services, and admin. Enrollment and Activity are read-only in admin so the timeline stays complete. 158 tests passing (29 new).
- 2026-10-19: Step 2 committed (99005ff). Step 3 implemented: data migration `pipeline/0002_seed_flows` with 10 tests built on the prod phase/step shape; checked forward, back and forward on the dev database. 168 tests passing. The known flaky `JobFactory` error (already in the bug log) showed up once.
- 2026-10-19: Step 3 committed (4d8a610). Step 4 implemented: signups enter Intake, and veteran reviewers get a verify-and-advance button. 180 tests passing.
- 2026-10-19: Step 4 committed (1cc7b0c). Step 5 implemented: staff layout, dashboard and Flows page; checked in a browser at desktop and phone widths. 197 tests passing.
- 2026-10-19: Step 5 committed (219cdfd). Step 6 implemented: row controls, triage, side panel; 2 Playwright tests; checked in a browser. 225 tests passing.
