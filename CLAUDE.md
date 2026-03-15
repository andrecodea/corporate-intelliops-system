# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

## Environment Setup

Copy `.env` and populate these keys before running:
- `ANTHROPIC_API_KEY` — primary LLM (claude-sonnet-4-6 by default); falls back to OpenAI if absent
- `OPENAI_API_KEY` — fallback LLM (gpt-5.2 by default)
- `TAVILY_API_KEY` — web search
- `LANGSMITH_API_KEY` — LLM observability (optional)
- `LANGGRAPH_DATABASE_URL` — PostgreSQL for persistent checkpoints (optional; defaults to in-memory)

Optional tuning vars: `MAX_SUBAGENTS_ITERATIONS` (default 1), `MAX_CONCURRENT_RESEARCH_UNITS` (default 2), `RECURSION_LIMIT` (default 50), `MODEL_NAME`, `FALLBACK_MODEL`.

## Architecture

**Entry point:** `langgraph.json` maps the `research` graph to `agent.py:build_agent`.

**`agent.py`** — builds a `deepagents` multi-agent graph:
- `LLMConfig` / `AgentConfig` (Pydantic): validate env-driven config
- `SubAgent` (dataclass): defines name, description, system_prompt, tools for each sub-agent
- `build_agent()`: initializes the LLM (Anthropic → OpenAI fallback), constructs 1 sub-agent, assembles middleware, returns a LangGraph `Runnable`
- Uses `FilesystemBackend(root_dir=workspace/, virtual_mode=True)` so agents write files with virtual paths (`/research_request.md` → `workspace/research_request.md`)

**One sub-agent:**
| Sub-agent | Tool(s) | Use case |
|---|---|---|
| `research-agent` | `tavily_search`, `think_tool` | Web search; fetches full page content via httpx + markdownify when snippets are insufficient |

**Middleware stack** (orchestrator only):
- `ToolRetryMiddleware` — retries up to 3×, 2× backoff, on `TimeoutError`/`ConnectionError`/`UsageLimitExceededError`

No `SummarizationMiddleware` — it caused context amnesia in sub-agents, leading to over-searching.

**`tools.py`** — two LangChain tools: `tavily_search`, `think_tool`.
- `tavily_search`: Tavily API for snippets; when `fetch_full_content=True`, fetches the page via `httpx` and converts HTML → Markdown with `markdownify`. `max_results` is `InjectedToolArg` (hidden from LLM, fixed at 1).
- `think_tool`: no-op reflection tool that prompts deliberate reasoning before/after searches.

**`prompts/`** — four Markdown prompt templates loaded at startup:
- Orchestrator: `orchestrator_agent_instructions.md` + `task_description_prefix.md` + `subagent_delegation_instructions.md`
- Sub-agent: `research_agent_instructions.md`
- Sub-agent prompt accepts a `{date}` format argument

**Orchestrator classifier (Step 0):** before running the full workflow, the orchestrator classifies the request — trivial/conversational queries are answered directly without web research.

**`workspace/`** — runtime output directory. `report_guidelines.md` lives here (loaded lazily by the agent when writing the final report). Agent-generated files (`research_request.md`, `final_report.md`) are excluded from git.

**`tests/run_agent.py`** — manual integration test. Measures TTFT, latency, and per-call token usage. Saves runs to `tests/runs/`. Cleans workspace before each run.

## Token Usage (benchmarks)

| Query type | LLM calls | Total tokens | Latency |
|---|---|---|---|
| Simple / single-topic | ~6 | ~40k | ~60s |
| Comparison / deep research | ~14 | ~107k | ~94s |

## Known Limitations

- `max_subagent_iterations` and `max_concurrent_research_units` in `AgentConfig` are prompt-only — not enforced at the framework level. Claude Sonnet follows these reliably; weaker models may not.
- Sub-agent iteration count has no hard code-level cap in deepagents.
