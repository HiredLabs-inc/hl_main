# Reference Data Management (IDEA-003)

Branch `feature/idea-003-reference-data` (from `develop`), not started.

> **Status:** drafted 2026-10-29. Not agreed yet: the choices in §5 are proposals, and the open items in §7 need answers before R1.

## 1. Context
IDEA-003: "staff pages to list, search, merge duplicates of and delete Companies (`resume.Organization`), Titles (`resume.Position`) and Locations." It comes from `docs/designs/completed/cold-apply-staff-redesign.md` §4.2 item 9 and §5.6.

Some of this already exists. The BUG-030 fix (4f703c5) added:
- `cold_apply/reference.py`: a `Kind` for each of companies, titles, concentrations and locations; `find_existing` (matches the name in any case); `usage` (grouped counts over every foreign key that points at the model); and the `can_edit` / `can_delete` rules.
- `ReferenceListView`, `ReferenceUpdateView` and `ReferenceDeleteView` at `/cold_apply/reference/<kind>/`. Staff see every row, with a search box, a "Used by" count, Edit, and Delete for unused rows. Participants see only the rows they added.
- `ReuseExistingMixin` on the create views, so a name typed in a different case reuses the existing row.

**What's still missing:**
1. **Merge.** Renaming a row to a name that already exists is refused (`views.py` `ReferenceUpdateView.form_valid`, with the comment "Merging duplicates is IDEA-003"), and a row in use can't be deleted. So staff have no way to get rid of a duplicate that's in use.
2. **Finding duplicates.** The list is sorted by name, but "Google", "Google LLC" and "Google Inc." don't sit together in search results unless you search for "google", and nothing points them out.
3. **Imports keep making duplicates.** `cold_apply/jobs.py` `make_job_from_google` uses `get_or_create(name=...)`, which is case-sensitive and keeps surrounding whitespace. A job with no company or title creates a row with an empty name.
4. **Staff can't find it.** The pages extend `base_app.html` (the legacy layout). The only links to them are the "Manage" links on the Experience, Education and Job forms. The staff nav has no Reference data entry.

**Foreign keys a merge has to re-point** (all found by `reference._related`, so new ones get picked up automatically):

| Model | Pointed at by |
|---|---|
| `Organization` | `Job.company` (SET_NULL), `Experience.org`, `Education.org`, `CertProjectActivity.org` (PROTECT) |
| `Position` | `Job.title` (SET_NULL), `Overview.title`, `Experience.position`, `WeightedBullet.position` (PROTECT) |
| `Location` | `Job.location` (SET_NULL) |
| `Concentration` | `Education.concentration` (PROTECT) |

None of the models that point at these has a unique constraint that includes the foreign key, so re-pointing can't fail on uniqueness. The one place that could end up with duplicates is `WeightedBullet`: after merging two titles, a participant could have two weights for the same bullet and title (§3.1).

## 2. Goals
- Staff can merge two or more rows of one kind into one, from the list or from a duplicates page. Every record that used the merged rows then uses the kept row, and the merged rows are deleted, all in one transaction.
- Before confirming, staff see what will change: each row with its usage broken down by record type.
- A **Possible duplicates** page per kind groups rows whose names match once case, spacing, punctuation and company suffixes are ignored.
- Job imports stop creating case and whitespace duplicates and empty-name rows.
- Reference data has an entry in the staff nav, and staff see it in the staff layout.
- Concentrations get merge too, because `reference.py` already treats them the same way.

**Not goals:** participants merging anything (merge is staff-only). Fuzzy matching beyond the normalisation in §3.3, such as "IBM" vs "International Business Machines". Cleaning up `Job.company_detail` / `location_detail` strings. Degrees, States and Countries.

## 3. Design

### 3.1 Merge service
`reference.merge(keep, others, actor)` in `cold_apply/reference.py`:
- Checks that every row is the same model and that `keep` isn't in `others`. Raises `ValueError` otherwise.
- Runs inside `transaction.atomic()`, locking all the rows with `select_for_update()` first.
- For each `(model, field)` from `_related(type(keep))`: `model.objects.filter(**{f"{field}__in": others}).update(**{field: keep})`.
- **WeightedBullet:** after re-pointing titles, if a participant has more than one row for the same `(position, bullet)`, keep the one with the highest weight and delete the others.
- Deletes `others`. Because everything now points at `keep`, PROTECT can't block it. If something does (a new row added between the update and the delete), the transaction rolls back and the view reports it.
- Returns `{model verbose name: count re-pointed}` for the success message, and logs one `logger.info` line with the actor, the kept pk, the merged pks and the counts. There's no audit model: `pipeline.Activity` is per person, so it doesn't fit.
- The kept row keeps its own field values. If a merged company had a website and the kept one didn't, the website is copied over. No other field is copied: the other kinds have only their name fields, and `org_type` stays as the kept row has it.

`queryset.update()` skips `save()` and signals. None of the pointing models has save logic or signals that depend on these fields today. R1 checks this again.

### 3.2 Merge pages (staff only)
- **List page:** for staff, each row gets a checkbox and the page gets a **Merge selected** button (enabled when two or more rows are checked). It submits a GET to the confirm page with `?ids=1,2,3`.
- **Confirm page** `reference/<kind>/merge/` (`ReferenceMergeView`, `UserPassesTestMixin` for `is_staff`): a table of the chosen rows with a radio button for **Keep**, the name, and the usage by record type ("3 jobs, 2 experiences"). The row with the most uses is selected by default. The **Merge** button POSTs `keep` and `ids`. On success, it redirects to the list with a message like "Merged 2 companies into Google: 5 jobs, 3 experiences moved".
- Rows that no longer exist when the form is posted are skipped. If fewer than two are left, the page goes back to the list with an error.
- **Rename into a duplicate:** where `ReferenceUpdateView` refuses a name that already exists, staff get a **Merge into "…"** link to the confirm page with both rows. Participants still get today's message.

### 3.3 Possible duplicates page
`reference/<kind>/duplicates/` (staff only), linked from the list page.
- `reference.duplicate_groups(kind)` loads `pk` plus the text field for every row and groups them by a normalised key:
  - lower case, accents removed (`unicodedata` NFKD), punctuation turned into spaces, whitespace collapsed;
  - companies only: trailing suffixes removed (`inc`, `llc`, `ltd`, `corp`, `corporation`, `co`, `company`, `plc`, `gmbh`);
  - locations: the key is the normalised city plus `state_id` plus `country_id`, so "Austin, TX" and "austin , TX" group but Austin TX and Austin MN don't.
- Only groups with two or more rows are shown, biggest first, each with its usage counts and a **Merge…** button for that group.
- This runs in Python over the whole table. It's fine for tens of thousands of rows. If the tables get much bigger, the key can move into a stored column.
- Empty-name rows are shown as one group at the top.

### 3.4 Imports
- `make_job_from_google` strips the title and company and looks them up with `reference.find_existing` before creating a row. New rows get `created_by=None`, as now.
- An empty title or company leaves `Job.title` / `Job.company` as `None` instead of creating an empty-name row. Both fields are already nullable.
- Merging the empty-name rows that exist today into something real doesn't make sense. The duplicates page lets staff see them, and R3 includes a data migration that sets `Job.title` / `Job.company` to `None` where they point at an empty-name row and deletes those rows if nothing else uses them. Run it on stage first.

### 3.5 Staff navigation and layout
- Add **Reference data** to the staff nav in `templates/staff_base.html`, after Volunteers, linking to `reference_list companies`.
- `reference_list.html`, `reference_form.html` and the new templates pick their base from the user: `{% extends request.user.is_staff|yesno:"staff_base.html,base_app.html" %}`. Participants keep today's layout. Staff get the staff nav and Tailwind styles, using the existing staff classes (`staff-field`, `staff-badge-*`) and the table styles from the staff people page.
- Search on the Locations list also matches the state and country names, not only the city.

## 4. Stages (one branch, `feature/idea-003-reference-data`)
- **R1: Merge service.** `reference.merge` with WeightedBullet clean-up, website copy and logging. Tests for every kind, for each pointing model, for rollback, and for the empty-name rows.
- **R2: Merge pages.** Checkboxes and button on the list, `ReferenceMergeView`, the confirm template, and the link from a refused rename. Access tests: participants and anonymous users get 403 or a redirect to login.
- **R3: Duplicates and imports.** `duplicate_groups`, the duplicates page, the `make_job_from_google` change, and the empty-name data migration.
- **R4: Staff layout and nav.** Base switch, staff nav entry, Locations search, then check every page and merge into develop.

Each stage ends with passing tests and can be merged into develop on its own.

## 5. Proposed decisions (to confirm)
1. Merge is staff-only. Participants keep edit and delete for their own unused rows, as BUG-030 set up.
2. The kept row's values win, except that a missing website is filled in from a merged company. Staff can rename the kept row after merging.
3. No undo and no audit table: the confirm page shows exactly what will change, and a log line is written. Admin backups are the fallback.
4. Concentrations get merge as well, at no extra cost.
5. Duplicate detection is the normalisation in §3.3 only, with no fuzzy or AI matching.

## 6. Verification
- `python manage.py test cold_apply` passes, including new tests in `cold_apply/tests/test_reference_data.py` (or a new `test_reference_merge.py`).
- Locally with `load_dev_data`: make "Acme", "ACME Inc." and "acme" companies, used by jobs, experiences and an education. Check that they show as one group on the duplicates page, then merge them. Every record now shows "Acme", the other two rows are gone, and the message counts match.
- Merge two titles where one participant has weighted bullets on both. That participant ends up with one weight per bullet.
- Import jobs with a mixed-case company name that already exists, and one with no company. No new duplicate or empty-name row is created.
- As a participant: no checkboxes, merge URLs return 403, and the list still looks like today.
- On stage: run the data migration, then open the duplicates page for each kind to see how much clean-up there is.

## 7. Open items
- Is merge staff-only (§5.1), or should volunteers with staff-dashboard access get it too? This depends on IDEA-005 (volunteer logins, in progress).
- How many rows and duplicates are there in prod today? A count from prod would show whether the Python grouping in §3.3 is enough.
- Should the kept row be the most used one by default (as proposed) or the oldest?
- Found while drafting, not part of this idea: `Location.__str__` raises if `country` or `state` is `None` (both are SET_NULL). This should go in `docs/bug-log.md` as a separate bug.
