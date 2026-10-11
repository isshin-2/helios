import asyncio
import sys
import io
import json
from playwright.async_api import async_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

async def test_adjuster_menu():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("Testing Dedicated Prop & Biomechanical Body Pose Adjuster Menu on http://127.0.0.1:8080...")
        await page.goto("http://127.0.0.1:8080/?model=airi", timeout=60000)
        await page.wait_for_selector("#canvas-container", state="visible")
        await page.wait_for_timeout(3500)

        # 1. Test top studio quick-jump button
        print("1. Testing top studio button #btn-open-adjust-menu...")
        top_btn_res = await page.evaluate("""() => {
            const btn = document.getElementById('btn-open-adjust-menu');
            if (!btn) return { hasBtn: false };
            btn.click();
            const tabPane = document.getElementById('tab-adjust');
            const tabBtn = document.getElementById('tab-btn-adjust');
            return {
                hasBtn: true,
                tabPaneActive: tabPane ? tabPane.classList.contains('active') : false,
                tabBtnActive: tabBtn ? tabBtn.classList.contains('active') : false
            };
        }""")
        print("  Top Studio Button Result:", top_btn_res)
        assert top_btn_res['hasBtn'], "Button #btn-open-adjust-menu must exist"
        assert top_btn_res['tabPaneActive'], "#tab-adjust must become active when clicked"
        assert top_btn_res['tabBtnActive'], "#tab-btn-adjust must have active class"

        # 2. Test sub-tab switching between Prop Tuner and Body Pose Tuner
        print("2. Testing sub-tab switching...")
        subtab_res = await page.evaluate("""() => {
            const btnProps = document.getElementById('subtab-btn-props');
            const btnBody = document.getElementById('subtab-btn-body');
            const paneProps = document.getElementById('adjust-subpane-props');
            const paneBody = document.getElementById('adjust-subpane-body');

            // Default state: props active
            const initPropsActive = paneProps?.classList.contains('active');

            // Click body
            if (btnBody) btnBody.click();
            const afterBodyClick = {
                bodyPaneActive: paneBody?.classList.contains('active'),
                propsPaneActive: paneProps?.classList.contains('active'),
                bodyBtnActive: btnBody?.classList.contains('active')
            };

            // Click back to props
            if (btnProps) btnProps.click();
            const afterPropsClick = {
                bodyPaneActive: paneBody?.classList.contains('active'),
                propsPaneActive: paneProps?.classList.contains('active'),
                propsBtnActive: btnProps?.classList.contains('active')
            };

            return {
                hasBtnProps: Boolean(btnProps),
                hasBtnBody: Boolean(btnBody),
                hasPaneProps: Boolean(paneProps),
                hasPaneBody: Boolean(paneBody),
                initPropsActive,
                afterBodyClick,
                afterPropsClick
            };
        }""")
        print("  Subtab Switch Result:", subtab_res)
        assert subtab_res['hasBtnProps'] and subtab_res['hasBtnBody'], "Subtab buttons must exist"
        assert subtab_res['afterBodyClick']['bodyPaneActive'], "Body pane must become active"
        assert not subtab_res['afterBodyClick']['propsPaneActive'], "Props pane must become inactive"
        assert subtab_res['afterPropsClick']['propsPaneActive'], "Props pane must toggle back to active"

        # 3. Test 3D Prop Tuner functionality
        print("3. Testing 3D Prop Tuner (calibration, sliders, saving)...")
        prop_tuner_res = await page.evaluate("""() => {
            const selectProp = document.getElementById('select-active-prop');
            const sliderZ = document.getElementById('slider-prop-1');
            const sliderX = document.getElementById('slider-prop-2');
            const sliderY = document.getElementById('slider-prop-3');
            const sliderScale = document.getElementById('slider-prop-4');
            const selectPath = document.getElementById('select-prop-path-mode');
            const sliderSpeed = document.getElementById('slider-prop-speed');
            const btnSave = document.getElementById('btn-save-props-calib');

            // Verify reactive auto-apply on prop selection
            if (selectProp) {
                selectProp.value = 'butterfly';
                selectProp.dispatchEvent(new Event('change'));
            }
            const poseAfterButterfly = typeof window.getCurrentPose === 'function' ? window.getCurrentPose() : null;

            // Switch to katana
            if (selectProp) {
                selectProp.value = 'katana';
                selectProp.dispatchEvent(new Event('change'));
            }
            const poseAfterKatana = typeof window.getCurrentPose === 'function' ? window.getCurrentPose() : null;

            // Adjust scale
            if (sliderScale) {
                sliderScale.value = '1.26';
                sliderScale.dispatchEvent(new Event('input'));
            }

            // Switch to drone and change path mode and speed
            if (selectProp) {
                selectProp.value = 'drone';
                selectProp.dispatchEvent(new Event('change'));
            }
            const poseAfterDrone = typeof window.getCurrentPose === 'function' ? window.getCurrentPose() : null;
            if (selectPath) {
                selectPath.value = 'figure8';
                selectPath.dispatchEvent(new Event('change'));
            }
            if (sliderSpeed) {
                sliderSpeed.value = '1.75';
                sliderSpeed.dispatchEvent(new Event('input'));
            }

            const sliderRotX = document.getElementById('slider-prop-rot-x');
            const sliderRotY = document.getElementById('slider-prop-rot-y');
            const sliderRotZ = document.getElementById('slider-prop-rot-z');

            if (sliderRotX) {
                sliderRotX.value = '15';
                sliderRotX.dispatchEvent(new Event('input'));
            }
            if (sliderRotY) {
                sliderRotY.value = '-25';
                sliderRotY.dispatchEvent(new Event('input'));
            }
            if (sliderRotZ) {
                sliderRotZ.value = '45';
                sliderRotZ.dispatchEvent(new Event('input'));
            }

            // Click save
            if (btnSave) btnSave.click();

            const calib = window.propsCalibration || {};
            const storageItem = localStorage.getItem('helios_props_calibration');

            return {
                poseAfterButterfly,
                poseAfterKatana,
                poseAfterDrone,
                katanaScale: calib.katana?.scale,
                dronePath: calib.drone?.pathMode,
                droneSpeed: calib.drone?.speed,
                droneRotX: calib.drone?.rotX,
                droneRotY: calib.drone?.rotY,
                droneRotZ: calib.drone?.rotZ,
                savedInStorage: Boolean(storageItem && storageItem.includes('figure8'))
            };
        }""")
        print("  Prop Tuner Result:", prop_tuner_res)
        assert prop_tuner_res['poseAfterButterfly'] == 'idle_airi_butterfly', f"Expected idle_airi_butterfly, got {prop_tuner_res['poseAfterButterfly']}"
        assert prop_tuner_res['poseAfterKatana'] == 'sword_guard_ready', f"Expected sword_guard_ready, got {prop_tuner_res['poseAfterKatana']}"
        assert prop_tuner_res['poseAfterDrone'] == 'idle_ren_drone', f"Expected idle_ren_drone, got {prop_tuner_res['poseAfterDrone']}"
        assert prop_tuner_res['katanaScale'] == 1.26, f"Expected katana scale 1.26, got {prop_tuner_res['katanaScale']}"
        assert prop_tuner_res['dronePath'] == 'figure8', f"Expected drone path figure8, got {prop_tuner_res['dronePath']}"
        assert prop_tuner_res['droneSpeed'] == 1.75, f"Expected drone speed 1.75, got {prop_tuner_res['droneSpeed']}"
        assert prop_tuner_res['droneRotX'] == 15, f"Expected drone rotX 15, got {prop_tuner_res['droneRotX']}"
        assert prop_tuner_res['droneRotY'] == -25, f"Expected drone rotY -25, got {prop_tuner_res['droneRotY']}"
        assert prop_tuner_res['droneRotZ'] == 45, f"Expected drone rotZ 45, got {prop_tuner_res['droneRotZ']}"
        assert prop_tuner_res['savedInStorage'], "Prop calibration must persist into localStorage"

        # 4. Test Biomechanical Body Pose Tuner
        print("4. Testing Biomechanical Body Pose Tuner...")
        body_tuner_res = await page.evaluate("""() => {
            // Activate Body Subtab
            document.getElementById('subtab-btn-body')?.click();

            const sliderHeadPitch = document.getElementById('slider-body-head-pitch');
            const sliderHeadYaw = document.getElementById('slider-body-head-yaw');
            const sliderSpineLean = document.getElementById('slider-body-spine-lean');
            const sliderCrouch = document.getElementById('slider-body-crouch');
            const sliderRLift = document.getElementById('slider-body-r-lift');
            const sliderLLift = document.getElementById('slider-body-l-lift');
            const sliderStance = document.getElementById('slider-body-stance-width');
            const selectRHand = document.getElementById('select-body-r-hand');

            // Apply adjustments
            if (sliderHeadPitch) {
                sliderHeadPitch.value = '15';
                sliderHeadPitch.dispatchEvent(new Event('input'));
            }
            if (sliderHeadYaw) {
                sliderHeadYaw.value = '-20';
                sliderHeadYaw.dispatchEvent(new Event('input'));
            }
            if (sliderSpineLean) {
                sliderSpineLean.value = '10';
                sliderSpineLean.dispatchEvent(new Event('input'));
            }
            if (sliderCrouch) {
                sliderCrouch.value = '-0.15';
                sliderCrouch.dispatchEvent(new Event('input'));
            }
            if (sliderRLift) {
                sliderRLift.value = '0.36';
                sliderRLift.dispatchEvent(new Event('input'));
            }
            if (sliderLLift) {
                sliderLLift.value = '-0.10';
                sliderLLift.dispatchEvent(new Event('input'));
            }
            if (sliderStance) {
                sliderStance.value = '12';
                sliderStance.dispatchEvent(new Event('input'));
            }
            if (selectRHand) {
                selectRHand.value = 'peace';
                selectRHand.dispatchEvent(new Event('change'));
            }

            // Hand 3D Rotations (Pitch, Yaw, Roll)
            const sliderRHandPitch = document.getElementById('slider-body-r-hand-pitch');
            const sliderRHandYaw = document.getElementById('slider-body-r-hand-yaw');
            const sliderRHandRoll = document.getElementById('slider-body-r-hand-roll');
            const sliderLHandPitch = document.getElementById('slider-body-l-hand-pitch');
            const sliderLHandYaw = document.getElementById('slider-body-l-hand-yaw');
            const sliderLHandRoll = document.getElementById('slider-body-l-hand-roll');

            if (sliderRHandPitch) {
                sliderRHandPitch.value = '25';
                sliderRHandPitch.dispatchEvent(new Event('input'));
            }
            if (sliderRHandYaw) {
                sliderRHandYaw.value = '-30';
                sliderRHandYaw.dispatchEvent(new Event('input'));
            }
            if (sliderRHandRoll) {
                sliderRHandRoll.value = '15';
                sliderRHandRoll.dispatchEvent(new Event('input'));
            }
            if (sliderLHandPitch) {
                sliderLHandPitch.value = '-10';
                sliderLHandPitch.dispatchEvent(new Event('input'));
            }
            if (sliderLHandYaw) {
                sliderLHandYaw.value = '20';
                sliderLHandYaw.dispatchEvent(new Event('input'));
            }
            if (sliderLHandRoll) {
                sliderLHandRoll.value = '-45';
                sliderLHandRoll.dispatchEvent(new Event('input'));
            }

            // Test target avatar switching the VRM
            const selectTarget = document.getElementById('select-body-target');
            let modelAfterRen = null;
            let dualAfterBoth = null;

            if (selectTarget) {
                selectTarget.value = 'ren';
                selectTarget.dispatchEvent(new Event('change'));
                modelAfterRen = window.activeModelId;

                selectTarget.value = 'both';
                selectTarget.dispatchEvent(new Event('change'));
                dualAfterBoth = window.dualTwinModeActive;

                selectTarget.value = 'airi';
                selectTarget.dispatchEvent(new Event('change'));
            }

            const adj = window.activeBodyPoseAdjustments || {};

            return {
                headPitch: adj.headPitch,
                headYaw: adj.headYaw,
                spineLean: adj.spineLean,
                crouch: adj.crouch,
                rArmLift: adj.rArmLift,
                lArmLift: adj.lArmLift,
                stanceWidth: adj.stanceWidth,
                rHandShape: adj.rHandShape,
                rHandPitch: adj.rHandPitch,
                rHandYaw: adj.rHandYaw,
                rHandRoll: adj.rHandRoll,
                lHandPitch: adj.lHandPitch,
                lHandYaw: adj.lHandYaw,
                lHandRoll: adj.lHandRoll,
                modelAfterRen,
                dualAfterBoth,
                modelAfterAiri: window.activeModelId
            };
        }""")
        print("  Body Pose Tuner Result:", body_tuner_res)
        assert body_tuner_res['headPitch'] == 15, "Head pitch must be 15"
        assert body_tuner_res['headYaw'] == -20, "Head yaw must be -20"
        assert body_tuner_res['spineLean'] == 10, "Spine lean must be 10"
        assert body_tuner_res['crouch'] == -0.15, "Crouch depth must be -0.15"
        assert body_tuner_res['rArmLift'] == 0.36, "Right arm lift must be 0.36"
        assert body_tuner_res['rHandShape'] == 'peace', "Right hand shape must be peace"
        assert body_tuner_res['rHandPitch'] == 25, "Right hand pitch must be 25"
        assert body_tuner_res['rHandYaw'] == -30, "Right hand yaw must be -30"
        assert body_tuner_res['rHandRoll'] == 15, "Right hand roll must be 15"
        assert body_tuner_res['lHandPitch'] == -10, "Left hand pitch must be -10"
        assert body_tuner_res['lHandYaw'] == 20, "Left hand yaw must be 20"
        assert body_tuner_res['lHandRoll'] == -45, "Left hand roll must be -45"
        assert body_tuner_res['modelAfterRen'] == 'twin', "Selecting ren must switch avatar model to twin"
        assert body_tuner_res['dualAfterBoth'] == True, "Selecting both must activate dual twin mode"
        assert body_tuner_res['modelAfterAiri'] == 'airi', "Selecting airi must switch avatar model to airi"

        # 5. Test Live Pose Capture & Reset
        print("5. Testing Live Pose Capture and Reset...")
        capture_and_reset_res = await page.evaluate("""() => {
            const btnCapture = document.getElementById('btn-body-capture');
            const btnReset = document.getElementById('btn-body-reset');
            const btnToggle = document.getElementById('btn-body-toggle-apply');

            // Toggle apply OFF and ON
            btnToggle?.click();
            const stateOff = window.activeBodyPoseAdjustments?.enabled;
            btnToggle?.click();
            const stateOn = window.activeBodyPoseAdjustments?.enabled;

            // Capture
            btnCapture?.click();
            const capturedAdj = { ...window.activeBodyPoseAdjustments };

            // Reset
            btnReset?.click();
            const resetAdj = { ...window.activeBodyPoseAdjustments };

            return {
                stateOff,
                stateOn,
                capturedHeadPitch: typeof capturedAdj.headPitch,
                resetHeadPitch: resetAdj.headPitch,
                resetSpineLean: resetAdj.spineLean,
                resetCrouch: resetAdj.crouch,
                resetRHandPitch: resetAdj.rHandPitch,
                resetLHandRoll: resetAdj.lHandRoll
            };
        }""")
        print("  Capture & Reset Result:", capture_and_reset_res)
        assert capture_and_reset_res['stateOff'] == False, "Toggle should turn off"
        assert capture_and_reset_res['stateOn'] == True, "Toggle should turn back on"
        assert capture_and_reset_res['resetHeadPitch'] == 0, "Reset should restore 0"
        assert capture_and_reset_res['resetSpineLean'] == 0, "Reset should restore 0"
        assert capture_and_reset_res['resetCrouch'] == 0, "Reset should restore 0"
        assert capture_and_reset_res['resetRHandPitch'] == 0, "Reset should restore rHandPitch 0"
        assert capture_and_reset_res['resetLHandRoll'] == 0, "Reset should restore lHandRoll 0"

        # 6. Test Zero UI element overlap
        print("6. Testing UI bounding box non-overlap...")
        overlap_res = await page.evaluate("""() => {
            const topUiRect = document.getElementById('top-ui')?.getBoundingClientRect();
            const chatRect = document.getElementById('chat-container')?.getBoundingClientRect();
            const badgeRect = document.getElementById('status-badge')?.getBoundingClientRect();

            const isOverlap = (r1, r2) => {
                if (!r1 || !r2) return false;
                return !(r1.right < r2.left || r1.left > r2.right || r1.bottom < r2.top || r1.top > r2.bottom);
            };

            return {
                overlapSidebarChat: isOverlap(topUiRect, chatRect),
                overlapSidebarBadge: isOverlap(topUiRect, badgeRect),
                topUiHeight: topUiRect ? topUiRect.height : 0
            };
        }""")
        print("  Bounding Box Check:", overlap_res)
        assert not overlap_res['overlapSidebarChat'], "Sidebar and chat bar must not overlap"
        assert not overlap_res['overlapSidebarBadge'], "Sidebar and status badge must not overlap"

        await browser.close()
        print("\nAll dedicated 3D Prop & Body Pose Adjuster Menu features verified 100%!")

if __name__ == '__main__':
    asyncio.run(test_adjuster_menu())
