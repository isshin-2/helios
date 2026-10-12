import asyncio
from playwright.async_api import async_playwright

async def inspect_hand_axes():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page(viewport={'width': 1280, 'height': 800})
        await page.goto('http://127.0.0.1:8080/?model=airi', wait_until='networkidle')
        await page.wait_for_timeout(2000)

        await page.click('button[data-tab="tab-props"]')
        await page.wait_for_timeout(300)
        await page.click('button[data-pose="sword_guard_ready"]')
        await page.wait_for_timeout(1000)

        info = await page.evaluate('''() => {
            const h = window.currentVrm.humanoid;
            const rHand = h.getNormalizedBoneNode('rightHand');
            const lHand = h.getNormalizedBoneNode('leftHand');
            const qR = new THREE.Quaternion();
            const qL = new THREE.Quaternion();
            rHand.getWorldQuaternion(qR);
            lHand.getWorldQuaternion(qL);

            const xR = new THREE.Vector3(1, 0, 0).applyQuaternion(qR);
            const yR = new THREE.Vector3(0, 1, 0).applyQuaternion(qR);
            const zR = new THREE.Vector3(0, 0, 1).applyQuaternion(qR);

            const xL = new THREE.Vector3(1, 0, 0).applyQuaternion(qL);
            const yL = new THREE.Vector3(0, 1, 0).applyQuaternion(qL);
            const zL = new THREE.Vector3(0, 0, 1).applyQuaternion(qL);

            return {
                rHandAxes: { x: [xR.x, xR.y, xR.z], y: [yR.x, yR.y, yR.z], z: [zR.x, zR.y, zR.z] },
                lHandAxes: { x: [xL.x, xL.y, xL.z], y: [yL.x, yL.y, yL.z], z: [zL.x, zL.y, zL.z] }
            };
        }''')
        print('Right Hand Axes:', info['rHandAxes'])
        print('Left Hand Axes:', info['lHandAxes'])
        await b.close()

if __name__ == '__main__':
    asyncio.run(inspect_hand_axes())
