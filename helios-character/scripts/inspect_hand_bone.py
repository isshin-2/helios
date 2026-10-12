import asyncio
from playwright.async_api import async_playwright

async def inspect_hand_bone():
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
            const wpR = new THREE.Vector3();
            const wqR = new THREE.Quaternion();
            const wpL = new THREE.Vector3();
            const wqL = new THREE.Quaternion();
            rHand.getWorldPosition(wpR);
            rHand.getWorldQuaternion(wqR);
            lHand.getWorldPosition(wpL);
            lHand.getWorldQuaternion(wqL);
            const eR = new THREE.Euler().setFromQuaternion(wqR, 'YXZ');
            const eL = new THREE.Euler().setFromQuaternion(wqL, 'YXZ');
            return {
                rPos: [wpR.x, wpR.y, wpR.z],
                rRotEuler: [eR.x, eR.y, eR.z],
                lPos: [wpL.x, wpL.y, wpL.z],
                lRotEuler: [eL.x, eL.y, eL.z]
            };
        }''')
        print('Airi Sword Guard Bone Info:', info)
        await b.close()

if __name__ == '__main__':
    asyncio.run(inspect_hand_bone())
