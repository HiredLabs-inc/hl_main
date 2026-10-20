# Backlog

Design and development ideas that came up during other work and are **not bugs** (those go in `docs/bug-log.md`). This file is shared by all work sessions, including Claude Code sessions.

**How to use it**
- **Add:** append a new entry with the next ID. Never renumber entries.
- **Pick up:** set **Status** to `Planned` and link the design doc or branch. When it ships, set it to `Done` with the commit, and leave the entry in place.
- **Drop:** set **Status** to `Dropped` and give a one-line reason.
- **Status values:** `Idea` · `Planned` · `In progress` · `Done` · `Dropped`
- **Source:** where the idea came from (design doc section, conversation, bug).

## Index

| ID | Status | Area | Summary |
|---|---|---|---|
| IDEA-001 | Idea | pipeline | Email assignees about new assignments and enrollments stuck in a step |
| IDEA-002 | Planned | pipeline | Kanban view of a flow on the staff dashboard |
| IDEA-003 | Idea | cold_apply | Staff pages to list, merge and delete companies, titles and locations |
| IDEA-004 | Idea | cold_apply | Self-service participant portal with its own access level |
| IDEA-005 | Idea | accounts | Volunteer logins |
| IDEA-006 | Idea | pipeline | Define the Nurture flow (today it's a placeholder) |

---

## IDEA-001 — Assignee notifications
- **Status:** Idea · **Area:** pipeline · **Source:** `docs/cold-apply-staff-redesign.md` §5.5, left out of §8 (2026-10-19)
- **What:** email a staff member when an enrollment is assigned to them, and when one of their enrollments has sat in the same step longer than N days.
- **Notes:** could reuse the daily `send_signup_reminders` command / Cloud Run Job from the signup redesign. Activity rows already record assignments and step changes, so the data is there.

## IDEA-002 — Kanban view of a flow
- **Status:** Planned · **Area:** pipeline · **Source:** `docs/cold-apply-staff-redesign.md` §4.4 and §5.2 (2026-10-19)
- **Plan:** `docs/kanban-board.md` on `feature/kanban-board` (agreed 2026-10-19); mockup https://claude.ai/artifact/XgapZE6b6efDJAAchPaAZ6. Starts after staff redesign Step 6.
- **What:** a second view of a flow tab on `/staff/`, with a column per phase or step and a card per enrollment. Moving a card calls the same `move_to_step` service as the table's dropdown.
- **Notes:** the table comes first because it handles filters and inline controls better. Worth adding if staff prefer to see the whole flow at a glance.

## IDEA-003 — Reference data management
- **Status:** Idea · **Area:** cold_apply · **Source:** `docs/cold-apply-staff-redesign.md` §4.2 item 9 and §5.6 (2026-10-19)
- **What:** staff pages to list, search, merge duplicates of and delete Companies (`resume.Organization`), Titles (`resume.Position`) and Locations.
- **Notes:** job imports and manual entry create duplicates over time. Merging means re-pointing foreign keys (jobs, experiences, overviews) before deleting.

## IDEA-004 — Self-service participant portal
- **Status:** Idea · **Area:** cold_apply · **Source:** `docs/cold-apply-staff-redesign.md` §7, BUG-030 (2026-10-19)
- **What:** a portal where participants use some of the tools themselves (add experience, education and bullets, view jobs), with an access level separate from staff.
- **Notes:** the portal and access level don't exist yet. Today only staff create companies, titles and locations, but any logged-in user technically can (BUG-030). Decide which reference data participants may create when this portal is designed.

## IDEA-005 — Volunteer logins
- **Status:** Idea · **Area:** accounts · **Source:** signup/login redesign ("no volunteer login yet"); `docs/cold-apply-staff-redesign.md` §5.5 and §7 (2026-10-19)
- **What:** let volunteers log in with a limited role, so they can be assignees on enrollments and do selected staff work.
- **Notes:** Jeff expects volunteers, but not soon. Assignee choices are limited to `is_staff` users until then. A volunteer role will need its own permission set, with no DD214 access.

## IDEA-006 — Define the Nurture flow
- **Status:** Idea · **Area:** pipeline · **Source:** `docs/cold-apply-staff-redesign.md` §7 (2026-10-19)
- **What:** decide what Nurture means for people who have finished or paused other flows (boot camp alumni, past job-search participants), and give it real steps.
- **Notes:** prod has 121 participants on Nurture → *Monthly Newsletter*, which is a placeholder; there is no newsletter. The staff redesign migrates them to a generic *Nurture* step in a Nurture flow until this is defined.
