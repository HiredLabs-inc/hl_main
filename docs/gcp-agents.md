# All agents through GCP AI APIs (IDEA-008)

Branches `feature/idea-008-tools` (effort T), then `feature/idea-008-search` (effort S), then `feature/idea-008-move` (effort M), each from `develop`.

> **Status:** design, written 2026-10-28. The three choices in §7 are agreed. Waiting for Jeff to agree the rest before T starts.

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
  - **Tool replies:** consecutive `{"role": "tool"}` messages are grouped into one `role="user"` Content of `Part.from_function_response(name=tool_name, response={"result": <parsed JSON content>})`, because Gemini expects every reply to one turn's calls together.
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

## 4. Plan
| Step | What | Done when |
|---|---|---|
| T | §3.1 | A funding run on Gemini with the Tavily tools saves leads |
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
- `test_settings.py`: an agent can be saved on a Gemini provider.
- `test_seed.py`: the `web_search` task and the move migration, both ways.
- Full suite: `docker compose -p hl-agents run --rm django python manage.py test`.

## 6. Verification (local with the mounted gcloud ADC, then `hl-main-stage`)
- A funding run on Gemini from `/agents/`. The run page shows searches whose results have real URLs (no `grounding-api-redirect`), page reads, and saved leads.
- An outreach run. Each saved email appears in a `read_page` result.
- The `web_search` task's calls show under its row in `/agents/settings/`, and the run's cost includes the search price.
- Switch an agent to Ollama. It still runs with the new tools.
- With `TAVILY_API_KEY` unset, both agents and the tasks still work.

## 7. Decisions (Jeff, 2026-10-28)
1. **Search as a tool.** `web_search` stays a function tool, backed by a separate Gemini call with Google Search grounding. Grounding isn't turned on in the agent's own call, so the loop, the checks and the run page stay provider-neutral.
2. **Keep Ollama** as a provider kind. Only the seeded agents move.
3. **`read_page` fetches directly** and converts the HTML in-house, so its text is the real page and the checks stay strict. Gemini URL context isn't used.

## 8. Open questions and risks
1. **Search suggestions.** Google's terms for Grounding with Google Search ask apps to show the search suggestions (`search_entry_point.rendered_content`) with grounded results. Does that apply when only staff see the results on the run page? If it does, show them on the run page's search entries.
**Answer** Yes. 
2. **Latency.** Gemini calls have no timeout (`docs/ai-tasks.md` §8 R), and `global` has had 74–156 s spikes. A run makes about twice as many Gemini calls as before (one per step and one per search), so check runs against `HLAGENTS_RUN_TIME_LIMIT` during the comparison.
3. **PDFs.** Tavily extract read PDFs, and some grant guidelines are PDFs. Add `pypdf` to `read_page` if the comparison shows runs need it.
4. **Bot blocking.** Some sites block plain fetches or need JavaScript. Tavily handled some of these. Count failed reads in the comparison.
5. **Model.** Which Gemini model the agents use (flash or pro) is decided from the comparison, since it's a settings change.

## 9. Status
Not started.
