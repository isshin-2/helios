import asyncio
from tools.browser_tool import BrowserTool

async def test_browser():
    tool = BrowserTool()
    print("Executing BrowserTool directly...")
    try:
        content, src = await tool.execute(
            user_id=1, 
            url="https://example.com", 
            extract_dom=False
        )
        print("--- RESULT ---")
        print(content)
        print("--------------")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_browser())
