import logging
from typing import Tuple, List, Dict
from pydantic import BaseModel, Field

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

from tools.base import BaseTool

logger = logging.getLogger(__name__)

class WebSearchInput(BaseModel):
    query: str = Field(..., description="The search query to look up on the web.")
    max_results: int = Field(5, description="The maximum number of search results to return.")

class WebSearchTool(BaseTool):
    """
    Performs a web search using DuckDuckGo to find real-time information from the internet.
    """
    
    def __init__(self, **kwargs):
        pass
        
    @property
    def name(self) -> str:
        return "web_search"
        
    @property
    def description(self) -> str:
        return "Searches the web in real-time to find current information, news, or answer questions."
        
    @property
    def input_schema(self) -> type[BaseModel]:
        return WebSearchInput
        
    @property
    def requires_permission(self) -> bool:
        return False
        
    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        if DDGS is None:
            return ("Error: duckduckgo_search library is not installed. Run `pip install duckduckgo_search`.", self.name)
            
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 5)
        
        try:
            results = []
            # DDGS is synchronous, but we are running in an async context. 
            # For simplicity, we call it directly (it's fast enough) or use asyncio.to_thread in a perfect world.
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(f"Title: {r.get('title')}\nSnippet: {r.get('body')}\nURL: {r.get('href')}\n")
            
            if not results:
                return (f"No results found for '{query}'.", self.name)
                
            formatted_results = "\n---\n".join(results)
            return (f"Web Search Results for '{query}':\n\n{formatted_results}", self.name)
            
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return (f"Error performing web search: {str(e)}", self.name)
