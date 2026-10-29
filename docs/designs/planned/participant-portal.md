# Self-Service Participant Portal (IDEA-004)

Branch `feature/idea-004-participant-portal` (from `develop`), not started.

> **Status:** drafted 2026-10-29. Not agreed yet: the choices in §5 are proposals, and the open items in §7 need answers before P1.

## 1. Context
IDEA-004: "a portal where participants use some of the tools themselves (add experience, education and bullets, view jobs), with an access level separate from staff." It comes from `docs/designs/completed/cold-apply-staff-redesign.md` §7 (the BUG-030 question on shared reference data) and its decision "Participants keep create rights on reference data (BUG-030) for now … revisit with the self-service portal".

**What a participant gets today:**
- After onboarding, `user_home` (`userprofile/views.py`) sends them to `welcome`, a static page that says "we will reach out to you via email in the next 2-3 business days". There's no link onward.
- The Toolbox menu in `base_app.html` shows **Cold Apply** only with `perms.cold_apply`, which participants don't hold. So nothing on the site links a participant to their tools.
- **But the tools already work for them by URL.** Every participant-facing cold_apply view is guarded by ownership, not by role (`cold_apply/guards.py`): `OwnedObjectMixin` / `owned_by` (staff see everything, others only their own rows), `ParticipantAccessMixin` (participant pk in the URL), and `ParticipantOrStaffMixin` (any user with a `Participant`). `cold_apply:home` sends a participant to their own `participant_detail`. `cold_apply/tests/test_access.py` pins that participants can't see each other's data.

So a participant who knows the URLs can today:

| Tool | Views | Cost or risk |
|---|---|---|
| Profile page (jobs, latest experience, education, resume link) | `ParticipantDetailView` | none |
| Experience, education, concentrations | `Experience*`, `Education*`, `ConcentrationCreateView`, `delete_exp`, `delete_education` | creates shared reference rows (BUG-030) |
| Bullets and overviews | `Bullet*`, `Overview*`, `delete_bullet` | none |
| AI bullets, overviews and job keywords | `regenerate_bullet_view`, `OverviewCreateView` (generate), `job_keywords_view`, `refresh_keywords` | LLM calls through hlagents `complete()`; the only cap is the site-wide `daily_cost_cap` (`hlagents/models.py` `spent_today`) |
| Jobs: add, edit, delete, change status | `JobCreateView`, `JobUpdateView`, `delete_job`, `job_status_update_modal_view` | none |
| Find new jobs | `find_new_jobs_view` → `task_get_jobs_for_participant` | a queued task that drives Playwright against Google Jobs (`cold_apply/jobs.py` `get_jobs_from_google`) |
| Tailored resume | `configure_tailored_resume_view`, `tailored_resume_view` | none |
| Reference data they added | `Reference*View` | BUG-030 rules (`cold_apply/reference.py`) |

**What's missing for a portal:**
1. **An access level.** Being a participant is all it takes today, and there's no way to turn a tool on for one person and off for another. Staff can't tell who is using the tools.
2. **An entry point.** No home page, no nav, and the welcome page doesn't change once someone is working with Hired Labs.
3. **Cost limits per person.** One participant pressing "regenerate" in a loop can use the whole day's LLM budget, which also stops staff and the agents. Job searches have no limit at all.
4. **Pages that read well for a participant.** The pages extend `base_app.html` (the legacy layout) and were built for staff working on someone's behalf. Some wording assumes staff ("Open staff workspace" is already hidden, but headings like "Participant" are not).

**Related work:**
- IDEA-005 (volunteer logins, `docs/designs/in-progress/volunteer-logins.md`) added `is_participant(user)` (`Profile.is_onboarded`) and `is_volunteer(user)` in `userprofile/guards.py`, and sets the rule that access is granted through **groups in Django admin**. Its V2 plans `cold_apply.view_all_participants` for staff and an "assigned to me" branch in `owned_by`. This design adds a third kind of user to the same guards.
- IDEA-003 (reference data, `docs/designs/planned/reference-data.md`) keeps merge staff-only. Participants creating rows from the portal will make more duplicates, which IDEA-003 cleans up.
- IDEA-009 (resume parser) would be a portal tool later: upload a resume and review what was found.

## 2. Goals
- Staff turn the portal on for a participant, and can turn it off again. Who has it is visible on the staff person page.
- Which tools a portal user gets is set by permissions, so a tool can be held back (job search, AI tools) without a code change, following the IDEA-005 approach.
- A participant with the portal lands on a **portal home** after login, with a card per tool they can use, and the site nav links there.
- Participants without the portal can't reach the cold_apply tools at all, closing today's URL-only access.
- Each portal user has a daily limit on LLM spend and on job searches, separate from the site-wide cap.
- Staff see portal activity they care about (portal turned on or off) on the person's timeline.
- Nothing staff can do today changes. Ownership checks stay exactly as they are.

**Not goals:** a new visual design for every cold_apply page (P4 does the pages a participant sees most; the rest can follow). Participants seeing staff notes, steps, assignees or the Activity timeline. Participants signing up for flows or boot camp sessions themselves. Messaging between participant and staff. Merge or delete of shared reference data beyond BUG-030's rules. The resume parser (IDEA-009).

## 3. Design

### 3.1 Access level
- **Permissions** in `Participant.Meta.permissions` (`cold_apply/models.py`), one migration:
  - `cold_apply.use_portal`: the portal home and the profile, experience, education, bullets, overviews, jobs and tailored resume pages;
  - `cold_apply.use_ai_tools`: AI bullets, overviews and job keywords;
  - `cold_apply.use_job_search`: Find new jobs.
- **Group:** a data migration creates **Portal** holding all three, the same way `userprofile/migrations/0022_review_veteran_status.py` creates Veteran reviewers. Staff who want a participant to have the portal without, say, job search make a second group in admin ("Portal (no job search)"). No code change needed.
- **Helper** `can_use_portal(user, perm="cold_apply.use_portal")` in `cold_apply/guards.py`: staff pass (as now; V2 of IDEA-005 turns that into `view_all_participants`); everyone else needs `is_participant(user)` **and** the permission. Volunteers who aren't onboarded never pass, whatever groups they're in.
- Superusers pass `has_perm` anyway; they're staff, so nothing changes for them.

### 3.2 Gates
- `PortalMixin` (CBVs, with a `portal_permission` attribute, default `use_portal`) and `portal_required(perm)` (function views) in `cold_apply/guards.py`. They run **before** the ownership checks and raise `PermissionDenied` when `can_use_portal` is false. Ownership (`owned_by`, `ParticipantAccessMixin`, `OwnedObjectMixin`) is unchanged and still decides *which* rows.
- `ParticipantOrStaffMixin` becomes a thin wrapper over the same check, so the reference-data create views (BUG-030) and `LocationDetailView` follow the portal too.
- Each view in the §1 table gets the gate with the matching permission. The AI views need `use_ai_tools`, and `find_new_jobs_view` needs `use_job_search`.
- `task_get_jobs_for_participant` itself is `csrf_exempt` and called by the task queue, not by a browser. It stays as it is; the check happens in `find_new_jobs_view` before queuing.
- **Templates hide what the user can't use:** the Generate/Regenerate buttons check `perms.cold_apply.use_ai_tools`, and Find new jobs checks `perms.cold_apply.use_job_search`. Staff hold neither permission explicitly, so the templates use a `can_use` template filter backed by `can_use_portal`, not `perms` directly.
- **Behaviour change:** participants who use the tools by URL today lose access until staff add them to Portal. P1 includes a query to list participants with jobs or experience rows created by themselves in the last 90 days, so staff can decide who to add before the release (§7).

### 3.3 Turning it on
- On the staff person page (`staff_person`, `userprofile/people.py`), a **Portal** row: "Off" with a **Turn on** button, or "On since <date>" with **Turn off**. Only staff see it.
- Turning on adds the user to **Portal**; turning off removes them from every group that holds `use_portal`. Both write an `Activity` row (`kind=note`, body "Portal turned on" / "Portal turned off", actor = staff user), so it shows on the timeline. No new Activity kind is needed.
- The button is shown only for participants (`is_participant`). If the user isn't onboarded yet, the row says so.
- **Email:** turning on sends one email ("You can now use the Hired Labs tools") with a link to the portal home, using the existing `templates/account/email/` pattern. Turning off sends nothing.
- Admin can still change groups directly; the person page reads group membership, so both ways agree.

### 3.4 Portal home and navigation
- **URL:** `/portal/` (`portal_home`, in `cold_apply/urls.py` or `hl_main/urls.py`, behind `PortalMixin`).
- **Routing:** `user_home` checks `is_staff`, then `is_volunteer`, then `can_use_portal`, then onboarding. A portal user lands on `/portal/`. An onboarded participant without the portal still gets `welcome`. `cold_apply:home` sends a portal user to `/portal/` instead of `participant_detail`.
- **Participant-volunteers** (IDEA-005 §3.6) land on the volunteer home, which gets a **My tools** card linking to `/portal/` when they have the portal.
- **Content:** a heading with their name, then a card for each tool they can use:
  - **My experience and education** → `participant_experience_list`, with counts;
  - **My jobs** → `participant_detail` jobs panel, with counts by status;
  - **Find jobs** → `find_new_jobs` (if `use_job_search`), with the last search date;
  - **Resumes** → the jobs list, since a tailored resume is made per job.
  - **Where you are:** the names of their active enrollments' flows ("Resume & Job Search", "Boot Camp — waitlist" or the session date). Flow names only: step names are written for staff (§7).
- **Nav:** the Toolbox menu in `base_app.html` shows **My tools** → `/portal/` when `can_use_portal`, in place of today's `perms.cold_apply` check for non-staff. `welcome.html` gets a "Go to your tools" button for portal users.

### 3.5 Cost limits
- **LLM:** new field `AgentLimits.participant_daily_cost_cap` (default `0.50`). `task_problem` (or a new check next to it in `hlagents/completion.py`) adds: if the user isn't staff and their `TaskCall` cost today is at or over the cap, refuse with "You've used today's AI help. Try again tomorrow." That message reaches the participant through the existing `TextGenerationError` path. Staff and agent runs aren't affected.
- **Job search:** at most `PORTAL_JOB_SEARCHES_PER_DAY` (setting, default 3) `JobSearch` rows per participant per day when the user isn't staff. `find_new_jobs_view` checks before queuing and shows a message instead of the form when the limit is reached.
- Both limits show on the staff person page next to the Portal row ("AI today: $0.12 of $0.50; searches today: 1 of 3"), so staff can see who's near them.

### 3.6 Pages for participants
- `participant_detail.html`, `participant_experience_list.html` and the experience, education and bullet forms get participant wording when the viewer is the owner: "My jobs", "My experience", and no "Participant" headings. One `is_own` context variable (`object.user_id == request.user.id`) drives it.
- Breadcrumbs start at **My tools** for portal users and at the staff person page for staff.
- These pages keep `base_app.html` in this idea. A portal layout (Tailwind, `hl-` classes like `new_home_base.html`) is a later step (§7).

### 3.7 Reference data
- Participants keep BUG-030's rights (create; edit or delete their own unused rows), now behind `use_portal`. This answers the "revisit with the self-service portal" decision: the portal is the access level that holds them.
- The **Manage** links on the forms stay. Participants never see merge (IDEA-003 §5.1).

## 4. Stages (one branch, `feature/idea-004-participant-portal`)
- **P1: Access level and gates.** Permissions, the Portal group migration, `can_use_portal`, `PortalMixin` / `portal_required`, gates on every view in §1, `ParticipantOrStaffMixin` change, template checks, and the "recent self-service users" query. Tests in `cold_apply/tests/test_access.py`: a participant without Portal gets 403 everywhere; with Portal they reach their own pages and still 404 on others'; `use_ai_tools` and `use_job_search` are enforced separately; a volunteer in Portal who isn't onboarded gets 403; staff are unchanged.
- **P2: Turning it on.** The person page row, turn on/off views (staff only), Activity rows and the email. Tests for both, and that a non-participant shows no button.
- **P3: Portal home and routing.** `/portal/`, `user_home` and `cold_apply:home` routing, the volunteer-home card, the nav entry and the welcome button. Tests extend `userprofile/tests/test_navigation.py` and `test_onboarding.py`.
- **P4: Limits and wording.** `participant_daily_cost_cap`, the job search limit, the person-page usage line, and the participant wording and breadcrumbs. Then check every page as a participant and as staff, and merge into develop.

Each stage ends with passing tests and can be merged into develop on its own. P1 alone changes behaviour for participants (§3.2), so P1 and P2 should ship in the same release.

## 5. Proposed decisions (to confirm)
1. The portal is off by default and staff turn it on per person. The alternative is on for everyone once onboarded, or on automatically when they're enrolled in Resume & Job Search.
2. Access is three permissions in one **Portal** group, managed like IDEA-005's groups, rather than a flag on `Profile`.
3. Participants without the portal lose today's URL-only access to the tools.
4. Per-person daily limits: $0.50 of LLM spend and 3 job searches, adjustable in admin and settings.
5. Participants see only the names of their flows, not steps, assignees or notes.
6. Pages keep the legacy layout for now, with participant wording; a new portal layout is separate work.

## 6. Verification
- `python manage.py test cold_apply userprofile hlagents pipeline` passes.
- Locally with `load_dev_data`: log in as a participant without the portal. `/portal/` and every URL in §1 give 403, and login lands on `welcome`.
- As staff, turn the portal on from the person page. The timeline shows "Portal turned on" and the email is in the console backend.
- As that participant: login lands on `/portal/` with all four cards. Add experience, education and bullets, add a job, generate a bullet, run a job search, make a tailored resume. Another participant's job URL gives 404.
- Lower the caps to tiny values. The next AI call shows the "today's AI help" message, the fourth search shows the limit message, and staff can still generate text.
- Move the participant to a group with `use_portal` only. The AI buttons and Find jobs are gone, and their URLs give 403.
- As a participant-volunteer with the portal: login lands on the volunteer home with a **My tools** card.
- On stage before release: run the recent self-service query and add those participants to Portal.

## 7. Open items
- **Who gets it first** (§5.1): everyone onboarded, people in Resume & Job Search, or staff's choice per person?
- **Today's URL-only users:** is anyone using the tools on their own today? The P1 query on prod answers this, and decides whether to add them to Portal in the release migration.
- **Job search at participant volume:** `get_jobs_from_google` scrapes Google Jobs with Playwright. More searches mean more chance of being blocked. Is 3 a day per person safe, or should job search stay staff-only at first (a Portal group without `use_job_search`)?
- **Cap values:** are $0.50 a day and 3 searches a day right?
- **Showing steps:** some steps could be useful to participants ("Waiting for veteran review"). That needs participant-facing step labels on `pipeline.Step`, which is a separate change.
- **Portal layout:** when should the participant pages move off `base_app.html`? It could be done with the dark mode work (IDEA-010 D4 covers legacy cold_apply pages).
- **IDEA-005 V2 overlap:** when staff move to `cold_apply.view_all_participants`, `can_use_portal`'s staff branch should use the same permission. Whichever lands second makes the change.
