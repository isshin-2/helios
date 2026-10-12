import asyncio
from playwright.async_api import async_playwright

async def snap_swords():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page(viewport={'width': 1280, 'height': 800})
        
        # Test Airi Guard
        await page.goto('http://127.0.0.1:8080/?model=airi', wait_until='networkidle')
        await page.wait_for_timeout(1500)
        await page.click('button[data-tab="tab-props"]')
        await page.wait_for_timeout(300)
        await page.click('button[data-pose="sword_guard_ready"]')
        await page.wait_for_timeout(1500)
        await page.screenshot(path='viewer/sword_debug_airi_guard.png')

        # Test Airi Flourish
        await page.click('button[data-pose="sword_sheathe_flourish"]')
        await page.wait_for_timeout(1500)
        await page.screenshot(path='viewer/sword_debug_airi_flourish.png')

        # Test Ren Guard
        await page.goto('http://127.0.0.1:8080/?model=twin', wait_until='networkidle')
        await page.wait_for_timeout(1500)
        await page.click('button[data-tab="tab-props"]')
        await page.wait_for_timeout(300)
        await page.click('button[data-pose="sword_guard_ready"]')
        await page.wait_for_timeout(1500)
        await page.screenshot(path='viewer/sword_debug_ren_guard.png')

        # Test Ren Flourish
        await page.click('button[data-pose="sword_sheathe_flourish"]')
        await page.wait_for_timeout(1500)
        await page.screenshot(path='viewer/sword_debug_ren_flourish.png')

        await b.close()
        print('Captured sword debug screenshots successfully!')

if __name__ == '__main__':
    asyncio.run(snap_swords())
