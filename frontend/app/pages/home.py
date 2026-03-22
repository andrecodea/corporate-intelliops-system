import streamlit as st

st.title("Corporate Intelligence Operations")
st.caption("Structured intelligence for B2B decisions · Powered by Claude Sonnet · Built with LangGraph + deepagents")

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### Four Intelligence Modes")
    st.markdown(
        "Choose the operation that fits your decision: "
        "**Due Diligence**, **Competitor Intel**, **Vendor Evaluation**, or **Sales Intel**. "
        "Each mode structures the research context and shapes the deliverables."
    )

with col2:
    st.markdown("#### Multi-agent Research")
    st.markdown(
        "An orchestrator classifies the request and delegates to specialized research sub-agents "
        "running in parallel. Web search, full-page fetch, and deliberate reasoning — "
        "all coordinated automatically."
    )

with col3:
    st.markdown("#### Deliver & Edit")
    st.markdown(
        "Export the final report as a styled **PDF** for distribution or sharing via Slack. "
        "Open in **Obsidian** when the analyst needs to annotate, extend, or integrate into a workspace."
    )

st.divider()
st.page_link("pages/research.py", label="Start an intelligence operation", icon=":material/network_intelligence:")
