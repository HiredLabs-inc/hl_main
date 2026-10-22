# HL Agents: a staff UI for AI search agents

Branch `feature/hlagents-01` (develop merged in 2026-10-21), worktree `.claude/worktrees/hlagents-01`.

> **Status:** draft, 2026-10-21. Direction agreed in Q&A with Jeff (§6). Open questions are in §7. No code has been written beyond the empty `hlagents` app and the prototype in `examples/utils/`.

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
   - unknown tools and tool exceptions returned to the model as tool messages instead of crashing
   - `AgentRun.messages` saved after every turn, so the run page shows progress and a crash keeps the history

### 3.2 Models (`hlagents/models.py`)
| Model | Fields | Notes |
|---|---|---|
| `ProviderConfig` | name, kind, base_url, secret_env, active | `secret_env` names the env var or secret that holds the key. **Keys are never stored in the DB.** |
| `AgentConfig` | name, agent_type, provider FK, model, system_prompt, default_request, tools (JSON), tool_descriptions (JSON), max_iterations, active | `agent_type` is a choice from the code registry. Seeded from the prototype prompts by a data migration. You can have several configs per type, for example to compare two models. |
| `AgentRun` | config FK, snapshot (provider, model, prompt), started_by, status, messages (JSON), error, iterations, task FK, created/updated | The snapshot records what was actually used, even if the config changes later. Status: queued / running / done / failed. |
| `Lead` | kind, org_name, first_name, last_name, contact_email, funding_amount, application_deadline, url, justification, review_status, source_run FK, dedupe_key | Unique on (kind, dedupe_key). The key is the normalized org name for funding and the normalized email for outreach, as in the prototype. Review status: new / approved / rejected. |

### 3.3 Running an agent
1. **Run** creates an `AgentRun` with the system prompt and `default_request` (editable before you start). It then calls `background_tasks.queue.queue_task("/agents/tasks/run/<id>/", …)`.
2. The worker view (`work_task` + `is_authorized_task_request`) runs the loop, parses the final reply, and upserts Leads. Duplicates are skipped, and the run records counts like "Inserted 7, skipped 3 duplicates."
3. The run page polls the run's status with htmx while it is queued or running.
4. **Follow-up:** typing a message appends it to `messages` and queues the run again. Any new candidates are added to the same run.
5. A parse failure marks the run failed, shows the raw reply, and still allows a follow-up such as "Return only the JSON."

### 3.4 UI
Built with Django templates, htmx, Alpine, Tailwind and Preline, in the same style as `/staff/`.
- **`/agents/`**: a card per active `AgentConfig` (type, provider and model, last run) with a Run button, and recent runs below.
- **`/agents/runs/<id>/`**: on the left, the conversation (user messages, tool calls collapsed as "searched: …", agent replies) and a follow-up box. On the right, this run's candidates, each with Approve, Reject and inline edit.
- **`/agents/leads/`**: all leads, filtered by kind and review status.
- **`/agents/settings/`**: edit agents (provider, model, prompt, tools, default request) and providers.

### 3.5 Permissions
- Every page uses `app_permission_required("hlagents")` from `userprofile/guards.py`. Staff are granted the permission now. Volunteers get it when IDEA-005 (volunteer logins) lands, with no code change.
- The settings pages also require `hlagents.change_agentconfig`.

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
| H2 | Runs and review UI: worker task, `/agents/`, run page, leads list, permission gate | Both agents run locally against Ollama Cloud and their leads can be reviewed |
| H3 | Chat follow-ups and settings UI | Switching an agent's model in the UI changes the next run |
| H4 | Pipeline: generalize Enrollment and Activity, seed the flows, approve → enroll | An approved lead appears on the Funding board |
| H5 | Secrets on stage, deploy to stage, prod checklist | Works on stage |

## 6. Decisions (2026-10-21)
1. The main deliverable is a **web UI**. The code layer exists to serve it.
2. The first agents are the two prototypes: **funding** and **outreach**.
3. **Users:** staff now and volunteers later, controlled by a permission rather than `is_staff`.
4. **Provider-agnostic**, per agent, switchable without a deploy. The first provider is **Ollama Cloud** with an API key.
5. **Interaction:** run and review, plus chat on a run. No freeform chat in v1.
6. **Results:** Django models, fed into pipeline flows by **generalizing Enrollment**.
7. **Configuration** (provider, model, prompt, tools) is edited in the **agents UI**.

## 7. Open questions
1. Which Ollama Cloud model(s) should be the defaults? Do we want a cost or iteration cap per run, or a daily cap?
2. The outreach agent collects individuals' emails from the web. What do the privacy policy and CAN-SPAM require of us? How long do we keep rejected leads?
3. What is the contacts CSV the outreach prototype dedupes against (`input_file_path`)? Should it be imported as existing leads, and should it be importable again later?
4. What are the steps for the Funding flow (for example Found → Researching → Applying → Submitted → Awarded/Declined) and the Outreach flow (for example Found → Contacted → Replied → Partner)?
5. Should lead edits and review decisions go in the pipeline activity log from the start, or only once a lead is enrolled?
6. Should resume generation (`cold_apply/text_generation.py`, which uses the retired `text-bison@001`, BUG-038) move onto this provider layer later?
