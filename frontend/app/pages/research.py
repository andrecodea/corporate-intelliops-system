import re
import io
import json
import urllib.parse
import os

import httpx
import streamlit as st
import markdown as md_lib
from xhtml2pdf import pisa
from httpx_sse import connect_sse, SSEError

API_URL = os.getenv("RESEARCH_API_URL", "http://localhost:8005/research/stream")

st.title("Intelligence")
st.caption("Choose a mode, fill in the context, and the agent will research, synthesize, and deliver a structured report.")

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

def report_to_pdf(content: str, title: str = "Intelligence Report") -> bytes:
    html_body = md_lib.markdown(content, extensions=["tables", "fenced_code"])
    html = f"""<!DOCTYPE html>
    <html><head><meta charset="utf-8"><style>
    @page {{ margin: 2cm; }}
    body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11pt; color: #1a1a1a; line-height: 1.6; }}
    h1 {{ font-size: 20pt; color: #0f172a; border-bottom: 2px solid #0f172a; padding-bottom: 6px; }}
    h2 {{ font-size: 14pt; color: #1e3a5f; margin-top: 20px; }}
    h3 {{ font-size: 12pt; color: #374151; }}
    code {{ background: #f3f4f6; padding: 1px 4px; font-family: Courier, monospace; font-size: 10pt; }}
    pre {{ background: #f3f4f6; padding: 10px; border-left: 3px solid #6b7280; }}
    blockquote {{ border-left: 3px solid #d1d5db; margin-left: 0; padding-left: 12px; color: #6b7280; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
    th {{ background: #1e3a5f; color: white; padding: 6px 10px; text-align: left; }}
    td {{ border: 1px solid #d1d5db; padding: 6px 10px; }}
    tr:nth-child(even) {{ background: #f9fafb; }}
    a {{ color: #1e40af; }}
    </style></head><body>
    {html_body}
    </body></html>"""
    buffer = io.BytesIO()
    pisa.CreatePDF(html, dest=buffer, encoding="utf-8")
    return buffer.getvalue()

def send_pdf_to_slack(pdf_bytes: bytes, filename: str) -> bool:
    token = os.getenv("SLACK_BOT_TOKEN", "")
    channel = os.getenv("SLACK_CHANNEL_ID", "")
    if not token or not channel:
        return False
    try:
        response = httpx.post(
            "https://slack.com/api/files.upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"channels": channel, "title": filename.replace(".pdf", "")},
            files={"file": (filename, pdf_bytes, "application/pdf")},
            timeout=30,
        )
        return response.json().get("ok", False)
    except Exception:
        return False

# --------------------
# |      MODES       |
# --------------------

MODES = {
    "Due Diligence": {
        "icon": ":material/policy:",
        "caption": "Risk assessment for M&A, investment, or partnerships",
    },
    "Competitor Intel": {
        "icon": ":material/radar:",
        "caption": "Competitive landscape, positioning, and recent moves",
    },
    "Vendor Evaluation": {
        "icon": ":material/compare_arrows:",
        "caption": "Tool/vendor comparison before a procurement decision",
    },
    "Sales Intel": {
        "icon": ":material/handshake:",
        "caption": "Account research before a prospect meeting",
    },
}

def _url_hint(url: str, label: str = "company") -> str:
    return f"The official website for this {label} is {url} — use it to confirm the correct entity before searching."

def build_query(mode: str, fields: dict) -> str:
    if mode == "Due Diligence":
        lines = [
            f"Due diligence research on {fields['company']} operating in the {fields['sector']} sector.",
            f"Context: {fields['deal_type']} evaluation.",
        ]
        if fields.get("company_url"):
            lines.append(_url_hint(fields["company_url"]))
        if fields.get("focus"):
            lines.append(f"Additional focus: {fields['focus']}.")
        lines.append(
            "Deliverables: risk assessment, financial signals, reputation and legal flags, "
            "leadership background, and any red flags relevant to the deal type."
        )

    elif mode == "Competitor Intel":
        lines = [
            f"Competitive intelligence: analyze {fields['competitor']} as a competitor to {fields['our_company']} in the {fields['sector']} market.",
            f"Dimensions to cover: {fields['dimensions']}.",
        ]
        if fields.get("competitor_url"):
            lines.append(_url_hint(fields["competitor_url"], label="competitor"))
        if fields.get("focus"):
            lines.append(f"Additional focus: {fields['focus']}.")
        lines.append(
            "Deliverables: product and feature comparison, pricing signals, go-to-market differences, "
            "recent moves and announcements, and identifiable weaknesses."
        )

    elif mode == "Vendor Evaluation":
        lines = [
            f"Vendor evaluation for {fields['category']}.",
            f"Our current stack: {fields['stack']}.",
            f"Priority criteria: {fields['criteria']}.",
        ]
        if fields.get("focus"):
            lines.append(f"Additional focus: {fields['focus']}.")
        lines.append(
            "Deliverables: top vendor comparison with trade-offs, integration complexity with the described stack, "
            "pricing model, and real-world adoption signals."
        )

    elif mode == "Sales Intel":
        lines = [
            f"Sales intelligence on {fields['target_company']} ahead of a meeting to present {fields['our_product']}.",
            f"Meeting objective: {fields['objective']}.",
        ]
        if fields.get("target_url"):
            lines.append(_url_hint(fields["target_url"], label="target company"))
        if fields.get("focus"):
            lines.append(f"Additional focus: {fields['focus']}.")
        lines.append(
            "Deliverables: company overview, likely pain points, current tech stack signals, "
            "recent news and triggers, and key decision-maker profiles."
        )

    else:
        return ""

    return " ".join(lines)

# --------------------
# |      INPUT       |
# --------------------

mode = st.radio(
    "Mode",
    options=list(MODES.keys()),
    horizontal=True,
    label_visibility="collapsed",
)

st.caption(MODES[mode]["caption"])
st.divider()

fields: dict = {}

if mode == "Due Diligence":
    col1, col2 = st.columns(2)
    with col1:
        fields["company"] = st.text_input("Company", placeholder="e.g. Acme Corp")
        fields["sector"] = st.text_input("Sector", placeholder="e.g. B2B SaaS, Fintech")
    with col2:
        fields["deal_type"] = st.selectbox(
            "Deal type",
            ["M&A", "Investment", "Partnership", "Vendor contract"],
        )
        fields["focus"] = st.text_input("Additional focus (optional)", placeholder="e.g. ESG exposure, leadership track record")
    fields["company_url"] = st.text_input("Company website (optional)", placeholder="e.g. https://acmecorp.com", help="Anchors the research to the correct entity and prevents ambiguity.")

elif mode == "Competitor Intel":
    col1, col2 = st.columns(2)
    with col1:
        fields["our_company"] = st.text_input("Your company / product", placeholder="e.g. Contoso")
        fields["competitor"] = st.text_input("Competitor", placeholder="e.g. Fabrikam")
    with col2:
        fields["sector"] = st.text_input("Market / sector", placeholder="e.g. HR Tech, Cloud ERP")
        fields["dimensions"] = st.text_input(
            "Dimensions to compare",
            placeholder="e.g. pricing, product, go-to-market",
            value="product, pricing, go-to-market, recent moves",
        )
    col_url, col_focus = st.columns(2)
    with col_url:
        fields["competitor_url"] = st.text_input("Competitor website (optional)", placeholder="e.g. https://fabrikam.com", help="Anchors the research to the correct entity and prevents ambiguity.")
    with col_focus:
        fields["focus"] = st.text_input("Additional focus (optional)", placeholder="e.g. enterprise segment only")

elif mode == "Vendor Evaluation":
    col1, col2 = st.columns(2)
    with col1:
        fields["category"] = st.text_input("Tool / category", placeholder="e.g. Data orchestration, Observability")
        fields["stack"] = st.text_input("Current stack", placeholder="e.g. Python, dbt, Snowflake, AWS")
    with col2:
        fields["criteria"] = st.text_input(
            "Priority criteria",
            placeholder="e.g. open-source, scalability, cost",
            value="scalability, integration, cost, community",
        )
        fields["focus"] = st.text_input("Additional focus (optional)", placeholder="e.g. self-hosted only")

elif mode == "Sales Intel":
    col1, col2 = st.columns(2)
    with col1:
        fields["target_company"] = st.text_input("Target company", placeholder="e.g. Northwind Inc")
        fields["our_product"] = st.text_input("Your product / solution", placeholder="e.g. AI-powered analytics platform")
    with col2:
        fields["objective"] = st.selectbox(
            "Meeting objective",
            ["Initial discovery", "Demo / proof of concept", "Negotiation / closing", "Expansion / upsell"],
        )
        fields["focus"] = st.text_input("Additional focus (optional)", placeholder="e.g. focus on the CFO's priorities")
    fields["target_url"] = st.text_input("Company website (optional)", placeholder="e.g. https://northwind.com", help="Anchors the research to the correct entity and prevents ambiguity.")

OPTIONAL_FIELDS = {"focus", "company_url", "competitor_url", "target_url"}
required_filled = all(v for k, v in fields.items() if k not in OPTIONAL_FIELDS)
query = build_query(mode, fields) if required_filled else ""

search_btn = st.button("Run", icon=MODES[mode]["icon"], type="primary", disabled=not required_filled)

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

    with col_report:
        st.subheader("Report")
        report_placeholder = st.empty()

    RENDER_EVERY = 15
    token_buffer = ""
    had_tool_calls = False

    STATUS_LABELS = {
        "task": "Delegating to research agent...",
        "tavily_search": "Searching the web...",
        "think_tool": "Assessing findings...",
        "write_file": "Writing report...",
        "edit_file": "Writing report...",
    }

    with col_activity:
        st.subheader("Agent Activity")
        with st.spinner(""):
            status_placeholder = st.empty()
            activity_placeholder = st.empty()
            status_placeholder.markdown("_Planning research..._")

            def render_activity():
                lines = [format_activity_item(t, i, d) for t, i, d in st.session_state.activity_items]
                activity_placeholder.markdown("\n\n".join(lines) if lines else "")

            try:
                for event_type, data in stream_events(query):
                    if event_type == "error":
                        status_placeholder.markdown("_Error_")
                        st.error(f"Agent error: {data.get('message', 'Unknown error')}")
                        break

                    elif event_type == "tool_call":
                        had_tool_calls = True
                        tool = data.get("tool", "")
                        inp = data.get("input", {})
                        st.session_state.activity_items.append((tool, inp, False))
                        if tool in STATUS_LABELS:
                            status_placeholder.markdown(f"_{STATUS_LABELS[tool]}_")
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
                                status_placeholder.markdown("_Answering from existing knowledge..._")
                            st.session_state.report_content += token
                            token_buffer += token
                            if len(token_buffer) >= RENDER_EVERY:
                                report_placeholder.markdown(fix_latex(st.session_state.report_content))
                                token_buffer = ""

                    elif event_type == "done":
                        if token_buffer:
                            report_placeholder.markdown(fix_latex(st.session_state.report_content))
                        status_placeholder.empty()
                        render_activity()

            except Exception as e:
                status_placeholder.markdown("_Error_")
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

    title_match = re.search(r'^#\s+(.+)$', report_content, re.MULTILINE)
    report_title = title_match.group(1) if title_match else "Intelligence Report"
    pdf_filename = re.sub(r'[^\w\s-]', '', report_title).strip().replace(' ', '_') + ".pdf"

    with col1:
        pdf_bytes = report_to_pdf(report_content, report_title)
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=pdf_filename,
            mime="application/pdf",
            icon=":material/picture_as_pdf:",
        )

    with col2:
        obs_name = urllib.parse.quote(report_title)
        obsidian_uri = f"obsidian://new?name={obs_name}&content={urllib.parse.quote(report_content)}"
        st.link_button(
            "Edit in Obsidian",
            obsidian_uri,
            icon=":material/edit_note:",
        )

    with col3:
        slack_enabled = bool(os.getenv("SLACK_BOT_TOKEN") and os.getenv("SLACK_CHANNEL_ID"))
        if st.button("Send PDF to Slack", icon=":material/send:", disabled=not slack_enabled):
            if send_pdf_to_slack(pdf_bytes, pdf_filename):
                st.success("PDF sent to Slack.")
            else:
                st.error("Failed to send. Check SLACK_BOT_TOKEN and SLACK_CHANNEL_ID.")
