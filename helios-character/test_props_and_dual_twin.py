import asyncio
import sys
import io
from playwright.async_api import async_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

async def test_props_and_dual_twin():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("Testing High-Rendered Props & Dual-Twin Synergy on http://127.0.0.1:8080...")
        await page.goto("http://127.0.0.1:8080/?model=twin", timeout=60000)
        await page.wait_for_selector("#canvas-container", state="visible")
        await page.wait_for_timeout(3500)

        # 1. Verify Drone Bug Fix: Ensure 0 blue light in drone materials
        drone_colors = await page.evaluate("""() => {
            const objs = window.interactiveSceneObjects;
            if (!objs) return null;
            const toHex = (c) => c ? '#' + c.getHexString() : null;
            return {
                chassisColor: toHex(objs.droneChassisMat?.color),
                edgeColor: toHex(objs.droneEdgeMat?.color),
                eyeColor: toHex(objs.droneEyeMat?.color),
                eyeEmissive: toHex(objs.droneEyeMat?.emissive),
                ring1Color: toHex(objs.droneRingMat1?.color),
                ring2Color: toHex(objs.droneRingMat2?.color),
            };
        }""")
        print("Recon Drone Colors Check:", drone_colors)
        assert drone_colors is not None, "interactiveSceneObjects must exist"
        # Verify no cyan / electric blue in the drone optics or wireframe:
        for key, hex_val in drone_colors.items():
            if hex_val:
                assert not hex_val.lower().startswith('#00e5') and not hex_val.lower().startswith('#00ff') and not hex_val.lower().startswith('#3296'), f"Drone material {key} ({hex_val}) must not have blue light"
        print("  -> PASSED: Drone contains 0 blue lights (tactical amber/carbon only).")

        # 2. Verify High-Rendered Objects (Cyber Deck, Blades, Monocle, Holo-Dice, Datapad)
        objects_check = await page.evaluate("""() => {
            const objs = window.interactiveSceneObjects;
            const mGroup = objs.monocleGroup;
            const hasBoomArmOrBoxes = mGroup ? mGroup.children.some(c => {
                const geoType = c.geometry?.type || '';
                return geoType === 'BoxGeometry' || geoType === 'CylinderGeometry';
            }) : false;

            return {
                hasConsoleGroup: Boolean(objs.consoleGroup),
                hasDckCanvas: Boolean(objs.dckCanvas),
                hasBladeGroup: Boolean(objs.bladeGroup),
                hasMonocleGroup: Boolean(objs.monocleGroup),
                hasButterflyGroup: Boolean(objs.butterflyGroup),
                hasDroneGroup: Boolean(objs.droneGroup),
                hasHoloDiceGroup: Boolean(objs.holoDiceGroup),
                hasDatapadGroup: Boolean(objs.datapadGroup),
                hasPadCanvas: Boolean(objs.padCanvas),
                hasBoomArmOrBoxes
            };
        }""")
        print("High-Rendered Objects Check:", objects_check)
        for obj_name, exists in objects_check.items():
            if obj_name != 'hasBoomArmOrBoxes':
                assert exists, f"Interactive object {obj_name} must be initialized"
        assert not objects_check['hasBoomArmOrBoxes'], "Monocle must have zero black boom mic cylinders or bulky black box meshes"
        print("  -> PASSED: All high-rendered props initialized and monocle clutter-free (0 black lines/squares).")

        # 3. Test Dual Twin Synergy Mode trigger
        dual_res = await page.evaluate("""() => {
            const btnDual = document.getElementById('btn-model-dual');
            if (btnDual) btnDual.click();
            return {
                hasBtn: Boolean(btnDual),
                activeModelId: window.activeModelId || null,
                dualModeActive: Boolean(window.startDualTwinSynergy),
                btnActive: btnDual ? btnDual.classList.contains('active') : false
            };
        }""")
        print("Dual Twin Mode Trigger:", dual_res)
        assert dual_res['hasBtn'], "Button #btn-model-dual must exist"
        assert dual_res['btnActive'], "#btn-model-dual must have active class"

        await page.wait_for_timeout(2500)

        # 4. Test Twin Synergy Poses: twin_synergy_combat and twin_synergy_briefing
        synergy_poses_res = await page.evaluate("""() => {
            const combatBtn = document.querySelector('button[data-pose="twin_synergy_combat"]');
            const briefingBtn = document.querySelector('button[data-pose="twin_synergy_briefing"]');
            if (combatBtn) combatBtn.click();
            const poseAfterCombat = window.getCurrentPose ? window.getCurrentPose() : null;
            if (briefingBtn) briefingBtn.click();
            const poseAfterBriefing = window.getCurrentPose ? window.getCurrentPose() : null;
            return {
                hasCombatBtn: Boolean(combatBtn),
                hasBriefingBtn: Boolean(briefingBtn),
                poseAfterCombat,
                poseAfterBriefing
            };
        }""")
        print("Twin Synergy Poses Check:", synergy_poses_res)
        assert synergy_poses_res['hasCombatBtn'], "Combat stance button must exist"
        assert synergy_poses_res['hasBriefingBtn'], "Briefing stance button must exist"
        assert synergy_poses_res['poseAfterCombat'] == 'twin_synergy_combat', f"Expected twin_synergy_combat, got {synergy_poses_res['poseAfterCombat']}"
        assert synergy_poses_res['poseAfterBriefing'] == 'twin_synergy_briefing', f"Expected twin_synergy_briefing, got {synergy_poses_res['poseAfterBriefing']}"
        print("  -> PASSED: Dual Twin Synergy Poses verified.")

        await browser.close()
        print("\nAll High-Rendered Props and Dual-Twin Synergy features verified 100%!")

if __name__ == '__main__':
    asyncio.run(test_props_and_dual_twin())
