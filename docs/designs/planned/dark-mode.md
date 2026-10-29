# Dark Mode (IDEA-010)

Branch `feature/idea-010-dark-mode` (from `develop`), not started.

> **Status:** drafted 2026-10-29. Storage and rollout agreed with Jeff (decisions in §5). Open items in §7.

## 1. Context
IDEA-010: "users and site visitors can select dark or light mode, and the site defaults to the system setting." Today every page is light only.

What's already in place:
- Tailwind 3.3 with `darkMode: 'class'` already set (`frontend/tailwind.config.js`), built by Vite into `src/main.css` and loaded with `{% load_vite_js 'src/main.js' %}`. Alpine 3 and htmx are in `frontend/src/main.js`.
- Three base templates: `templates/base.html` (used by `staff_base.html` for about 50 pages and `base_app.html` for 17 legacy cold_apply pages), `templates/new_home_base.html` (public site, plus `account/base.html` for allauth and onboarding pages), and `resume/templates/resume/base_resume.html` (Bootstrap resume documents).
- Most colours are already semantic custom tokens: `hl-muted`, `hl-line`, `hl-ink`, `hl-mist`, `hl-navy` and others, about 550 uses. There are also about 260 raw `bg-white` / `text-gray-*` / `border-gray-*` uses, mostly in `userprofile`, `frontend` components, `templates` and `cold_apply`.
- Only `userprofile/onboarding_upload_resume.html` and `frontend/templates/components/spinner.html` have `dark:` classes. They came from Preline copy-paste, do nothing today, will switch on once dark mode exists, and include a typo (`dark:hover:bg-bray-800`).

## 2. Goals
- Three choices: **System** (the default), **Light** and **Dark**. Visitors and logged-in users get the same control.
- The choice is saved **in this browser only** (`localStorage`). No account field or migration (decided 2026-10-29).
- No flash of the wrong theme when a page loads.
- Every page in `base.html` and `new_home_base.html` looks right in both modes, and text meets WCAG AA contrast.
- One branch, `feature/idea-010-dark-mode`, built in stages and merged only when every page is done, so no flag is needed (decided 2026-10-29).

**Not goals:** resume documents and PDFs (`base_resume.html` doesn't extend `base.html`, so they stay light, which suits printing). Emails. Django admin, which has its own theme switch since 4.2.

## 3. Design

### 3.1 Colour tokens as CSS variables
- In `tailwind.config.js`, the neutral tokens become `rgb(var(--hl-ink) / <alpha-value>)`, so `/opacity` modifiers keep working. The values go in `main.css` `@layer base`: `:root { ... }` for light and `.dark { ... }` for dark. Every existing `text-hl-muted` etc. then flips with no template edit.
- **Tokens that flip:**

  | Token | Light (today) | Dark |
  |---|---|---|
  | `hl-page` (new, body background) | `#FFFFFF` | `#0A1626` |
  | `hl-surface` (new, cards, menus, nav; replaces `bg-white`) | `#FFFFFF` | `#0E1F33` (brand navy) |
  | `hl-fg` (new, strong text; replaces `text-hl-navy`/`text-gray-900` on surfaces) | `#0E1F33` | `#F1F5F9` |
  | `hl-ink` | `#3B4A5C` | `#CBD5E1` |
  | `hl-muted` | `#5A6878` | `#94A3B8` |
  | `hl-line` | `#E4E8EE` | `#2E4560` |
  | `hl-mist` | `#F5F7FA` | `#16304B` |
  | `hl-cream` | `#FFF3E3` | `#3A2A12` |
  | `hl-orange-text` | `#B45F06` | `#FBB040` |
  | `hl-amber` | `#8A4A05` | `#FBC56E` |

  The exact dark values are first picks. Stage D5 checks contrast on each text/background pair.
- **Tokens that stay fixed:** `hl-navy`, `hl-navy-2`, `hl-navy-line`, `hl-steel`, `orange`, `hl-orange`, `hl-blue`. These are brand colours, and the staff header (`bg-hl-navy text-white`) is already dark. Places that use `hl-navy` as **text** on a light surface (36 uses) move to `hl-fg`. Navy **buttons** (`.hl-btn-dark`, the nav's Sign up / My account) get a `dark:` style (`bg-hl-navy-2` with an `hl-navy-line` border) so they stay visible on a navy surface.
- **Raw grays and white** are swapped for tokens by this table, not with `dark:` pairs: `bg-white`→`bg-hl-surface`, `bg-gray-50/100`→`bg-hl-mist`, `text-gray-900/800`→`text-hl-fg`, `text-gray-700/600`→`text-hl-ink`, `text-gray-500/400`→`text-hl-muted`, `border-gray-100…300`/`divide-gray-*`→`hl-line`. `text-white` on coloured buttons stays.
- **Status colours** (green/amber/red badges, `.btn-*`): `dark:` variants go in the component classes in `main.css` (`.staff-badge-ok/warn/bad`, `.btn-*`, `.btn-outline-*`, `.td`, `.tr`, `.auth-*`), not in templates.
- **Forms:** `@tailwindcss/forms` gives inputs a white background. A `.dark` base rule sets inputs, selects and textareas to `hl-surface` / `hl-line` / `hl-fg`, with a readable placeholder colour.
- `html { color-scheme: light }` and `.dark { color-scheme: dark }`, so scrollbars, date pickers and other native controls match.
- Classes built in Python (`pipeline/*.py`, `core/templatetags`, `frontend/templatetags`, `cold_apply/forms.py`) follow the same table.

### 3.2 Applying the theme without a flash
A small inline script in `<head>` of `base.html` and `new_home_base.html`, **before** `load_vite_js`, reads `localStorage['hl-theme']` (`light` | `dark` | missing = system), checks `matchMedia('(prefers-color-scheme: dark)')`, and sets `class="dark"` on `<html>`. It's wrapped in `try` because localStorage can throw in private modes. It's a shared include (`frontend/templates/components/theme_head.html`) so both bases stay the same. No CSP is set today, so an inline script is fine. If one is added later, this script needs a nonce or hash.

### 3.3 The switcher
- `frontend/src/theme.js` (imported by `main.js`) registers an Alpine store `theme` with `choice` (`system`/`light`/`dark`) and `set(choice)`. `set` writes or clears localStorage and toggles the class. While the choice is System, a `matchMedia` change listener follows the OS live.
- `frontend/templates/components/theme_toggle.html`: a three-option radio group (System / Light / Dark, with sun, moon and monitor icons and visible labels), `role="radiogroup"`, usable with the keyboard.
- Where it goes:
  - `staff_base.html` Menu dropdown, under **Account**.
  - `base_app.html` Menu dropdown, under **Settings**.
  - Public site: `site_footer.html`, and the mobile menu in `site_nav.html`.

### 3.4 Images
`HiredLabs-transparent.png` (used in the nav and footer) has a navy wordmark that won't show on a dark surface. It needs a light-wordmark version (`HiredLabs-transparent-light.png`), shown with `dark:hidden` / `hidden dark:block` pairs. Photos are fine as they are.

## 4. Stages (one branch, `feature/idea-010-dark-mode`)
- **D1 — Tokens and switcher.** Config, CSS variables, the new tokens, component classes in `main.css`, the form rules, `theme_head.html`, `theme.js`, `theme_toggle.html`, and the toggle in all three menus.
- **D2 — Staff pages.** `staff_base.html` and its pages in `pipeline`, `hlagents`, `userprofile` (staff views) and `templates/`, plus the board (`board.js` `board-saving` style) and classes built in Python.
- **D3 — Public site, account and onboarding.** `new_home_base.html`, `site_nav`, `site_footer`, home, about, impact, how-it-works, legal pages (`.hl-prose`, `.hl-card`, `.hl-btn-*`), `account/*`, and both onboarding bases. Fix or remove the stray Preline `dark:` classes. Add the light logo.
- **D4 — Legacy and shared pieces.** The 17 `base_app.html` cold_apply pages, `modal.html`, `components/toaster.html`, `breadcrumb.html`, `spinner.html`, and the form components (`form_input`, `inline_form_input`, `form_errors`).
- **D5 — Check and merge.** Go through every page in both modes, check contrast, run the leftovers grep (§6), then merge into develop.

## 5. Decisions (2026-10-29)
1. The choice is saved in this browser only (localStorage), not on the account.
2. Everything ships at once from one branch, built in stages D1–D5. No feature flag.
3. Tokens become CSS variables instead of adding `dark:` to each template. Brand colours stay fixed.
4. Resume documents, emails and Django admin are out of scope.

## 6. Verification
- `cd frontend && npm run build` succeeds. Then `python manage.py runserver`.
- In both modes, plus System with the OS switched both ways: `/staff/` (table and board), a person page, flows, volunteers, `/agents/`, the public home/about/impact/legal pages, login and signup, onboarding steps, and a legacy cold_apply page (e.g. job detail). Open the menus, the modal, a toast and a form with errors.
- No flash: hard-reload with dark chosen and CPU throttling on in devtools.
- Leftovers grep: `grep -rnE "\b(bg-white|text-gray-[0-9]+|bg-gray-[0-9]+|border-gray-[0-9]+)\b"` over the template dirs and the Python files that build classes. Only allowed exceptions are left, and each is listed in the doc.
- Contrast: every text token on `hl-page`, `hl-surface` and `hl-mist` is ≥ 4.5:1 in both modes (checked with a script or devtools).
- `python manage.py test` passes. A small test in `hl_main/tests` renders one page from each base and checks that the head script and toggle are there.

## 7. Open items
- The light-wordmark logo: Jeff provides it, or it's made from the current PNG.
- Whether the dark page colours should be navy (as above) or a neutral near-black. To be decided from a mockup in D1.
