import asyncio
import sys
import io
from playwright.async_api import async_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

async def inspect_rig():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        print("Loading Airi...")
        await page.goto("http://127.0.0.1:8080/?model=airi", timeout=60000)
        await page.wait_for_selector("#canvas-container", state="visible")
        await page.wait_for_timeout(4000)
        
        airi_rig = await page.evaluate("""() => {
            return {
                rSide: rigMetrics.rSide,
                lSide: rigMetrics.lSide,
                L1: rigMetrics.L1,
                L2: rigMetrics.L2,
                reach: rigMetrics.L1 + rigMetrics.L2,
                headPos: rigMetrics.headPos,
                chestPos: rigMetrics.chestPos,
                hipsPos: rigMetrics.hipsPos,
                rShoulderPos: rigMetrics.rShoulderPos,
                lShoulderPos: rigMetrics.lShoulderPos,
                shoulderWidth: rigMetrics.rShoulderPos.distanceTo(rigMetrics.lShoulderPos)
            };
        }""")
        print("Airi Rig:", airi_rig)
        
        await page.screenshot(path="helios-character/airi_idle.png")
        
        print("\nLoading Ren...")
        await page.goto("http://127.0.0.1:8080/?model=twin", timeout=60000)
        await page.wait_for_selector("#canvas-container", state="visible")
        await page.wait_for_timeout(4000)
        
        ren_rig = await page.evaluate("""() => {
            return {
                rSide: rigMetrics.rSide,
                lSide: rigMetrics.lSide,
                L1: rigMetrics.L1,
                L2: rigMetrics.L2,
                reach: rigMetrics.L1 + rigMetrics.L2,
                headPos: rigMetrics.headPos,
                chestPos: rigMetrics.chestPos,
                hipsPos: rigMetrics.hipsPos,
                rShoulderPos: rigMetrics.rShoulderPos,
                lShoulderPos: rigMetrics.lShoulderPos,
                shoulderWidth: rigMetrics.rShoulderPos.distanceTo(rigMetrics.lShoulderPos)
            };
        }""")
        print("Ren Rig:", ren_rig)
        
        # Take screenshot of Ren idle
        await page.screenshot(path="helios-character/ren_idle.png")
        
        # Test pose: tactical_stand_at_ease
        await page.evaluate("""() => {
            window.setPose('tactical_stand_at_ease');
        }""")
        await page.wait_for_timeout(1000)
        await page.screenshot(path="helios-character/ren_at_ease.png")
        
        # Test pose: idle_ren_drone
        await page.evaluate("""() => {
            window.setPose('idle_ren_drone');
        }""")
        await page.wait_for_timeout(1000)
        await page.screenshot(path="helios-character/ren_drone_pose.png")
        
        # Test pose: arms_folded_relaxed
        await page.evaluate("""() => {
            window.setPose('arms_folded_relaxed');
        }""")
        await page.wait_for_timeout(1000)
        await page.screenshot(path="helios-character/ren_folded_arms.png")
        
        await browser.close()
        print("Screenshots taken successfully!")

if __name__ == '__main__':
    asyncio.run(inspect_rig())
