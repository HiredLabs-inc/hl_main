# All agents through GCP AI APIs (IDEA-008)

Branches `feature/idea-008-tools` (effort T), then `feature/idea-008-search` (effort S), then `feature/idea-008-move` (effort M), each from `develop`.

> **Status:** design agreed with Jeff on 2026-10-28 (§7). T built on `feature/idea-008-tools`, and S on `feature/idea-008-search`, which branches from T (§9). M not started.

## 1. Context
IDEA-008 in `docs/backlog.md`: run the agents (funding, outreach and future ones) on Google's APIs on Vertex AI instead of Ollama Cloud and Tavily.

**What's there now:**
- **Provider:** IDEA-007 added a text-only `GeminiProvider` (`hlagents/providers/gemini.py`, `docs/ai-tasks.md` §3.1). Given tools, it raises `ProviderError("Gemini can't use tools yet (IDEA-008).")`, and `AgentConfigForm` (`hlagents/forms.py:89`) won't let an agent use a Gemini provider.
- **Loop:** `hlagents/loop.py` expects tool calls in the canonical Ollama/OpenAI message shape (`providers/base.py`), and runs the tools itself (`_call_tool`).
- **Tools:** `web_search` (`tools/web_search.py`) calls Tavily search, and `read_page` (`tools/read_page.py`) calls Tavily extract. Both need `TAVILY_API_KEY`.
- **Lead checks:** each agent checks a candidate's grounded field against the text its tools returned (`conversation.tool_text`, `AgentType.validate`). For funding the field is `application_url`, and for outreach it's `contact_email`. Anything not found is rejected as "not in sources" and sent back once to be fixed. This check is the main protection against made-up leads, so it has to survive the move.
- **Seeds:** the agents are seeded on "Ollama Cloud" (`0002_seed_agents`). `AgentLimits.tool_costs` holds Tavily's prices (`0002`, `0007_lead_quality`).

## 2. Goals
1. `GeminiProvider` handles tool calls, so any agent can run on Gemini.
2. `web_search` and `read_page` no longer need Tavily: search goes through Google Search grounding on Vertex, and pages are fetched directly.
3. The lead checks are as strict as today.
4. The seeded agents move to Gemini. Ollama stays a provider staff can switch to in settings.
5. Every Gemini call, including the ones behind `web_search`, is logged and counts toward the daily cap.

**Not in scope:** new agents, PDF reading (§8), and removing the Ollama provider.

## 3. Design

### 3.1 Tool calls in `GeminiProvider` (effort T)
- **Tools in:** each canonical `{"type": "function", "function": {name, description, parameters}}` becomes a `types.FunctionDeclaration(name, description, parameters_json_schema=parameters)`, all inside one `types.Tool`. Automatic function calling stays disabled, so the loop keeps running the tools and saving after each turn.
- **Messages in** (`_content` grows):
  - **Assistant:** `role="model"`, with a text part when there's content and one `Part(function_call=FunctionCall(name, args))` per tool call.
  - **Thought signatures:** Gemini 3 models require each function-call part to be sent back with the `thought_signature` it came with, or the call fails. The adapter stores it on the canonical call as `call["thought_signature"]`, base64-encoded so it fits in `AgentRun.messages` (JSON), and decodes it when sending.
  - **Tool replies:** consecutive `{"role": "tool"}` messages are grouped into one `role="user"` Content of `Part.from_function_response(name=tool_name, response=<the tool's JSON object>)`, because Gemini expects every reply to one turn's calls together.
  - **Notes** (`conversation.note`) are ordinary user text, as now.
- **Reply out:** `{"role": "assistant", "content": text, "tool_calls": [{"function": {"name", "arguments": dict}, "thought_signature": …}]}`. Thought summaries, if asked for, go under `"thinking"`, which the run page already shows.
- **Error checks:**
  - An empty reply is an error only if it also has no function calls.
  - The finish-reason check stays. `MALFORMED_FUNCTION_CALL` raises `ProviderError` naming the reason, and the run fails with it.
- **Settings form:** remove the Gemini refusal in `AgentConfigForm.clean`.
- **Ollama:** check that `OllamaProvider` accepts the extra `thought_signature` key, so a run started on Gemini can take a follow-up on Ollama. If the client rejects it, strip it before sending.

### 3.2 `web_search` on Google Search grounding (effort S)
Same name, arguments and output shape (`{"results": [{title, url, content}]}`), so the loop, `conversation.py`, the run page and Ollama agents don't change.
- **A task behind the tool:**
  - Add `web_search` to `task_types.py`.
  - Seed its `TaskConfig` on "Gemini on Vertex" with a flash model, short instructions ("Search the web for the query. For each source, say what it says about the query."), and `options: {"google_search": true}`.
  - Staff can then change its model and instructions in `/agents/settings/`, and each search is a `TaskCall` that counts toward the daily cap, like any task.
- **Provider:** `GeminiProvider` maps `options["google_search"]` to `types.Tool(google_search=types.GoogleSearch())`. `ChatResult` gains `sources: list[dict]` (empty by default), filled from the candidate's `grounding_metadata`.
- **Service:** split the body of `completion.complete()` into a function that returns the `ChatResult`. `complete()` still returns the text, and `web_search` calls the new function. A `CompletionFailed` becomes a `ToolError`, which the loop already hands to the model as `{"error": …}`.
- **Results:**
  - One result per `grounding_chunks[i].web`, with its title and URI.
  - The URIs are `vertexaisearch.cloud.google.com/grounding-api-redirect/…` links. Resolve each to the real URL with one request that doesn't follow redirects and reads `Location`. Drop chunks that don't resolve, because a redirect link would fail the funding URL check.
  - A result's `content` is the `grounding_supports` segments that cite that chunk, joined and cut to `SNIPPET_LENGTH`. Results are capped at `max_results`.
- **Search suggestions** (decision 4): the tool also returns `search_entry_point.rendered_content`, Google's own search-suggestions HTML, under a `suggestions` key. The run page shows it, unchanged, on each search's result entry. The model never sees it: the loop removes it from the tool reply before the provider call and stores it beside the reply.

### 3.3 Grounded checks after the switch
- **Funding** checks URLs, and search URLs are now real resolved URIs, so the check is as strict as before.
- **Outreach** checks emails. Tavily's snippets were page text, but grounding snippets are written by the model, so an email in one could be made up.
  - Add `AgentType.grounded_tools`, default `("web_search", "read_page")`.
  - Set `OutreachAgent.grounded_tools = ("read_page",)`. `conversation.tool_text(messages, tools)` keeps only those tools' replies.
  - Tell the outreach prompt to confirm each email with `read_page` (seeded prompt and the CORRECT note in `loop.py`).
- Check how many outreach candidates this rejects in the comparison (§4 M1).

### 3.4 `read_page` by direct fetch (effort S)
Same output shape: `{url, content, truncated}`.
- **Fetch:**
  - `requests.get`, about 20 s timeout, a normal browser User-Agent, `stream=True`, and a cap of about 3 MB.
  - Only `text/html` and `text/plain`. Anything else raises `ToolError("Can't read <type> pages.")`.
- **HTML to text:** BeautifulSoup (new dependency `beautifulsoup4`).
  - Drop `script`, `style`, `noscript`, `nav`, `footer` and `header`.
  - Write links as `text (url)`, with absolute URLs, so the funding URL check still finds links on the page.
  - Collapse whitespace and cut to `PAGE_LENGTH`.
- **SSRF guard:** the worker runs on Cloud Run beside the metadata server, and the URL comes from the model.
  - Only `http` and `https`.
  - Resolve the host and refuse private, loopback, link-local (including `169.254.169.254`), multicast and reserved addresses.
  - Follow redirects by hand, at most 5, and check every hop.

### 3.5 Removing Tavily
After stage is checked:
- delete `tavily-python` from `requirements.txt`
- delete `TAVILY_API_KEY` from `hl_main/settings/base.py` and `cloud.py`
- remove the secret from Secret Manager and Terraform, wherever it's set

### 3.6 Costs
- **Tokens:** the agent's turns use the "Gemini on Vertex" token rates already entered for tasks. The `web_search` task's calls are `TaskCall`s at the same rates.
- **Searches:** Google charges per grounded search on top of tokens. `AgentLimits.tool_costs["web_search"]` becomes that price, and `read_page` becomes $0. Look up the current Vertex price during M.

### 3.7 Run time limits and Stop (effort T)
**What's there now:**
- A run has a time limit, `HLAGENTS_RUN_TIME_LIMIT` (480 s, `hl_main/settings/base.py`). The loop only checks it between steps (`_Turn.converse`), so it can't stop a call that's already running.
- Gemini calls have no timeout. With one set, the SDK fails calls that would have succeeded (`docs/ai-tasks.md` §8 R).
- So nothing stops one slow call except the worker's 900 s request timeout. When that hits, Cloud Run kills the request, and the run is never saved again. It shows "Running" forever, and `follow_up_problem` refuses follow-ups on it ("still working").
- Gemini on `global` has taken 74–156 s on single calls, and a run on Gemini makes about twice as many calls (one per step and one per search). Slow calls will become more common.
- Staff can't stop a run.

**Changes:**
1. **A hard limit on each call.** `providers.call_with_limit(func, seconds)` runs the call in a worker thread and waits up to `seconds`. If the call isn't back by then, it raises `ProviderError("<model> didn't answer within N s.")`. The thread is abandoned, and its reply is thrown away when it arrives. The limit is the smaller of `HLAGENTS_CALL_TIME_LIMIT` (new, 120 s) and the time left in the run. The loop uses it for the agent's own calls, and `web_search` uses it for its search call. It works the same for Ollama.
2. **The run limit holds.** With (1), no run can go much past 480 s, even mid-call. A run stopped by either limit is Failed with a clear message, keeps its messages and any leads it saved, and can take a follow-up.
3. **Stop button.** A new `AgentRun.stop_requested` flag and a new status, *Stopped by staff*.
   - The run page shows **Stop** while a run is queued or running, to anyone who can start runs.
   - A queued run stops at once, and the worker skips it, because it only starts queued runs.
   - A running run checks the flag before each step and each tool call, and stops at the next check. That takes up to one call's limit (120 s). Until then the page shows "Stopping…".
   - A stopped run keeps its leads and can take a follow-up.
4. **Stuck runs are cleaned up.** A run that has said Running for longer than the worker timeout (900 s) since its last save is marked Failed: "The worker stopped before the run finished." This is checked when the run page or the runs list loads, so no scheduled job is needed. The loop saves after every step, and a step can't take 900 s because of (1), so a live run is never caught by this.

Single-shot tasks (`completion.complete`) could use `call_with_limit` too, but that changes how resume generation and keywords behave, so it's not part of IDEA-008 (§8).

## 4. Plan
| Step | What | Done when |
|---|---|---|
| T | §3.1, §3.7 | A funding run on Gemini with the Tavily tools saves leads, and a run can be stopped from its page |
| S | §3.2–3.4 | Runs on either provider search and read pages with no Tavily key |
| M | Compare, move the seeds, then §3.5 | The seeded agents run on Gemini on stage, and Tavily is gone |

**M — Move the agents** (`feature/idea-008-move`)
1. **Compare first:** add `--provider` to `hlagents_compare`, so one command can compare Ollama and Gemini on the same request. Look at leads found, rejections by reason, cost and time. Tune the agent prompts and the `web_search` instructions until Gemini is at least as good.
2. **Migration** `hlagents/00xx_agents_on_gemini`:
   - Point the seeded funding and outreach agents at "Gemini on Vertex" with the chosen model.
   - Set the new `tool_costs`, but only where the row still has the seeded values, as `0007_lead_quality` does.
   - Make it reversible.
3. **Docs:** a §10 in `docs/hlagents.md`, §9 Status here, IDEA-008 → Done, release notes.
4. **Stage checklist:**
   - Grounding with Google Search is enabled for the project, and the service account can use it.
   - The Gemini token rates are entered.
   - Run each agent once and review the leads.
   - Then do §3.5.

## 5. Tests
- `test_gemini.py`, with `genai.Client` mocked:
  - tool schemas become FunctionDeclarations
  - tool calls and replies make a round trip: grouped function responses, with signatures sent back
  - a reply with function calls and no text is accepted
  - `MALFORMED_FUNCTION_CALL` raises
  - `google_search` is mapped, and `sources` is filled from grounding metadata
- `test_tools.py`, with `requests_mock`:
  - grounding chunks become results with resolved URLs, unresolved ones are dropped, and snippets come from supports
  - `read_page` turns HTML into text, keeps links and truncates
  - the SSRF guard refuses `localhost`, `10.0.0.1`, `169.254.169.254`, and a redirect to any of them
  - a PDF or image raises `ToolError`
- `test_agents.py` / `test_conversation.py`: `grounded_tools` filtering. An outreach email found only in a search snippet is rejected as "not in sources".
- `test_loop.py`: a whole run through `GeminiProvider` with a mocked client: tool call, reply, final JSON, lead saved.
- §3.7, with `FakeProvider` and a reply that sleeps:
  - a slow call fails the run with the time-limit message, and the run takes a follow-up
  - the call limit shrinks to the time left in the run
  - Stop on a queued run stops it, and the worker skips it
  - Stop on a running run stops it at the next step or tool call, and keeps its leads
  - a Running run not saved for 900 s is marked Failed when its page loads
  - the Stop button's permission
- `test_settings.py`: an agent can be saved on a Gemini provider.
- `test_seed.py`: the `web_search` task and the move migration, both ways.
- Full suite: `docker compose -p hl-agents run --rm django python manage.py test`.

## 6. Verification (local with the mounted gcloud ADC, then `hl-main-stage`)
- A funding run on Gemini from `/agents/`. The run page shows searches whose results have real URLs (no `grounding-api-redirect`), page reads, and saved leads.
- An outreach run. Each saved email appears in a `read_page` result.
- The `web_search` task's calls show under its row in `/agents/settings/`, and the run's cost includes the search price.
- Switch an agent to Ollama. It still runs with the new tools.
- With `TAVILY_API_KEY` unset, both agents and the tasks still work.
- Search entries on the run page show Google's search suggestions.
- Start a run and press Stop. It ends as *Stopped by staff* within about two minutes, with the leads it had saved. Send it a follow-up.
- Locally, set `HLAGENTS_CALL_TIME_LIMIT` to 5 s. A run fails with "didn't answer within 5 s" instead of hanging.

## 7. Decisions (Jeff, 2026-10-28)
1. **Search as a tool.** `web_search` stays a function tool, backed by a separate Gemini call with Google Search grounding. Grounding isn't turned on in the agent's own call, so the loop, the checks and the run page stay provider-neutral.
2. **Keep Ollama** as a provider kind. Only the seeded agents move.
3. **`read_page` fetches directly** and converts the HTML in-house, so its text is the real page and the checks stay strict. Gemini URL context isn't used.
4. **Show Google's search suggestions** on the run page (§3.2). Answered for §8 question 1 ("Does that apply when only staff see the results?"): yes.
5. **Run time limits and Stop** (§3.7): Jeff asked for a way to stop a long run and a built-in cap on how long a run takes. 120 s per call and 480 s per run, agreed.

## 8. Notes for later
None of these need a decision now. They'll be checked during the comparison (§4 M1).
1. **Latency.** Covered by §3.7. In the comparison, count how many runs hit the call or run limit. If many do, raise the limits or use a faster model.
2. **PDFs.** Tavily extract read PDFs, and some grant guidelines are PDFs. Add `pypdf` to `read_page` if the comparison shows runs need it.
3. **Bot blocking.** Some sites block plain fetches or need JavaScript. Tavily got past some of these. Count failed reads in the comparison.
4. **Model.** The comparison decides which Gemini model the agents use (flash or pro). It's a settings change.
5. **Task time limits.** Resume generation and keywords also have no Gemini timeout. They could use `call_with_limit` with `completion.TIMEOUT` (45 s) in a later effort.

## 9. Status
### T — Tool calls, time limits and Stop (2026-10-28, `feature/idea-008-tools`)
Built as §3.1 and §3.7, with these differences:
- **Tool replies and text get separate turns.** A user turn with both function responses and text fails on Vertex with 400 "Requests ending with a model turn are not supported." This happened at the step limit, where the wrap-up note follows the tool replies. Tool replies in a row are one turn. Every text message gets its own user turn, and Vertex accepts user turns in a row. This was checked against `hl-main-stage` with each layout, with and without tools.
- **Tool replies are sent as the tool's JSON object**, not under `"result"`, so tool errors arrive under `"error"` as Gemini expects. A reply that isn't a JSON object is sent as `{"output": …}`.
- **Calls from another provider.** A step's first call with no thought signature, such as one made on Ollama earlier in the run, is sent with Google's documented placeholder `skip_thought_signature_validator`. Call ids, when Gemini sends them, are kept on the canonical call and copied to the matching replies.
- **Ollama** drops the extra `id` and `thought_signature` keys itself, so nothing is stripped.
- **`call_with_limit`** (`hlagents/providers/base.py`) runs the call in a thread. The call can't use the database, because the thread has its own connection. Provider calls don't use it.
- **Loop saves** use `AgentRun.save_progress()`, which saves every field except `stop_requested`, so a save in the middle of a run can't undo a Stop. `follow_up` clears the flag.
- **Settings:** `HLAGENTS_CALL_TIME_LIMIT = 120` and `HLAGENTS_STALE_RUN_AFTER = 900`. Migration `hlagents/0011_run_stop` adds `stop_requested` and the *Stopped by staff* status.
- **Checked against `hl-main-stage`** (`gemini-3.8-flash`, Tavily tools, local dev data, rolled back): a funding run finished in 8 steps, 7 tool calls and 82 s, with signatures sent back on every step. It saved 1 lead. With `HLAGENTS_CALL_TIME_LIMIT=1`, a run failed after 1 s with "gemini-3.8-flash didn't answer within 1 s."
- **Tests:** `hlagents/tests/test_gemini.py` (rewritten with real SDK response types), and the new `test_run_limits.py`: the call limit, Stop on queued and running runs, stuck runs, the Stop view and its permission, and a full run through a mocked Gemini client. In `test_settings.py`, an agent can now use Gemini. The full suite (641) passes.

**Not done in T:** Stop and the time limits were only tested by the tests and the 1 s run above, not by pressing Stop in a browser.

### S — Google search and direct page reads (2026-10-28, `feature/idea-008-search`)
Branched from `feature/idea-008-tools`, not `develop`, because it needs T's provider. Built as §3.2 and §3.4, with these differences:
- **No `grounded_tools`.** §3.3 planned to count only `read_page` replies as an outreach agent's sources. Instead, `web_search` removes URLs and email addresses from its snippets, which are Gemini's own words. Real URLs come only from the resolved sources, and emails only from pages. Both agents' checks stay strict, and neither agent needs a special case. `web_search`'s new `note` tells the model "Snippets leave out links and email addresses: read the page for those." `tool_schema` always adds a tool's note after its description, because the seeded agents override `web_search`'s description.
- **`read_page` keeps headers, footers and nav**, where contact emails and links to the right page often are. Only script, style, noscript, template, svg and iframe are dropped. Lines break only at block elements, and links are spaced apart so a link with no text can't run into the next one's URL.
- **Search suggestions** are a `suggestions` key on the tool message, beside `content`, which is all the providers send. The run page shows them in a sandboxed `<iframe srcdoc>`, unchanged, with a `<base target="_blank">` so their links open in a new tab.
- **Names:** `completion.complete_result(key, message, user=None, limit=None)` returns the `ChatResult`. `web_search` calls it with `limit=HLAGENTS_CALL_TIME_LIMIT`. The task key is `web_search` ("Web search for agents"), seeded by `hlagents/0012_web_search_task` with the resume options at temperature 0.2 plus `google_search: true`. New dependency `beautifulsoup4==4.15.0`.
- **Not done yet (M):** `tavily-python`, `TAVILY_API_KEY` and the Tavily-era `tool_costs` (search $0.016, read $0.002) are still there, but nothing uses Tavily.
- **Checked against `hl-main-stage`** (`gemini-3.8-flash` for agent and search, no Tavily key, local dev data, rolled back):
  - One search took 12.6 s and returned 4 results. Every grounding link resolved to the real page with one HEAD request.
  - `read_page` read `cst.dav.org/grants` in 1.6 s. It refused `169.254.169.254`, `localhost` and an `ftp` URL.
  - **Funding:** Done in 15 steps, 14 tool calls (11 searches, 3 reads) and **293 s**. It saved 3 leads on the funders' own pages (Call of Duty Endowment, Bank of America Charitable Foundation, DAV Charitable Service Trust).
  - **Outreach:** Done in 15 steps, 14 tool calls (5 searches, 9 reads) and 161 s. It saved 3 county or post contacts, each email from a page it read.
  - Every search had suggestions, and all 7 outreach searches were logged as `web_search` task calls with none failed. The outreach run page showed 6 suggestion frames for 7 searches. I couldn't reproduce that with test data (7 searches give 7 frames, and a view test covers it), so check it on stage.
- **Latency for M:** a grounded search takes about 10–20 s, so search-heavy runs are slow. The funding run used 293 of its 480 s. The comparison should look at a faster model for the `web_search` task, fewer searches per run, or a longer run limit.
- **Tests:** `test_tools.py` was rewritten for both tools: grounding results, redirects, URL and email removal, dedupe and cap, HTML to text, size cap, redirects, and the address guard. Also added: grounding and suggestions in `test_gemini.py`, `complete_result` in `test_completion.py`, suggestions in `test_loop.py`, `test_conversation.py` and `test_views.py`, and the seed in `test_seed.py`. Loop tests mock `web_search.search` instead of Tavily. The full suite (657) passes.
