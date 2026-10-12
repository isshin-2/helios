import asyncio
from playwright.async_api import async_playwright

async def inspect_blade_vector():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page(viewport={'width': 1280, 'height': 800})
        await page.goto('http://127.0.0.1:8080/?model=twin', wait_until='networkidle')
        await page.wait_for_timeout(2000)

        await page.click('button[data-tab="tab-props"]')
        await page.wait_for_timeout(300)
        await page.click('button[data-pose="sword_sheathe_flourish"]')
        await page.wait_for_timeout(1000)

        info = await page.evaluate('''() => {
            const blade = window.interactiveSceneObjects.bladeGroup;
            const vUp = new THREE.Vector3(0, 1, 0).applyQuaternion(blade.quaternion);
            const vForward = new THREE.Vector3(0, 0, 1).applyQuaternion(blade.quaternion);
            const vRight = new THREE.Vector3(1, 0, 0).applyQuaternion(blade.quaternion);

            return {
                bladeAxisY: [vUp.x, vUp.y, vUp.z],
                bladeFlatZ: [vForward.x, vForward.y, vForward.z],
                bladeEdgeX: [vRight.x, vRight.y, vRight.z]
            };
        }''')
        print('Ren Flourish Blade Axes in World Space:', info)
        await b.close()

if __name__ == '__main__':
    asyncio.run(inspect_blade_vector())
