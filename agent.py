"""Build the agent graph for the Deep Research Assistant"""

# Utils
import os
from datetime import datetime
import logging
from dotenv import load_dotenv
from pathlib import Path

# LLMOps
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import ToolRetryMiddleware
from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_core.runnables import Runnable 
from tools import tavily_search, think_tool
from tavily import UsageLimitExceededError

# Data Validation
from pydantic import BaseModel, Field
from langchain_core.language_models import BaseChatModel
from dataclasses import dataclass, asdict

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
    RESEARCH_WORKFLOW_INSTRUCTIONS = _load_prompt("prompts/orchestrator_agent_instructions.md")
    SUBAGENT_DELEGATION_INSTRUCTIONS = _load_prompt("prompts/subagent_delegation_instructions.md")
    RESEARCHER_INSTRUCTIONS = _load_prompt("prompts/research_agent_instructions.md")
    TASK_DESCRIPTION_PREFIX = _load_prompt("prompts/task_description_prefix.md")
except FileNotFoundError as e:
    log.error(f"Failed to load prompt: {e}", exc_info=True)
    raise

# --------------------
# |   INIT CLASSES   |
# --------------------
class LLMConfig(BaseModel):
    model_name: str 
    base_url: str 
    fallback_model: str 
    fallback_url: str 

class AgentConfig(BaseModel):
    max_subagent_iterations: int = Field(default=1, ge=1)
    max_concurrent_research_units: int = Field(default=2, ge=1, le=10)
    recursion_limit: int = Field(default=50, gt=0, le=100)
    current_date: str

@dataclass
class SubAgent():
    name: str
    description: str
    system_prompt: str
    tools: list

# --------------------
# |   INIT CONFIGS   |
# --------------------
llm_config = LLMConfig(
    model_name = os.getenv("MODEL_NAME", "claude-sonnet-4-6"),
    base_url = os.getenv("BASE_URL", "https://api.anthropic.com"),
    fallback_model = os.getenv("FALLBACK_MODEL", "gpt-5.2"),
    fallback_url = os.getenv("FALLBACK_BASE_URL", "https://api.openai.com/v1"),
)

agent_config = AgentConfig(
    max_concurrent_research_units = int(os.getenv("MAX_CONCURRENT_RESEARCH_UNITS", 2)),
    max_subagent_iterations = int(os.getenv("MAX_SUBAGENTS_ITERATIONS", 1)),
    recursion_limit = int(os.getenv("RECURSION_LIMIT", 50)),
    current_date = datetime.now().strftime("%d-%m-%Y")
)

# --------------------
# |     INIT LLM     |
# --------------------
def _init_llm(config: LLMConfig) -> BaseChatModel:
    """Initializes LLM with LLMConfig Pydantic BaseModel and fallback mechanism.
    
    Uses LLMConfig to initialize an LLM model, the config pulls:
        model_name (str): the Large Language Model's name.
        base_url (str): the provider's base URL for inference.
        fallback_model (str): the fallback Large Language Model's name.
        fallback_url (str): the fallback model provider's base URL for inference.

    Returns:
        BaseChatModel: LLM ready for inference.
    """
    log.info("[AGENT] Initializing LLM Configurations...")

    try:
        anthropic_key: str | None = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            log.info(f"[AGENT] LLM initialized: model={config.model_name}")
            return ChatAnthropic(model=config.model_name, api_key=anthropic_key)

        openai_key: str | None = os.getenv("OPENAI_API_KEY")
        if openai_key:
            log.info(f"[AGENT] LLM initialized: model={config.fallback_model} (fallback)")
            return ChatOpenAI(model=config.fallback_model, base_url=config.fallback_url, api_key=openai_key)

        raise EnvironmentError("No LLM API key found, provide ANTHROPIC_API_KEY or OPENAI_API_KEY in .env")
    except Exception as e:
        log.error(f"Failed to initialize LLM: {e}", exc_info=True)
        raise

# --------------------
# |  INIT SUBAGENTS  |
# --------------------
def _init_subagents(config: AgentConfig) -> list[dict]:
    """Initializes Subagents with a Pydantic BaseModel as config.
    
    Uses AgentConfig to initialize a list of subagents, the config pulls:
        current_date (str): today's date and time.

    Returns:
        list[dict]: List of dictionaries containing subagent specifications (name, description, prompt and tools)
    """
    try:
        log.info("[AGENT] Initializing Subagent Configurations...")

        research_subagent = SubAgent(
            name="research-agent",
            description="Delegate research to the researcher sub-agent. Searches the web and fetches full page content when needed. Only give this agent one topic at a time.",
            system_prompt=RESEARCHER_INSTRUCTIONS.format(date=config.current_date),
            tools=[tavily_search, think_tool],
        )

        return [asdict(research_subagent)]
    except Exception as e:
        log.error(f"Failed to initialize subagents: {e}", exc_info=True)
        raise

# ---------------------
# | INIT INSTRUCTIONS |
# ---------------------
def _assemble_instructions(config: AgentConfig, other_agents: list) -> str:
    """Assembles the deepagent's main instructions

    Uses AgentConfig to initialize instructions, the config pulls:
        max_concurrent_research_units (int): max concurrent subagents that can be executed.
        max_subagent_iterations (int): max amount of times a subagent can iterate through a single task.

    Args:
        other_agents (list): list of subagents names.

    Returns:
        str: concatenated prompt with all variables formatted.
    """
    try:
        log.info(f"[AGENT] Initializing instruction configurations...")
        return (
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
    except Exception as e:
        log.error(f"Failed to initialize prompt configurations: {e}", exc_info=True)
        raise

# ---------------------
# | INIT AGENT GRAPH  |
# ---------------------
def build_agent() -> Runnable:
    """Initializes deepagent with subagents"""
    try:
        log.info("[AGENT] Initializing Deep Research Agent...")

        llm = _init_llm(llm_config)
        log.info("[AGENT] LLM initialized successfully")

        tools: list = [tavily_search, think_tool]
        log.info(f"[AGENT] Tools loaded successfully")

        subagents: list = _init_subagents(agent_config)
        log.info(f"[AGENT] Subagents initialized successfully")

        other_agents: list = [s['name'] for s in subagents]

        INSTRUCTIONS = _assemble_instructions(agent_config, other_agents=other_agents)
        log.info(f"[AGENT] Instructions loaded successfully")

        # --------------------
        # |  INIT DEEPAGENT  |
        # --------------------
        workspace_dir = BASE_DIR / "workspace"
        workspace_dir.mkdir(exist_ok=True)
        backend = FilesystemBackend(root_dir=workspace_dir, virtual_mode=True)

        agent_graph = create_deep_agent(
            model=llm,
            tools=tools,
            system_prompt=INSTRUCTIONS,
            subagents=subagents,
            checkpointer=InMemorySaver(),
            backend=backend,
            middleware=[
                ToolRetryMiddleware(
                    max_retries=3,
                    backoff_factor=2, # waits 2x the time on each retry
                    retry_on=(TimeoutError, ConnectionError, UsageLimitExceededError) # For tavily API errors
                ),
            ]
        )

        log.info(f"[AGENT] Main tools: {[t.name for t in tools]}")
        return agent_graph.with_config({"recursion_limit": agent_config.recursion_limit})
    except Exception as e:
        log.error(f"build_agent function failed: {e}", exc_info=True)
        raise