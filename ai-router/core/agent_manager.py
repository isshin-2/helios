import logging
from typing import Dict, Any, Type
from agents.browser_agent import BrowserAgent

logger = logging.getLogger(__name__)

class AgentManager:
    """
    Phase 8: AGENT_MANAGER Implementation.
    Registry for execution agents.
    """
    def __init__(self):
        self.agents: Dict[str, Type] = {
            "browsing": BrowserAgent
        }

    def get_agent(self, agent_type: str):
        agent_class = self.agents.get(agent_type)
        if agent_class:
            return agent_class()
        return None

    def register_agent(self, agent_type: str, agent_class: Type):
        self.agents[agent_type] = agent_class

agent_manager = AgentManager()
