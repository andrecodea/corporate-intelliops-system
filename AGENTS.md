# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

**Product:** Corporate Intelligence Operations — structured B2B intelligence platform with four modes: Due Diligence, Competitor Intel, Vendor Evaluation, and Sales Intel. Each mode collects structured context via the frontend, assembles a targeted query via `build_query()`, and delivers a cited intelligence report as PDF (for distribution) or Markdown/Obsidian (for editing).

## Papel do Codex neste projeto

O usuário é estagiário estudando engenharia de software através deste projeto. Além de implementar funcionalidades, o Codex tem um papel ativo de ensino:

- **Explicar padrões de design** aplicados em cada arquivo — nome do padrão, como está implementado, e por que foi escolhido
- **Documentar decisões de arquitetura** — o problema que motivou a decisão, a alternativa descartada, e o trade-off consciente
- **Explicar o código linha por linha** quando solicitado, com foco em mecanismos não-óbvios (ex: por que `[0]` em vez de `int` numa closure)
- **Revisar resumos e documentações** escritos pelo usuário sobre o código, apontando imprecisões e o que está faltando

Ao explicar, priorize o *porquê* sobre o *o quê*. O usuário consegue ler o código — o que ele precisa é reconstruir o raciocínio por trás dele.

## Commands

**Install dependencies:**
```bash
uv sync
```

**Run integration test:**
```bash
python tests/run_agent.py "your query here"
```

**Run the agent (via LangGraph dev server):**
```bash
PYTHONUTF8=1 uv run langgraph dev --no-reload --allow-blocking
```
- `PYTHONUTF8=1` — required on Windows to avoid cp1252 encoding crash
- `--allow-blocking` — required because `InMemorySaver` does synchronous I/O inside the ASGI event loop
- Studio UI: `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

**Run the FastAPI backend:**
```bash
uv run uvicorn backend.api:app --reload
```
- Endpoint: `POST /research/stream` — SSE streaming

**Run the Streamlit frontend:**
```bash
uv run streamlit run frontend/app/app.py
```

## Environment Setup

Copy `.env` and populate these keys before running:
- `ANTHROPIC_API_KEY` — primary LLM (Codex-sonnet-4-6 by default); falls back to OpenAI if absent
- `OPENAI_API_KEY` — fallback LLM (gpt-5.2 by default)
- `TAVILY_API_KEY` — web search
- `SLACK_BOT_TOKEN` — Slack bot token for PDF upload (`xoxb-...`); requires `files:write` scope (optional)
- `SLACK_CHANNEL_ID` — target Slack channel ID (e.g. `C0XXXXXXXXXX`) for PDF delivery (optional)
- `LANGSMITH_API_KEY` — LLM observability (optional)
- `LANGGRAPH_DATABASE_URL` — PostgreSQL for persistent checkpoints (optional; defaults to in-memory)
- `FIRECRAWL_API_KEY` — full-page extraction (replaces httpx in Sprint 1; required for `fetch_full_content=True`)

Optional tuning vars: `MAX_SUBAGENTS_ITERATIONS` (default 1), `MAX_CONCURRENT_RESEARCH_UNITS` (default 2), `RECURSION_LIMIT` (default 50), `MODEL_NAME`, `FALLBACK_MODEL`, `SUBAGENT_BASE_URL`, `SUBAGENT_API_KEY` (custom provider for sub-agent).

## Project Structure

```
corporate-intelliops-agent/
├── backend/
│   ├── agent.py        # LangGraph orchestrator (build_agent)
│   ├── api.py          # FastAPI SSE endpoint
│   ├── tools.py        # tavily_search + think_tool
│   └── prompts/        # 4 base prompt templates + modes/ directory
│       └── modes/      # 4 mode-specific prompt files (one per intelligence mode)
├── frontend/
│   └── app/
│       ├── app.py      # Streamlit entry point (multi-page)
│       ├── pages/      # home.py, research.py, info.py
│       └── .streamlit/ # Theme config (Space Grotesk/Mono fonts)
├── tests/
│   ├── run_agent.py    # Integration test CLI
│   └── runs/           # JSON results with token metrics
├── workspace/          # Runtime output (agent-generated files, excluded from git)
├── examples/           # Sample generated reports
└── langgraph.json      # Entry point: research → backend/agent.py:build_agent
```

## Architecture

**Entry point:** `langgraph.json` maps the `research` graph to `backend/agent.py:build_agent`.

**`backend/agent.py`** — builds a `deepagents` multi-agent graph:
- `LLMConfig` / `AgentConfig` (Pydantic): validate env-driven config
- `SubAgent` (dataclass): defines name, description, system_prompt, tools for each sub-agent
- `build_agent()`: initializes the LLM (Anthropic → OpenAI fallback), constructs 1 sub-agent, assembles middleware, returns a LangGraph `Runnable`
- Uses `FilesystemBackend(root_dir=workspace/, virtual_mode=True)` so agents write files with virtual paths (`/research_request.md` → `workspace/research_request.md`)

**One active sub-agent:**
| Sub-agent | Tool(s) | Use case |
|---|---|---|
| `research-agent` | `tavily_search`, `think_tool` | Web search; fetches full page content via Firecrawl (Sprint 1 — replaces httpx + markdownify) when snippets are insufficient |

**Middleware stack** (orchestrator only):
- `ToolRetryMiddleware` — retries up to 3×, 2× backoff, on `TimeoutError`/`ConnectionError`/`UsageLimitExceededError`

No `SummarizationMiddleware` — it caused context amnesia in sub-agents, leading to over-searching.

**`backend/tools.py`** — two LangChain tools: `tavily_search`, `think_tool`.
- `create_tavily_search(max_calls)`: factory that returns a `tavily_search` instance with a hard cap enforced via closure counter. Each sub-agent gets a fresh instance with its own zeroed counter (`max_calls=5`). When the limit is reached, the tool returns a blocking message instead of executing.
- `tavily_search`: Tavily API for snippets (search layer); when `fetch_full_content=True`, fetches the full page via Firecrawl (extraction layer — handles Cloudflare and JS-rendered pages); falls back to Tavily snippet on failure. `max_results` is `InjectedToolArg` (hidden from LLM, fixed at 3).
- `think_tool`: no-op reflection tool that prompts deliberate reasoning before/after searches.

**`backend/prompts/`** — prompt templates:
- Orchestrator: `orchestrator_agent_instructions.md` + `task_description_prefix.md` + `subagent_delegation_instructions.md`
- Sub-agent: `research_agent_instructions.md` (accepts `{date}` format argument)
- `modes/` — one file per intelligence mode (`due_diligence.md`, `competitor_intel.md`, `vendor_evaluation.md`, `sales_intel.md`). Each defines research priorities, search strategy, and report structure for that mode. Loaded at request time by the API — **not** at agent startup — so the system prompt stays lean and only the active mode's instructions are in context.

**Orchestrator classifier (Step 0):** before running the full workflow, the orchestrator classifies the request — trivial/conversational queries are answered directly without web research.

**`backend/api.py`** — FastAPI REST layer:
- `POST /research/stream`: accepts `{"query": string, "mode": string | null}`, responds with SSE stream
- Event types: `token`, `tool_call`, `tool_result`, `error`, `done`
- Clears workspace (`research_request.md`, `final_report.md`) before each run
- `_load_mode_prompt(mode)`: reads the corresponding file from `prompts/modes/` and prepends it to the query before passing to the agent. If `mode` is absent or unrecognized, the query is passed as-is (graceful degradation).

**`frontend/app/`** — Streamlit multi-page UI:
- **home.py**: landing page — product positioning, four intelligence modes, CTA
- **research.py**: main interface — mode selector (radio), structured input per mode, optional company URL field (anchors entity resolution, prevents model from researching the wrong company), `build_query()` assembles a targeted prompt from structured fields, streaming SSE consumer, 2-column layout (Activity + Report), export to PDF / Obsidian / Slack
- **info.py**: Mermaid architecture diagrams and benchmark tables
- LaTeX conversion: `\[...\]` → `$$...$$`, `\(...\)` → `$...$`
- PDF export: `report_to_pdf()` converts Markdown → HTML → PDF via `xhtml2pdf` with styled CSS
- Slack export: uploads PDF via `files.upload` Slack Bot API (requires `SLACK_BOT_TOKEN` + `SLACK_CHANNEL_ID`; not webhook — webhooks can't upload files)

**`workspace/`** — runtime output directory. Agent-generated files (`research_request.md`, `final_report.md`) are excluded from git. `large_tool_results/` stores cached full-page fetches.

**`tests/run_agent.py`** — manual integration test. Measures TTFT, latency, and per-call token usage via `UsageTracker` callback. Saves runs to `tests/runs/`. Cleans workspace before each run.

## Design Patterns

Understanding these patterns is critical before modifying the codebase — extending them correctly avoids regressions.

### Factory — `backend/tools.py::create_tavily_search(max_calls)`
Returns a new `tavily_search` tool instance with its own closure-captured call counter. This is how per-sub-agent rate limiting works. **Never share one instance across sub-agents.** Sub-agents use `max_calls=5`.

```python
def create_tavily_search(max_calls: int = 5):
    call_count = [0]  # mutable cell captured by closure
    @tool
    def tavily_search(...):
        if call_count[0] >= max_calls:
            return "HARD LIMIT REACHED..."
        call_count[0] += 1
        ...
    return tavily_search
```

### Strategy — `backend/agent.py::_init_llm()`
LLM selection is a two-strategy chain: Anthropic (primary) → OpenAI (fallback). Controlled entirely by env vars. Adding a third provider means adding a new `elif` branch here.

### Middleware — `backend/agent.py` (deepagents `create_deep_agent`)
`ToolRetryMiddleware` is applied only to the orchestrator (not sub-agents). It intercepts `TimeoutError`, `ConnectionError`, `UsageLimitExceededError` and retries up to 3× with 2× backoff. `SummarizationMiddleware` was deliberately removed — it caused context amnesia.

### Observer / Callback — `tests/run_agent.py::UsageTracker`
Extends `BaseCallbackHandler`, hooks into `on_llm_end` to capture token usage per call. Non-intrusive: zero changes to production code. The pattern for adding new metrics is to extend this class.

### Builder — `backend/agent.py::build_agent()`
Constructs the agent graph in a fixed ordered sequence: env parsing → Pydantic validation → LLM init → tool instantiation → sub-agent construction → prompt assembly → graph creation → config injection. Preserve this order when adding new steps.

### Template Method — `backend/agent.py` (prompt assembly)
Orchestrator prompt is assembled from three separate Markdown files joined with separator lines:
```python
INSTRUCTIONS = ORCHESTRATOR_INSTRUCTIONS
    + "\n\n" + "=" * 80 + "\n\n"
    + TASK_DESCRIPTION_PREFIX
    + "\n\n" + "=" * 80
    + SUBAGENT_DELEGATION_INSTRUCTIONS.format(...)
```
Add new prompt sections by creating a new file in `backend/prompts/` and splicing it here.

### Adapter — `backend/api.py::event_stream()`
Translates LangGraph's internal message types (`AIMessageChunk`, `ToolMessage`, etc.) into typed SSE events (`token`, `tool_call`, `tool_result`, `error`, `done`). This is the single point of protocol translation — keep it that way.

### Facade — `frontend/app/pages/research.py::stream_events()`
Wraps `httpx_sse.connect_sse` into a simple generator yielding `(event_type, data_dict)` tuples. All SSE connection logic, JSON parsing, and error handling lives here.

### Dependency Injection — `backend/tools.py` (`InjectedToolArg`)
`max_results=3` is hidden from the LLM via `Annotated[int, InjectedToolArg]`. This prevents the LLM from requesting more results than intended. Use the same pattern for any tool parameter that should be fixed at runtime.

### Config — `backend/agent.py` (`LLMConfig`, `AgentConfig` Pydantic models)
All env vars are parsed once into Pydantic models at module load. Validation (ranges, types) happens here. If you add a new tuning var, add it to the appropriate model with a `Field(default=..., ge=..., le=...)` constraint — don't `os.getenv()` inline throughout the code.

### Per-request Prompt Injection — `backend/api.py::_load_mode_prompt()`
Mode-specific prompts are loaded at **request time**, not at agent startup. The system prompt stays fixed and lean; the mode instructions travel with the user message:
```
[mode prompt from prompts/modes/{mode}.md]

---

[assembled query from build_query()]
```
**Why at request time:** `build_agent()` runs once at startup — injecting mode there would mean rebuilding the agent per request. Putting it in the user message keeps the architecture stateless and the system prompt stable. **Adding a new mode:** create a new `.md` file in `prompts/modes/` and add an entry to `MODE_FILES` in `api.py`.

---

## Roadmap

See `ROADMAP.md` for the full sprint plan (one week per sprint). Summary of decided architecture:

**Sprint order:** Calibration → New Intelligence Modes → Evals → Production Readiness → RAG → React SaaS → Collaboration → Monetization

**SaaS Frontend (Sprint 6):** Vite + React SPA · Supabase (Auth + PostgreSQL + Storage) · existing FastAPI unchanged
- Auth: email/password + Google OAuth via Supabase
- New FastAPI endpoint: `POST /reports/save` — persists research to Supabase after stream ends
- Routes: `/login`, `/dashboard`, `/research`, `/report/:id`, `/settings`
- Dashboard: card grid with filter sidebar (mode, date, company search)
- Key components: `AuthGuard`, `ResearchCard`, `FilterSidebar`, `ResearchForm`, `StreamViewer`, `ReportView`
- Supabase tables: `researches`, `reports`, `profiles` — all with Row Level Security by user_id

**New intelligence modes (Sprint 2):** each = new `.md` in `prompts/modes/` + entry in `MODE_FILES`:
Market Mapping, Leadership Intel, Funding & Deal Intelligence, Risk Assessment, Regulatory Watch, Talent Signal, Partnership & Ecosystem Mapping

**RAG (Sprint 5):** reports chunked and embedded via Supabase pgvector; conversational agent per report answers questions grounded in the report content. Firecrawl is the extraction layer for full-page fetch — NOT part of RAG.

**Monetization (Sprint 10):** credit-based plans, Pay as You Go for Pro, per-seat add-on.

## Token Usage (benchmarks)

| Query type | LLM calls | Total tokens | Latency |
|---|---|---|---|
| Simple / single-topic | ~2 | ~18k | ~15–20s |
| Comparison / deep research | ~10 | ~90k | ~75s |

## Known Limitations

- `max_subagent_iterations` and `max_concurrent_research_units` in `AgentConfig` are prompt-only — not enforced at the framework level. Codex Sonnet follows these reliably; weaker models may not.
- `tavily_search` hard cap is per-instance: the closure counter resets for each new sub-agent session, which is the intended behavior. The orchestrator's default `tavily_search` instance has no counter reset between requests — restart the server to reset it (not an issue in normal use since the orchestrator self-limits via prompt).
