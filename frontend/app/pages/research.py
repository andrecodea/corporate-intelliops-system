import re
import json
import urllib.parse
import os

import httpx
import streamlit as st
from httpx_sse import connect_sse, SSEError

API_URL = os.getenv("RESEARCH_API_URL", "http://localhost:8005/research/stream")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

st.title("Research")
st.caption("Enter a query and the agent will search the web, synthesize findings, and produce a cited report.")

# --------------------
# |    UTILITIES     |
# --------------------

def fix_latex(text: str) -> str:
    text = re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', text, flags=re.DOTALL)
    text = re.sub(r'\\\((.*?)\\\)', r'$\1$', text)
    return text

def format_activity_item(tool: str, inp: dict, done: bool = False) -> str:
    suffix = " \u2713" if done else ""

    if tool == "task":
        detail = inp.get("description", "")[:80] + "..."
        return f"**Delegate**{suffix} \u2014 {detail}"
    elif tool == "tavily_search":
        detail = inp.get("query", "")
        return f"**Search**{suffix} \u2014 _{detail}_"
    elif tool == "think_tool":
        return f"**Think**{suffix} \u2014 assessing findings"
    elif tool == "write_file":
        detail = inp.get("file_path", "")
        return f"**Write**{suffix} \u2014 `{detail}`"
    elif tool == "read_file":
        detail = inp.get("file_path", "")
        return f"**Read**{suffix} \u2014 `{detail}`"
    return f"**{tool}**{suffix}"

def stream_events(query: str):
    try:
        with httpx.Client(timeout=180) as client:
            with connect_sse(client, "POST", API_URL, json={"query": query}) as source:
                for event in source.iter_sse():
                    try:
                        data = json.loads(event.data) if event.data and event.data != "{}" else {}
                        yield event.event, data
                    except json.JSONDecodeError:
                        continue
    except SSEError as e:
        raise ConnectionError(f"API returned a non-SSE response. Is the server running? ({e})")

def send_to_slack(content: str) -> bool:
    try:
        response = httpx.post(
            SLACK_WEBHOOK_URL,
            json={"text": f"*Deep Research Report*\n\n{content[:2900]}"},
            timeout=10,
        )
        return response.status_code == 200
    except Exception:
        return False

# --------------------
# |      INPUT       |
# --------------------

query = st.text_input(
    "Query",
    placeholder="e.g. What are the latest advances in context engineering for LLMs?",
    label_visibility="collapsed",
)
search_btn = st.button("Search", icon=":material/search:", type="primary", disabled=not query)

st.divider()

# --------------------
# |    STREAMING     |
# --------------------

if "report_content" not in st.session_state:
    st.session_state.report_content = ""
    st.session_state.activity_items = []

if search_btn and query:
    st.session_state.report_content = ""
    st.session_state.activity_items = []

    col_activity, col_report = st.columns([2, 3], gap="large")

    with col_activity:
        st.subheader("Agent Activity")
        activity_placeholder = st.empty()

    with col_report:
        st.subheader("Report")
        report_placeholder = st.empty()

    RENDER_EVERY = 15

    token_buffer = ""
    had_tool_calls = False

    activity_placeholder.markdown("_Thinking..._")

    def render_activity():
        lines = [format_activity_item(tool, inp, done) for tool, inp, done in st.session_state.activity_items]
        activity_placeholder.markdown("\n\n".join(lines) if lines else "")

    try:
        for event_type, data in stream_events(query):
            if event_type == "error":
                st.error(f"Agent error: {data.get('message', 'Unknown error')}")
                break

            elif event_type == "tool_call":
                had_tool_calls = True
                tool = data.get("tool", "")
                inp = data.get("input", {})
                st.session_state.activity_items.append((tool, inp, False))
                render_activity()

            elif event_type == "tool_result":
                if st.session_state.activity_items:
                    tool, inp, _ = st.session_state.activity_items[-1]
                    st.session_state.activity_items[-1] = (tool, inp, True)
                render_activity()

            elif event_type == "token":
                token = data.get("content", "")
                if token:
                    if not had_tool_calls:
                        activity_placeholder.info("No deep research needed — answered from existing knowledge.")
                    st.session_state.report_content += token
                    token_buffer += token
                    if len(token_buffer) >= RENDER_EVERY:
                        report_placeholder.markdown(fix_latex(st.session_state.report_content))
                        token_buffer = ""

            elif event_type == "done":
                if token_buffer:
                    report_placeholder.markdown(fix_latex(st.session_state.report_content))
                render_activity()

    except Exception as e:
        st.error(f"Connection error: {e}")

elif st.session_state.report_content:
    col_activity, col_report = st.columns([2, 3], gap="large")

    with col_activity:
        st.subheader("Agent Activity")
        lines = [format_activity_item(tool, inp, done) for tool, inp, done in st.session_state.activity_items]
        st.markdown("\n\n".join(lines) if lines else "")

    with col_report:
        st.subheader("Report")
        st.markdown(fix_latex(st.session_state.report_content))

# --------------------
# |     EXPORTS      |
# --------------------

if st.session_state.report_content:
    report_content = st.session_state.report_content
    st.divider()
    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button(
            "Download Markdown",
            data=report_content,
            file_name="research_report.md",
            mime="text/markdown",
            icon=":material/download:",
        )

    with col2:
        obsidian_uri = f"obsidian://new?content={urllib.parse.quote(report_content)}"
        st.link_button(
            "Open in Obsidian",
            obsidian_uri,
            icon=":material/open_in_new:",
        )

    with col3:
        if SLACK_WEBHOOK_URL:
            if st.button("Send to Slack", icon=":material/send:"):
                ok = send_to_slack(report_content)
                st.success("Sent to Slack.") if ok else st.error("Failed to send.")
        else:
            st.button(
                "Send to Slack",
                icon=":material/send:",
                disabled=True,
                help="Set SLACK_WEBHOOK_URL in .env to enable.",
            )
