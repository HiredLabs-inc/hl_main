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
| BUG-002 | Medium | Open | rates, releases | Views only require login; any self-signup can use them |
| BUG-003 | Medium | Open | userprofile | `handle_onboard_complete` can raise IntegrityError for an existing participant |
| BUG-004 | Medium | Open | cold_apply | `home_view` returns 500 for a non-staff user with no Participant |
| BUG-005 | Medium | Open | userprofile | `Profile.service_package` hard-codes `default=1` |
| BUG-006 | Medium | Open | settings | `manage.py` defaults to prod settings |
| BUG-007 | Low | Open | settings | `PRODUCTION` is only defined in `cloud.py` |
| BUG-008 | Low | Open | background_tasks | `work_task` crashes on a missing task and swallows task errors |
| BUG-009 | Low | Open | cold_apply | `OverviewDeleteView.get_success_url` crashes when no job matches |
| BUG-010 | Low | Open | cold_apply | Suspected: `JobUpdateView.get_success_url` with no `?from=` |
| BUG-011 | Low | Open | cold_apply | Dead or broken code: `ConfigureTailoredResumeView`, `create_interaction`, unreachable branches |
| BUG-012 | Low | Open | tests | Two stale test modules never run |
| BUG-013 | Low | Open | dev data | `load_dev_data` creates two superusers with the same email |
| BUG-014 | Low | Open | frontend | `npm install` rewrites `package-lock.json` |
| BUG-015 | Low | Open | hlagents | `hlagents` scaffold is half-wired (on `feature/hlagents-01`) |

---

## BUG-001 — Deletes and keyword refresh run on GET links (CSRF)
- **Severity:** High · **Status:** Fixed (`fix/bug-001-csrf-get-deletes`, 1d04bee; merged into `feature/signup-login-redesign`) · **Found:** 2026-10-16, signup redesign Step 1
- **Where:**
  - Views: `cold_apply/views.py` `delete_job`, `delete_exp`, `delete_education`, `delete_bullet`, `refresh_keywords`
  - Templates: `cold_apply/templates/cold_apply/partials/job_actions.html:7`, `participant_experience_list.html:41,72`, `partials/bullet_detail_li.html:18`, `partials/bullet_preview_detail_li.html:9`, `job_detail.html:61`
- **Problem:** these views change data on a plain GET from an `<a href>`. A link or image on any other site can make a logged-in user's browser delete their own jobs, experience or bullets. Step 1 added owner checks, so one user can no longer delete another user's data, but this cross-site request risk remains.
- **Fix idea:** add `@require_POST` and change the links to small POST forms (or `hx-post` with the CSRF header already set on `<body>`).

## BUG-002 — rates and releases views only require login
- **Severity:** Medium · **Status:** Open · **Found:** 2026-10-16
- **Where:** `rates/views.py` (`RateRequestListView`, `RecommendationCreateView`, `world_rates`); `releases/views.py` (all views, including `AppCreateView` and `ReleaseCreateView`)
- **Problem:** any logged-in user can use these, including an unverified self-signup. The "World Rates" nav link is hidden by `perms.rates` in `templates/base_app.html:63`, but the views don't check that permission.
- **Fix idea:** decide who should use each view. Then apply `StaffRequiredMixin` (`userprofile/guards.py`) or `PermissionRequiredMixin` to match the nav.

## BUG-003 — `handle_onboard_complete` can raise IntegrityError
- **Severity:** Medium · **Status:** Open · **Found:** 2026-10-16
- **Where:** `userprofile/models.py:59` (`Profile.handle_onboard_complete`)
- **Problem:** it calls `Participant.objects.get_or_create(user=self.user, current_step=step)`, which looks up by both user and step. `Participant.user` is one-to-one, so if the user already has a Participant on a different step, the lookup misses, the create runs, and it raises IntegrityError. This can happen when onboarding is resubmitted or a Participant was created by hand.
- **Fix idea:** `get_or_create(user=self.user, defaults={"current_step": step})`.

## BUG-004 — `home_view` 500 for non-staff without a Participant
- **Severity:** Medium · **Status:** Open · **Found:** 2026-10-16
- **Where:** `cold_apply/views.py` `home_view` (`# TODO handle no profile`)
- **Problem:** `request.user.participant.id` raises RelatedObjectDoesNotExist for a verified user who hasn't finished onboarding.
- **Fix idea:** redirect to `userprofile:user_home`, which already routes to onboarding.

## BUG-005 — `Profile.service_package` hard-codes `default=1`
- **Severity:** Medium · **Status:** Open · **Found:** 2026-10-16
- **Where:** `userprofile/models.py:31`
- **Problem:** every new Profile points at ServicePackage pk=1. On a fresh database, in tests, or if that row is ever deleted, creating a Profile fails with a foreign-key error. This broke the old onboarding tests and `load_dev_data` (worked around in that command on `feature/signup-login-redesign`).
- **Fix idea:** `default=None`, or a callable that looks the package up by name, plus a data migration that seeds the packages.

## BUG-006 — `manage.py` defaults to prod settings
- **Severity:** Medium · **Status:** Open · **Found:** 2026-10-16
- **Where:** `manage.py:9` (`setdefault("DJANGO_SETTINGS_MODULE", "hl_main.settings.prod")`)
- **Problem:** running `manage.py` anywhere `DJANGO_SETTINGS_MODULE` isn't set (a host shell, a new IDE run configuration) loads prod settings. Docker Compose sets dev settings, so normal dev use isn't affected.
- **Fix idea:** default to `hl_main.settings.dev`; Cloud Run already sets the variable explicitly.

## BUG-007 — `PRODUCTION` setting only defined in `cloud.py`
- **Severity:** Low · **Status:** Open · **Found:** 2026-10-16
- **Where:** `hl_main/settings/cloud.py:16`; read in `background_tasks/queue.py` (`send_task_to_queue`, `delete_task`)
- **Problem:** `base.py`, `dev.py` and `build.py` don't define `PRODUCTION`. With `DEBUG=False` under those settings (for example `delete_task` in tests), `settings.PRODUCTION` raises AttributeError. The new `is_authorized_task_request` uses `getattr(..., False)` to avoid this.
- **Fix idea:** `PRODUCTION = False` in `base.py`.

## BUG-008 — `work_task` crashes on a missing task and swallows errors
- **Severity:** Low · **Status:** Open · **Found:** 2026-10-16
- **Where:** `background_tasks/queue.py` `work_task`
- **Problem:** a missing or wrong `X-Task-Id` gives `task = None`, so `task.start()` raises AttributeError and the request returns 500. If the task function raises, the error is recorded but the view still returns `{"status": "success"}`, so Cloud Tasks never retries.
- **Fix idea:** return 404 for an unknown task. Return a non-2xx response on failure if retries are wanted.

## BUG-009 — `OverviewDeleteView.get_success_url` can crash
- **Severity:** Low · **Status:** Open · **Found:** 2026-10-16
- **Where:** `cold_apply/views.py` `OverviewDeleteView.get_success_url`
- **Problem:** `self.object.participant.job_set.filter(title=self.object.title).first().id` raises AttributeError when no job has that title. The overview is already deleted by then, so the user sees a 500 after a successful delete.
- **Fix idea:** fall back to the participant detail page.

## BUG-010 — Suspected: `JobUpdateView.get_success_url` without `?from=`
- **Severity:** Low · **Status:** Open (Suspected) · **Found:** 2026-10-16
- **Where:** `cold_apply/views.py` `JobUpdateView.get_success_url`
- **Problem:** `resolve(self.request.GET.get("from"))` only catches `Resolver404`. With no `from` parameter it calls `resolve(None)`, which may raise a different exception. Not reproduced.
- **Fix idea:** check `from_url` before calling `resolve`, and use `url_has_allowed_host_and_scheme`.

## BUG-011 — Dead or broken code in cold_apply
- **Severity:** Low · **Status:** Open · **Found:** 2026-10-16
- **Where:** `cold_apply/views.py`
  - `ConfigureTailoredResumeView`: not routed, and uses `self.kwargs[""]`.
  - `create_interaction`: not routed.
  - `ParticipantDetailView.get_form_class`: unreachable lines after `return`.
  - `OrganizationUpdateView` / `TitleUpdateView` / `ExperienceUpdateView.form_valid`: unreachable `else: print(form.errors)`.
  - `ParticipantDetailView.form_valid`: returns `None` for any form other than `NewJobSelectionForm`.
- **Fix idea:** delete the dead code; return a response in every branch.

## BUG-012 — Stale test modules never run
- **Severity:** Low · **Status:** Open · **Found:** 2026-10-16
- **Where:** `cold_apply/tests/cold_apply_models_test.py`, `userprofile/tests/up_models_test.py`
- **Problem:** Django's test discovery only picks up `test*.py`, so these files never run. They also use fields that no longer exist (`Participant.name`, `email`, `uploaded_resume`; `Profile.nickname`).
- **Fix idea:** delete them, or rename to `test_*.py` and rewrite with the factories in `cold_apply/tests/factories.py`.

## BUG-013 — `load_dev_data` creates two superusers with the same email
- **Severity:** Low · **Status:** Open · **Found:** 2026-10-16
- **Where:** `cold_apply/management/commands/load_dev_data.py` (lines with `create_superuser`)
- **Problem:** it creates usernames `admin@admin.com` and `admin`, both with email `admin@admin.com`. Login is by email through allauth, so which account you get is ambiguous. The README says to log in as `admin` / `admin`.
- **Fix idea:** create one superuser and update the README.

## BUG-014 — `npm install` rewrites `package-lock.json`
- **Severity:** Low · **Status:** Open · **Found:** 2026-10-16
- **Where:** `frontend/package-lock.json`; the `frontend` service in `docker-compose.yml` runs `npm install` on every start
- **Problem:** the committed lock file doesn't match what the container's npm produces, so every frontend start dirties the working tree. It also showed up in commit `3774ce6` on `feature/hlagents-01`.
- **Fix idea:** regenerate and commit the lock file with the container's npm version, and use `npm ci` in the compose command.

## BUG-015 — `hlagents` scaffold is half-wired
- **Severity:** Low · **Status:** Open · **Found:** 2026-10-15 · **Branch:** `feature/hlagents-01`
- **Where:** `hlagents/`, `hl_main/urls.py`
- **Problem:**
  - `hlagents/urls.py` is empty, so enabling the include raises ImproperlyConfigured.
  - The app isn't in `INSTALLED_APPS`.
  - `import hlagents` in `hl_main/urls.py` is unused.
  - The `hlagents/` directory is owned by root.
  - Commit message "added urls" actually commented the include out.
- **Fix idea:** add `urlpatterns = []`, register the app, and `chown` the directory.
