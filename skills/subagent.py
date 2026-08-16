import re
import json
from typing import Tuple
from skills.base import BaseSkill
from providers.ollama import OllamaProvider
from config import OLLAMA_HOST, MODEL_CONFIG

class SubAgentSkill(BaseSkill):
    """
    Spawns a 'sub-agent' by making a secondary backend LLM request to research or plan a complex task.
    """
    def __init__(self):
        self.provider = OllamaProvider(host=OLLAMA_HOST)
        
    def match(self, prompt: str) -> bool:
        prompt_lower = prompt.lower()
        patterns = [
            r"research deeply", r"spawn an agent", r"sub-agent", 
            r"analyze thoroughly", r"investigate fully"
        ]
        return any(re.search(pattern, prompt_lower) for pattern in patterns)
        
    async def execute(self, prompt: str, **kwargs) -> Tuple[str, str]:
        # Formulate a prompt for the sub-agent
        sub_prompt = f"You are a specialized sub-agent for HELIOS. Your task is to thoroughly analyze, research, or plan the following request, and return a comprehensive report.\n\nRequest: {prompt}"
        
        try:
            # We use a reasoning or general model for the sub-agent
            model = "deepseek-r1:7b" # Defaulting to deepseek for sub-agent tasks
            
            response = await self.provider.chat(
                model=model,
                messages=[{"role": "user", "content": sub_prompt}],
                options={"num_ctx": 4096},
                stream=False
            )
            
            result = response.get("message", {}).get("content", "Sub-agent failed to generate a response.")
            
            formatted_result = f"🤖 **Sub-Agent Report:**\n\n{result}"
            return (formatted_result, "SubAgentSkill")
            
        except Exception as e:
            return (f"Sub-agent execution failed: {str(e)}", "SubAgentSkill")
