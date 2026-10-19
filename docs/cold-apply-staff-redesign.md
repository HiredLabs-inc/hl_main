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
 ├─ Enrollment: Intake               step: Veteran review     assignee: —        status: active
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
One page, `/staff/` (or `/cold_apply/staff/`; **[decide]**), with tabs:

- **Intake.** New applicants, grouped by intake step: *Applied → Veteran review → Triage*.
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
- **Intake:** the *Veteran review* step can only be completed by a reviewer. The step model gets an optional `required_permission`, and the dashboard hides or disables that step change for other staff.
- **Superusers:** they pass Django permission checks automatically. That's acceptable if superusers stay a short list. **[decide]**

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
- **Jobs and applications:** out of scope. Recommend dropping the unused `Application` model and keeping `Job.status` / `status_reason`. **[decide]**

### 5.7 Data model changes
| Change | Notes |
|---|---|
| New `Flow` (name, slug, description, active, order) | Seeded: Intake, Resume & Job Search, Boot Camp |
| `Phase.flow` FK | Existing phases go under Resume & Job Search |
| `Step.required_permission` (optional char) | For the Intake *Veteran review* step |
| New `Enrollment` (person→User, flow, current_step, assignee→User, status: active/paused/completed/withdrawn, started_at, step_entered_at, ended_at) | Only one non-ended enrollment per (person, flow) |
| New `Activity` (person, enrollment?, kind, text, from/to, actor, created_at) | Replaces `Interaction` |
| Permission `userprofile.review_veteran_status` + "Veteran reviewers" group | Data migration creates the group |
| Retire `Participant.current_step` | Data migration: each Participant gets an Enrollment in Resume & Job Search at its current step. Participants in "Nurture" or "Do Not Contact" become paused enrollments; DNC already lives on `Profile.dnc` |

**Where the code lives [decide]:** this proposal puts Flow/Enrollment/Activity in a **new small app (`pipeline`)** keyed on `User`, with no imports from cold_apply. The dashboard, row partials and `staff_base.html` go there too. Cold apply then becomes the Resume & Job Search flow plus its job and resume tools, and a future program needs only new flow data and its own tools. The alternative is to keep everything inside `cold_apply`. That's faster to start but not reusable.

`Participant` stays for now, because jobs, bullets, experience and the other tools point at it. It can be folded into `User`/`Profile` later.

## 6. Decisions
| Date | Decision | Why |
|---|---|---|
| 2026-10-19 | Staff move people through triage and flows from the dashboard, without opening each record | §3.1 |
| 2026-10-19 | DD214s are visible only to holders of a veteran-reviewer permission; other staff see status only | §3.2 |
| 2026-10-19 | Each participant has a tracked assignee | §3.3 |
| 2026-10-19 | A participant can be in more than one flow at once (e.g. Boot Camp and resume services) | §2.4 |

## 7. Open questions
- **Where is the assignee recorded?** The draft puts one assignee on each enrollment; the alternative is one per participant.
- **Should Intake be a flow?** The draft models intake (Applied → Veteran review → Triage) as a flow, rather than as status fields on the profile.
- **New app or inside cold_apply?** The draft proposes a new `pipeline` app keyed on `User`.
- **URL for the dashboard:** `/staff/` or `/cold_apply/staff/`?
- **Boot Camp and cohorts:** should a Boot Camp enrollment link to a `BootCampSession` once one is scheduled, with "Waitlist" meaning no session yet?
- **DD214 access for superusers:** should superusers get DD214 access automatically, or only through the reviewer group (a custom check rather than `has_perm`)?
- **Who is in the "Veteran reviewers" group** at launch?
- **Is the GCS media bucket private?** If any public access exists, fixing it comes before anything else here.
- **Who counts as staff:** only `is_staff`, or volunteers later? The signup redesign decided "no volunteer login yet".
- **`Application` model:** drop it as unused, or replace `Job.status`/`status_reason` with it?
- **Shared reference data:** should participants be able to create Companies, Titles and Locations (BUG-030), or only staff?

## 8. Plan
**TODO:** ordered steps, filled in after Section 5.

### Step 0 — Working environment
- Tests run in Docker under their own compose project:
  - `docker compose -p hl-cold-apply build django`
  - `docker compose -p hl-cold-apply run --rm frontend sh -c "npm ci && npm run build"`
  - `docker compose -p hl-cold-apply run --rm django python manage.py test`

## 9. Status
- 2026-10-19: worktree and doc created; review in Section 4.
- 2026-10-19: §1–3 filled in by Jeff; bugs logged (BUG-021–030); §5 drafted for review.
