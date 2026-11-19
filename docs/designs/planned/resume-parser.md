# Resume Parser (IDEA-009)

Branch `feature/idea-009-resume-parser` (from `develop`), not started.

> **Status:** drafted 2026-10-29. Not agreed yet: the choices in §5 are proposals, and the open items in §7 need answers before P1.

## 1. Context
IDEA-009: "a participant or staff member uploads a resume (PDF or DOCX), and an LLM extracts experiences, education, bullets, companies, titles and locations. The person reviews the extracted values before they're saved." It came out of the BUG-030 discussion (2026-10-23).

**What already exists:**
- **Uploaded resumes.** Onboarding's Upload Resume step saves the file to `userprofile.Profile.resume` (`upload_to="uploads/"`, GCS in cloud). Staff open it from the person page (`userprofile/people.py` `_resume_url`, a signed URL) and the legacy participant detail page. Nothing reads its contents.
- **Matching.** `cold_apply/reference.py` `find_existing(model, values)` finds a company, title, concentration or location by name in any case (BUG-030). `ReuseExistingMixin` uses it on the create views.
- **Single-shot AI tasks.** `hlagents/completion.py` `complete(key, message, user)` runs a `TaskConfig` (provider, model, instructions, options) and records a `TaskCall` that counts toward the daily cost cap (IDEA-007). Resume generation and job keywords use it, through the "Gemini on Vertex" provider. `cold_apply/keywords.py` `parse_reply` and `text_generation.parse_bullets` already pull JSON out of a reply that may be in a code fence.
- **Text extraction libraries.** `pypdf` and `pdfminer.six` are in `requirements.txt`. There's nothing for DOCX.
- **Leftovers.** `ML_MODELS_PATH`, `ENTITIES_PATH` and `RESUME_OUT_PATH` in `hl_main/settings/base.py` point at the old `resume_parser` app. Nothing in the repo reads them.

**What the parser fills in** (`resume/models.py`):

| Model | Fields to fill | Required foreign keys |
|---|---|---|
| `Experience` | start_date (required), end_date (null = present) | `org` → `Organization`, `position` → `Position` (both PROTECT) |
| `Bullet` | text, type "Work" | `experience` |
| `Education` | status (completed / in progress) | `org`, `degree` → `Degree` (no `created_by`, a fixed list), `concentration` → `Concentration` |

**Locations don't fit.** `Experience` has no location field: `cold_apply.Location` is only used by `Job.location`. The backlog lists locations, but there's nowhere to put one from a resume today (§5.4).

`Organization.website` is a required CharField with no default, so new companies get `""`, as the create form already allows. `Bullet.MAX_PER_PARTICIPANT` (400) still applies.

## 2. Goals
- From a participant's experience page, staff or the participant can parse either the resume already on their profile or a newly uploaded PDF or DOCX.
- The LLM returns experiences (company, title, dates, bullets) and education (school, degree, concentration, status) as JSON.
- A review page shows everything found. Each value shows whether it matches an existing row ("existing") or will be created ("new"). The person can edit any value, pick a different existing row, and untick anything they don't want.
- Saving creates every ticked record in one transaction. Companies, titles and concentrations are reused through `find_existing`, so only unmatched values create rows, with `created_by` set to the person saving.
- Entries that look like ones the participant already has are unticked by default.
- The call runs through `complete()`, so the model is chosen in `/agents/settings/` and spend counts toward the daily cap.
- The dead `resume_parser` settings are removed.

**Not goals:** parsing skills, certifications, projects or the summary into `Overview` / `CertProjectActivity` (a later step, §7). Adding a location to `Experience`. Fuzzy matching ("Google" vs "Google LLC"; that's IDEA-003's duplicates page). Keeping the resume text or a copy of the file. Running parses in bulk over every existing profile.

## 3. Design

### 3.1 Text extraction (`cold_apply/resume_parser.py`)
`extract_text(file) -> str`:
- **PDF:** `pypdf.PdfReader`, joining `page.extract_text()` for each page.
- **DOCX:** stdlib `zipfile` and `xml.etree`, reading `word/document.xml` paragraph by paragraph (`w:p`, joining `w:t`), so no new dependency. Table cells are paragraphs too, so two-column resumes still come out in a usable order.
- Anything else, an encrypted PDF, or fewer than 200 characters of text (a scanned image) raises `ResumeParseError` with a message for the user: "We couldn't read text from this file. Try a PDF exported from Word or Google Docs."
- Text is cut at 30,000 characters (well past any real resume) to bound the cost.
- Limits on upload: 5 MB, `.pdf` / `.docx` by extension and by the first bytes (`%PDF` or `PK`).

Sending the PDF to Gemini as a file part would handle layout better, but `ChatProvider.chat` only takes text messages. Text first; §7 has the trade-off.

### 3.2 The task
- New key `resume_parse` ("Resume parser") in `hlagents/task_types.py`, seeded by a data migration on the "Gemini on Vertex" provider like `job_keywords` was, with `model = settings.GEMINI_MODEL`.
- **Options:** temperature 0, `max_output_tokens` 8192 (a resume with 6 jobs and 30 bullets is about 3,000 tokens of JSON), thinking_budget 0.
- **Instructions** ask for one JSON object and nothing else:

```json
{
  "experiences": [
    {"company": "Acme", "title": "Logistics Manager",
     "start": "2019-03", "end": "present",
     "bullets": ["Cut delivery times 20% by ..."]}
  ],
  "education": [
    {"school": "Texas A&M University", "degree": "BS", "concentration": "Supply Chain Management",
     "status": "completed"}
  ]
}
```

  - Dates are `YYYY-MM`, `YYYY`, `"present"` or `null`. Text is copied as written, not rewritten. Military service is an experience, with the branch as the company and the rank or MOS title as the title.
- `parse_resume(text, user) -> ParsedResume` calls `complete("resume_parse", text, user)` and parses the reply with the same code-fence-tolerant JSON load as `keywords.parse_reply` (moved to a shared helper if it's a third copy). A reply that isn't the right shape raises `ResumeParseError`.
- **Timing:** the call runs inside the request, under `completion.TIMEOUT` (45 s). Flash-class models answer a resume in about 10 to 20 s. The button shows the existing spinner and is disabled while it runs.

### 3.3 Draft storage (`cold_apply.ResumeImport`)
The review spans a GET and a POST, and staff may leave and come back, so the parse result is stored:

| Field | Notes |
|---|---|
| participant | FK, CASCADE |
| created_by | FK to User, SET_NULL |
| created_at | |
| source | "profile" or "upload", plus the file name, for the page heading |
| data | JSON: the parsed result, after normalising (§3.4) |

- No resume text or file is stored. An uploaded file is read in memory and dropped. It is **not** saved to `Profile.resume` (§5.3).
- The row is deleted when the person saves or discards. A management command deletes rows older than 7 days, run daily alongside `send_signup_reminders`.
- One open import per participant: parsing again replaces it.

### 3.4 Normalising and matching
Before the draft is stored, each value is cleaned and matched once:
- **Names:** stripped and spaces collapsed; empty values dropped.
- **Companies, titles, concentrations:** `reference.find_existing`. The draft keeps the matched pk, or `null` for "new".
- **Degree:** matched on `abbr` or `name` in any case, ignoring dots ("B.S." = "BS"). No match leaves it blank, and the review page requires a pick from the list, because `Degree` is a fixed list that participants can't add to.
- **Dates:** `YYYY-MM` → the 1st of the month; `YYYY` → 1 January, flagged "year only" on the review page; `present` / `null` end → no end date. A missing start date is left blank, and the review page requires one before that experience can be saved.
- **Already there:** an experience with the same company and title as one of the participant's, and a start date within 31 days, is marked a likely duplicate and unticked. The same for education with the same school and degree. A bullet whose text matches an existing bullet on that experience (ignoring case and whitespace) is unticked.

### 3.5 Pages
- **Entry point:** an **Import from resume** button on `participant_experience_list.html`, next to Add Experience. It opens a small page, `ResumeImportStartView` (`/cold_apply/participants/<pk>/resume_import/`), with two choices: "Use the resume on file (uploaded <date>)" when `Profile.resume` is set, and a file field. If an import is already open, it links to it first.
- **Review:** `ResumeImportReviewView` (`.../resume_import/review/`). One card per experience and per education, in resume order:
  - an include checkbox;
  - company / school, title, concentration as text fields with an **existing** or **new** badge, and a "use existing" select (the same one the Experience form uses) to point at a different row;
  - start and end dates;
  - bullets as a list of text areas, each with its own checkbox;
  - warnings: "likely duplicate", "year only", "pick a degree".
- **Save:** POST validates every ticked card with the existing `ExperienceForm` / Education form rules, plus the bullet limit (§3.6). Errors re-render the page with the draft as typed. Success redirects to the experience list with "Added 4 experiences, 1 education and 23 bullets; created 2 companies and 1 title."
- **Discard** deletes the draft.
- **Access:** all three views use `ParticipantAccessMixin`, so staff reach any participant and a participant only themselves. The pages extend the same base as the experience list.

### 3.6 Saving (`resume_parser.apply(draft, cleaned, user)`)
In one `transaction.atomic()`:
1. For each ticked card, resolve company, title and concentration: the chosen pk, else `find_existing` again (another person may have added it since the parse), else create with `created_by=user`. Companies created from education get `org_type="Edu"`.
2. Create the `Experience` / `Education` rows, then the ticked bullets (`type="Work"`, `auto_generated=False`, since the text is the participant's own).
3. Refuse the whole save if the bullets would take the participant over `Bullet.MAX_PER_PARTICIPANT`, naming how many are left.
4. Delete the draft and return the counts for the message.

A unique-name race on create (two people adding "Acme" at once) is caught with `IntegrityError` and retried as a lookup.

### 3.7 Clean-up
Remove `ML_MODELS_PATH`, `ENTITIES_PATH` and `RESUME_OUT_PATH` from `hl_main/settings/base.py`.

## 4. Stages (one branch, `feature/idea-009-resume-parser`)
- **P1: Extraction and the task.** `extract_text`, the `resume_parse` key and seed, `parse_resume`, the normalising and matching in §3.4, and the settings clean-up. Tests with small PDF and DOCX fixtures, a scanned (no text) PDF, and `FakeProvider` replies, good and malformed.
- **P2: Draft and start page.** `ResumeImport` model and migration, the start view (profile resume or upload, size and type checks), the button, and the stale-draft command. Access tests: another participant gets 404, anonymous users go to login.
- **P3: Review and save.** The review page, `apply`, the success message. Tests for reuse vs create, the case-insensitive match, duplicates unticked, the bullet limit, the degree requirement, and rollback when one card is invalid.
- **P4: Check and merge.** Try it on real resumes on stage (§6), tune the instructions in `/agents/settings/`, then merge into develop.

Each stage ends with passing tests and can be merged into develop on its own.

## 5. Proposed decisions (to confirm)
1. **Text extraction in Python, not a file sent to Gemini.** It fits `complete()` as it is, works with any provider, and keeps the provider interface text-only. Revisit if real resumes come out jumbled (§7).
2. **Review before anything is saved, always.** Nothing goes into the participant's records straight from the LLM.
3. **A new upload isn't saved to the profile.** The file on the profile is the one from onboarding, and staff use it as the original. Replacing it is a separate choice the person can make from their profile.
4. **No locations for now.** `Experience` has no location field, and adding one changes the experience form, resume output and IDEA-003's merge list. If it's wanted, it's a small follow-up: a nullable `Experience.location` FK, then the parser fills it with the same matching.
5. **Participants can use it as well as staff**, through `ParticipantAccessMixin`, as they can already add experiences themselves. Their calls count toward the same daily cap. If IDEA-004 adds per-participant limits, this task goes under them.
6. **Synchronous, not a background task.** One call in about 10 to 20 s is fine with a spinner. If stage shows calls near the 45 s limit, move the parse to `background_tasks` and poll with the existing `task_status` view.

## 6. Verification
- `python manage.py test cold_apply hlagents` passes, including new `cold_apply/tests/test_resume_parser.py`.
- Locally with `load_dev_data` and a working Gemini provider: parse a two-page PDF and a DOCX. Every job and school appears, dates are right, and bullets match the resume text.
- Make a participant whose resume names "ACME" when "Acme" exists: the review shows "Acme" as existing, and saving creates no new company.
- Parse the same resume twice for one participant after saving once: every card is unticked as a likely duplicate.
- A scanned PDF and a `.txt` renamed to `.pdf` give the friendly error and no `TaskCall`.
- Turn the `resume_parse` task off in `/agents/settings/`: the page says it's unavailable, as resume generation does.
- As participant A, open participant B's import URLs: 404.
- On stage: parse 5 to 10 real resumes (with permission), note time per call and cost from `TaskCall`, and fix any instruction problems.

## 7. Open items
- **Can we use real resumes on stage for tuning?** They're participant data. If not, we need a handful of realistic test resumes, including military ones.
- **Text vs native PDF.** If two-column or heavily formatted resumes come out jumbled from `pypdf`, the fix is a `files` option on `ChatProvider.chat` so Gemini reads the PDF itself. That's a provider-interface change, worth doing only if P4 shows the need.
- **Locations (§5.4):** add `Experience.location` now, later, or never?
- **Should the summary, certifications and projects be parsed too?** `Overview` and `CertProjectActivity` exist. Leaving them out keeps the first version small.
- **Should onboarding offer it?** Right after the Upload Resume step, "We found 4 jobs, want to review them?" would save the most typing, but onboarding is a signup flow that shouldn't wait 20 s on an LLM. Suggest after P4, as its own change.
- Related: IDEA-003's duplicates page cleans up near-duplicates ("Google LLC") that exact matching here lets through.
