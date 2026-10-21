import logging
from typing import Dict, Any, Type
from agents.browser_agent import BrowserAgent
from agents.computer_agent import ComputerAgent

logger = logging.getLogger(__name__)

class AgentManager:
    """
    Registry for execution agents.
    """
    def __init__(self):
        self.agents: Dict[str, Type] = {
            "browsing": BrowserAgent,
            "browser": BrowserAgent,
            "computer": ComputerAgent,
        }

    def get_agent(self, agent_type: str, *args, **kwargs):
        agent_class = self.agents.get(agent_type)
        if agent_class:
            try:
                return agent_class(*args, **kwargs)
            except Exception:
                try:
                    return agent_class()
                except Exception as e:
                    logger.error(f"Failed to instantiate agent {agent_type}: {e}")
                    return None
        return None

    def register_agent(self, agent_type: str, agent_class: Type):
        self.agents[agent_type] = agent_class


agent_manager = AgentManager()
