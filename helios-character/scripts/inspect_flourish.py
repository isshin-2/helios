import asyncio
from playwright.async_api import async_playwright

async def inspect_flourish():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page(viewport={'width': 1280, 'height': 800})
        await page.goto('http://127.0.0.1:8080/?model=airi', wait_until='networkidle')
        await page.wait_for_timeout(2000)

        await page.click('button[data-tab="tab-props"]')
        await page.wait_for_timeout(300)
        await page.click('button[data-pose="sword_sheathe_flourish"]')
        await page.wait_for_timeout(1000)

        info = await page.evaluate('''() => {
            const h = window.currentVrm.humanoid;
            const rHand = h.getNormalizedBoneNode('rightHand');
            const wpR = new THREE.Vector3();
            const wqR = new THREE.Quaternion();
            rHand.getWorldPosition(wpR);
            rHand.getWorldQuaternion(wqR);

            const xR = new THREE.Vector3(1, 0, 0).applyQuaternion(wqR);
            const yR = new THREE.Vector3(0, 1, 0).applyQuaternion(wqR);
            const zR = new THREE.Vector3(0, 0, 1).applyQuaternion(wqR);

            return {
                rPos: [wpR.x, wpR.y, wpR.z],
                rHandAxes: { x: [xR.x, xR.y, xR.z], y: [yR.x, yR.y, yR.z], z: [zR.x, zR.y, zR.z] }
            };
        }''')
        print('Airi Sword Flourish Info:', info)
        await b.close()

if __name__ == '__main__':
    asyncio.run(inspect_flourish())
