# Deep Research Agent

A multi-agent deep research assistant built with [deepagents](https://github.com/langchain-ai/deepagents) and LangGraph. Given a query, it autonomously searches the web, synthesizes findings, and produces a structured report with cited sources.

## Architecture

### Agent Flow

```mermaid
flowchart TD
    U([User Query]) --> O[Orchestrator\nclaude-sonnet-4-6]

    O -->|Trivial query| D([Direct Answer])

    O -->|Research needed| B[Step 1: Save\nresearch_request.md]
    B --> C{Query type?}

    C -->|Single topic| R1[research-agent]
    C -->|Comparison| R2[research-agent A\n2–3 topics]
    C -->|Comparison| R3[research-agent B\n2–3 topics]

    R1 --> S[Synthesize findings]
    R2 --> S
    R3 --> S

    S --> W[Step 2: Read\nreport_guidelines.md]
    W --> F[Step 3: Write\nfinal_report.md]
    F --> V[Step 4: Verify vs\nresearch_request.md]
    V --> OUT([Final Report])
```

### Research Agent Loop

```mermaid
flowchart TD
    IN([Task from Orchestrator]) --> Search[tavily_search\nsnippet mode]
    Search --> Think[think_tool\nassess findings]
    Think -->|Snippet sufficient| More{More gaps?}
    Think -->|Need full content| Fetch[tavily_search\nfetch_full_content=True\nhttpx + markdownify]
    Fetch --> Think2[think_tool\nreassess]
    Think2 --> More
    More -->|Yes, max 3 searches| Search
    More -->|No| OUT([Summary + Sources])
```

### LLM Call Budget

```mermaid
flowchart LR
    subgraph Simple ["Simple query (~6 calls, ~40k tokens)"]
        direction LR
        O1[Orchestrator\nplan] --> RA1[research-agent\n3–4 calls] --> O2[Orchestrator\nwrite report]
    end

    subgraph Complex ["Comparison query (~14 calls, ~107k tokens)"]
        direction LR
        O3[Orchestrator\nplan] --> RA2[agent A\n4–5 calls] & RA3[agent B\n4–5 calls] --> O4[Orchestrator\nwrite report\n3–4 calls]
    end
```

## Stack

| Component | Choice |
|---|---|
| LLM (primary) | `claude-sonnet-4-6` (Anthropic) |
| LLM (fallback) | `gpt-5.2` (OpenAI) |
| Agent framework | `deepagents` + LangGraph |
| Web search | Tavily API |
| Full page fetch | `httpx` + `markdownify` |
| Checkpointing | `InMemorySaver` (default) / PostgreSQL |

## Setup

```bash
# Install dependencies
uv sync

# Copy and fill environment variables
cp .env.example .env
```

Required keys in `.env`:

```env
ANTHROPIC_API_KEY=...   # primary LLM
OPENAI_API_KEY=...      # fallback LLM
TAVILY_API_KEY=...      # web search
```

Optional:

```env
LANGSMITH_API_KEY=...         # observability
LANGGRAPH_DATABASE_URL=...    # persistent checkpoints (PostgreSQL)
MODEL_NAME=claude-sonnet-4-6
MAX_CONCURRENT_RESEARCH_UNITS=2
MAX_SUBAGENTS_ITERATIONS=1
RECURSION_LIMIT=50
```

## Running

**Integration test (CLI):**

```bash
python tests/run_agent.py "what is context engineering for AI agents?"
```

**LangGraph dev server:**

```bash
PYTHONUTF8=1 uv run langgraph dev --no-reload --allow-blocking
```

## Performance Benchmarks

| Query type | LLM calls | Total tokens | Latency |
|---|---|---|---|
| Simple / single-topic | ~6 | ~40k | ~60s |
| Comparison / deep research | ~14 | ~107k | ~94s |

## Roadmap

### Phase 1 — Token & Cost Optimization
- [ ] Compress sub-agent findings before passing to orchestrator (reduce report-writing context)
- [ ] Route report-writing calls to a cheaper model (e.g. Haiku) instead of Sonnet
- [ ] Evaluate removing the verification step (Step 6) to save 1 orchestrator call

### Phase 2 — API Layer (FastAPI)
- [ ] Expose the agent as a REST API via FastAPI
- [ ] Streaming endpoint (`/stream`) for real-time token delivery
- [ ] Thread/session management for multi-turn conversations
- [ ] Request validation and structured error responses

### Phase 3 — Frontend (CopilotKit)
- [ ] Custom chat UI built with [CopilotKit](https://copilotkit.ai)
- [ ] Real-time streaming rendering of the final report
- [ ] Source citations rendered as clickable cards
- [ ] Research progress indicators (which sub-agent is running, search queries in flight)
