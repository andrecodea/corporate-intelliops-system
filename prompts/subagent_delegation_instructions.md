# Sub-Agent Research Coordination

## Sub-Agent Roles

| Agent | Tool | When to use |
|---|---|---|
| **research-agent** | `tavily_search`, `think_tool` | Searches the web; fetches full page content via `fetch_full_content=True` when snippets are insufficient |

## Delegation Strategy

**Default: 1 research-agent.** Parallelize only when the query explicitly requires comparing distinct entities or clearly separated aspects.

- Simple or single-topic queries → 1 research-agent
- Explicit comparisons → max 2 research-agents in parallel, each covering a group of 2–3 items (never 1 agent per item)

## Limits
- Max {max_concurrent_research_units} parallel sub-agents per iteration
- Stop after {max_subagent_iterations} delegation rounds or when you have sufficient information
