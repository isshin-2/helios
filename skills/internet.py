import re
from typing import Tuple
from .base import BaseSkill
from duckduckgo_search import DDGS

class InternetSkill(BaseSkill):
    def match(self, prompt: str) -> bool:
        # Since the user requested implicit triggering, the classifier will route
        # internet requests to the tools executor. We will match broadly here
        # or rely on a specific kwarg from the executor if needed.
        # For safety, if it hits this skill through the "internet" route, it will execute.
        return True # The router guarantees it wants internet if it gets here.
        
    async def execute(self, prompt: str, **kwargs) -> Tuple[str, str]:
        """
        Executes a duckduckgo search.
        Extracts the search query from the prompt heuristically.
        """
        # A simple heuristic to extract search query
        query = prompt
        
        # Remove common conversational wrappers if any
        query = re.sub(r"^(search the web for|look up|search for|what is|who is|latest news on)\s+", "", query, flags=re.IGNORECASE)
        
        try:
            with DDGS() as ddgs:
                # Get top 3 results
                results = list(ddgs.text(query, max_results=3))
                
            if not results:
                return ("No search results found.", "internet_search")
                
            formatted_results = "Here are the top web search results:\n\n"
            for i, res in enumerate(results):
                formatted_results += f"{i+1}. **{res.get('title')}**\n{res.get('body')}\n(Source: {res.get('href')})\n\n"
                
            return (formatted_results, "internet_search")
        except Exception as e:
            return (f"Failed to execute internet search: {e}", "internet_search")
