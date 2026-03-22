"""
Corporate Intelligence Operations - Streamlit App

Structure:
- Home: landing page with product overview and intelligence modes
- Intelligence Operations: structured input, real-time agent activity, report export
- Info: architecture diagrams, stack, and performance benchmarks
"""

import streamlit as st
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


def main():
    st.set_page_config(
        page_title="Corporate Intelligence Operations",
        page_icon=":material/network_intelligence:",
        layout="wide",
    )

    pages = [
        st.Page("pages/home.py", title="Home", icon=":material/home:"),
        st.Page("pages/research.py", title="Intelligence Operations", icon=":material/network_intelligence:"),
        st.Page("pages/info.py", title="Info", icon=":material/info:"),
    ]

    page = st.navigation(pages)
    page.run()

    st.sidebar.caption(
        "Built with [deepagents](https://github.com/langchain-ai/deepagents) + LangGraph. "
        "Uses [Space Grotesk](https://fonts.google.com/specimen/Space+Grotesk) "
        "and [Space Mono](https://fonts.google.com/specimen/Space+Mono)."
    )


if __name__ == "__main__":
    main()
