# AI tasks: resume generation and keyword extraction through hlagents (IDEA-007)

Branches `feature/idea-007-resume` (effort R), then `feature/idea-007-keywords` (effort K), both from `develop`.

> **Status:** design agreed with Jeff on 2026-10-23 (decisions in §7). R merged into develop (c847d4c). K done on `feature/idea-007-keywords` (§8).

## 1. Context
IDEA-007 in `docs/backlog.md`, from `docs/hlagents.md` §6.14: run resume generation and job keyword extraction through the hlagents provider layer, so their provider and model can be switched in settings like the agents'.

**Resume generation works today.** BUG-038 was fixed in e61356f and merged in c92d401.
- `cold_apply/text_generation.py` `generate_text()` calls Gemini on Vertex directly through `google-genai`.
  - The model comes from `settings.GEMINI_MODEL` (default `gemini-3.8-flash`) and the endpoint from `GEMINI_LOCATION` (default `global`). Auth is ADC.
  - Automatic function calling is disabled (b917053).
- It raises `TextGenerationError`. The overview and bullet create views (`cold_apply/views.py:734`, `:840`) show it as a form error, and `regenerate_bullet_view` (`:864`) returns 502 with the message.
- `OverviewUpdateView` (rebuilt for BUG-044) only edits text, so it doesn't call generation.
- `python manage.py vertex` is a smoke test.

So this is no longer a fix. It moves the provider and model choice from an env var and a deploy to `/agents/settings/`.

**Keyword extraction is weak.** `cold_apply/static/scripts/keyword_analyzer/keyword_analyzer.py` is "TF-IDF" fit on one job description at a time. With one document every IDF is the same, so it only counts words.
- **Phrases are scrambled.** Stopwords and punctuation are removed before bigrams and trigrams are built, and each phrase's words are then alphabetized. "5+ years of experience in Python" gives "python years", and "senior software engineer" gives "engineer senior software".
- **Boilerplate wins.** Equal-opportunity, benefits and "about us" text often outranks skills.
- **Tech terms break.** "C++" becomes "c", and "Node.js" becomes "nodejs".
- **The custom stopword list was tuned to a few sample jobs.** It includes uber, playstation, nextdoor and stanford.
- **Odd edge cases.** All three lists are cut to the shortest one's length, and rows pair the i-th unigram, bigram and trigram, which means nothing.

An LLM should be much better at this. The costs are a few seconds per job, a small charge, results that can differ between runs, and phrases that may not appear in the description (§3.6 checks for those).

BUG-043 (9be02a6) deleted the dead `analyzer.py` and `composer.py` and the tokenizer/tagger code. What's left, `analyze` and `hook_after_jd_analysis` in `keyword_analyzer.py` plus `bullet_weighter.weigh`, needs only the baked-in NLTK `stopwords`, so it's safe to keep as the fallback. `cold_apply/tests/test_bullet_weighter.py` covers `weigh()`.

hlagents H1–H7 are merged into develop. The provider layer is `hlagents/providers/` (`ChatProvider`, `ChatResult`, `get_provider`, `ProviderConfig`), but the only adapter is Ollama.

## 2. Goals and the IDEA-008 boundary
1. Resume generation and keyword extraction call the hlagents provider layer. Each one's provider, model and instructions are a settings change.
2. Resume generation stays on Gemini through the switch, so nothing changes for users on deploy.
3. Every call is logged and counts toward the hlagents daily cost cap.
4. These are **two separate efforts**: R (resume generation) first, then K (keywords).

**Not combined with IDEA-008.** Keeping resume generation on Gemini needs a `gemini` provider kind, which overlaps IDEA-008, but that isn't a reason to combine them.
- IDEA-007 adds a **text-only** `GeminiProvider` with no tool calls. That's enough for single-shot tasks.
- IDEA-008 later teaches the same adapter tool calls (translating to and from the canonical message shape), swaps Tavily for Google search grounding, and moves the agents.
- IDEA-008 then starts from an adapter that's already tested on Vertex.

**Future consumer:** IDEA-009 (resume parser) would be another task key on the same foundation. It's out of scope here, but it's a reason to keep `complete()` generic.

## 3. Design

### 3.1 Gemini provider (`hlagents/providers/gemini.py`)
- Registered as `gemini` in `PROVIDERS` and `ProviderConfig.Kind`.
- Uses `genai.Client(vertexai=True, project=settings.GCP_PROJECT_ID, location=…)`.
  - `ProviderConfig.base_url` is a URLField, so add a `location` CharField. Blank means `settings.GEMINI_LOCATION`.
  - There's no `secret_env`, so `key_problem()` returns "" (ADC).
- `chat(model, messages, tools, options=None)` maps the system message to `system_instruction`, and user and assistant messages to `contents`.
- A non-empty `tools` raises `ProviderError("Gemini tool calls arrive with IDEA-008")`. Until then, the agent settings form refuses a Gemini provider.
- Token counts come from `response.usage_metadata` (`prompt_token_count`, `candidates_token_count`). An empty `response.text` raises `ProviderError`.
- Today's tuning from `generate_text` becomes the default `options`: temperature 0.5, top_p 0.8, top_k 40, max_output_tokens 1024, thinking_budget 0.
- The timeout is set through `HttpOptions`.
- `automatic_function_calling=AutomaticFunctionCallingConfig(disable=True)` is always on in the adapter, not an option.

### 3.2 Provider interface changes
- `ChatProvider.chat` takes an optional `options` dict. `OllamaProvider` passes it through as Ollama `options`, with `max_output_tokens` mapped to `num_predict`. The agents and `FakeProvider` ignore it.
- `get_provider(config, timeout=None)`. Single-shot tasks use about 45 s, because they run inside a web request. Agents keep 180 s.

### 3.3 Models (migration `hlagents/0008_ai_tasks`)
| Model | Fields | Notes |
|---|---|---|
| `TaskConfig` | key, provider FK (PROTECT), model, instructions, options (JSON), active | `key` is unique, a choice from a code registry: `resume_overview`, `resume_bullets`, `bullet_rewrite`, and in K `job_keywords`. `instructions` is the system prompt. |
| `TaskCall` | config FK, model, user (nullable), input_tokens, output_tokens, cost, ok, error, created_at | One row per call, including failures. |

- `AgentRun.spent_today()` becomes a module-level `spent_today()` that sums `AgentRun.cost` and `TaskCall.cost` for today. Its callers are `loop.py:107`, `services.py:102` and `views.py:265`.
- **Seeds:**
  - A "Gemini on Vertex" `ProviderConfig` (kind `gemini`, location from settings).
  - One `TaskConfig` per resume key on it, with `model = settings.GEMINI_MODEL` at migration time, so behavior doesn't change on deploy.
  - Instructions are the fixed parts of today's prompts.
  - Token rates are seeded at 0. Admins need to enter Gemini's rates, or the daily cap ignores task spend (§4, checklist).

### 3.4 Service (`hlagents/completion.py`)
- `complete(key, user_message, user=None) -> str`:
  - loads the active `TaskConfig`
  - checks `key_problem()`, and `spent_today()` against `AgentLimits.daily_cost_cap`
  - calls the provider with no tools
  - records a `TaskCall` with cost (`ProviderConfig.token_cost`) and returns the text
- Any failure (missing or inactive config, cap reached, `ProviderError`, a client exception or timeout) records a `TaskCall` with `ok=False` and raises `CompletionFailed(model, reason)`.
- It logs sizes only, never participant text, as `generate_text` does today.

### 3.5 Settings UI
- `/agents/settings/` gets a **Tasks** section with each task's provider, model, active flag, and today's calls and cost.
- `/agents/settings/tasks/<id>/` edits provider, model, instructions, options and active. It follows `agent_settings_view` and requires `change_agentconfig` (Agent admins).
- The provider form gets the `location` field for Gemini.

### 3.6 Keywords (`cold_apply/keywords.py`)
- `extract_keywords(job, user=None)` calls `complete("job_keywords", job.description)`. It expects JSON `{"unigrams": [...], "bigrams": [...], "trigrams": [...]}` with up to 20 of each, in their natural word order. Parsing is as lenient as `AgentType.parse` (a code fence is accepted).
- **Checks:**
  - Each phrase must have the right word count and appear in the description (case-insensitive, whitespace-normalized). The rest are dropped.
  - The three lists are trimmed to the same length, because the table pairs them by row.
  - An empty list counts as a failure.
- **Fallback:** on `CompletionFailed`, a parse error or a failed check, it runs the existing `analyze()` and `hook_after_jd_analysis()` and logs a warning.
- It writes `KeywordAnalysis` rows: deletes the job's old rows and bulk-creates the new ones.
- Storage stays the unigram/bigram/trigram table, so the fallback and the LLM write the same shape. `weigh()` splits bigrams and trigrams into exactly 2 and 3 words, and the word-count check guarantees that. `weigh()`, `job_detail.html` and `get_keywords` don't change.

## 4. Plan
| Step | What | Done when |
|---|---|---|
| R | §3.1–3.5, and resume generation moved onto `complete()` | Generation works on the seeded Gemini task, and switching a task's model in settings changes the next call |
| K | §3.6, after a comparison on real jobs | Job pages show LLM keywords in natural order, and fall back to the old algorithm when the provider fails |

**R — Resume generation** (`feature/idea-007-resume`)
1. `cold_apply/text_generation.py`:
   - The prompt builders (`generate_overview`, `generate_bullets`, `generate_bullet`, `rewrite_bullet_for_job`) keep their signatures. Each passes its task key and builds only the user message.
   - `generate_text(prompt)` becomes `generate_text(key, prompt, user=None)`. It calls `complete()` and turns `CompletionFailed` into `TextGenerationError(f"The LLM failed you. {model} feels shame, but you can try again later.")`.
   - The `google-genai` client code moves into `GeminiProvider`.
2. The call sites don't change, since they already catch `TextGenerationError` (`views.py:734`, `:840`, `:864`). `request.user` is passed through for the `TaskCall` log.
3. The `vertex` command calls `complete("resume_overview", …)` and prints the provider, model and token counts.
4. `settings.GEMINI_MODEL` is read only by the seed migration. A comment says the runtime model choice is in `TaskConfig`. `GEMINI_LOCATION` stays as the provider's default location.
5. Docs:
   - a §9 "Tasks and the Gemini provider" in `docs/hlagents.md`
   - IDEA-007 → In progress
   - a note in IDEA-008 that a text-only `GeminiProvider` exists
6. **Stage checklist:**
   - Confirm the seeded Gemini provider and tasks.
   - Enter Gemini token rates in `/agents/settings/`.
   - Run `python manage.py vertex`.
   - Generate an overview and a bullet.

**K — Keyword extraction** (`feature/idea-007-keywords`)
1. **Compare first:** `python manage.py keywords_compare --jobs N [--model …]` prints the old and LLM keywords side by side for N real jobs, with nothing saved. Use it to confirm the improvement and tune the instructions before switching.
2. A migration seeds the `job_keywords` `TaskConfig` on the Gemini provider.
3. `cold_apply/keywords.py` (§3.6).
4. `JobDetailView.get_context_data` (`cold_apply/views.py` ~279) calls `extract_keywords(self.object, self.request.user)` instead of `analyze`. `refresh_keywords` is unchanged. The call stays lazy on the job page; moving it to a background task is a follow-up if the latency bothers people.
5. Docs: update §9 in `hlagents.md`, set IDEA-007 → Done, and note that the in-house analyzer is now only the fallback.

## 5. Tests
- `hlagents/tests/test_gemini.py`: mock `genai.Client` to check the system/user mapping, options, token counts, that tools are refused, and that an empty reply raises `ProviderError`.
- `hlagents/tests/test_completion.py` with `FakeProvider`:
  - Success logs a `TaskCall` with cost.
  - An inactive config, the daily cap (counting runs and task calls) and a provider exception each raise `CompletionFailed` and log `ok=False`.
  - `spent_today` sums both.
- Settings view tests: the task edit page and its permission, and an agent can't use a Gemini provider.
- `test_seed.py`: the migration seeds the Gemini provider and the tasks with `GEMINI_MODEL`.
- `cold_apply/tests/test_text_generation.py` patches `get_provider` with `FakeProvider` instead of `genai.Client`:
  - Each generator sends the expected user message.
  - A failure shows the shame message with the model name, as a form error and as the 502 body on regenerate, and nothing is saved.
- K, `cold_apply/tests/test_keywords.py`:
  - Valid JSON writes rows.
  - Phrases that aren't in the description or have the wrong word count are dropped.
  - Failure falls back to `analyze` (mocked).
- K, `test_bullet_weighter.py`: add a case with natural-order LLM phrases (for example "senior software engineer").
- Run `docker compose -p hl-agents run --rm django python manage.py test` for the full suite.

## 6. Verification (local, with the mounted gcloud ADC)
- `python manage.py vertex` returns text from the seeded Gemini task, with token counts.
- As staff on a participant: auto-generate an overview for a job, generate 3 bullets, and regenerate a bullet for a job. Each produces text, and a `TaskCall` row appears in `/agents/settings/`.
- Switch `resume_overview` to the Ollama provider with `gemma4:31b`. The next overview uses it (check `TaskCall.model`). Switch it back.
- Set a task's model to something bogus, or turn off its provider. Each action shows "The LLM failed you. <model> feels shame, but you can try again later." with no 500 and nothing saved.
- Lower the daily cap below today's spend, and generation is refused with the same message.
- K: run `keywords_compare` on real jobs. Refresh a job's keywords and check that the phrases read in natural order. Disable the task, refresh, and check that the old algorithm's keywords appear.

## 7. Decisions (Jeff, 2026-10-23)
1. **IDEA-008 stays separate.** IDEA-007 adds only a text-only Gemini adapter (§2).
2. **Cost:** every call is logged and counted toward the hlagents **daily** cap. Single calls have no per-run cap.
3. **Keyword storage:** keep the `KeywordAnalysis` unigram/bigram/trigram table.
4. **Keyword failure:** fall back to the existing algorithm for now.
5. **Text generation failure:** show "The LLM failed you. `<model>` feels shame, but you can try again later.", naming the configured model.
6. **Keyword rows** (during K): rows run to the longest list, and shorter lists leave blank cells. Cutting all three to the shortest, as §3.6 first said, kept only 4–10 of about 30 usable phrases, because three-word phrases are scarce.

## 8. Status
### R — Resume generation (done 2026-10-23, `feature/idea-007-resume`)
Built as §3.1–3.5 and §4 R describe, with these differences:
- **No Gemini timeout.** `GeminiProvider` ignores `timeout`. `HttpOptions(timeout=…)` is also sent to Vertex as a deadline, and with it set, a call that took 2.7 s without it ran for the full 45 s and failed with 504 DEADLINE_EXCEEDED. A client-side httpx timeout isn't a limit either, because the SDK retries after it (one call took 57 s with a 45 s timeout). Ollama tasks do use the 45 s timeout.
- **Thinking (BUG-049).** `gemini-3.8-flash` ignores `thinking_budget: 0` in about half of calls and thinks for 650–950 tokens, which counted against the old 1024-token limit and cut replies off. The tasks are seeded with `max_output_tokens: 8192`. `GeminiProvider` raises `ProviderError` when the finish reason isn't STOP, and adds thinking tokens to the output tokens, since they're billed as output.
- **Migrations:** `hlagents/0008_ai_tasks` (schema) and `0009_seed_ai_tasks` (seed). They're separate because Postgres won't drop a table in the same transaction that deleted its seed rows, so a single migration couldn't be reversed.
- **`generate_bullet`** (singular) was dead code, imported but never called, so it was deleted instead of getting a task.
- **Bullets:** the bullets task asks for a JSON list. `parse_bullets` accepts a JSON list, a code fence, or one bullet per line (dropping bullet characters, numbers and stray brackets), and keeps at most the quantity asked for.
- **Names:** the task key registry is `hlagents/task_types.py`. `services._cap_problem` and `_provider_problem` became public (`cap_problem`, `provider_problem`) so tasks share the agents' checks and messages. The daily-cap message now says "agent runs and tasks".
- **Checked against `hl-main-stage`** (2026-10-23, `gemini-3.8-flash`): `python manage.py vertex`; through the views on dev data, an overview, 3 bullets and 3 rewrites. Switching the overview task to Ollama Cloud with no key showed "The LLM failed you. gemma4:31b feels shame…" and saved nothing. Latency varies: most calls took a few seconds, but one took 77 s.
- **Tests:** `hlagents/tests/test_completion.py`, `test_gemini.py`, and additions to `test_providers.py`, `test_settings.py` and `test_seed.py`. `cold_apply/tests/test_text_generation.py` was rewritten to go through the tasks with `FakeProvider`. The full suite (607) passes.

**Stage checklist (R):**
1. Deploy. Migrations `hlagents` 0008 and 0009 run, and seed the Gemini provider and the three tasks on `GEMINI_MODEL`.
2. In `/agents/settings/`, check the tasks and enter Gemini's token rates on **Gemini on Vertex** (seeded at $0, so task spend doesn't count toward the cap until then).
3. Run `python manage.py vertex`, then generate an overview, bullets and a rewrite on a test participant, and check that each appears under its task's recent calls.

### K — Keyword extraction (done 2026-10-23, `feature/idea-007-keywords`)
- **Comparison first** (`python manage.py keywords_compare`, on 6 dev-data jobs against `hl-main-stage`):
  - The LLM's keywords are real skills and duties in their natural order ("Python, Java, C++", "Conduct code reviews", "data visualization tools").
  - The old analyzer's are boilerplate and scrambled phrases ("opportunity perfect requirements", "make performance product").
  - The checks dropped only 1–2 of about 30 phrases per job.
  - Three-word phrases are the short list (4–10 per job), which led to decision 6.
- **Built as §3.6, except:**
  - **Blank cells:** rows run to the longest list (decision 6). `weigh()` now adds each cell's words, skipping blanks, instead of assuming exactly 2 and 3 words. `_keyword_text` in `text_generation.py` skips blanks.
  - **The job page doesn't wait.** Only the `global` endpoint serves `gemini-3.8-flash` (`us-central1` and `us-east4` return 404), and it's spiky: 156 s and 74 s in 5 calls, with the rest at 2–5 s. The page now renders its keywords from `partials/job_keywords.html`. With none yet, it shows "Finding keywords…", and htmx posts to the new `cold_apply:job_keywords` (`job_keywords_view`), which finds them and swaps the list in. `refresh_keywords` is unchanged: it deletes them, and the page finds new ones.
  - **Phrase checks:** commas, semicolons, colons, brackets and quotes count as word separators, so "Python, Java and" is three words. Phrases must match whole words, ignoring case. The model's casing is kept ("C++", "SQL").
  - **One writer:** both sources go through `save_keywords`. The analyzer's `hook_after_jd_analysis` and `hook_after_bullet_analysis` were deleted (now unused).
  - **No description:** a job without a description goes straight to the fallback, with no call.
- **Migration:** `hlagents/0010_job_keywords_task` adds the key and seeds the task on the Gemini provider, with the resume options at temperature 0.2.
- **Checked against `hl-main-stage`** on dev data: the job page loads in 0.1–1.8 s, and the keywords follow in 3.5–5.3 s with 12–18 rows. A real browser (Playwright) showed htmx loading the list. Browser tests stub the task, so they use the fallback and make no LLM call.
- **Tests:** `cold_apply/tests/test_keywords.py`, a blank-cell case in `test_bullet_weighter.py`, the endpoint in `test_access.py`, and the seed in `test_seed.py`. The full suite (621) passes.

**Stage checklist (K):** deploy (migration `hlagents` 0010). Open a job page and check that the keywords appear after "Finding keywords…". Click Refresh Keywords and check that they come back. Each fill appears under **Job description keywords** in `/agents/settings/`.
