import re
from typing import Tuple
from skills.base import BaseSkill

try:
    from composio import ComposioToolSet, Action
except ImportError:
    ComposioToolSet = None

class ComposioSkill(BaseSkill):
    """
    Skill for handling third-party integrations (Gmail, Calendar, etc.) via Composio.
    """
    def __init__(self):
        self.toolset = ComposioToolSet() if ComposioToolSet else None
        
    def match(self, prompt: str) -> bool:
        prompt_lower = prompt.lower()
        keywords = ["read my email", "check my email", "check my calendar", "calendar events", "send an email"]
        return any(kw in prompt_lower for kw in keywords)
        
    async def execute(self, prompt: str, **kwargs) -> Tuple[str, str]:
        if not self.toolset:
            return ("Error: composio-core is not installed or configured.", "composio_skill")
            
        prompt_lower = prompt.lower()
        
        # Super basic matching for demonstration
        try:
            if "read my email" in prompt_lower or "check my email" in prompt_lower:
                # Fetch recent emails
                result = self.toolset.execute_action(
                    action=Action.GMAIL_FETCH_EMAILS, 
                    params={}
                )
                return (f"Composio Gmail Result: {result}", "composio_skill")
                
            elif "calendar events" in prompt_lower or "check my calendar" in prompt_lower:
                result = self.toolset.execute_action(
                    action=Action.GOOGLECALENDAR_GET_CURRENT_DATE_AND_TIME, 
                    params={}
                )
                return (f"Composio Calendar Result: {result}", "composio_skill")
                
            return ("Matched Composio intent, but action mapping is not yet fully implemented for this request.", "composio_skill")
            
        except Exception as e:
            return (f"Composio execution failed: {str(e)}\n\nMake sure you have linked the app by running `composio add gmail` in the terminal.", "composio_skill")
