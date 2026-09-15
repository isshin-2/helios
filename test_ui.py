import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Log all console messages
        def handle_console(msg):
            print(f"CONSOLE [{msg.type}]: {msg.text}")
        page.on("console", handle_console)
        
        # Log all page errors
        def handle_page_error(err):
            print(f"PAGE ERROR: {err}")
        page.on("pageerror", handle_page_error)
        
        print("Navigating to http://127.0.0.1:8000/...")
        try:
            await page.goto("http://127.0.0.1:8000/")
            await page.wait_for_load_state("networkidle")
            print("Page loaded successfully.")
            
            # Keep it open a bit to let scripts run
            await page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"Failed to load: {e}")
            
        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())
