import asyncio
from playwright.async_api import async_playwright

async def inspect_ren():
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
        fl_info = await page.evaluate('''() => {
            const h = window.currentVrm.humanoid;
            const rHand = h.getNormalizedBoneNode('rightHand');
            const wp = new THREE.Vector3();
            rHand.getWorldPosition(wp);
            return [wp.x, wp.y, wp.z];
        }''')
        print('Ren Flourish rHand pos:', fl_info)

        # Guard
        await page.click('button[data-pose="sword_guard_ready"]')
        await page.wait_for_timeout(1000)
        gd_info = await page.evaluate('''() => {
            const h = window.currentVrm.humanoid;
            const rHand = h.getNormalizedBoneNode('rightHand');
            const lHand = h.getNormalizedBoneNode('leftHand');
            const wpR = new THREE.Vector3();
            const wpL = new THREE.Vector3();
            rHand.getWorldPosition(wpR);
            lHand.getWorldPosition(wpL);
            return { r: [wpR.x, wpR.y, wpR.z], l: [wpL.x, wpL.y, wpL.z] };
        }''')
        print('Ren Guard Hand positions:', gd_info)
        await b.close()

if __name__ == '__main__':
    asyncio.run(inspect_ren())
