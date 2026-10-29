# Backlog

Design and development ideas that came up during other work and are **not bugs** (those go in `docs/bug-log.md`). This file is shared by all work sessions, including Claude Code sessions.

**How to use it**
- **Add:** append a new entry with the next ID. Never renumber entries.
- **Pick up:** set **Status** to `Planned` and link the design doc or branch. When it ships, set it to `Done` with the commit, and leave the entry in place.
- **Drop:** set **Status** to `Dropped` and give a one-line reason.
- **Status values:** `Idea` · `Planned` · `In progress` · `Done` · `Dropped`
- **Source:** where the idea came from (design doc section, conversation, bug).
- **Design docs** live in `docs/designs/planned/`, `in-progress/` or `completed/`, matching the item's Status. When the Status changes, `git mv` the doc to match and update links to it.
- Move completed items to the "Completed" section at the bottom while retaining numerical order.
    - Mark the completed items with the commit and release number

## Index

| ID | Status | Area | Summary |
|---|---|---|---|
| IDEA-001 | Planned | pipeline | Email assignees about new assignments and enrollments stuck in a step |
| IDEA-003 | Planned | cold_apply | Staff pages to list, merge and delete companies, titles and locations |
| IDEA-004 | Idea | cold_apply | Self-service participant portal with its own access level |
| IDEA-005 | In progress | accounts | Volunteer logins |
| IDEA-006 | Planned | pipeline | Define the Nurture flow (today it's a placeholder) |
| IDEA-008 | In progress | hlagents | Move agents to Google AI APIs where possible |
| IDEA-009 | Idea | cold_apply | Parse an uploaded resume into experience, education, companies, titles and locations |
| IDEA-010 | Planned | whole_site | Add dark-mode option |
---

## IDEA-001 — Assignee notifications
- **Status:** Planned · **Area:** pipeline · **Source:** `docs/designs/completed/cold-apply-staff-redesign.md` §5.5, left out of §8 (2026-10-19)
- **Plan:** `docs/designs/planned/assignee-notifications.md` (drafted 2026-10-29): stages N1 (assigned email), N2 (stuck digest and command), N3 (Cloud Run job and scheduler).
- **What:** email a staff member when an enrollment is assigned to them, and when one of their enrollments has sat in the same step longer than N days.
- **Notes:** could reuse the daily `send_signup_reminders` command / Cloud Run Job from the signup redesign. Activity rows already record assignments and step changes, so the data is there.

## IDEA-003 — Reference data management
- **Status:** Planned · **Area:** cold_apply · **Source:** `docs/designs/completed/cold-apply-staff-redesign.md` §4.2 item 9 and §5.6 (2026-10-19)
- **Plan:** `docs/designs/planned/reference-data.md` (drafted 2026-10-29, not agreed): stages R1 (merge service), R2 (merge pages), R3 (duplicates page and import fixes), R4 (staff layout and nav). List, edit and delete already shipped with BUG-030 (4f703c5).
- **What:** staff pages to list, search, merge duplicates of and delete Companies (`resume.Organization`), Titles (`resume.Position`) and Locations.
- **Notes:** job imports and manual entry create duplicates over time. Merging means re-pointing foreign keys (jobs, experiences, overviews) before deleting.

## IDEA-004 — Self-service participant portal
- **Status:** Idea · **Area:** cold_apply · **Source:** `docs/designs/completed/cold-apply-staff-redesign.md` §7, BUG-030 (2026-10-19)
- **What:** a portal where participants use some of the tools themselves (add experience, education and bullets, view jobs), with an access level separate from staff.
- **Notes:** the portal and access level don't exist yet. Participants can already create companies, titles, concentrations and locations from their forms, and edit or delete the ones they added while nobody else uses them (BUG-030, `cold_apply/reference.py`).

## IDEA-005 — Volunteer logins
- **Status:** In progress: V1 (invites, volunteer home, lead boards) merged into develop in 3f7c025 on 2026-10-22; V2 (Staff group, assigned-only people work) when needed. Doc `docs/designs/in-progress/volunteer-logins.md` §5 · **Area:** accounts · **Source:** signup/login redesign ("no volunteer login yet"); `docs/designs/completed/cold-apply-staff-redesign.md` §5.5 and §7 (2026-10-19)
- **What:** let volunteers log in with a limited role, so they can be assignees on enrollments and do selected staff work.
- **Notes:** Jeff expects volunteers, but not soon. Assignee choices are limited to `is_staff` users until then. A volunteer role will need its own permission set, with no DD214 access.
- **Commit** 3f7c025
- **Release** 3.4.0

## IDEA-006 — Define the Nurture flow
- **Status:** Planned · **Area:** pipeline · **Source:** `docs/designs/completed/cold-apply-staff-redesign.md` §7 (2026-10-19)
- **Plan:** `docs/designs/planned/nurture-flow.md` (drafted 2026-10-29, not agreed): stages NF1 (steps and due), NF2 (entering and leaving), NF3 (check-in emails), NF4 (re-permission pass), NF5 (outcomes, optional).
- **What:** decide what Nurture means for people who have finished or paused other flows (boot camp alumni, past job-search participants), and give it real steps.
- **Notes:** prod has 121 participants on Nurture → *Monthly Newsletter*, which is a placeholder; there is no newsletter. The staff redesign migrates them to a generic *Nurture* step in a Nurture flow until this is defined.

## IDEA-008 — All agents through GCP AI APIs
- **Status:** In progress: T, S and M built on `feature/idea-008-tools`, `-search` and `-move` (2026-10-28); next stage, then remove Tavily · **Area:** hlagents · **Source:** None
- **Plan:** `docs/designs/in-progress/gcp-agents.md` (agreed 2026-10-28, §7): effort T (Gemini tool calls), S (Google search grounding and direct page fetch in place of Tavily), M (compare, move the seeded agents, remove Tavily).
- **What:** run all agents (funding, outreach, and unbuilt, future agents) through GCP AI APIs instead of Tavily and Ollama
- **Notes:** needs hlagents H1. IDEA-007 added a text-only `GeminiProvider` (`hlagents/providers/gemini.py`, `docs/designs/completed/hlagents.md` §9). This idea would add tool calls to it (translating to and from the canonical message shape) and replace Tavily with Google search grounding.

## IDEA-009 — Resume parser
- **Status:** Idea · **Area:** cold_apply · **Source:** BUG-030 discussion (2026-10-23)
- **What:** a participant or staff member uploads a resume (PDF or DOCX), and an LLM extracts experiences, education, bullets, companies, titles and locations. The person reviews the extracted values before they're saved. Each value is matched case-insensitively to an existing row (the matching BUG-030 added), and only unmatched values create new rows. Less typing, fewer duplicates.
- **Notes:** an earlier parser lived in a separate `resume_parser` app. It isn't in this repo's history, but `ML_MODELS_PATH`, `ENTITIES_PATH` and `RESUME_OUT_PATH` in `hl_main/settings/base.py` still point at it. This would use Gemini on Vertex like `cold_apply/text_generation.py` (or hlagents, see IDEA-007). Related to IDEA-003 (merging duplicates).

## IDEA-010 — Dark mode
- **Status:** Planned · **Area:** whole_site · **Source:** Human brain
- **Plan:** `docs/designs/planned/dark-mode.md` (drafted 2026-10-29): stages D1 (tokens and switcher), D2 (staff), D3 (public, account, onboarding), D4 (legacy cold_apply and shared pieces), D5 (check and merge).
- **What:** users and site visitors can select dark or light mode, and the site defaults to the system setting.
- **Notes:** It's only white background now.

## Completed
| ID | Status | Area | Summary |
|---|---|---|---|
| IDEA-002 | Done | pipeline | Kanban view of a flow on the staff dashboard |
| IDEA-007 | Done | cold_apply | Resume generation and keyword extraction through the hlagents provider layer |

## IDEA-002 — Kanban view of a flow
- **Status:** Done (`feature/kanban-board`, B1–B4, merged into develop in 800e7cb on 2026-10-20) · **Area:** pipeline · **Source:** `docs/designs/completed/cold-apply-staff-redesign.md` §4.4 and §5.2 (2026-10-19)
- **Plan:** `docs/designs/completed/kanban-board.md` (agreed 2026-10-19; §7 records what was built); mockup https://claude.ai/artifact/XgapZE6b6efDJAAchPaAZ6.
- **What:** a second view of a flow tab on `/staff/`, with a column per phase or step and a card per enrollment. Moving a card calls the same `move_to_step` service as the table's dropdown.
- **Notes:** the table comes first because it handles filters and inline controls better. Worth adding if staff prefer to see the whole flow at a glance.

## IDEA-007 — Resume generation and keyword extraction through hlagents
- **Status:** Done (R merged into develop in c847d4c, K in 29cdaf2, on 2026-10-23) · **Area:** cold_apply · **Source:** `docs/designs/completed/hlagents.md` §7 on `feature/hlagents-01`, Jeff's answer to Q6 (2026-10-22)
- **Plan:** `docs/designs/completed/ai-tasks.md` (agreed 2026-10-23; §8 records what was built): effort R (resume generation, with a text-only Gemini provider) on `feature/idea-007-resume`, then effort K (keywords) on `feature/idea-007-keywords`.
- **What:** run resume generation (`cold_apply/text_generation.py`) and job keyword extraction (today an in-house algorithm) through the hlagents provider layer, so their model and provider can be switched in settings like the agents'.
- **Notes:** needs hlagents H1 (providers) merged first. Resume generation now calls Gemini on Vertex directly (`settings.GEMINI_MODEL`, BUG-038), so this is about switching provider in settings, not a fix. Do these as two separate efforts, not part of the hlagents build.
- **Commit** 29cdaf2
- **Release** not released yet
