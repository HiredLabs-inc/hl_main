# Kanban Board for Flows (IDEA-002)

Branch `feature/kanban-board` (from `develop`), worktree `.claude/worktrees/kanban-board`.

**Mockup:** https://claude.ai/artifact/XgapZE6b6efDJAAchPaAZ6 (private until shared). Four artboards: the interactive board for Resume & Job Search, card anatomy and states, a 121-person column (Nurture), and phone width.

> **Status:** design agreed with Jeff on 2026-10-19 (decisions in §6). Implementation starts after staff redesign Step 6 is merged.

## 1. Context
IDEA-002 in `docs/backlog.md`, from `docs/cold-apply-staff-redesign.md` §4.4 and §5.2: "a second view of a flow tab on `/staff/`, with a column per phase or step and a card per enrollment. Moving a card calls the same `move_to_step` service as the table's dropdown."

It builds on the staff redesign, which isn't finished:
- **Needs:** Step 2 (`pipeline` models and services, done), Step 5 (dashboard, filters, row partial) and Step 6 (inline step change view, quick-view side panel).
- **Doesn't need:** Steps 7–10. The board can ship any time after Step 6.

Volumes are small. Prod (2026-10-19) has 4 people in Resume & Job Search, 9 in Boot Camp and 121 in Nurture, almost all on one step. The board is for seeing a flow at a glance, not for handling scale.

## 2. Goals
- See where everyone in one flow is, and who is stuck, without scrolling a table.
- Move one person to another step by dragging, or with a **Move** menu that works with a keyboard or on a phone.
- No new rules. Every move goes through `pipeline.services.move_to_step`, so step permissions and the Activity timeline behave exactly as they do from the table.

**Not goals:** bulk moves, reordering cards within a step, changing assignee or status from the board (the card opens the side panel for that), editing flows.

## 3. Design

### 3.1 Where it lives
- A **Table | Board** switch on each flow tab of `/staff/` (Resume & Job Search, Boot Camp, Nurture, and future flows).
- **Not on Intake or My people.** Intake has two steps and its main action is the triage form, which a drag can't express. My people mixes flows, so there's no single set of columns.
- The view is a GET param, `?view=board`, kept with the other filters, so a board can be bookmarked. A new session opens on the table. After that, the last view used is remembered in the session, so staff who prefer the board land on it.

### 3.2 Columns
- **One column per step, grouped under a phase header.** `move_to_step` targets a step, so dropping on a phase column would need a second question ("which step?"). Step columns map one to one onto the service.
- The phase header shows the phase title and how many people are in it.
- **Empty steps collapse** to a 48px strip with the step title written vertically. A strip still accepts a drop and opens when a card lands on it. A "Collapse empty steps" checkbox (on by default) turns this off. Without it, Resume & Job Search would be 13 columns wide with 4 people in it.
- Steps owned by the participant (`Step.owner == "Participant"`, e.g. *Fill out intake form*) are labelled **Waiting on participant** under the column title.
- The board scrolls sideways inside its box; the page itself doesn't.

### 3.3 Cards
One card per **open** enrollment (ended ones are never shown). Each card shows (see the anatomy artboard):

1. **Name.** A button that opens the Step 6 quick-view side panel.
2. **Assignee** initials. A dashed "?" means unassigned.
3. **Days in step**, from `step_entered_at`. Amber past the "in step > N days" threshold the table uses. N is 14 to start with, set in one place so it can change later.
4. **Veteran badge**, the same three values as the table. No DD214 link, ever.
5. **Other open enrollments**, e.g. "Also in Boot Camp", so someone in two flows is visible from either board.
6. **Last activity** kind and age. For a soft rejection, this is the reason ("Unclear DD214").
7. **Move** button.

**Status:** paused, rejected and no-show cards stay in their step column, greyed, with the status shown first. They can be moved; moving doesn't change the status. DNC shows as a badge.

**Order:** oldest in step first. Cards can't be reordered by hand, because there's nothing to save the order to and it would mean nothing to other staff.

### 3.4 Moving a card
Two ways, both calling the same endpoint:
- **Drag** a card to another column (desktop). The column under the pointer gets a blue outline. On drop the card goes into the new column at once, faded, until the server answers.
- **Move** opens a menu of every step in the flow, grouped by phase, with the current one marked. This is the keyboard, screen reader and touch path, not a fallback.

**The request** is the Step 6 step-change POST that the table's dropdown uses, with two additions:
- `from_step`: the step the card was on when the board was drawn. If the enrollment is no longer on that step, the view refuses with **409** instead of moving it (someone else moved it in the meantime). The table gets this check too, for free.
- `render=card`: the view returns the card partial instead of the table row, plus out-of-band swaps for the two column counts and the phase counts.

**After a move:** the card gets a blue ring for a few seconds and a toast says "Moved Kim Nguyen to Analyze keywords in job posts. Undo". Undo is a second `move_to_step` back to the old step, so the timeline records both moves, which is accurate. `step_entered_at` resets on both moves, as it would from the table. The toast is an `aria-live` region.

### 3.5 When a move is refused
The card goes back to wherever the server says it is, with a red ring and the reason on the card:

| Response | Cause | Message |
|---|---|---|
| 409 | Someone else moved it since the board loaded | "Sam Taylor moved Kim to *Analyze keywords* a minute ago." (from the latest step-change Activity) |
| 403 | The step it's on has a `required_permission` the user lacks | "Only veteran reviewers can move people off *Verify Veteran Status*." |
| 400 | The enrollment ended (completed or withdrawn) | "This enrollment has ended." The card is removed. |

### 3.6 Permissions
- Staff only, like the rest of `/staff/`.
- For a card on a step with `required_permission` the user doesn't hold, the card isn't draggable and **Move** is disabled ("Reviewer only"). The server still checks (`can_leave_step`). Today only Intake has such a step, and Intake has no board, but flows are data, so the board handles it.

### 3.7 Filters
The board uses the table's filters unchanged: search, assignee (anyone / me / unassigned), status, "in step > N days", phase. The phase filter hides the other phase groups. The count strip at the top links to the same filters. Hidden cards don't change the columns, so the board's shape stays the same while filtering.

### 3.8 Big columns
Nurture has 121 people on one step.
- Each column renders the oldest 25 cards, then "Show 25 more" (an htmx GET that appends the next 25) and "Open all 121 in the table".
- Past 30 cards in a column, cards switch to one line (name and days). Hovering or focusing one shows the full card.

### 3.9 Phone width
Dragging across 13 columns on a phone doesn't work. At phone width the board shows one step at a time: a step picker ("Phase 2 · Create Initial Job List (2)") with previous and next buttons, then that step's cards at full width. **Move** opens a bottom sheet with the step list. No drag on touch.

## 4. Implementation

### 4.1 Drag and drop library
- **Chosen: SortableJS** (`sortablejs` on npm, MIT, about 45 KB minified). It handles mouse and touch, drop indicators and scrolling while dragging, and htmx's own docs use it for this. Configure it with `sort: false` (no reordering inside a column) and one shared `group` per board. Its `onAdd` sends the POST with `htmx.ajax`, then htmx swaps in the response.
- Not chosen: native HTML5 drag and drop with a small Alpine component. No new dependency, but no touch support and more edge cases to handle by hand.

The frontend already bundles htmx 1.9 and Alpine 3 through Vite (`frontend/src/main.js`); SortableJS is added there as an npm dependency.

### 4.2 Server side (all in `pipeline`)
- **Dashboard view:** the Step 5 view reads `view=board` and renders `pipeline/board.html` instead of the table. Both use the same filtered queryset builder, so filters behave identically.
- **Query:** the flow's open enrollments with `select_related("person__profile", "current_step__phase", "assignee")`, the last activity as a `Subquery` annotation, and the person's other open enrollments prefetched. Steps come from one query on the flow. Cards are grouped by step in Python, which is fine at these volumes. Target: a fixed number of queries whatever the board size.
- **Templates:** `pipeline/board.html`, `pipeline/partials/board_column.html`, `pipeline/partials/board_card.html`.
- **Endpoints:**
  - The Step 6 step-change view gains `from_step` (409 on mismatch) and `render=card`.
  - `GET /staff/flows/<slug>/board/steps/<step_pk>/?offset=25` returns the next cards for one column, with the current filters.
- **No model changes.** No migration.

### 4.3 Tests
- Staff-only access to the board and the column endpoint.
- The board shows open enrollments only, grouped by step, oldest first, with each filter.
- A move with `render=card` calls `move_to_step`, writes one step-change Activity and returns the card and both counts.
- 409 on a stale `from_step`, 403 on a gated step, 400 on an ended enrollment. None of them writes an Activity.
- Undo writes a second step-change Activity.
- The column endpoint pages correctly and keeps filters.
- A fixed query count with 50 enrollments across 10 steps.
- One Playwright test: drag a card to another column and check it saved; then use **Move** with the keyboard.

## 5. Plan
Each step ends with passing tests. Ask before each commit. Starts after staff redesign Step 6 is merged.

- **B1. Read-only board.** View switch, columns, collapsed empty steps, cards (including one-line cards past 30), filters, column cap with "Show more". Quick view opens from the name.
- **B2. Move menu.** `from_step` and `render=card` on the step-change view, the menu, the toast with Undo, and the refused states. This works without any drag code.
- **B3. Drag and drop.** SortableJS (§4.1) and the drag states.
- **B4. Phone layout.** One step at a time, step picker, bottom sheet.

B1 and B2 alone are usable, so B3 and B4 can wait if staff don't miss them.

## 6. Decisions
| Date | Decision | Why |
|---|---|---|
| 2026-10-19 | A new session opens on the table; the session then remembers the last view | Table first, as in the staff redesign |
| 2026-10-19 | Board on flow tabs only, not Intake or My people | Triage needs its form; My people mixes flows |
| 2026-10-19 | Days-in-step warning at 14 days | Good for a start; one setting, can change later |
| 2026-10-19 | SortableJS for drag and drop | Mouse and touch support |
| 2026-10-19 | One-line cards past 30 per column, from the start | Nurture has 121 on one step |
| 2026-10-19 | Card fields as in §3.3, nothing added | They show enough for now |

## 7. Status
- 2026-10-19: design and mockup drafted for review.
- 2026-10-19: Jeff answered the open questions (§6); design agreed.
