import os
from crewai import Agent, LLM
from typing import Optional
from dotenv import load_dotenv
import litellm

from src.config import ConfigLoader
from src.tools import (
    RAGTool, 
    MemoryTool, 
    ArxivTool, 
    FirecrawlSearchTool
)
from src.rag import RAGPipeline
from src.memory import ZepMemoryLayer

# Configure litellm to retry on rate limits (Groq free tier = 6000 TPM)
litellm.num_retries = 5
litellm.request_timeout = 60
litellm.drop_params = True  # drop unsupported params silently

# Lazy-init: ensure load_dotenv() has run before reading the key
_groq_llm_instance = None

def _get_groq_llm() -> LLM:
    global _groq_llm_instance
    if _groq_llm_instance is None:
        load_dotenv()
        _groq_llm_instance = LLM(
            model="groq/llama-3.1-8b-instant",
            api_key=os.getenv("GROQ_API_KEY"),
        )
    return _groq_llm_instance


class Agents:
    """Class for creating agents from configuration files"""
    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        self.config_loader = config_loader or ConfigLoader()
    
    def create_rag_agent(self, rag_pipeline: RAGPipeline) -> Agent:
        config = self.config_loader.get_agent_config("rag_agent")
        rag_tool = RAGTool(rag_pipeline=rag_pipeline)
        return Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            tools=[rag_tool],
            llm=_get_groq_llm(),
            max_retry_limit=3,
            verbose=config.get("verbose", True)
        )
    
    def create_memory_agent(self, memory_layer: ZepMemoryLayer) -> Agent:
        config = self.config_loader.get_agent_config("memory_agent")
        memory_tool = MemoryTool(memory_layer=memory_layer)
        return Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            tools=[memory_tool],
            llm=_get_groq_llm(),
            max_retry_limit=3,
            verbose=config.get("verbose", True)
        )
    
    def create_web_search_agent(self, firecrawl_api_key: str) -> Agent:
        config = self.config_loader.get_agent_config("web_search_agent")
        web_search_tool = FirecrawlSearchTool(api_key=firecrawl_api_key)
        return Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            tools=[web_search_tool],
            llm=_get_groq_llm(),
            max_retry_limit=3,
            verbose=config.get("verbose", True)
        )
    
    def create_arxiv_agent(self) -> Agent:
        config = self.config_loader.get_agent_config("arxiv_agent")
        arxiv_tool = ArxivTool()
        return Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            tools=[arxiv_tool],
            llm=_get_groq_llm(),
            max_retry_limit=3,
            verbose=config.get("verbose", True)
        )
    
    def create_evaluator_agent(self) -> Agent:
        config = self.config_loader.get_agent_config("evaluator_agent")
        return Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            llm=_get_groq_llm(),
            max_retry_limit=3,
            verbose=config.get("verbose", True)
        )
    
    def create_synthesizer_agent(self) -> Agent:
        config = self.config_loader.get_agent_config("synthesizer_agent")
        return Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            llm=_get_groq_llm(),
            max_retry_limit=3,
            verbose=config.get("verbose", True)
        )