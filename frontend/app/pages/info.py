import streamlit as st
import streamlit.components.v1 as components

st.title("How it works")
st.caption("Architecture, agent flow, and performance benchmarks for Corporate Intelligence Operations.")

# --------------------
# |    MERMAID       |
# --------------------

def render_mermaid(diagram: str, height: int = 400):
    html = f"""
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({{ startOnLoad: false, theme: 'neutral' }});
        document.addEventListener('DOMContentLoaded', async () => {{
            await mermaid.run();
            const svg = document.querySelector('svg');
            if (svg) {{
                const h = svg.getBoundingClientRect().height;
                window.parent.postMessage({{ type: 'streamlit:setFrameHeight', height: h + 32 }}, '*');
            }}
        }});
    </script>
    <div class="mermaid" style="font-family: sans-serif;">
    {diagram}
    </div>
    """
    components.html(html, height=height, scrolling=False)

# --------------------
# |   AGENT FLOW     |
# --------------------

st.subheader("Agent Flow")
st.markdown(
    "Each operation starts with the orchestrator classifying the request. "
    "Single-subject operations (Due Diligence, Sales Intel) use one research agent. "
    "Comparative operations (Competitor Intel, Vendor Evaluation) dispatch two agents in parallel."
)

render_mermaid("""
flowchart LR
    U([Intelligence Request]) --> O[Orchestrator]
    O -->|Trivial| D([Direct Answer])
    O -->|Operation| C{Subjects?}
    C -->|Single| R1[research-agent]
    C -->|Comparison| R2[agent A]
    C -->|Comparison| R3[agent B]
    R1 --> T[think_tool]
    R2 --> T
    R3 --> T
    T -->|Gap remains| RX[research-agent]
    RX --> F[Write report]
    T -->|Sufficient| F
    F --> OUT([Intelligence Report])
""", height=280)

st.divider()

# --------------------
# | RESEARCH AGENT   |
# --------------------

st.subheader("Research Agent Loop")
st.markdown(
    "Each research sub-agent has a hard limit of **2 searches**. "
    "Results are returned as a compressed bullet-point summary — not raw search output — "
    "to reduce context size passed back to the orchestrator."
)

render_mermaid("""
flowchart LR
    IN([Task from Orchestrator]) --> Search[tavily_search — 3 results]
    Search --> Gap{Gap remains?}
    Gap -->|Yes| Search2[tavily_search — targeted query]
    Gap -->|No| OUT([Compressed summary + Sources])
    Search2 --> OUT
""", height=180)

st.divider()

# --------------------
# |   LLM BUDGET     |
# --------------------

st.subheader("LLM Call Budget")

render_mermaid("""
flowchart LR
    subgraph Simple ["Simple query (~5 calls, ~35k tokens)"]
        direction LR
        O1[Orchestrator plan] --> RA1[research-agent 1-2 calls] --> O2[Orchestrator think + write 2-3 calls]
    end
    subgraph Complex ["Comparison query (~10 calls, ~90k tokens)"]
        direction LR
        O3[Orchestrator plan] --> RA2[agent A 1-2 calls] & RA3[agent B 1-2 calls] --> O4[Orchestrator think + write 3-4 calls]
    end
""", height=220)

st.divider()

# --------------------
# |     STACK        |
# --------------------

st.subheader("Stack")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
| Component | Choice |
|---|---|
| LLM (primary) | `claude-sonnet-4-6` |
| LLM (fallback) | `gpt-5.2` |
| Agent framework | `deepagents` + LangGraph |
| Web search | Tavily API |
""")

with col2:
    st.markdown("""
| Component | Choice |
|---|---|
| Full page fetch | `httpx` + `markdownify` |
| Checkpointing | `InMemorySaver` / PostgreSQL |
| API layer | FastAPI + SSE |
| Frontend | Streamlit |
""")

st.divider()

# --------------------
# |   BENCHMARKS     |
# --------------------

st.subheader("Performance Benchmarks")
st.dataframe(
    {
        "Query type": ["Simple / single-topic", "Comparison / deep research"],
        "LLM calls": ["~5", "~10"],
        "Total tokens": ["~35k", "~90k"],
        "Latency": ["~50s", "~75s"],
    },
    hide_index=True,
    use_container_width=True,
)
