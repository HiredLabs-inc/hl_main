# HL Agents: a staff UI for AI search agents

Branch `feature/hlagents-01` (develop merged in 2026-10-21), worktree `.claude/worktrees/hlagents-01`.

> **Status:** agreed 2026-10-22 (§6). Jeff answered the open questions in §7. H1–H4 are done (§8). H5 (stage) is a checklist for Jeff (§8). H6 (stages in `/agents/`) is on `feature/hlagents-02`. H7 (lead quality) is on `feature/hlagents-03`.

## 1. Context
We have two working prototype agents in `examples/utils/` that run outside the app:

- **Funding agent:** finds grants and corporate giving programs worth $25k–$100k that fund veteran services, workforce or tech training, or formerly incarcerated people.
- **Outreach agent:** finds individual people at veteran-serving organizations who could help spread the word about the boot camps and increase enrollment.

How the prototype works:
- `agent_loop.py` calls `provider.chat(model, messages, tools)`. The provider uses the Ollama client's message shape. When the model returns `tool_calls`, the loop runs them from a registry and appends `role: "tool"` replies. It stops when a reply has no tool calls.
- The only tool is `web_search` (Tavily, `tools/tool_definitions.py`).
- The system prompts (`system_prompts/*.py`) ask the model to return JSON only. `response_parser.web_search_parser` strips any code fences and runs `json.loads`.
- `db_interactions.py` writes results to local SQLite files. Funding results are deduped on org name. Outreach results are deduped on email, including against an existing contacts CSV.
- `agent_classes/agents.py` (`SearchAgent`) wires those pieces together and switches on `purpose`.

The prototype has no UI, is run by hand, and keeps its results on one machine. Run history, prompts and model choice all live in code.

## 2. Goals
1. Staff, and volunteers later, run agents from a web page, review what the agents find, and keep the good results.
2. Talking to an agent is part of the workflow. A run is a conversation, so you can follow up with something like "find 5 more in Texas" or "only foundations".
3. **Provider-agnostic.** Each agent has its own provider and model. Switching either is a settings change in the UI, not a deploy. The first provider is Ollama Cloud.
4. Results are Django models, deduped across runs.
5. Approved results enter **pipeline flows** (Funding, Outreach) and get the same board, assignment and activity log that participants have.
6. Adding a new agent type is mostly a prompt, a parser and a result mapping.

**Not in v1:** freeform chat that isn't tied to producing candidates; participant-facing agents; sending outreach email from the app.

## 3. Design

### 3.1 Layers
```
UI (templates + htmx)  ──►  AgentRun  ──►  background_tasks (Cloud Tasks)
                                              │
                                              ▼
                         loop.run(run) ──► ChatProvider (Ollama, …)
                              │       └──► Tools (web_search, …)
                              ▼
                     AgentType.parse() ──► Lead (dedupe) ──► pipeline.enroll()
```

1. **Providers** (`hlagents/providers/`). `ChatProvider.chat(model, messages, tools) -> ChatResult`. The canonical message format is the one the prototype already uses, which is the Ollama/OpenAI shape: `role`, `content`, `tool_calls[{function: {name, arguments}}]`, and `role: "tool"` replies. `OllamaProvider` uses the `ollama` client with host `https://ollama.com` and a bearer key. A registry maps `kind` to its class. Later adapters (Anthropic, Vertex/Gemini, OpenAI) translate to and from the canonical shape, so the loop and the stored conversations never change.
2. **Tools** (`hlagents/tools/`). Each tool is a function plus a JSON schema and a default description. An agent can override the description, which is the only difference between the two prototype schemas. Tools read their own secrets from settings, rather than the loop passing `api_key` as it does today. First tool: `web_search` (Tavily).
3. **Agent types** (`hlagents/agents/`). Agent types are code, because each one needs its own parser and result mapping. An `AgentType` has:
   - `key` and `label`
   - `allowed_tools`
   - `parse(final_text) -> list[dict]`
   - `dedupe_key(candidate)`
   - `to_lead(candidate)`

   `FundingAgent` and `OutreachAgent` replace `SearchAgent` and `db_interactions.py`.
4. **Loop** (`hlagents/loop.py`). A port of `agent_loop` that adds:
   - a cap on iterations
   - a **cost cap** (§3.8): the loop stops before a provider call when the run or today's total is at its cap
   - unknown tools and tool exceptions returned to the model as tool messages instead of crashing
   - `AgentRun.messages` saved after every turn, so the run page shows progress and a crash keeps the history

### 3.2 Models (`hlagents/models.py`)
| Model | Fields | Notes |
|---|---|---|
| `ProviderConfig` | name, kind, base_url, secret_env, input_cost_per_mtok, output_cost_per_mtok, active | `secret_env` names the env var or secret that holds the key. **Keys are never stored in the DB.** Costs are admin-entered estimates in $ per million tokens. They're 0 for Ollama Cloud, which is a subscription. |
| `AgentConfig` | name, agent_type, provider FK, model, system_prompt, default_request, tools (JSON), tool_descriptions (JSON), max_iterations, active | `agent_type` is a choice from the code registry. Seeded from the prototype prompts by a data migration. You can have several configs per type, for example to compare two models. |
| `AgentRun` | config FK, snapshot (provider, model, prompt), started_by, status, messages (JSON), error, iterations, input_tokens, output_tokens, tool_calls, cost, task FK, created/updated | The snapshot records what was actually used, even if the config changes later. Status: queued / running / done / failed / capped. |
| `Lead` | kind, source, org_name, first_name, last_name, contact_email, funding_amount, application_deadline, url, justification, review_status, opted_out_at, source_run FK, dedupe_key | Unique on (kind, dedupe_key). The key is the normalized org name for funding and the normalized email for outreach, as in the prototype. Source: agent / import (community partners CSV, §3.9). Review status: new / approved / rejected. Rejected leads are kept until someone deletes them, which also keeps agents from finding them again. `opted_out_at` only marks the record; the opt-out itself is handled in the email. `funding_amount` and `application_deadline` are text, because models return ranges and phrases like "rolling". |
| `AgentLimits` | run_cost_cap, daily_cost_cap, tool_costs (JSON, $ per call) | A single row, edited by admins in the settings page (§3.8). |

### 3.3 Running an agent
1. **Run** creates an `AgentRun` with the system prompt and `default_request` (editable before you start). It then calls `background_tasks.queue.queue_task("/agents/tasks/run/<id>/", …)`.
2. The worker view (`work_task` + `is_authorized_task_request`) runs the loop, parses the final reply, and upserts Leads. Duplicates are skipped, and the run records counts like "Inserted 7, skipped 3 duplicates."
3. The run page polls the run's status with htmx while it is queued or running.
4. **Follow-up:** typing a message appends it to `messages` and queues the run again. Any new candidates are added to the same run.
5. A parse failure marks the run failed, shows the raw reply, and still allows a follow-up such as "Return only the JSON."

### 3.4 UI
Built with Django templates, htmx, Alpine, Tailwind and Preline, in the same style as `/staff/`.
- **`/agents/`**: a card per active `AgentConfig` (type, provider and model, last run) with a Run button, and recent runs below. Anyone who can run agents can pick a model for one run. The choices are the agent's own model plus the models staff list on each usable provider (`ProviderConfig.models`). The agent's model stays the default, and the run records what it used.
- **`/agents/runs/<id>/`**: on the left, the conversation (user messages, tool calls collapsed as "searched: …", agent replies) and a follow-up box. On the right, this run's candidates, each with Approve, Reject and inline edit.
- **`/agents/leads/`**: all leads, filtered by kind and review status.
- **`/agents/settings/`**: edit agents (provider, model, prompt, tools, default request) and providers, including each provider's list of models that people can pick per run.

### 3.5 Permissions
- Every page uses `app_permission_required("hlagents")` from `userprofile/guards.py`. Staff are granted the permission now. Volunteers get it when IDEA-005 (volunteer logins) lands, with no code change.
- The settings pages also require `hlagents.change_agentconfig`. Providers also need `change_providerconfig`, and the cost caps need `change_agentlimits`. The **Agent admins** group has all three. It starts empty: superusers already have every permission, and others are added by hand.
- A provider's API key can only come from an env var listed in `HLAGENTS_PROVIDER_SECRETS` (in settings, so changing it takes a deploy). The key is sent to the provider's base URL, so otherwise anyone who can edit providers could send any secret in the environment to a server of their choosing.

### 3.6 Pipeline integration
`pipeline.Enrollment.person` is a required FK to `User`, and funders and contacts aren't users. Decision: **generalize Enrollment.**
- `Enrollment.person` becomes nullable. A nullable `lead` FK to `hlagents.Lead` is added, with a `CheckConstraint` that exactly one of the two is set. `Activity` gets the same change.
- An `Enrollment.subject` property and a label helper replace direct `.person` access in `pipeline/services.py`, `actions.py`, `dashboard.py`, `admin.py` and the partials (`enrollment_row.html`, `board_card_body.html`, `person_panel.html`). That's about 100 references, mostly in tests.
- `enroll()` accepts `lead=` as well as `person`. The person-only parts of the dashboard, such as the people panel and triage, stay person-only.
- A data migration seeds the **Funding** and **Outreach** flows (steps are an open question, §7). Approving a lead enrolls it in the flow for its kind.

### 3.7 Secrets and dependencies
- `OLLAMA_API_KEY` and `TAVILY_API_KEY` come from env and Secret Manager, the same way other credentials do. Stage and prod need both.
- Add `ollama` and `tavily-python` to `requirements.txt`.
- Delete `examples/` once everything in it is ported.

### 3.8 Cost cap
- Every provider reply reports its token counts (Ollama: `prompt_eval_count` and `eval_count`). The loop adds them to the run, along with each tool call. The run's `cost` is tokens × the provider's rates, plus tool calls × `AgentLimits.tool_costs` (Tavily is about $0.008 per basic search).
- Before each provider call, the loop stops the run with status **capped** if the run's cost is at `run_cost_cap`, or if today's total across all runs is at `daily_cost_cap`. A capped run keeps its messages. A follow-up continues it only if there's room under the caps.
- Admins change the caps and rates in `/agents/settings/` without a deploy. The defaults are $1 per run and $10 per day.

### 3.9 Community partners CSV
The outreach prototype dedupes against an uploaded CSV of current **community partners**: organizations we already have a relationship with (we send them boot camp announcements, and they send us events). They aren't funders.
- `/agents/leads/import/` uploads that CSV. Each row becomes an Outreach lead with source **import** and review status approved. Once H4 lands, it is enrolled at the Outreach flow's **Partner** step. Rows already present (same email) are updated, not duplicated, so the import can be run again whenever the list changes.
- Agents dedupe against these leads like any other, so they never re-find a current partner.
- The file's columns are `EMAIL` and `Status`. `Status` is mostly blank. Otherwise it's `Bounced`, sometimes with a count, such as `Bounced #3`.
- `Lead` gets a `bounces` count. Blank is 0, `Bounced` is 1, and `Bounced #N` is N. Bounced partners are still imported, so agents don't re-find them, and the leads list shows the bounce count. Unknown `Status` values stop the import and list the rows, rather than guessing.
- The CSV has no names or orgs, so imported leads have only an email until someone edits them.

### 3.10 Activity log
Everything is logged in the pipeline activity log from the start: a lead being found by a run, imported, edited, approved, rejected, or opted out. That requires `Activity.lead` (§3.6). The Activity half of the pipeline change moves into H2, so logging starts with the review UI. H4 does the Enrollment half.

## 4. Implementation
### 4.1 Tests
- A `FakeProvider` that returns scripted replies (a tool call, then final JSON) tests the loop, the parsing, lead dedupe and follow-ups without network access. Tavily is stubbed.
- View tests cover the permission gate, run, follow-up, approve and settings.
- The pipeline suite (including `test_board` and `test_browser`) must stay green after the Enrollment change. New tests cover lead enrollments.
- Tests run in docker compose: `docker compose -p hl-agents run --rm django python manage.py test hlagents pipeline`.

## 5. Plan
| Step | What | Done when |
|---|---|---|
| H0 | Merge develop, write this doc, agree on it | §7 answered |
| H1 | Core: providers, tools, agent types, loop, models, migrations, seed configs; wire `hlagents.urls` | Unit tests pass with `FakeProvider` |
| H2 | Runs and review UI: `Activity.lead` and logging (§3.10), worker task, `/agents/`, run page, leads list with opt-out, partners CSV import, permission gate | Both agents run locally against Ollama Cloud, and their leads can be reviewed and show up in the log |
| H3 | Chat follow-ups and settings UI, including cost caps and rates | Switching an agent's model in the UI changes the next run, and lowering the cap stops a run |
| H4 | Pipeline: generalize Enrollment, seed the Funding and Outreach flows, approve → enroll | An approved lead appears on the Funding board, and imported partners appear at Partner |
| H5 | Secrets on stage, deploy to stage, prod checklist | Works on stage |

## 6. Decisions (2026-10-21)
1. The main deliverable is a **web UI**. The code layer exists to serve it.
2. The first agents are the two prototypes: **funding** and **outreach**.
3. **Users:** staff now and volunteers later, controlled by a permission rather than `is_staff`.
4. **Provider-agnostic**, per agent, switchable without a deploy. The first provider is **Ollama Cloud** with an API key.
5. **Interaction:** run and review, plus chat on a run. No freeform chat in v1.
6. **Results:** Django models, fed into pipeline flows by **generalizing Enrollment**.
7. **Configuration** (provider, model, prompt, tools) is edited in the **agents UI**.

Added 2026-10-22, from Jeff's answers in §7:

8. **Cost cap** to start, adjustable by admins without a deploy. The unit is estimated dollars, per run and per day (§3.8).
9. **Opt-out:** a mark on the lead (`opted_out_at`) only. The opt-out itself happens in the email.
10. **Rejected leads** are kept until someone deletes them.
11. The **community partners CSV** is imported as Outreach leads, and the import can be repeated (§3.9).
12. **Flow steps** to start with. Funding: Found → Researching → Applying → Submitted → Awarded / Declined. Outreach: Found → Contacted → Replied → Partner. We'll revise them after people have used them.
13. **Everything goes in the activity log** from the start (§3.10).
14. **Resume generation** (BUG-038) and **keyword extraction** will move onto this provider layer later, as separate efforts (IDEA-007).
15. The **default model** for the seeded agents is `gemma4:31b`, the model the prototype used (2026-10-22). The prototype ran it as `gemma4:31b-cloud` through a local Ollama. The `-cloud` suffix is only for local Ollama; calling `https://ollama.com` directly takes the plain name. This gets confirmed on the first real run in H2.

Added 2026-10-29:

16. **Model per run:** anyone with `add_agentrun` picks a provider and model for each run on `/agents/`, from the models staff list on each provider. It doesn't change the agent's saved default. Cost rates are still per provider, so a model is costed at its provider's rate.

## 7. Open questions
Answered 2026-10-22, and folded into §6 and §3, including the partners CSV columns and the prototype model. Nothing is open.

Original questions and answers:

1. Which Ollama Cloud model(s) should be the defaults? Do we want a cost or iteration cap per run, or a daily cap?
- cost cap to start, but this needs to an adjustable setting that can be changed by by admins
2. The outreach agent collects individuals' emails from the web. What do the privacy policy and CAN-SPAM require of us? How long do we keep rejected leads?
- There needs to be a way to mark leads as opted out. We'll deal with the opt out in the email, though, so nothing other than a mark on the record for now. Keep rejected leads until deleted. 
3. What is the contacts CSV the outreach prototype dedupes against (`input_file_path`)? Should it be imported as existing leads, and should it be importable again later?
- it is an uploaded csv file with current "community partners" - those organizations, with which we have a relatonship. We send them announcements of upcoming boot camps, they send us event stuff, or whatever else they do. It's not funders, but communit partners
4. What are the steps for the Funding flow (for example Found → Researching → Applying → Submitted → Awarded/Declined) and the Outreach flow (for example Found → Contacted → Replied → Partner)?
- Those are good to start. We can change them later once we have people use it for a bit and get some feedback.
5. Should lead edits and review decisions go in the pipeline activity log from the start, or only once a lead is enrolled?
- All of it should hit the log for now
6. Should resume generation (`cold_apply/text_generation.py`, which uses the retired `text-bison@001`, BUG-038) move onto this provider layer later?
- yes. Also the keyword extraction, which now uses an in-house algorithm. That too will run through this layer eventually, but those are separate efforts.

## 8. Status
### H1 — Core (done 2026-10-22)
- **Agent types:** `hlagents/agents/`. `AgentType.parse` accepts plain JSON, a code fence, or a list wrapped in a one-key object. Funding leads are deduped on the normalized org name. Outreach leads are deduped on the normalized email, and a missing or invalid email skips the candidate.
- **Providers:** `hlagents/providers/` (`ChatProvider`, `ChatResult`, `OllamaProvider`, `get_provider`). The key is read from the env var named by `ProviderConfig.secret_env`, and a missing key fails the run with a clear error.
- **Tools:** `hlagents/tools/` (`web_search` via Tavily, `TAVILY_API_KEY` in `base.py` and `cloud.py`, default empty).
- **Loop:** `hlagents/loop.py` `run_agent(run, provider=None)`. Unknown tools, disabled tools, tool exceptions and bad arguments go back to the model as `{"error": …}`. The run and daily caps are checked before each provider call. The step limit comes from `AgentConfig.max_iterations`.
- **Services and models:** `hlagents/services.py` (`create_run`, `save_leads`) and `hlagents/models.py`. Migration `0002_seed_agents` seeds the Ollama Cloud provider (`OLLAMA_API_KEY`), the two agents with the prototype prompts and `gemma4:31b`, and `AgentLimits` ($1 per run, $10 per day, $0.008 per search).
- **Wiring:** the app is in `INSTALLED_APPS`, and `/agents/` is included with no pages yet. Admin is registered for all models.
- **Dependencies:** `ollama==0.6.3`, `tavily-python==0.8.5`.
- **Dev keys:** `OLLAMA_API_KEY` and `TAVILY_API_KEY` go in `.env.local` in the repo root. It's gitignored, and compose loads it into `django` and `django-tasks` if it exists. `.env.dev` isn't loaded, because its `GOOGLE_APPLICATION_CREDENTIALS` would override the mounted gcloud credentials.
- **Tests:** `hlagents/tests/` has 39 tests using `FakeProvider` and a mocked `TavilyClient`. The full suite (336 tests) passes.
- `examples/` stayed until H2 had run both agents for real. It was deleted in H2.

### H2 — Runs and review UI (done 2026-10-22)
- **Activity log:** `pipeline.Activity` now belongs to a person *or* a lead (nullable `person`, new `lead` FK, check constraint `activity_person_or_lead`), with new kinds: found by agent, imported, edited, review, opt-out. `hlagents/services.py` logs every lead change.
- **Worker:** `services.start_run` queues `hlagents:task_run_agent`, and `hlagents/tasks.py` `run_agent_task` only starts runs that are still **queued**, so a Cloud Tasks retry can't run one twice. Runs stop after `HLAGENTS_RUN_TIME_LIMIT` (480 s), which is under the 10-minute Cloud Tasks deadline. Each Ollama call times out after 180 s.
- **`background_tasks.queue.work_task`** no longer wraps the whole task in one transaction. That transaction hid a run's progress, and the cold_apply job search's "running" status, until the task finished. It also broke `task.fail()` after a database error. The row lock that marks a task as started is unchanged.
- **Pages:**
  - `/agents/`: an agent card with an editable request and a Run button, plus recent runs
  - `/agents/runs/<id>/`: the conversation (searches, collapsed results, the answer) and the run's leads with Approve and Reject. It polls every 3 s while the run is queued or running.
  - `/agents/leads/`: filters by kind, review status and source, plus search
  - `/agents/leads/<id>/`: edit form, opt-out toggle and activity timeline
  - `/agents/leads/import/`: partners CSV import
  - An Agents link in the staff nav for anyone with hlagents permissions
- **Permissions:** migration `0004_agents_group` creates the **Agents** group (view agents, runs and leads; start runs; change and add leads) and adds all active staff to it. Volunteers get access by joining the group. Settings permissions are left for H3.
- **Partners import:** `Lead.bounces` is new. `read_partners_csv` rejects the whole file if any row is bad, and lists every bad row.
- **Tailwind:** `frontend/tailwind.config.js` now scans `hlagents/templates` and `hlagents/*.py`.
- **Real runs (2026-10-22, `gemma4:31b`):**
  - Funding: 3 searches and 5 leads in about 10 s, at an estimated $0.02.
  - Outreach: 3 searches and 10 leads.

  Both `gemma4:31b` and `gemma4:31b-cloud` work against `https://ollama.com`.
- **Lead quality is for H3** (prompt editing):
  - The funding agent copies the "$25k–$100k" criteria in as every lead's amount.
  - It returns agency homepages rather than specific opportunities.
  - The outreach prompt says "exactly 10", which overrides a request for 5. It returned VA researchers, who may not be the outreach targets we want.
- **Tests:** 79 in `hlagents`, and the full suite (376) passes.

### H3 — Follow-ups and settings (done 2026-10-22)
- **Follow-ups:** a finished, failed or capped run has a follow-up box under its conversation. `services.follow_up` adds the message and queues the run again. The agent sees the whole conversation, any new candidates are added to the same run, and `result` describes the latest turn. A follow-up is refused, with the reason shown in place of the box, while the run is in progress, at the run or daily cap, or when the provider is off or has no key. The step limit applies to each turn. The cost cap applies to the run and all its follow-ups.
- **Starting runs** checks the same things. An agent card shows the reason instead of the Run button.
- **Settings pages:**
  - `/agents/settings/`: lists agents and providers, shows whether each provider's key is set (the name only, never the value) and today's spend, and has the caps and tool rates form.
  - `/agents/settings/agents/<id>/`: edit provider, model, default request, system prompt, tools, tool descriptions, step limit and active. An agent's type is fixed once it exists.
  - `/agents/settings/agents/new/` (`?copy=<id>` starts from a copy of another agent, for example to compare two models).
  - `/agents/settings/providers/<id>/` and `/new/`.
- **Permissions:** migration `0005` adds the **Agent admins** group, and `HLAGENTS_PROVIDER_SECRETS` limits which env vars a provider can use as its key (§3.5).
- **Prompts:** migration `0005` replaces the seeded prompts and default requests, but only where they are still the seeded text. The changes:
  - Funding: the amount and deadline come from the funder's page, or are left blank. The criteria range is never used. The URL must be the specific program's page.
  - Outreach: the count comes from the request (10 if it doesn't give one). The prompt lists the roles that fit and those that don't (researchers, clinicians and so on). Emails must appear in a search result and are never guessed.
  - Both: follow-ups return only new candidates, and an empty result is `[]`.
- **Real runs (2026-10-22, `gemma4:31b`):**
  - Outreach in Ohio: asked for 5 and got 5. They were county veteran service officers and outreach staff with published county addresses. One was a shared `veterans@` mailbox.
  - Funding: no amounts are copied from the criteria any more; they're blank instead. A follow-up asking for 3 more, only foundations and corporate programs, added 3 leads to the same run. Over two turns: 8 searches, about $0.06.
- **Still weak, next steps for lead quality:**
  - Funding URLs are often home pages (grants.gov, legalzoom.com), and amounts are blank. The model only sees search snippets and can't open a funder's page to check it. Adding a page-reading tool (Tavily extract) would let it verify.
  - The outreach agent could drop shared mailboxes in code, not only by prompt.
- **Tests:** 109 in `hlagents`, and the full suite (406) passes.

### H4 — Pipeline (done 2026-10-22)
- **Lead flows:** `Flow.subject` is person or lead. `Enrollment.person` is nullable, and there's a new `Enrollment.lead`. A check constraint (`enrollment_person_or_lead`) requires exactly one of the two, and a lead has one open enrollment per flow. `pipeline.services.enroll(None, flow, actor, lead=lead)` enrolls a lead, and refuses a lead in a people flow or a person in a lead flow. Moves, status changes and notes on a lead's enrollment go on the lead's timeline.
- **Flows:** migration `hlagents/0006` seeds them and enrolls leads that were already approved.
  - **Funding:** Prospect (Found, Researching) → Application (Applying, Submitted) → Decision (Awarded, Declined)
  - **Outreach:** Prospect (Found) → Outreach (Contacted, Replied) → Partner (Partner)
  - Awarded, Declined and Partner are final steps (`completes_flow`, BUG-037), so a lead enrollment can be completed from them. Withdrawn is always allowed; Dropped isn't (it's Boot Camp only).
- **Review:**
  - Approving a lead enrolls it at Found. Imported partners go to Partner.
  - Rejecting it withdraws its open enrollment (reason "Lead rejected"). Approving it again starts a new enrollment.
  - Setting it back to New leaves the enrollment alone.
  - A missing or inactive flow means no enrollment.
- **Partners import:** puts every partner on Partner, including an agent lead already enrolled at an earlier step.
- **Staff dashboard (`/staff/`):**
  - Funding and Outreach get tabs, with the table and board, after My people and Everyone.
  - Cards and rows link to the lead's page, and show Opted out and bounce badges. Search covers org, name and email.
  - **People only:** My people, Everyone, the Unassigned and stale counts, "Enroll in" choices, triage and the person panel. A lead can't be enrolled in other flows by hand.
- **Lead page:** shows the lead's flow and step. For staff, the flow name links to its tab.
- **Migration note:** `pipeline/0006` gives `pipeline_flow.subject` a database default of `person`. Older data migrations (`0002_seed_flows`, which tests run again) create flows through historical models that don't know the field. Django 4.2 has no `db_default`.
- **Access:** the boards are under `/staff/`, so only staff see them. Volunteers in the Agents group review and edit leads in `/agents/`, but don't see boards until volunteer logins (IDEA-005) decide what they get.
- **Tests:** 425 in the full suite, including `pipeline/tests/test_leads.py` and the lead flow tests in `hlagents/tests/test_services.py`.

### H5 — Stage, then prod (checklist, not started)
Deploys run `migrate` automatically (`infra/cloudbuild/deploy.yaml`). Nothing here needs Terraform: the worker's 900 s timeout and the 10-minute Cloud Tasks deadline already cover the 480 s run limit.
1. **Secrets:** add `OLLAMA_API_KEY` and `TAVILY_API_KEY` to the environment's `.env` secret (the one `GCP_SECRETS_NAME` names) in `hl-main-stage`, and later `hl-main-prod`. Use separate keys per environment if the providers allow it, so stage usage can be told apart.
2. **Merge** `feature/hlagents-01` into develop, then push develop and staging. Migrations that run:
   - `pipeline` 0005, 0006 (renumbered after develop's `0004_enrollment_endings`, BUG-037)
   - `hlagents` 0001–0006
   - `hlagents` 0004 adds every active staff user to **Agents**
3. **Admins:** add whoever should change agents, providers and caps to **Agent admins** (superusers already can).
4. **Check on stage:**
   - Run each agent once.
   - Follow up on a run.
   - Approve a lead and find it on the Funding board.
   - Import the real partners CSV and check bounces and the Partner step.
   - Lower the run cap and confirm a run stops.
5. **Prod:** the same secrets and Agent admins, at the next release. Look at the caps first: the defaults are $1 per run and $10 per day, and Ollama Cloud's rates are set to $0 because it's a subscription.

### H6 — Stages in /agents/ (2026-10-22, `feature/hlagents-02`)
On stage, the leads looked unusable: there was no way to mark how far an application had got. The Funding and Outreach flows already had the steps, but you could only move a lead on the `/staff/` board, and nothing in `/agents/` led there. Jeff chose to keep the H4 steps and add controls where people work with leads.
- **Service:** `services.set_stage(lead, step, actor, from_step=None)` moves the lead's open enrollment with `pipeline.move_to_step`, so each move is logged on the lead's timeline. It refuses a lead with no open enrollment ("Approve this lead to track its stage."), a step from another flow, and a stale move (`StaleStep`, e.g. after someone moved it on the board). `services.attach_stages(leads)` sets `lead.enrollment` and `lead.stage_steps` for a list in a fixed number of queries.
- **`POST /agents/leads/<id>/stage/`** (`change_lead`) takes `step` and `from_step`. An htmx request gets the lead row back, redrawn with the saved stage and any error. A form post redirects to the lead page with a message.
- **Leads list and run page:** a Stage column. Approved leads have a select grouped by phase that moves on change; other leads say "Not tracked". The leads list filters by stage (step title, grouped by flow).
- **Lead page:** a Stage box with the select and Move, how long the lead has been on the step, and for staff "View on the Funding board →". Untracked leads say why.
- **`/agents/`:** staff get Funding board and Outreach board buttons.
- **Not built:** completing an enrollment (Awarded, Declined, Partner are final steps) stays on the board. A lead can be moved onto those steps here, but not marked complete.
- **Tests:** `StageTest` in `test_services.py` and `StageViewTest` in `test_views.py`, including a query-count check for the leads list. The full suite (448) passes.

### H7 — Lead quality (2026-10-23, `feature/hlagents-03`)
On stage, both agents' leads were poor. Funding leads were home pages with no amount or deadline, or closed programs. Outreach leads had the wrong roles, shared mailboxes and emails that looked made up. Agents found leads we already had, and runs failed on bad JSON or the step limit. The causes: the agents could only see search snippets, didn't know the date or the existing leads, and nothing checked their answers.
- **Tools:**
  - `web_search` uses Tavily advanced search with 8 results, and returns only each result's title, URL and snippet (up to 1,000 characters). It takes an optional `max_results`.
  - New `read_page(url)` (Tavily extract, markdown) returns up to 12,000 characters of a page.
- **Context:** a run's system prompt ends with today's date. The first request, and each follow-up, is followed by a note listing the leads we already have (`services.known_leads_hint`): funder names, or outreach emails with name and org. It lists the 300 most recent, including rejected leads.
- **Checks** (`AgentType.validate`): a candidate's `application_url` or `contact_email` has to appear in what the run's tools returned (`conversation.tool_text`). URLs are compared without scheme, `www.`, query or trailing slash. Funding URLs can't be a home page. Outreach emails can't be shared mailboxes (`info@`, `office@`, `veterans@`, …). `save_leads` returns a `SaveResult` with counts by reason, and the run's result reads like "Inserted 4. Skipped: 3 already known, 2 not in sources, 1 home page."
- **Loop:**
  - A reply that isn't valid JSON is sent back once to be fixed.
  - The last allowed step offers no tools, so the agent answers with what it has.
  - Candidates that fail a check (not in sources, home page or shared mailbox) are sent back once to be fixed or replaced, if at least two steps are left.
  - These messages are notes (`conversation.note`). The run page shows them as "Note to the agent", and doesn't count them as staff's messages. The run page also shows pages read, and counts tool calls instead of searches.
- **Listing and news sites** (2026-10-23, after the comparison): a funding lead's URL can't be on a grant listing or news site. `agents/funding.py` has `BLOCKED_DOMAINS` (Instrumentl, GrantWatch, Candid, PR Newswire, …), and also blocks `news.`/`newsroom.`/`press.`/`blog.` hosts and paths with a `news`, `press`, `blog` or `stories` segment. These leads are sent back to be fixed, like home pages. In two real gemma runs, the first had 4 such URLs rejected and replaced. Some still get through: listing sites that aren't on the list, and press releases at plain paths. The list is in code, so adding a site takes a deploy.
- **Migration `0007_lead_quality`:** gives the seeded agents `read_page` and new prompts that use it (search, read the program's or directory's page, and only include what the page shows). It sets the rates to $0.016 per search (advanced is 2 credits) and $0.002 per page read. Prompts, tools and rates that were edited in settings are kept.
- **Comparing models:** `python manage.py hlagents_compare --agent "Funding opportunities" --models gemma4:31b,gpt-oss:120b --request "…" [--repeat N] [--keep]` runs the agent once per model and prints its leads and a summary table. Each run is rolled back, so every model starts from the same leads, unless `--keep` is given. `--steps N` overrides the step limit for the comparison.
- **The last step:** gpt-oss and nemotron sometimes call tools even when none are offered. On the last step those calls are dropped, and the reply is taken as the answer.
- **Comparison (2026-10-23, dev keys, 5 per request, with no known leads):**
  - The dev Ollama key is on the **free plan**. Only `gemma4:31b`, `gpt-oss:20b`/`120b` and `nemotron-3-super`/`ultra` work. kimi, deepseek, glm and minimax return 402, and mistral-large-4 returns 403. Check stage's key before choosing a model there.
  - **Outreach, Ohio:** `gemma4:31b` (17 s, 2 steps) and `nemotron-3-ultra` (45 s) each returned 5 county service officers and outreach staff, each with a personal work address, all found in sources. `nemotron-3-super` returned 3 (it used all 15 steps). `gpt-oss:120b` used all 15 steps and gave an empty answer.
  - **Funding, 15 steps:** only `gemma4:31b` finished (43 s, 6 leads, 1 home page skipped). Some leads were still aggregator pages (instrumentl, grantsmarts) or out of range. The others used all 15 steps, one tool call per step, and gave an empty answer.
  - **Funding, 30 steps:** `nemotron-3-ultra` returned the best leads: real program pages for Wounded Warrior Project, Bob Woodruff and Infinite Hero. But it took 493 s, which is over the 480 s run limit. `gpt-oss:120b` (119 s) mostly returned press releases and a program whose deadline had passed.
  - **Next:** keep `gemma4:31b` for outreach. For funding, choose between gemma (fast, weaker) and nemotron-3-ultra with about 20 steps (better, slow). Check stage's Ollama plan.
- **Tests:** `test_tools.py` and `test_compare.py` are new. `test_loop.py`, `test_conversation.py` and `test_seed.py` cover the rest.

## 9. Tasks and the Gemini provider (IDEA-007, `docs/designs/completed/ai-tasks.md`)
Besides agents, hlagents runs **tasks**: single provider calls with no tools, used by other apps.
- **Models:**
  - `TaskConfig`: one row per key in `hlagents/task_types.py`, with provider, model, instructions (the system prompt) and options.
  - `TaskCall`: one row per call, failed or not, with tokens and cost.
  - `models.spent_today()` replaces `AgentRun.spent_today()` and adds task calls, so tasks count toward the daily cap.
- **Service:** `hlagents.completion.complete(key, message, user=None)` returns the reply or raises `CompletionFailed(model, reason)`. It refuses an inactive task or provider, a missing key, or the daily cap, using the same checks as runs (`services.provider_problem`, `cap_problem`).
- **Gemini provider** (`providers/gemini.py`, kind `gemini`): Gemini on Vertex AI with the server's Google credentials, at `ProviderConfig.location` or `GEMINI_LOCATION`. It's text only until IDEA-008 adds tool calls, so the agent settings form refuses a Gemini provider.
- **Provider changes:** `ChatProvider.chat` takes `options` (temperature, top_p, top_k, max_output_tokens, thinking_budget). Providers are built with `from_config(config, timeout)`.
- **Settings:** `/agents/settings/` lists the tasks with today's calls and cost. `/agents/settings/tasks/<id>/` edits a task and shows its recent calls (Agent admins).
- **Tasks so far:** `resume_overview`, `resume_bullets` and `bullet_rewrite`, used by `cold_apply/text_generation.py`, and `job_keywords`, used by `cold_apply/keywords.py` (with the in-house analyzer as its fallback).

## 10. Agents on Gemini and Google search (IDEA-008, `docs/designs/in-progress/gcp-agents.md`)
- **Provider:** `GeminiProvider` handles tool calls, so agents can run on Gemini. Thought signatures are kept on each tool call (`thought_signature`, base64) and sent back. Tool replies share a Gemini turn, and text gets its own.
- **Tools:**
  - `web_search` runs the `web_search` task: a Gemini call with Google Search grounding. It returns the cited sources with real URLs and snippets with links and emails removed, plus Google's search suggestions. The run page shows those, and the model never sees them.
  - `read_page` fetches the page itself (HTML, text or PDF) and refuses non-public addresses.
  - Tavily is no longer used.
- **Time limits and Stop:** each model call in a run is cut off at `HLAGENTS_CALL_TIME_LIMIT` (120 s) or the time left in the run. Staff can stop a run from its page (*Stopped by staff*). Runs left Running after the worker died are marked Failed after `HLAGENTS_STALE_RUN_AFTER` (900 s).
- **Seeds (0013):**
  - Both agents are on Gemini on Vertex with `GEMINI_MODEL`.
  - Searches use `gemini-3.5-flash-lite`.
  - Tool costs are $0.014 per search and $0 per read.
  - Ollama Cloud is still a provider an agent can be switched to.
- **Comparing:** `hlagents_compare` takes `--provider` and `--search-model`.

