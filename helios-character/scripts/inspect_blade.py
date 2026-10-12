import asyncio
from playwright.async_api import async_playwright

async def inspect_blade_transforms():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page(viewport={'width': 1280, 'height': 800})
        await page.goto('http://127.0.0.1:8080/?model=twin', wait_until='networkidle')
        await page.wait_for_timeout(2000)

        await page.click('button[data-tab="tab-props"]')
        await page.wait_for_timeout(300)

        # Flourish
        await page.click('button[data-pose="sword_sheathe_flourish"]')
        await page.wait_for_timeout(1000)
        fl_blade = await page.evaluate('''() => {
            const h = window.currentVrm.humanoid;
            const rHand = h.getNormalizedBoneNode('rightHand');
            const blade = window.interactiveSceneObjects.bladeGroup;
            const wpHand = new THREE.Vector3();
            rHand.getWorldPosition(wpHand);
            return {
                handPos: [wpHand.x, wpHand.y, wpHand.z],
                bladePos: [blade.position.x, blade.position.y, blade.position.z],
                bladeVisible: blade.visible
            };
        }''')
        print('Ren Flourish Blade vs Hand:', fl_blade)
        await b.close()

if __name__ == '__main__':
    asyncio.run(inspect_blade_transforms())
