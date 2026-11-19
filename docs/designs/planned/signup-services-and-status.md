# Signup: services and self-identified status (IDEA-011)

Branch `feature/idea-011-signup-services` (from `develop`), not started.

> **Status:** drafted 2026-11-19. Not agreed yet: the choices in §5 are proposals, and the open items in §7 need answers before S1.

## 1. Context
Two changes to signup and the participant record:

1. **Services.** An applicant opts into one or more services: "Resume & job search", "Coding boot camp", or "Both".
2. **Self-identified status.** We're opening services to formerly incarcerated people, so applicants say whether they are "Veteran", "Formerly incarcerated" or "Both" at signup. Each status has a verification step for staff. Veterans keep the DD214 upload. Formerly incarcerated applicants don't upload anything, and their verification is a manual button with no document to review.

**What already exists:**
- **Signup is one page.** `userprofile/views.py` `onboarding_view` renders `ProfileForm` (`userprofile/forms.py`) for `userprofile/onboarding.html`. On submit it calls `Profile.handle_onboard_complete()`, which calls `intake.start_intake(user, is_veteran=...)`. The veteran, service-package and upload templates (`onboarding_veteran_profile.html`, `onboarding_upload_service_doc.html`, `onboarding_service_package.html`, `onboarding_upload_resume.html`) are not routed by any URL. They are legacy.
- **`is_veteran` is never set at signup.** It is nullable with default `True`, and `ProfileForm` doesn't include it. So every new signup is treated as a veteran and goes through the veteran review step. This design fixes that as part of S2.
- **Service doc is required at signup for everyone.** `Profile.service_doc` has no `blank=True`, so the model form requires it. Branch, military specialty, years and rank are required the same way.
- **Coding boot camp interest already exists** as `Profile.bootcamp` ("Are you interested in a free coding bootcamp?"). It shows as "Boot camp interest" on the person panel (`pipeline/templates/pipeline/partials/person_panel.html`) and the person page.
- **Flows.** `pipeline` has Intake, Resume & Job Search (`resume-job-search`), Boot Camp (`boot-camp`) and Nurture. Intake has the steps Verify Veteran Status (gated by `userprofile.review_veteran_status`), then Triage. `pipeline.services.complete_triage` enrolls the person in the flows staff pick, then ends Intake.
- **Veteran verification is manual.** A reviewer opens `update_veteran_status_view` (`userprofile/views.py`), opens the DD214 through `service_doc_view`, and clicks "Verified, move to …", which calls `intake.verify_and_advance`. The VA API helper `userprofile/va_api.py` `confirm_veteran_status` is not called from any view.
- **Participant record.** The staff person page is `userprofile/templates/userprofile/people/person.html`, with a veteran status section and a "Boot camp interest" line. The people table is `people_table.html`.

## 2. Goals
- The signup form asks for services (one of three options) and status (one of three options), both required.
- Veterans, including those who are also formerly incarcerated, upload a service doc and pass the veteran review exactly as today.
- Formerly incarcerated applicants have no upload and no document review. They pass a manual verification button that a staff reviewer clicks.
- Applicants who are both go through both verifications, in order, then to triage.
- Triage starts with the services the applicant chose already ticked. Staff can change them.
- The person page shows both answers and the verification state.

**Not goals:** a document upload or any stored record of the details of someone's criminal history. Automatic checks of any kind. Changing the veteran verification itself. Auto-enrolling people in flows (the verification and triage still decide that). Changing the Nurture flow (IDEA-006). Changing what a formerly incarcerated person can see in the portal (IDEA-004).

## 3. Design

### 3.1 Data (`userprofile.Profile`)
| Field | Type | Notes |
|---|---|---|
| `is_veteran` | existing, nullable | set from the status choice at signup |
| `is_formerly_incarcerated` | Boolean, default False | set from the status choice at signup |
| `formerly_incarcerated_verified` | Boolean, default False | set by a reviewer, like `veteran_verified` |
| `wants_resume_job_search` | Boolean, default False | set from the services choice |
| `wants_boot_camp` | Boolean, default False | replaces `bootcamp`. Migration copies `bootcamp` into it, then `bootcamp` is removed |

Each three-way choice is stored as two booleans. "Both" is then two Trues, and nothing needs a combined value. The UI is a three-option radio group using the existing `ButtonRadioSelectWidget`. Mapping:
- Veteran: `is_veteran=True`, `is_formerly_incarcerated=False`.
- Formerly incarcerated: `is_veteran=False`, `is_formerly_incarcerated=True`.
- Both: both True.

Services mapping: Resume & job search sets `wants_resume_job_search`. Coding boot camp sets `wants_boot_camp`. Both sets both.

**Permission.** A new `userprofile.review_formerly_incarcerated_status`, added to the existing veteran reviewers group in a migration. It does not grant DD214 access. It is separate so it can be granted on its own later (§7).

### 3.2 Signup form (`ProfileForm`)
- Add the two choice fields, both required, with the labels "Services" and "Status". Save both as in §3.1.
- Veteran fields (`service_branch`, `military_specialiaty`, `years_of_service`, `rank_at_separation`, `service_doc`) are shown and required only when the status includes veteran. Required means the same as today: `service_branch` and `service_doc` must be present when the form is saved for a veteran, and the form rejects a save without them.
- A formerly incarcerated applicant who is not a veteran sees no upload. `resume` stays as it is for everyone.
- `bootcamp` is removed from the form. It is replaced by the services choice.
- `profile_update_view` uses the same `ProfileForm`, so the same rules apply there. Changing answers after onboarding is an open question (§7).

### 3.3 Intake routing (`userprofile/intake.py`)
The Intake Applicants phase becomes:
1. **Verify Veteran Status**: `applies_to="veteran"`, permission `review_veteran_status` (as today).
2. **Verify Formerly Incarcerated Status**: `applies_to="formerly_incarcerated"`, permission `review_formerly_incarcerated_status`. New step, placed before Triage.
3. **Triage** (as today).

`Step.applies_to` is a new blank-by-default CharField on `pipeline.Step`. Blank means everyone. The app that owns the step interprets the key, and pipeline doesn't need to know about profiles. In `intake.py`, a map from key to predicate: `"veteran"` → `is_veteran is not False`, `"formerly_incarcerated"` → `is_formerly_incarcerated`.

- `start_intake` enters the person at the first step that applies to them. It replaces the single-step skip it has today.
- `verify_and_advance(profile, actor, kind)` sets the matching verified flag (`veteran_verified` or `formerly_incarcerated_verified`), then moves to the next step that applies, or to Triage if there is none. It returns the enrollment, or None if the person isn't waiting on that step.
- `awaiting_verification(user, kind)` replaces `awaiting_veteran_review`.
- Existing Intake enrollments are unchanged. People already past the veteran step, or in Triage, aren't moved. Nobody has `is_formerly_incarcerated` set until they sign up under the new form.

### 3.4 Staff verification (`update_veteran_status_view` and person page)
- The existing veteran review page gets a second section, **Formerly incarcerated**, with its own button, "Verified, move to …". The button shows only when the person is waiting on that step, and only for users with `review_formerly_incarcerated_status`.
- The section shows the current status and no document. It has no DD214 link and no signed URL.
- A `status_reviewer_required` decorator in `userprofile/guards.py` guards the new POST, next to `veteran_reviewer_required`.
- The veteran section is unchanged, including the DD214 link and `service_doc_view`.

### 3.5 Triage and the participant record
- `triage_view` pre-ticks the flows that match `wants_resume_job_search` and `wants_boot_camp`. Staff can untick them. Nothing is enrolled until triage is submitted, as now.
- The person page (`people/person.html`) shows a **Services** line (what they asked for, and what they're enrolled in) and a **Formerly incarcerated** line next to the veteran section. Its verified state is shown the same way as the veteran one.
- The "Boot camp interest" line becomes "Coding boot camp" from `wants_boot_camp`. The person panel is updated to match.
- The people table doesn't show the formerly incarcerated status. It is visible on the person page only.

### 3.6 Privacy
- The formerly incarcerated answer is sensitive. It is stored as a boolean only. No document, no details, and no free text.
- It is not used in emails, in logs, or in the people table.
- The timeline entry for the verification records the step name, like the veteran step does. The step name is "Verify Formerly Incarcerated Status", which staff with the person page can see.
- The public site and any participant-facing pages don't show it.

## 4. Stages (one branch, `feature/idea-011-signup-services`)
- **S1: Data and routing setup.** The §3.1 fields and migration (copy `bootcamp` into `wants_boot_camp`, then remove `bootcamp`), the new permission and group grant, `Step.applies_to` in pipeline, and the new Intake step before Triage. Tests: migration copies the flag; the new step exists before Triage and has the permission.
- **S2: Signup form.** The two choice fields, the mapping in §3.1, veteran fields and doc required only for veterans, `bootcamp` removed. Tests: each of the 9 combinations (3 statuses × 3 services); a formerly incarcerated applicant saves with no upload; a veteran without a DD214 is rejected as today; "both" status saves both booleans; choices are required.
- **S3: Intake routing and verification.** `start_intake`, `verify_and_advance(kind)`, `awaiting_verification`, the staff section and POST in §3.4. Tests: veteran-only goes veteran step → Triage; formerly incarcerated goes straight to the FI step → Triage with no document; both go through both steps in order; a reviewer without the new permission gets 403; a button press when not waiting does nothing and says so.
- **S4: Triage and person page.** Pre-ticked services in triage, the person page sections, the boot camp label change, the person panel update. Tests: triage pre-selects from the profile; person page shows both answers; formerly incarcerated status is absent from the people table.
- **S5: Check and merge.** Sign up as each of the 3 statuses on stage, walk each through Intake and triage, confirm no service doc is requested of a formerly incarcerated applicant, then merge into develop.

Each stage ends with passing tests and can be merged into develop on its own, except that S2 must follow S1 and S3 must follow S1.

## 5. Proposed decisions (to confirm)
1. **Two booleans per choice, with a three-option radio on the form.** The model stays simple, and "both" needs no special case.
2. **Services pre-tick triage; they don't auto-enroll.** The veteran and formerly incarcerated verifications and triage still decide who joins each flow, as they do now. Auto-enrolling after verification is a small follow-up if wanted (§7).
3. **Formerly incarcerated verification is a separate Intake step, after the veteran step.** Both kinds of status can apply, so each has its own step and button. Each step appears only for people who have that status.
4. **A separate permission for formerly incarcerated review.** It is granted to the same staff group, so today's reviewers can do both. It doesn't grant DD214 access, so the two can be split later.
5. **`bootcamp` is replaced by `wants_boot_camp`.** The existing answer carries over, so no one loses their boot camp interest.
6. **The DD214 and veteran fields are required only for veterans.** This is the only change to the veteran path, and it comes from the status question. The veteran verification process is unchanged.
7. **`is_veteran` is set from the status question at signup.** This closes the gap in §1, where every signup is treated as a veteran.

## 6. Verification
- `python manage.py test userprofile pipeline` passes, including new tests for each stage in §4.
- On stage, with test accounts and the veteran reviewer and formerly incarcerated reviewer roles: go through all three statuses end to end, and check each person's Intake timeline and triage pre-ticks.
- Confirm a formerly incarcerated applicant can't reach a DD214 or the service doc URL (`service_doc_view` returns 404 with no doc).
- Confirm a reviewer with only `review_veteran_status` can't press the formerly incarcerated button.
- Migration on a copy of prod data: count `bootcamp=True` before and `wants_boot_camp=True` after, and check they match.

## 7. Open items
- **Is "neither" a valid answer?** The brief lists three options and no "neither". This design requires one of them. A staff-created record can still be neither, through the existing non-veteran path.
- **Can people change their answers after signup?** Services: yes, I'd suggest, from the profile update page. Status: changing after verification should need staff, since the verified flag is what counts. Which?
- **Should services auto-enroll after verification instead of pre-ticking triage?** Proposal 2 pre-ticks. Auto-enroll is faster but skips staff review of who joins.
- **Who should review formerly incarcerated status?** Proposal 4 grants the new permission to the same group for now. Should a separate group be used?
- **Who can see the formerly incarcerated answer on the person page?** Proposal: any staff member, with only the reviewer permission allowing the verify button. Or restrict the view too?
- **Wording.** Labels are "Veteran", "Formerly incarcerated", "Both" and "Resume & job search", "Coding boot camp", "Both". The step title is "Verify Formerly Incarcerated Status". Confirm the wording before S2.
- **Existing `bootcamp` data.** Counts of current `bootcamp=True` and of existing profiles with `is_veteran` set to True by default aren't known from the repo. Check on prod before S1 so the migration note is accurate.
