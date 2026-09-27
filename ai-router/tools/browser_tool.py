"""
HELIOS — Browser Tool
Uses Playwright to navigate pages, extract text, and build DOM accessibility trees.
Replaces the old Selenium backend for faster, more stable execution.
"""

import json
import logging
from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field

from tools.base import BaseTool
from security.capabilities import Capability

try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger("helios.tools.browser")

class BrowserToolInput(BaseModel):
    url: str = Field(description="The URL to navigate to.")
    extract_dom: bool = Field(default=False, description="If True, returns an accessibility tree instead of raw text.")

class BrowserTool(BaseTool):
    """Navigates to web pages and extracts content using Playwright."""
    
    @property
    def name(self) -> str:
        return "browser_tool"

    @property
    def description(self) -> str:
        return "Navigate to a URL and extract text content or a DOM accessibility tree."

    @property
    def input_schema(self) -> type[BaseModel]:
        return BrowserToolInput

    @property
    def required_capabilities(self) -> list[Capability]:
        return [Capability.BROWSER_CONTROL, Capability.NETWORK_ACCESS]

    async def execute(self, user_id: int, url: str, extract_dom: bool = False, **kwargs) -> Tuple[str, str]:
        if not PLAYWRIGHT_AVAILABLE:
            return "Error: Playwright is not installed. Run: pip install playwright && playwright install", self.name
            
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Navigate and wait for network idle to ensure JS executes
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
                if extract_dom:
                    # Get basic accessibility snapshot
                    snapshot = await page.accessibility.snapshot()
                    content = json.dumps(snapshot, indent=2)
                else:
                    # Extract visible text using a robust locator
                    content = await page.evaluate("""() => {
                        const text = document.body.innerText;
                        return text;
                    }""")
                    
                await browser.close()
                
                # Truncate if too long (arbitrary safety limit)
                if len(content) > 15000:
                    content = content[:15000] + "\n...[truncated]"
                    
                return content, self.name
        except Exception as e:
            logger.error(f"Browser navigation failed for {url}: {e}")
            return f"Error loading {url}: {e}", self.name
