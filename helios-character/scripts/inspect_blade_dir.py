import asyncio
from playwright.async_api import async_playwright

async def inspect_blade_matrix():
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
            const hilt = blade.children[0];
            const guard = blade.children[1];
            const bladeMesh = blade.children[2];

            const wHilt = new THREE.Vector3();
            const wGuard = new THREE.Vector3();
            const wTip = new THREE.Vector3();

            hilt.getWorldPosition(wHilt);
            guard.getWorldPosition(wGuard);
            bladeMesh.getWorldPosition(wTip);

            const dir = new THREE.Vector3().subVectors(wTip, wGuard).normalize();

            return {
                bladePos: [blade.position.x, blade.position.y, blade.position.z],
                guardPos: [wGuard.x, wGuard.y, wGuard.z],
                bladeDir: [dir.x, dir.y, dir.z],
                quaternion: [blade.quaternion.x, blade.quaternion.y, blade.quaternion.z, blade.quaternion.w]
            };
        }''')
        print('Ren Flourish Blade Direction and Guard Pos:', info)
        await b.close()

if __name__ == '__main__':
    asyncio.run(inspect_blade_matrix())
