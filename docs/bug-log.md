# Bug Log

Bugs found during other work and **not fixed at the time**. This file is shared by all work sessions, including Claude Code sessions.

**How to use it**
- **Add:** append a new entry with the next ID. Never renumber entries.
- **Fix:** set **Status** to `Fixed`, add the branch or commit, and leave the entry in place.
- **Skip:** if a bug turns out not to be one, set **Status** to `Won't fix` and give a one-line reason.
- **Status values:** `Open` · `In progress` · `Fixed` · `Won't fix`
- **Severity:** **High** means a security or data risk, or a crash on a normal path. **Medium** means a crash on an edge path, or something broken that people use. **Low** means cleanup, dead code or tooling.
- Mark anything you suspect but haven't reproduced as **Suspected**.

## Index

| ID | Severity | Status | Area | Summary |
|---|---|---|---|---|
| BUG-001 | High | Fixed | cold_apply | Deletes and keyword refresh run on GET links, so they're open to CSRF |
| BUG-002 | Medium | Fixed | rates, releases | Views only require login; any self-signup can use them |
| BUG-003 | Medium | Fixed | userprofile | `handle_onboard_complete` can raise IntegrityError for an existing participant |
| BUG-004 | Medium | Fixed | cold_apply | `home_view` returns 500 for a non-staff user with no Participant |
| BUG-005 | Medium | Fixed | userprofile | `Profile.service_package` hard-codes `default=1` |
| BUG-006 | Medium | Fixed | settings | `manage.py` defaults to prod settings |
| BUG-007 | Low | Fixed | settings | `PRODUCTION` is only defined in `cloud.py` |
| BUG-008 | Low | Fixed | background_tasks | `work_task` crashes on a missing task and swallows task errors |
| BUG-009 | Low | Fixed | cold_apply | `OverviewDeleteView.get_success_url` crashes when no job matches |
| BUG-010 | Low | Won't fix | cold_apply | Suspected: `JobUpdateView.get_success_url` with no `?from=` |
| BUG-011 | Low | Fixed | cold_apply | Dead or broken code: `ConfigureTailoredResumeView`, `create_interaction`, unreachable branches |
| BUG-012 | Low | Fixed | tests | Two stale test modules never run |
| BUG-013 | Low | Fixed | dev data | `load_dev_data` creates two superusers with the same email |
| BUG-014 | Low | Fixed | frontend | `npm install` rewrites `package-lock.json` |
| BUG-016 | Low | Fixed | infra | Every push to `develop` deploys to stage; needs a `staging` branch |
| BUG-017 | Low | Fixed | settings | `asgi.py` defaults to `hl_main.settings`, which isn't a valid settings module |
| BUG-018 | Medium | Fixed | infra | Stage deploy fails at `start-sql` when the stopped database takes too long to start |
| BUG-019 | Medium | Open | settings | Suspected: a request can hit a closed database connection (one 500 on stage sign-up) |
| BUG-020 | Low | Open | tests | Suspected: `ColdApplyAccessTest` setup sometimes fails with a value too long for a 50-character column |
| BUG-021 | High | Fixed | userprofile | Every staff user can open DD214s (veteran status page and Django admin) |
| BUG-022 | Medium | Fixed | cold_apply | Do Not Contact badge is never shown to staff |
| BUG-023 | Medium | Fixed | cold_apply | Participant page shows blank phone and email |
| BUG-024 | Medium | Fixed | cold_apply | Participants with no current step don't appear on the pipeline |
| BUG-025 | Low | Fixed | cold_apply | "Highest Education" is just the first Education row |
| BUG-026 | Low | Open | cold_apply | Pipeline registration date prints the month where the minutes should be |
| BUG-027 | Low | Fixed | cold_apply | Veteran status button is superuser-only but the view allows any staff |
| BUG-028 | Low | Fixed | userprofile | Suspected: Profile admin search raises FieldError (`user`, `nickname`) |
| BUG-029 | Low | Open | cold_apply | Dead or misleading code in the staff pages (`staff.html` navbar, `index.html`, Bootstrap script, URL typo) |
| BUG-030 | Low | Open | cold_apply | Any logged-in user can create companies, titles, positions, concentrations and locations, and list locations |
| BUG-031 | Medium | Fixed | userprofile | Suspected: new signups can land in Nurture, because phases and steps share order values |
| BUG-032 | Low | Open | cold_apply | Participant page says "Not a Veteran Veteran (None)" for a veteran with no service branch |

---

## BUG-001 — Deletes and keyword refresh run on GET links (CSRF)
- **Severity:** High · **Status:** Fixed (`fix/bug-001-csrf-get-deletes`, 1d04bee; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-16, signup redesign Step 1
- **Where:**
  - Views: `cold_apply/views.py` `delete_job`, `delete_exp`, `delete_education`, `delete_bullet`, `refresh_keywords`
  - Templates: `cold_apply/templates/cold_apply/partials/job_actions.html:7`, `participant_experience_list.html:41,72`, `partials/bullet_detail_li.html:18`, `partials/bullet_preview_detail_li.html:9`, `job_detail.html:61`
- **Problem:** these views change data on a plain GET from an `<a href>`. A link or image on any other site can make a logged-in user's browser delete their own jobs, experience or bullets. Step 1 added owner checks, so one user can no longer delete another user's data, but this cross-site request risk remains.
- **Fix idea:** add `@require_POST` and change the links to small POST forms (or `hx-post` with the CSRF header already set on `<body>`).

## BUG-002 — rates and releases views only require login
- **Severity:** Medium · **Status:** Fixed (`fix/bug-002-app-perms`, 16699d6; merged into `feature/signup-login-redesign`). Views now need app permissions, matching the nav: `perms.rates` / `perms.releases`. This replaces the staff-only fix in 6d34490 · **Found:** 2026-10-16
- **Where:** `rates/views.py` (`RateRequestListView`, `RecommendationCreateView`, `world_rates`); `releases/views.py` (all views, including `AppCreateView` and `ReleaseCreateView`)
- **Problem:** any logged-in user can use these, including an unverified self-signup. The "World Rates" nav link is hidden by `perms.rates` in `templates/base_app.html:63`, but the views don't check that permission.
- **Fix idea:** decide who should use each view. Then apply `StaffRequiredMixin` (`userprofile/guards.py`) or `PermissionRequiredMixin` to match the nav.

## BUG-003 — `handle_onboard_complete` can raise IntegrityError
- **Severity:** Medium · **Status:** Fixed (`fix/medium-bugs`, aec424e; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-16
- **Where:** `userprofile/models.py:59` (`Profile.handle_onboard_complete`)
- **Problem:** it calls `Participant.objects.get_or_create(user=self.user, current_step=step)`, which looks up by both user and step. `Participant.user` is one-to-one, so if the user already has a Participant on a different step, the lookup misses, the create runs, and it raises IntegrityError. This can happen when onboarding is resubmitted or a Participant was created by hand.
- **Fix idea:** `get_or_create(user=self.user, defaults={"current_step": step})`.

## BUG-004 — `home_view` 500 for non-staff without a Participant
- **Severity:** Medium · **Status:** Fixed (`fix/medium-bugs`, 72952ee; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-16
- **Where:** `cold_apply/views.py` `home_view` (`# TODO handle no profile`)
- **Problem:** `request.user.participant.id` raises RelatedObjectDoesNotExist for a verified user who hasn't finished onboarding.
- **Fix idea:** redirect to `userprofile:user_home`, which already routes to onboarding.

## BUG-005 — `Profile.service_package` hard-codes `default=1`
- **Severity:** Medium · **Status:** Fixed (`fix/medium-bugs`, fec8b7c; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-16
- **Where:** `userprofile/models.py:31`
- **Problem:** every new Profile points at ServicePackage pk=1. On a fresh database, in tests, or if that row is ever deleted, creating a Profile fails with a foreign-key error. This broke the old onboarding tests and `load_dev_data` (worked around in that command on `feature/signup-login-redesign`).
- **Fix idea:** `default=None`, or a callable that looks the package up by name, plus a data migration that seeds the packages.

## BUG-006 — `manage.py` defaults to prod settings
- **Severity:** Medium · **Status:** Fixed (`fix/medium-bugs`, fb21eee; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-16
- **Where:** `manage.py:9` (`setdefault("DJANGO_SETTINGS_MODULE", "hl_main.settings.prod")`)
- **Problem:** running `manage.py` anywhere `DJANGO_SETTINGS_MODULE` isn't set (a host shell, a new IDE run configuration) loads prod settings. Docker Compose sets dev settings, so normal dev use isn't affected.
- **Fix idea:** default to `hl_main.settings.dev`; Cloud Run already sets the variable explicitly.

## BUG-007 — `PRODUCTION` setting only defined in `cloud.py`
- **Severity:** Low · **Status:** Fixed (`fix/low-bugs`, 98771fb; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-16
- **Where:** `hl_main/settings/cloud.py:16`; read in `background_tasks/queue.py` (`send_task_to_queue`, `delete_task`)
- **Problem:** `base.py`, `dev.py` and `build.py` don't define `PRODUCTION`. With `DEBUG=False` under those settings (for example `delete_task` in tests), `settings.PRODUCTION` raises AttributeError. The new `is_authorized_task_request` uses `getattr(..., False)` to avoid this.
- **Fix idea:** `PRODUCTION = False` in `base.py`.

## BUG-008 — `work_task` crashes on a missing task and swallows errors
- **Severity:** Low · **Status:** Fixed (`fix/low-bugs`, 1e86a2e; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-16
- **Where:** `background_tasks/queue.py` `work_task`
- **Problem:** a missing or wrong `X-Task-Id` gives `task = None`, so `task.start()` raises AttributeError and the request returns 500. If the task function raises, the error is recorded but the view still returns `{"status": "success"}`, so Cloud Tasks never retries.
- **Fix idea:** return 404 for an unknown task. Return a non-2xx response on failure if retries are wanted.
- **Fix notes:** worse than logged: `select_for_update()` ran outside a transaction, so every task request raised TransactionManagementError and returned 500 before the task ran. Background job searches never ran in dev or on Cloud Run. Fixed by locking only while marking the task as started. Unknown or missing `X-Task-Id` now returns 404. Task errors are logged and recorded, and the endpoint reports the real status, and a failed task gets a 500 so Cloud Tasks retries it (27e6374, on `feature/signup-login-redesign`). The queue is capped at 3 attempts with 60s–600s backoff (5a1d817 on develop, Terraform `retry_config`). Applied to stage and prod 2026-10-17, and both queues were checked (3 attempts, 60s–600s), so 27e6374 is safe to deploy.

## BUG-009 — `OverviewDeleteView.get_success_url` can crash
- **Severity:** Low · **Status:** Fixed (`fix/low-bugs`, c341879; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-16
- **Where:** `cold_apply/views.py` `OverviewDeleteView.get_success_url`
- **Problem:** `self.object.participant.job_set.filter(title=self.object.title).first().id` raises AttributeError when no job has that title. The overview is already deleted by then, so the user sees a 500 after a successful delete.
- **Fix idea:** fall back to the participant detail page.

## BUG-010 — Suspected: `JobUpdateView.get_success_url` without `?from=`
- **Severity:** Low · **Status:** Won't fix: not reproducible. `resolve(None)` raises `Resolver404`, which is caught, and external or `//host` values don't resolve, so they fall back too (checked 2026-10-17) · **Found:** 2026-10-16
- **Where:** `cold_apply/views.py` `JobUpdateView.get_success_url`
- **Problem:** `resolve(self.request.GET.get("from"))` only catches `Resolver404`. With no `from` parameter it calls `resolve(None)`, which may raise a different exception. Not reproduced.
- **Fix idea:** check `from_url` before calling `resolve`, and use `url_has_allowed_host_and_scheme`.

## BUG-011 — Dead or broken code in cold_apply
- **Severity:** Low · **Status:** Fixed (`fix/low-bugs`, f7f0e90; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-16
- **Where:** `cold_apply/views.py`
  - `ConfigureTailoredResumeView`: not routed, and uses `self.kwargs[""]`.
  - `create_interaction`: not routed.
  - `ParticipantDetailView.get_form_class`: unreachable lines after `return`.
  - `OrganizationUpdateView` / `TitleUpdateView` / `ExperienceUpdateView.form_valid`: unreachable `else: print(form.errors)`.
  - `ParticipantDetailView.form_valid`: returns `None` for any form other than `NewJobSelectionForm`.
- **Fix idea:** delete the dead code; return a response in every branch.

## BUG-012 — Stale test modules never run
- **Severity:** Low · **Status:** Fixed (`fix/low-bugs`, 3c255aa; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-16
- **Where:** `cold_apply/tests/cold_apply_models_test.py`, `userprofile/tests/up_models_test.py`, and also `releases/tests/releases_models_test.py`. All three were deleted
- **Problem:** Django's test discovery only picks up `test*.py`, so these files never run. They also use fields that no longer exist (`Participant.name`, `email`, `uploaded_resume`; `Profile.nickname`).
- **Fix idea:** delete them, or rename to `test_*.py` and rewrite with the factories in `cold_apply/tests/factories.py`.

## BUG-013 — `load_dev_data` creates two superusers with the same email
- **Severity:** Low · **Status:** Fixed (`fix/low-bugs`, 9032f71; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-16
- **Where:** `cold_apply/management/commands/load_dev_data.py` (lines with `create_superuser`)
- **Problem:** it creates usernames `admin@admin.com` and `admin`, both with email `admin@admin.com`. Login is by email through allauth, so which account you get is ambiguous. The README says to log in as `admin` / `admin`.
- **Fix idea:** create one superuser and update the README.

## BUG-014 — `npm install` rewrites `package-lock.json`
- **Severity:** Low · **Status:** Fixed (`fix/low-bugs`, 3efeef5; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-16
- **Where:** `frontend/package-lock.json`; the `frontend` service in `docker-compose.yml` runs `npm install` on every start
- **Problem:** the committed lock file doesn't match what the container's npm produces, so every frontend start dirties the working tree. It also showed up in commit `3774ce6` on `feature/hlagents-01`.
- **Fix idea:** regenerate and commit the lock file with the container's npm version, and use `npm ci` in the compose command.

## BUG-016 — Every push to `develop` deploys to stage
- **Severity:** Low · **Status:** Fixed (`infra/bug-016-staging-branch`, 2d09d63; on develop). Applied 2026-10-17: `hl-stage-deploy` now watches `^staging$`, and `origin/staging` exists · **Found:** 2026-10-17 · **Type:** design, not a code defect
- **Where:** stage Cloud Build trigger, `deploy_branch = "develop"` in `infra/terraform/envs/stage/main.tf`
- **Problem:** by design, every push to `develop` builds and deploys to the GCP staging environment, including small commits such as bug-log updates.
- **Fix idea:** create a `staging` branch, point the stage trigger at it instead of `develop`, and update `infra/README.md` and `infra/cloudbuild/deploy.yaml` comments to match.
- **Fix notes:** bug-log commits never deployed: the trigger's `ignored_files` already skips pushes that only change `**/*.md`. Code merges did deploy. The stage trigger now watches `^staging$` (reviewed plan: 1 in-place change to `hl-stage-deploy`). Promote with `git push origin develop:staging`. Checked 2026-10-17: the trigger shows `^staging$`, and pushing develop (525b396) started no build. The first push of `staging` also started no build, probably because its head commit changed only `.md` files, which `ignored_files` skips. If a promotion only adds docs commits, run `gcloud builds triggers run hl-stage-deploy --branch=staging --project=hl-main-stage`. A full deploy from `staging` succeeded in build d4ecb19b (see BUG-018).

## BUG-017 — `asgi.py` defaults to an invalid settings module
- **Severity:** Low · **Status:** Fixed (`fix/low-bugs`, f670412; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-17, while fixing BUG-006
- **Where:** `hl_main/asgi.py:14` (`setdefault('DJANGO_SETTINGS_MODULE', 'hl_main.settings')`)
- **Problem:** `hl_main/settings/` has no `__init__.py` defining settings, so running ASGI without `DJANGO_SETTINGS_MODULE` set fails at startup. Nothing runs ASGI today (Cloud Run uses WSGI), so it has no effect yet.
- **Fix idea:** match `wsgi.py` (`hl_main.settings.prod`) or delete `asgi.py` if it isn't needed.

## BUG-018 — Stage deploy fails at `start-sql` when the database is slow to start
- **Severity:** Medium · **Status:** Fixed (40dc3c5 and d1e72cc on develop and staging). Verified by stage build d4ecb19b on 2026-10-17 · **Found:** 2026-10-17, while verifying BUG-016
- **Where:** `infra/cloudbuild/deploy.yaml`, `start-sql` step (`gcloud sql instances patch hl-$_ENV-sql --activation-policy=ALWAYS`)
- **Problem:** stage build c921841b (develop c5b2467, 2026-10-17 01:36 UTC) failed. The step that starts the stopped database gave up with `Operation ... is taking longer than expected`, so the migrate and deploy steps never ran and stage stayed on c2b679b. Any deploy that runs while the database is stopped by the nightly schedule can fail the same way.
- **Fix idea:** run the patch with `--async`, then `gcloud sql operations wait <op> --timeout=900`. Or poll until `state=RUNNABLE`. Treat "already ALWAYS" as success.
- **Fix notes:** the start operation took about 14 min (01:50–02:05 UTC), but `gcloud` stops waiting after about 5 min. The step now starts the database with `patch --async`, then checks `state` every 30 s for up to 30 min. If the patch itself fails (for example, a start is already running), the step still checks. The build timeout went from 3600s to 5400s. Tested on 2026-10-17 by rendering the step as Cloud Build would and running it against a stub `gcloud`: it succeeds once the database is running, succeeds when the patch fails, and fails after 60 checks.
- **Fix notes (2):** 40dc3c5 wasn't enough. In stage build 1c701310 (staging bb05ea1, 2026-10-17 21:38 UTC), the database reported `RUNNABLE` straight after the async patch, while its start operation (298d46f8) was still running. It reported `MAINTENANCE` soon after. `start-sql` passed in 35 s, and `migrate` failed with `OperationalError: connection failed: server closed the connection unexpectedly`. d1e72cc also waits until `gcloud sql operations list --filter='status!=DONE'` returns nothing. That filter was checked against the running operation, and the stub test now covers an early `RUNNABLE` report.
- **Verified:** stage build d4ecb19b (staging 6ecb3a4, 2026-10-17 22:14 UTC) succeeded. `start-sql` saw `RUNNABLE` with operation 7f409908 still pending and waited until it finished. Then `migrate`, `deploy-web` and `deploy-worker` all passed. `hl-stage-web` runs image `6ecb3a4` and returns 200. The database was already running for that build. Cold start verified on 2026-10-18 by the stage deploy of b899a8e. The database had been stopped overnight, and `start-sql` saw `RUNNABLE` early with operation c1a8e6c5 pending. It kept waiting through `MAINTENANCE` until the operation finished, and the deploy then succeeded.

## BUG-019 — A request can hit a closed database connection
- **Severity:** Medium · **Status:** Open · **Found:** 2026-10-17, stage sign-up test after build 8f748ade (46858e2) · **Suspected:** seen once, not reproduced
- **Where:** `hl-stage-web`, `POST /accounts/sign-up/` at 2026-10-18 01:52:18 UTC (instance ending `f9fb8e`)
- **Problem:** the request returned 500 with `django.db.utils.OperationalError: the connection is closed`, raised by psycopg on allauth's unique-email check (the first query in form validation). The same form posted 8 s later succeeded. Earlier requests on the same instance (login, home page, sign-up GET) were fine.
- **Checked:** Cloud SQL `hl-stage-sql` was `RUNNABLE` (activation policy `ALWAYS`) with no operations after 01:07 UTC, and its logs show only autovacuum around 01:52, with no terminated connections. `DATABASES` in `cloud.py` sets no `CONN_MAX_AGE`, so Django should open a new connection per request. The cause is not known. psycopg raising "is closed" (rather than "server closed the connection unexpectedly") means the client already had the connection marked closed before the query ran.
- **Fix idea:** if it happens again, compare instance and thread timing. Options: set `CONN_MAX_AGE` with `CONN_HEALTH_CHECKS = True` so dead connections are replaced, or check what in the request could close the connection (gunicorn `gthread`, 8 threads).

## BUG-020 — Flaky cold_apply test data: value too long for a 50-character column
- **Severity:** Low · **Status:** Open · **Found:** 2026-10-18, full test run during signup redesign Step 7 · **Suspected:** seen once; the rerun passed (95 tests)
- **Where:** `cold_apply/tests/test_access.py:32` (`JobFactory(participant=cls.owner)` in `setUpTestData`), factories in `cold_apply/tests/factories.py`
- **Problem:** `psycopg.errors.StringDataRightTruncation: value too long for type character varying(50)`. A Faker-generated value sometimes exceeds a `max_length=50` column, so the whole test class errors.
- **Checked:** the only 50-character column in `cold_apply/models.py` is `Job.remote`, which the factory fills from a fixed list. The value probably comes from a SubFactory (Organization, Position or Location), or from a column whose database length differs from the model. Not tracked down.
- **Fix idea:** find the column with `\d` on the test tables after a failure, then cap that factory field, e.g. `factory.LazyFunction(lambda: fake.company()[:50])`.

## BUG-021 — Every staff user can open DD214s
- **Severity:** High · **Status:** Fixed (`feature/cold-apply-staff-redesign`, 8adb309; merged into develop; deployed with the next release) · **Found:** 2026-10-19, cold_apply staff redesign review
- **Where:** `userprofile/views.py` `update_veteran_status_view` (`@staff_required`, makes a signed URL for `profile.service_doc`); `userprofile/admin.py` `ProfileAdmin` and `VeteranProfileAdmin` (the default change form shows `service_doc` as a link, and GCS storage signs it for 24 h by default)
- **Problem:** anyone with `is_staff` can reach the veteran status page and open the DD214. Anyone with view or change permission on Profile in admin can do the same. DD214s should be limited to a small group of veteran-status reviewers.
- **Fix idea:** add a custom permission (e.g. `userprofile.review_veteran_status`), check it on the view and in the templates, and exclude or guard `service_doc` in both admin classes. Planned in `docs/cold-apply-staff-redesign.md` §5.

## BUG-022 — Do Not Contact badge is never shown to staff
- **Severity:** Medium · **Status:** Fixed (`feature/cold-apply-staff-redesign`, e0b44c1, Step 7: the staff blocks moved from the participant page to the staff workspace, which shows the badge; not yet merged into develop) · **Found:** 2026-10-19, cold_apply staff redesign review
- **Where:** `cold_apply/templates/cold_apply/participant_detail.html` (`{% if object.user.is_staff %}` around the DNC badge)
- **Problem:** the check is whether the **participant** is staff, not the viewer. Participants are never staff, so staff never see "Do Not Contact".
- **Fix idea:** use `{% if user.is_staff %}`.

## BUG-023 — Participant page shows blank phone and email
- **Severity:** Medium · **Status:** Fixed (`feature/cold-apply-staff-redesign`, e0b44c1, Step 7: the broken lines were removed; the staff workspace shows the user's email and profile phone; not yet merged into develop) · **Found:** 2026-10-19, cold_apply staff redesign review
- **Where:** `cold_apply/templates/cold_apply/participant_detail.html` (`{{ object.phone }}`, `{{ object.email }}`)
- **Problem:** `Participant` has no `phone` or `email` field, so both always render empty.
- **Fix idea:** `object.user.profile.phone` and `object.user.email`.

## BUG-024 — Participants with no current step don't appear on the pipeline
- **Severity:** Medium · **Status:** Fixed (`feature/cold-apply-staff-redesign`, 4d8a610 and 219cdfd, Steps 3 and 5: everyone gets an enrollment, participants with no step go to Intake › Triage, and the dashboard lists enrollments instead of phases; not yet merged into develop) · **Found:** 2026-10-19, cold_apply staff redesign review
- **Where:** `cold_apply/templates/cold_apply/participant_list.html`; `Participant.current_step` is nullable with `on_delete=SET_NULL`
- **Problem:** every table filters on `participant.current_step.phase == phase`. A participant whose step is empty, or whose step was deleted, isn't listed anywhere, so staff lose track of them.
- **Fix idea:** add an "Unassigned" group. The staff redesign replaces this page anyway.

## BUG-025 — "Highest Education" is just the first Education row
- **Severity:** Low · **Status:** Fixed (`feature/cold-apply-staff-redesign`, e0b44c1, Step 7: the label is now "Education" and lists every entry; not yet merged into develop) · **Found:** 2026-10-19, cold_apply staff redesign review
- **Where:** `cold_apply/views.py` `ParticipantDetailView.get_context_data` (`Education.objects.filter(...).first()`)
- **Problem:** `Education` has no ordering, so this is whichever row the database returns first.
- **Fix idea:** order by degree level, or rename the label.

## BUG-026 — Pipeline date prints the month where the minutes should be
- **Severity:** Low · **Status:** Fixed (`feature/cold-apply-staff-redesign`, 219cdfd; the template was deleted; not yet merged into develop) · **Found:** 2026-10-19, cold_apply staff redesign review
- **Where:** `cold_apply/templates/cold_apply/participant_list.html` (`date:"F j, Y: H:m:s T"`)
- **Problem:** `m` is the month in Django's date format; minutes are `i`.
- **Fix idea:** `"F j, Y H:i T"`.

## BUG-027 — Veteran status button is superuser-only, the view is staff-only
- **Severity:** Low · **Status:** Fixed (`feature/cold-apply-staff-redesign`, 8adb309; merged into develop; deployed with the next release) · **Found:** 2026-10-19, cold_apply staff redesign review
- **Where:** `participant_detail.html` (`{% if user.is_superuser %}`) vs `userprofile/views.py` `update_veteran_status_view` (`@staff_required`)
- **Problem:** the button and the view disagree, so the button hides a page that any staff user can still open by URL. Superseded by BUG-021's permission.

## BUG-028 — Profile admin search raises FieldError
- **Severity:** Low · **Status:** Fixed (`feature/cold-apply-staff-redesign`, 8adb309; merged into develop; deployed with the next release) · **Found:** 2026-10-19, cold_apply staff redesign review · **Suspected:** read from code, not reproduced
- **Where:** `userprofile/admin.py` `ProfileAdmin.search_fields`
- **Problem:** it lists `"user"` (a ForeignKey, so `icontains` is invalid) and `"nickname"` (no longer a field). Any search in the Profile admin should raise FieldError. `list_filter = ("user", ...)` also lists every user as a filter.
- **Fix idea:** `search_fields = ("user__email", "user__first_name", "user__last_name", "city", "state")`, and drop `user` from `list_filter`.

## BUG-029 — Dead or misleading code in the cold_apply staff pages
- **Severity:** Low · **Status:** Fixed (`feature/cold-apply-staff-redesign`, 3766a04; not yet merged into develop) · **Found:** 2026-10-19, cold_apply staff redesign review
- **Where:** `cold_apply/`
- **Problem:**
  - `templates/staff.html` has a Bootstrap navbar in `block content`. All 23 cold_apply templates that extend it override `content`, so the navbar never renders.
  - `participant_detail.html` calls `new bootstrap.Collapse(...)` on `#jobs-panel-new-jobs`. Bootstrap isn't loaded and the element no longer exists (the panels are `<details>`).
  - `templates/cold_apply/index.html` is an old to-do list and isn't routed.
  - `ParticipantListView.model = Phase` although it lists Participants. `ParticipantDetailView` fetches the participant again instead of using `self.object`.
  - The URL `companiies/<pk>/update/` is misspelled.
- **Fix idea:** remove these as part of the staff redesign.

## BUG-030 — Any logged-in user can create shared reference data
- **Severity:** Low · **Status:** Open · **Found:** 2026-10-19, cold_apply staff redesign review
- **Where:** `cold_apply/views.py` `OrganizationCreateView`, `TitleCreateView`, `PositionCreateView`, `ConcentrationCreateView`, `LocationCreateView`, `LocationDetailView`, `LocationListView` (all `LoginRequiredMixin`)
- **Problem:** any participant can add companies, titles, positions, concentrations and locations, and list all locations. This may be intended, because participants pick these values on their own forms. Confirm before restricting.

## BUG-031 — New signups can land in the wrong phase
- **Severity:** Medium · **Status:** Fixed (`feature/cold-apply-staff-redesign`, 1cc7b0c, Step 4: signups get an explicit Intake enrollment; the old step is chosen by title, not "the first step"; not yet merged into develop) · **Found:** 2026-10-19, read-only prod query for the cold_apply staff redesign · **Suspected:** read from code and prod data, not reproduced
- **Where:** `userprofile/models.py` `Profile.handle_onboard_complete` (`Step.objects.order_by("phase__order", "order").first()`)
- **Problem:** on prod, Applicants, Phase 1 and Nurture all have phase order 0, and their first steps all have step order 0 (Verify Veteran Status, Send Initial Email, Boot Camp Alumni / Monthly Newsletter). Postgres may return any of these ties first, so a new participant can start in Nurture instead of Applicants.
- **Fix idea:** the cold_apply staff redesign (Step 4) replaces this with an explicit Intake enrollment. Until then, give Applicants a unique lowest order in admin.

## BUG-032 — Participant page says "Not a Veteran Veteran" for a veteran with no branch
- **Severity:** Low · **Status:** Open · **Found:** 2026-10-19, cold_apply staff redesign (Step 7 browser check)
- **Where:** `cold_apply/templates/cold_apply/participant_detail.html` (`{{object.user.profile.service_branch}} Veteran ({{ object.user.profile.rank_at_separation}})`); `Profile.service_branch` defaults to `"Not a Veteran"`, which isn't one of its choices
- **Problem:** when `is_veteran` is true but no branch was chosen, the page prints the raw default and the missing rank: "Not a Veteran Veteran (None)". The participant sees this about themselves.
- **Fix idea:** use `get_service_branch_display`, and skip the branch and rank when they're unset. Better, make the default `None`, since "Not a Veteran" duplicates `is_veteran`.
