import asyncio
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={'width': 1280, 'height': 720})
        
        # Test Airi with console, butterfly, sword guard
        print("Testing Airi...")
        await page.goto('http://127.0.0.1:8080/?model=airi')
        await page.wait_for_timeout(3500)
        
        airi_poses = ['idle_gaming_console', 'idle_airi_butterfly', 'sword_guard_ready']
        for pose in airi_poses:
            await page.evaluate(f'window.setPose("{pose}")')
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f'viewer/test_pose_airi_{pose}.png')
            print(f"Captured Airi {pose}")
            
        # Test Ren with console, tactical drone, sword guard
        print("Testing Ren...")
        await page.goto('http://127.0.0.1:8080/?model=twin')
        await page.wait_for_timeout(3500)
        ren_poses = ['idle_gaming_console', 'idle_ren_drone', 'sword_guard_ready']
        for pose in ren_poses:
            await page.evaluate(f'window.setPose("{pose}")')
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f'viewer/test_pose_ren_{pose}.png')
            print(f"Captured Ren {pose}")
            
        await b.close()
        print("All screenshots captured!")

if __name__ == '__main__':
    asyncio.run(inspect())
