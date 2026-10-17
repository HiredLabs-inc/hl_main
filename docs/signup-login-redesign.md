# Signup & Login Redesign

## Context
Signup currently creates a `User` the moment an email is entered, strips the password, and sends an optional confirmation email over Gmail SMTP. This fills the DB with bots, strands real users who get interrupted, and leaves no homepage login. Review also found authorization holes that let any self-signup see other veterans' data.

Decisions: password is set **after** email verification; **no volunteer login yet**; **Cloudflare Turnstile + honeypot**; purge existing junk, but give stuck people a way back; **move off Gmail SMTP**.

## Shortcomings
1. User created before email confirmed → bot accounts pile up.
2. Interrupted signup is a dead end ("email in use", no resend/login/reset).
3. No login link on the homepage.
4. Signup removes the password → users can't log back in.
5. Email send failure → 500 error and an orphaned account.
6. Signup form reveals which emails are registered.
7. No bot protection; rate limits bypassable via spoofed `X-Forwarded-For`.
8. No reminders or recovery path for people who stall.
9. No cleanup of unverified accounts.
10. **Any logged-in user** can reach staff pages and cold_apply participant data.
11. **IDOR**: any user can view/edit any veteran status and get a 7‑day link to their DD214 (`userprofile/views.py:120`).
12. Several cold_apply views have no auth at all; task endpoint trusts a client header.
13. Welcome "Done" button logs users out; logout is a GET link; broken URL names in `staff.html`.
14. Gmail SMTP is unreliable for transactional mail (sending limits, deliverability, no bounce handling).
15. Emailed links use `http://`; weak HSTS; Django 4.2.2 missing security patches.

## Plan

### Step 0 — Working environment
- Branch `feature/signup-login-redesign` from `develop`, in worktree `.claude/worktrees/signup-login-redesign`.
- Tests run in Docker under a separate compose project so the IDE's `hl_main` stack is untouched:
  - `docker compose -p hl-signup build django`
  - `docker compose -p hl-signup run --rm frontend sh -c "npm ci && npm run build"` (templates need `frontend/build/manifest.json`)
  - `docker compose -p hl-signup run --rm django python manage.py test`
- Test data comes from the factory-boy factories in `cold_apply/tests/factories.py`, replacing `cold_apply/fixtures/dev_data.json`, which was deleted in `f49da2f` (Mar 2025). Stale factory fields were fixed, and the stale `userprofile/tests/test_onboarding.py` was removed (Step 8 replaces it).
- Baseline on clean `develop`: 19 tests found, 15 errors (missing fixture, stale onboarding tests).

### Step 1 — Lock down authorization (fixes 10–12, ship first)
- Add `staff_required` / `StaffRequiredMixin` in `userprofile/guards.py` (beside `verified_required`); apply to `staff`, `update_veteran_status_view`, and staff cold_apply views.
- Add auth + `require_POST` to unauthenticated cold_apply views; verify Cloud Tasks OIDC token on `task_get_jobs_for_participant`.
- Shorten DD214 signed-URL expiry to ~10 minutes.

### Step 2 — Switch email provider (fixes 14)
- **Postmark** via **django-anymail 14.0**, the last version that supports Django 4.2 (15.x needs Django 5).
- `hl_main/settings/cloud.py` (shared by stage and prod):
  - Uses `anymail.backends.postmark.EmailBackend` when `POSTMARK_SERVER_TOKEN` is set in the Secret Manager secret.
  - Otherwise falls back to the existing Gmail SMTP settings, so deploying before the secret exists never stops mail.
  - Dev keeps the console backend.
- **Bounce and complaint handling:**
  - The anymail tracking webhook is at `/anymail/postmark/tracking/`, protected by HTTP basic auth from `ANYMAIL_WEBHOOK_SECRET` (`user:password`).
  - The URL is only mounted when a secret is set. Dev uses `dev:dev`.
  - `userprofile/signals.py` records spam complaints, and any bounce after which Postmark marks the address `Inactive`, in the new `EmailSuppression` model (also shown in admin).
  - Soft bounces are ignored. Step 6 reminders will skip suppressed addresses.
- Tests: `userprofile/tests/test_email.py` covers the webhook (hard bounce, soft bounce, spam complaint, delivery ignored, bad credentials) and sending through the Postmark API.
- **Manual setup (outside the code):**
  1. Create a Postmark account and server. Use the default "outbound" transactional stream.
  2. Add `hiredlabs.org` as a sender signature domain, then add Postmark's DKIM TXT record and Return-Path CNAME in DNS.
  3. Make sure SPF covers both Google and Postmark while both are in use. Add a DMARC record (start with `p=none` plus a `rua` report address, and tighten later).
  4. While the Postmark account is pending approval, it can only send to addresses on its own domain. Test on stage first.
  5. Add `POSTMARK_SERVER_TOKEN` and `ANYMAIL_WEBHOOK_SECRET` to the stage secret, deploy, and send a test (for example a password reset). Check delivery and DKIM in Postmark's activity view.
  6. In Postmark, add a webhook to `https://<host>/anymail/postmark/tracking/` with basic auth from the secret. Enable Bounce and Spam Complaint events.
  7. Repeat steps 5 and 6 for prod. Once Postmark is confirmed working, remove `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` and the SMTP fallback.

### Step 3 — Settings hygiene (fixes 15)
- `ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"`, HSTS 1 year (drop preload for now), Django → latest 4.2.x.
- Add Turnstile keys to settings.

### Step 4 — New signup flow (fixes 1, 2, 4–7)
- New `PendingSignup` model (email, timestamps, send count, last error). **No `User` until the link is clicked.**
- `/accounts/signup/`: email + Turnstile + honeypot → send a signed link (7-day expiry) → "Check your email" page with **Resend** and **Use a different email**.
- Entering an existing account's email shows the same page and sends a "log in or reset your password" email instead.
- Link → **Set password** page → create user with verified email → log in → onboarding.
- Expired/used link → "send me a new link."
- Send errors are caught and shown with a retry button.
- Disable allauth's own signup (`is_open_for_signup = False` in `hl_main/adapter.py`); fix client-IP detection there; one signup URL.
- Turnstile + honeypot also on password reset and contact forms.

### Step 5 — Login & navigation (fixes 3, 13)
- Homepage nav: **Log in / Sign up** when logged out; **My account / Log out** when logged in. Staff use the same login; existing `user_home` routes by role.
- Login page links to Sign up and Forgot password.
- "Done" on welcome page no longer logs out; logout becomes a POST button; fix `staff.html`.

### Step 6 — Helping stuck people (fixes 8)
- One reminder email ~24h after an unclicked signup link.
- Reminders at ~3 and ~14 days for users who created an account but didn't finish onboarding (logging in already resumes onboarding).
- Daily `send_signup_reminders` command (Cloud Scheduler → Cloud Run Job).
- Staff **Stuck signups** page: list pending/unfinished users with **Resend link**, **Send reminder**, **Delete**.

### Step 7 — Clean up existing data (fixes 9)
- `purge_legacy_unverified_users` command: targets non-staff, unverified, never-onboarded, no-password users created before cutover.
- `--dry-run`, `--export file.csv`, and optional `--invite --batch-size N` to email a new signup link before deleting.
- Run only after Steps 2 and 4 are live. Never-completed `PendingSignup` rows auto-expire after 30 days.

### Step 8 — Tests
- Signup creates no `User`; identical response for new vs. existing emails; token completion, expiry, reuse; send failure handled; Turnstile/honeypot rejection; staff-only access and IDOR closed; purge and reminder commands.
- Replace stale `userprofile/tests/test_onboarding.py`.

## Key files
`userprofile/{guards,models,forms,views,urls}.py`, `hl_main/adapter.py`, `hl_main/urls.py`, `hl_main/settings/{base,stage,prod}.py`, `cold_apply/views.py`, `templates/new_home_base.html`, `templates/account/*`, `templates/welcome.html`, `templates/base_app.html`, `requirements.txt`.

## Verification
- `python manage.py test userprofile cold_apply`.
- Dev walkthrough: sign up → close browser → re-enter email → resend → set password → log out → log in from homepage. Repeat with an existing email. Staff login lands on `/staff/`.
- As non-staff: staff pages and another user's veteran-status page are denied.
- Stage: send through Postmark and check delivery/DKIM; run the purge with `--dry-run --export` and review before the real run.
