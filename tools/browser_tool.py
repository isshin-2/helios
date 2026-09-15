import json
import logging
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from typing import Dict, Any

logger = logging.getLogger(__name__)

class BrowserTool:
    def __init__(self):
        self.driver = None

    def _init_driver(self):
        if self.driver is not None:
            return
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            logger.error(f"Failed to init browser: {e}")

    def get_page_content(self, url: str) -> str:
        try:
            self._init_driver()
            if not self.driver:
                return "Error: Could not initialize browser."
                
            self.driver.get(url)
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove scripts and styles
            for script in soup(["script", "style"]):
                script.extract()
                
            text = soup.get_text(separator='\n')
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Truncate if too long to save context
            if len(text) > 8000:
                text = text[:8000] + "\n...[truncated]"
                
            return text
        except Exception as e:
            return f"Failed to load {url}: {str(e)}"
            
    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

# For HELIOS tool registry
def execute_browser_tool(arguments: Dict[str, Any]) -> str:
    url = arguments.get("url")
    if not url:
        return "Error: Missing URL."
        
    browser = BrowserTool()
    content = browser.get_page_content(url)
    browser.close()
    return content

