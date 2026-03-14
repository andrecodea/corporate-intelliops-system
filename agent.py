"""Build the agent graph for the Deep Research Assistant"""

# Utils
import os
from datetime import datetime
import logging
from dotenv import load_dotenv
from pathlib import Path

# LLMOps
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import SummarizationMiddleware, ToolRetryMiddleware, FilesystemFileSearchMiddleware
from deepagents import create_deep_agent
from langchain_core.runnables import Runnable 
from tools import tavily_search, extract, crawl, think
from tavily import UsageLimitExceededError

# Data Validation
from pydantic import BaseModel, Field
from dataclasses import dataclass, asdict
from typing import List

load_dotenv()
log = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent

# Loader function
def _load_prompt(filename:str) -> str:
    with open(BASE_DIR / filename, 'r', encoding='utf-8') as file:
        return file.read()

# --------------------
# |   LOAD PROMPTS   |
# --------------------
try:
    RESEARCH_WORKFLOW_INSTRUCTIONS = _load_prompt("research_workflow_instructions.md")
    SUBAGENT_DELEGATION_INSTRUCTIONS = _load_prompt("subagent_delegation_instructions.md")
    CRAWLER_INSTRUCTIONS = _load_prompt("crawler_agent_instructions.md")
    EXTRACTOR_INSTRUCTIONS = _load_prompt("extraction_agent_instructions.md")
    RESEARCHER_INSTRUCTIONS = _load_prompt("research_agent_instructions.md")
    TASK_DESCRIPTION_PREFIX = _load_prompt("task_description_prefix.md")
except FileNotFoundError as e:
    log.error(f"Failed to load prompt: {e}", exc_info=True)
    raise

class AgentConfig(BaseModel):
    model_name: str 
    base_url: str 
    fallback_model: str 
    fallback_url: str 
    max_subagent_iterations: int = Field(default=3, ge=1)
    max_concurrent_research_units: int = Field(default=5, ge=1, le=10)
    recursion_limit: int = Field(default=50, gt=0, le=100)
    summarizer_model: str = Field()

@dataclass
class SubAgent:
    name: str
    description: str
    system_prompt: str
    tools: List

def build_agent() -> Runnable:
    """Initializes deepagent with subagents"""
    try:
        log.info("[AGENT] Initializing Deep Research Agent")
        api_key: str | None = os.getenv("INCEPTION_API_KEY")

        # --------------------
        # |   INIT CONFIGS   |
        # --------------------
        config = AgentConfig(
            model_name = os.getenv("MODEL_NAME", "mercury-2"),
            base_url = os.getenv("BASE_URL", "https://api.inceptionlabs.ai/v1"),
            fallback_model = os.getenv("FALLBACK_MODEL", "gpt-5.2"),
            fallback_url = os.getenv("FALLBACK_BASE_URL", "https://api.openai.com/v1"),
            max_concurrent_research_units = int(os.getenv("MAX_CONCURRENT_RESEARCH_UNITS", 5)),
            max_subagent_iterations = int(os.getenv("MAX_SUBAGENTS_ITERATIONS", 3)),
            summarizer_model = os.getenv("SUMMARIZER_MODEL", "gpt-4.1-mini"),
            recursion_limit = int(os.getenv("RECURSION_LIMIT", 50)),
        )

        # Get current date
        current_date = datetime.now().strftime("%d-%m-%Y")

        # If there's no need for fallback
        model_name = config.model_name
        base_url = config.base_url

        # Fallback to OpenAI
        if not api_key:
            api_key: str | None = os.getenv("OPENAI_API_KEY")
            base_url = config.fallback_url
            model_name = config.fallback_model
            if not api_key:
                raise EnvironmentError("No LLM API key found, please provide either an INCEPTION_API_KEY or OPENAI_API_KEY in the .env file")

        # Init LLM
        llm = init_chat_model(
            model=model_name,
            base_url=base_url,
            api_key=api_key
        )

        # --------------------
        # |  INIT SUBAGENTS  |
        # --------------------
        research_subagent = SubAgent(
            name="research-agent",
            description="Delegate research to the researcher sub-agent. Only give this researcher one topic at a time.",
            system_prompt=RESEARCHER_INSTRUCTIONS.format(date=current_date),
            tools=[research, think]
        )

        extraction_subagent = SubAgent(
            name= "extraction-agent",
            description="Delegate extraction to the single web page extraction sub-agent. Only give this extractor one topic at a time.",
            system_prompt=EXTRACTOR_INSTRUCTIONS.format(date=current_date),
            tools=[extract, think]
        )

        crawling_subagent = SubAgent(
            name="crawling-agent",
            description="Delegate multi web page crawling to the crawling sub-agent. Only give this crawler one topic at a time.",
            system_prompt=CRAWLER_INSTRUCTIONS.format(date=current_date),
            tools=[crawl, think]
        )

        tools: list = [tavily_search, tavily_extract, tavily_crawl, think]
        subagents: list = [asdict(s) for s in [research_subagent, extraction_subagent, crawling_subagent]]
        other_agents: list = [s['name'] for s in subagents]

        INSTRUCTIONS = (
            RESEARCH_WORKFLOW_INSTRUCTIONS
            + "\n\n"
            + "=" * 80
            + "\n\n"
            + "=" * 80
            + TASK_DESCRIPTION_PREFIX
            + "\n\n"
            + SUBAGENT_DELEGATION_INSTRUCTIONS.format(
                max_concurrent_research_units=config.max_concurrent_research_units,
                max_subagent_iterations=config.max_subagent_iterations,
                other_agents=other_agents,
            )
        )

        # --------------------
        # |  INIT DEEPAGENT  |
        # --------------------
        agent_graph = create_deep_agent(
            model=llm,
            tools=tools,
            system_prompt=INSTRUCTIONS,
            subagents=subagents,
            checkpointer=InMemorySaver(),
            middleware=[
                ToolRetryMiddleware(
                    max_retries=3,
                    backoff_factor=2, # waits 2x the time on each retry
                    retry_on=[TimeoutError, ConnectionError, UsageLimitExceededError] # For tavily API errors
                ),

                # Context management middlewares
                SummarizationMiddleware( 
                    model=config.summarizer_model,
                    trigger=("fraction", 0.8),
                    keep=("fraction", 0.8) # removes 20% of context window
                ),
                FilesystemFileSearchMiddleware(
                    root_path="./workspace"
                )
            ]
        )

        log.info(f"[AGENT] Deep Research Agent created with model={model_name}")
        log.info(f"[AGENT] Main tools: {[t.name for t in tools]}")
        return agent_graph.with_config({"recursion_limit": config.recursion_limit})
    except Exception as e:
        log.error(f"build_agent function failed: {e}", exc_info=True)
        raise