import * as THREE from 'three';
import { createVRMRendererContext } from './vrm/renderer.js';
import { Humanizer } from './vrm/humanizer.js?v=14';
import {
    MIXAMO_TO_VRM_MAP,
    EMOTION_SPEAKING_POSE_POOLS,
    IDLE_OBJECT_AND_WAITING_POSES,
    PROTOCOL_ANIMATION_MAP,
    mapProtocolAnimationToPose,
    isSpecialTrickPose,
    isIdleObjectOrWaitingPose,
    extractMixamoFBXClip,
    AnimationManager,
    NavigationController,
} from './vrm/animation.js?v=16';
import { ExpressionController } from './vrm/expressions.js';
import { AudioLipSync } from './vrm/lip_sync.js?v=15';
import { Live2DRendererAdapter } from './live2d/renderer.js';
import { createFBXHumanoidAdapter } from './vrm/fbx_adapter.js?v=2';
import { RigEditor } from './vrm/rig_editor.js?v=3';

export {
    Humanizer,
    MIXAMO_TO_VRM_MAP,
    IDLE_OBJECT_AND_WAITING_POSES,
    AnimationManager,
    NavigationController,
    AudioLipSync,
    ExpressionController,
    Live2DRendererAdapter,
};

// Global Three.js clock declared at top of module to avoid any Temporal Dead Zone
const clock = new THREE.Clock();

// Status & Activity HUD elements
const statusBadge = document.getElementById('status-badge');
const thoughtBanner = document.getElementById('thought-banner');
const thoughtText = document.getElementById('thought-text');

function updateStatus(msg) {
    if (statusBadge) statusBadge.innerText = msg;
}

function updateActivityBanner(activity) {
    if (!thoughtBanner || !thoughtText) return;
    if (activity && activity.trim().length > 0) {
        thoughtText.innerText = activity;
        thoughtBanner.style.display = 'block';
    } else {
        thoughtBanner.style.display = 'none';
    }
}

// ----------------------------------------------------
// RENDERER CONTEXT SETUP (VRM + Live2D Adapter)
// ----------------------------------------------------
const container = document.getElementById('canvas-container');
const {
    scene,
    camera,
    renderer,
    controls,
    loader,
    fbxLoader,
    VRMUtils,
    gridHelper,
    stateAccentLight,
} = createVRMRendererContext(container);
const live2dAdapter = new Live2DRendererAdapter(container, updateStatus);
const rigEditor = new RigEditor({
    scene,
    camera,
    renderer,
    controls,
    getCurrentVrm: () => currentVrm,
    onStatus: updateStatus,
});
window.rigEditor = rigEditor;
window.camera = camera;
window.controls = controls;

// ----------------------------------------------------
// 3D INTERACTIVE CHARACTER OBJECTS (DISAPPEAR WHEN NOT INTERACTED WITH)
// - Popup: AI Core Menu Widget (650x320 mode-menu with Black Hole SVG + System Access options)
// - Orb: AI Core Black Hole (Event Horizon + -15deg tilted orbital accretion rings + reticle ticks)
// ----------------------------------------------------
function createInteractiveIdleObjects(parentScene) {
    // 1. 3D AI Core Popup Widget (650x320 aspect ratio, projected by left arm & interacted with by right arm)
    const popupGroup = new THREE.Group();
    popupGroup.name = 'HeliosCharacterPopup3D';
    popupGroup.position.set(0.05, 1.15, 0.24);
    popupGroup.rotation.set(-0.04, 0.0, 0.0);
    popupGroup.visible = false;

    const popupCanvas = document.createElement('canvas');
    popupCanvas.width = 1300;
    popupCanvas.height = 640;
    const popupCtx = popupCanvas.getContext('2d');
    const popupTexture = new THREE.CanvasTexture(popupCanvas);
    popupTexture.colorSpace = THREE.SRGBColorSpace;
    popupTexture.needsUpdate = true;

    const panelGeo = new THREE.PlaneGeometry(0.37, 0.182);
    const panelMat = new THREE.MeshBasicMaterial({
        map: popupTexture,
        transparent: true,
        opacity: 0.0,
        side: THREE.DoubleSide,
        depthWrite: false,
    });
    const panelMesh = new THREE.Mesh(panelGeo, panelMat);
    panelMesh.userData.interactiveType = 'popup';
    popupGroup.add(panelMesh);

    // Subtle bordermat kept at 0 opacity since rounded border is rendered on the high-DPI canvas
    const borderEdges = new THREE.EdgesGeometry(panelGeo);
    const borderMat = new THREE.LineBasicMaterial({
        color: 0x2c3038,
        transparent: true,
        opacity: 0.0,
    });
    const borderLines = new THREE.LineSegments(borderEdges, borderMat);
    borderLines.visible = false;
    popupGroup.add(borderLines);

    // Touch ripple ring on the 3D popup surface right where the character's right index finger pokes it
    const ringGeo = new THREE.RingGeometry(0.01, 0.026, 32);
    const ringMat = new THREE.MeshBasicMaterial({
        color: 0x00e5ff,
        transparent: true,
        opacity: 0.0,
        side: THREE.DoubleSide,
        depthWrite: false,
    });
    const touchRing = new THREE.Mesh(ringGeo, ringMat);
    touchRing.position.set(0.08, 0.0, 0.004);
    popupGroup.add(touchRing);

    parentScene.add(popupGroup);

    // 1b. 3D Left-Arm Holographic Projector Emitter & Projection Cone Beam (connects projecting left wrist to the 3D Popup)
    const projectorGroup = new THREE.Group();
    projectorGroup.name = 'HeliosPopupProjector3D';
    projectorGroup.visible = false;

    const emitterRingGeo = new THREE.RingGeometry(0.014, 0.028, 32);
    const projectorEmitterMat = new THREE.MeshBasicMaterial({
        color: 0x00e5ff,
        transparent: true,
        opacity: 0.0,
        side: THREE.DoubleSide,
        depthWrite: false,
    });
    const projectorEmitterRing = new THREE.Mesh(emitterRingGeo, projectorEmitterMat);
    projectorEmitterRing.rotation.x = -Math.PI * 0.5;
    projectorGroup.add(projectorEmitterRing);

    // 5 projection beam rays (left wrist emitter -> 4 popup corners + popup bottom-center)
    const projectorBeamPositions = new Float32Array(10 * 3);
    const projectorBeamGeo = new THREE.BufferGeometry();
    projectorBeamGeo.setAttribute('position', new THREE.BufferAttribute(projectorBeamPositions, 3));
    const projectorBeamMat = new THREE.LineBasicMaterial({
        color: 0x00e5ff,
        transparent: true,
        opacity: 0.0,
    });
    const projectorBeamLines = new THREE.LineSegments(projectorBeamGeo, projectorBeamMat);
    projectorGroup.add(projectorBeamLines);

    parentScene.add(projectorGroup);

    // 2. 3D AI Core Black Hole Orb for the character (matches black-hole-svg, hidden until idle_orb_curious)
    const orbGroup = new THREE.Group();
    orbGroup.name = 'HeliosCharacterOrb3D';
    orbGroup.position.set(0.22, 1.07, 0.23);
    orbGroup.visible = false;

    const orbCanvas = document.createElement('canvas');
    orbCanvas.width = 512;
    orbCanvas.height = 512;
    const orbCtx = orbCanvas.getContext('2d');
    const orbTexture = new THREE.CanvasTexture(orbCanvas);
    orbTexture.colorSpace = THREE.SRGBColorSpace;
    orbTexture.needsUpdate = true;

    // Billboarded Black Hole SVG plane (Event Horizon + -15deg accretion arcs + 4 reticle ticks)
    const coreGeo = new THREE.PlaneGeometry(0.19, 0.19);
    const coreMat = new THREE.MeshBasicMaterial({
        map: orbTexture,
        transparent: true,
        opacity: 0.0,
        side: THREE.DoubleSide,
        depthWrite: false,
    });
    const coreMesh = new THREE.Mesh(coreGeo, coreMat);
    coreMesh.userData.interactiveType = 'orb';
    orbGroup.add(coreMesh);

    // 3D Volumetric Event Horizon sphere (#050507 core-black) at the center of the Black Hole
    const innerGeo = new THREE.SphereGeometry(0.029, 24, 24);
    const innerMat = new THREE.MeshBasicMaterial({
        color: 0x050507,
        transparent: true,
        opacity: 0.0,
    });
    const innerMesh = new THREE.Mesh(innerGeo, innerMat);
    innerMesh.userData.interactiveType = 'orb';
    orbGroup.add(innerMesh);

    // 3D Tilted (-15deg) Accretion Disk Rings around the 3D Event Horizon sphere
    const gyroGeo = new THREE.TorusGeometry(0.068, 0.0014, 12, 64);
    const gyroMat = new THREE.MeshBasicMaterial({
        color: 0x00e5ff,
        transparent: true,
        opacity: 0.0,
    });
    const gyroRing = new THREE.Mesh(gyroGeo, gyroMat);
    gyroRing.rotation.set(Math.PI * 0.42, 0, THREE.MathUtils.degToRad(-15));
    orbGroup.add(gyroRing);

    const gyroGeo2 = new THREE.TorusGeometry(0.082, 0.0011, 12, 64);
    const gyroRing2 = new THREE.Mesh(gyroGeo2, gyroMat);
    gyroRing2.rotation.set(Math.PI * 0.46, 0, THREE.MathUtils.degToRad(-15));
    orbGroup.add(gyroRing2);

    parentScene.add(orbGroup);

    // 3. 3D Viewport Glass Touch Target Ring (hidden until idle_screen_curious)
    const screenRingGroup = new THREE.Group();
    screenRingGroup.name = 'HeliosCharacterGlassTap3D';
    screenRingGroup.position.set(-0.05, 1.22, 0.30);
    screenRingGroup.visible = false;

    const glassOuterGeo = new THREE.RingGeometry(0.022, 0.028, 36);
    const glassRingMat = new THREE.MeshBasicMaterial({
        color: 0x00e5ff,
        transparent: true,
        opacity: 0.0,
        side: THREE.DoubleSide,
        depthWrite: false,
    });
    const glassOuterRing = new THREE.Mesh(glassOuterGeo, glassRingMat);
    screenRingGroup.add(glassOuterRing);

    const glassInnerGeo = new THREE.RingGeometry(0.006, 0.011, 24);
    const glassInnerMat = new THREE.MeshBasicMaterial({
        color: 0xebf0f5,
        transparent: true,
        opacity: 0.0,
        side: THREE.DoubleSide,
        depthWrite: false,
    });
    const glassInnerRing = new THREE.Mesh(glassInnerGeo, glassInnerMat);
    screenRingGroup.add(glassInnerRing);

    parentScene.add(screenRingGroup);

    // 4. 3D Cybernetic Wrist Hologram Projection (hidden until idle_waiting_look)
    const wristHudGroup = new THREE.Group();
    wristHudGroup.name = 'HeliosCharacterWristHud3D';
    wristHudGroup.visible = false;
    const wristPlaneGeo = new THREE.PlaneGeometry(0.095, 0.052);
    const wristPlaneMat = new THREE.MeshBasicMaterial({
        color: 0x0d0e12,
        transparent: true,
        opacity: 0.0,
        side: THREE.DoubleSide,
        depthWrite: false,
    });
    const wristPlaneMesh = new THREE.Mesh(wristPlaneGeo, wristPlaneMat);
    wristHudGroup.add(wristPlaneMesh);

    const wristEdges = new THREE.EdgesGeometry(wristPlaneGeo);
    const wristEdgeMat = new THREE.LineBasicMaterial({
        color: 0x00e5ff,
        transparent: true,
        opacity: 0.0,
    });
    const wristBorder = new THREE.LineSegments(wristEdges, wristEdgeMat);
    wristHudGroup.add(wristBorder);
    parentScene.add(wristHudGroup);

    return {
        popupGroup,
        panelMesh,
        panelMat,
        popupCanvas,
        popupCtx,
        popupTexture,
        borderMat,
        touchRing,
        ringMat,
        projectorGroup,
        projectorEmitterRing,
        projectorEmitterMat,
        projectorBeamGeo,
        projectorBeamMat,
        orbGroup,
        orbCanvas,
        orbCtx,
        orbTexture,
        coreMesh,
        coreMat,
        innerMesh,
        innerMat,
        gyroRing,
        gyroRing2,
        gyroMat,
        screenRingGroup,
        glassOuterRing,
        glassInnerRing,
        glassRingMat,
        glassInnerMat,
        wristHudGroup,
        wristPlaneMat,
        wristEdgeMat,
    };
}

const interactiveSceneObjects = createInteractiveIdleObjects(scene);
window.interactiveSceneObjects = interactiveSceneObjects;

// ----------------------------------------------------
// VRM MODEL LOADER & EXACT SKELETON CALIBRATION
// ----------------------------------------------------
let currentVrm = null;
let emissiveMaterials = [];
let humanizer = null;
let animManager = null;
let navController = null;
let audioLipSync = null;
let expressionCtrl = new ExpressionController(null, highlightPresetButton);
let availableExpressions = [];
let baseFacingYaw = Math.PI;
let backflipStartTime = -1;
let voiceMuted = false;
let selectedVoiceId = 'af_heart';

function collectEmissiveMaterials(vrm) {
    const list = [];
    const seen = new Set();
    if (!vrm || !vrm.scene) return list;
    vrm.scene.traverse((obj) => {
        if (!obj.isMesh || !obj.material) return;
        const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
        for (const mat of mats) {
            if (!mat || seen.has(mat)) continue;
            seen.add(mat);
            const hasEmissiveMap = Boolean(
                mat.emissiveMap || mat.uniforms?.emissiveMap?.value
            );
            const hasEmissiveColor = Boolean(
                mat.emissive && (mat.emissive.r > 0.01 || mat.emissive.g > 0.01 || mat.emissive.b > 0.01)
            );
            if (hasEmissiveMap || hasEmissiveColor) {
                list.push({
                    mat,
                    isEye: /eyeiris/i.test(mat.name || ''),
                });
            }
        }
    });
    return list;
}

const rigMetrics = {
    rSide: 1,
    lSide: -1,
    camZ: -1,
    forwardX: -1,
    leftFingerCurlZ: 1,
    rightFingerCurlZ: -1,
    leftThumbOpposeY: 1,
    rightThumbOpposeY: -1,
    leftThumbFlexZ: 1,
    rightThumbFlexZ: -1,
    leftElbowFwdY: -1,
    rightElbowFwdY: 1,
    L1: 0.204,
    L2: 0.193,
    LHand: 0.108,
    headPos: new THREE.Vector3(0, 1.268, 0.023),
    neckPos: new THREE.Vector3(0, 1.202, 0.031),
    chestPos: new THREE.Vector3(0, 0.983, -0.017),
    hipsPos: new THREE.Vector3(0, 0.836, -0.004),
    rShoulderPos: new THREE.Vector3(0.095, 1.167, 0.023),
    lShoulderPos: new THREE.Vector3(-0.095, 1.167, 0.023)
};

const FINGER_NAMES = ['Thumb', 'Index', 'Middle', 'Ring', 'Little'];
const FINGER_SEGMENTS = ['Proximal', 'Intermediate', 'Distal'];

const DEFAULT_VRM_URL = 'models/Helios_Airi.vrm';
const BASE_VRM_URL = 'models/Helios_Airi.vrm';

function disposeCurrentAvatar() {
    if (!currentVrm) return;
    scene.remove(currentVrm.scene);
    if (currentVrm.isFBXModel) {
        currentVrm.scene.traverse((obj) => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) {
                if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose());
                else obj.material.dispose();
            }
        });
    } else {
        try {
            VRMUtils.deepDispose(currentVrm.scene);
        } catch (e) {
            console.warn('VRMUtils.deepDispose fallback:', e);
        }
    }
    currentVrm = null;
    window.currentVrm = null;
}

function loadFBXModel(url, isBlob = false) {
    updateStatus('Loading FBX model... 0%');

    fbxLoader.load(
        url,
        (fbxAsset) => {
            const vrm = createFBXHumanoidAdapter(fbxAsset);

            disposeCurrentAvatar();

            currentVrm = vrm;
            window.currentVrm = vrm;
            scene.add(vrm.scene);

            baseFacingYaw = vrm.scene.rotation.y;

            calibrateSkeletonAndRestPose(vrm);
            emissiveMaterials = collectEmissiveMaterials(vrm);

            humanizer = new Humanizer(vrm, rigMetrics);
            animManager = new AnimationManager(vrm, {
                onPoseChanged: (resolvedName) => {
                    currentPose = resolvedName;
                    highlightPoseButton(resolvedName);
                },
                onBackflipTrigger: () => {
                    backflipStartTime = clock.getElapsedTime();
                },
            });
            navController = new NavigationController(vrm.scene, animManager, baseFacingYaw, {
                onHighlightNav: highlightNavButton,
                onSetPose: setPose,
                onStatus: updateStatus,
                controlsTarget: controls.target,
            });
            audioLipSync = new AudioLipSync(vrm, {
                onFinish: () => {
                    finishSpeakingProcedure();
                },
            });
            audioLipSync.setMuted(voiceMuted);
            availableExpressions = expressionCtrl.setVRM(vrm);

            applyProceduralPose(0, 1.0);
            vrm.humanoid.update();
            vrm.scene.updateMatrixWorld(true);

            readAndRenderPresets(vrm);
            focusOnModel(vrm);
            applyStateVisualTheme(currentState);
            if (rigEditor) rigEditor.attachToModel(vrm);

            updateStatus('HELIOS FBX Character Ready! (Rigged Humanoid with Cel-Shading)');
            console.log('HELIOS Character FBX initialized:', vrm);

            if (isBlob) {
                URL.revokeObjectURL(url);
            }
        },
        (progress) => {
            if (progress.total > 0) {
                const pct = Math.round((progress.loaded / progress.total) * 100);
                updateStatus(`Loading FBX: ${pct}%`);
            }
        },
        (error) => {
            console.error('Failed to load FBX model:', url, error);
            updateStatus('Error loading FBX model: ' + (error?.message || error));
        }
    );
}

function loadVRM(url, isBlob = false) {
    updateStatus('Loading VRM model... 0%');

    loader.load(
        url,
        (gltf) => {
            const vrm = gltf.userData.vrm;

            disposeCurrentAvatar();

            currentVrm = vrm;
            window.currentVrm = vrm;
            scene.add(vrm.scene);

            VRMUtils.rotateVRM0(vrm);
            baseFacingYaw = vrm.scene.rotation.y;

            calibrateSkeletonAndRestPose(vrm);
            emissiveMaterials = collectEmissiveMaterials(vrm);

            humanizer = new Humanizer(vrm, rigMetrics);
            animManager = new AnimationManager(vrm, {
                onPoseChanged: (resolvedName) => {
                    currentPose = resolvedName;
                    highlightPoseButton(resolvedName);
                },
                onBackflipTrigger: () => {
                    backflipStartTime = clock.getElapsedTime();
                },
            });
            navController = new NavigationController(vrm.scene, animManager, baseFacingYaw, {
                onHighlightNav: highlightNavButton,
                onSetPose: setPose,
                onStatus: updateStatus,
                controlsTarget: controls.target,
            });
            audioLipSync = new AudioLipSync(vrm, {
                onFinish: () => {
                    finishSpeakingProcedure();
                },
            });
            audioLipSync.setMuted(voiceMuted);
            availableExpressions = expressionCtrl.setVRM(vrm);

            applyProceduralPose(0, 1.0);
            vrm.humanoid.update();
            vrm.scene.updateMatrixWorld(true);

            readAndRenderPresets(vrm);
            focusOnModel(vrm);
            applyStateVisualTheme(currentState);
            if (rigEditor) rigEditor.attachToModel(vrm);

            updateStatus(
                `HELIOS Character Ready! (${availableExpressions.length} BlendShapes | Modular VRM Addon)`
            );
            console.log('HELIOS Character VRM initialized:', vrm);

            if (isBlob) {
                URL.revokeObjectURL(url);
            }
        },
        (progress) => {
            if (progress.total > 0) {
                const pct = Math.round((progress.loaded / progress.total) * 100);
                updateStatus(`Loading VRM: ${pct}%`);
            }
        },
        (error) => {
            console.error('Failed to load VRM:', url, error);
            if (!isBlob && url !== BASE_VRM_URL) {
                console.warn('Falling back to base VRM model:', BASE_VRM_URL);
                loadVRM(BASE_VRM_URL, false);
                return;
            }
            updateStatus('Error loading VRM: ' + (error?.message || error));
        }
    );
}

function getRigSpacePos(bone, rootBone, outVec = new THREE.Vector3()) {
    if (!bone || !rootBone) return outVec;
    rootBone.updateWorldMatrix(true, true);
    bone.getWorldPosition(outVec);
    return rootBone.worldToLocal(outVec);
}

function calibrateSkeletonAndRestPose(vrm) {
    if (!vrm || !vrm.humanoid) return;
    const h = vrm.humanoid;

    const hips = h.getNormalizedBoneNode('hips');
    if (hips) {
        hips.traverse(obj => obj.quaternion.identity());
        hips.updateWorldMatrix(true, true);
    }
    vrm.humanoid.update();
    vrm.scene.updateMatrixWorld(true);

    const rootNode = hips ? hips.parent || hips : vrm.scene;

    const head = h.getNormalizedBoneNode('head');
    const neck = h.getNormalizedBoneNode('neck');
    const chest = h.getNormalizedBoneNode('chest');
    const rUpper = h.getNormalizedBoneNode('rightUpperArm');
    const rLower = h.getNormalizedBoneNode('rightLowerArm');
    const rHand = h.getNormalizedBoneNode('rightHand');
    const rIdxDist = h.getNormalizedBoneNode('rightIndexDistal');
    const lUpper = h.getNormalizedBoneNode('leftUpperArm');
    const lIdxProx = h.getNormalizedBoneNode('leftIndexProximal');
    const lIdxDist = h.getNormalizedBoneNode('leftIndexDistal');
    const rIdxProx = h.getNormalizedBoneNode('rightIndexProximal');

    if (head) getRigSpacePos(head, rootNode, rigMetrics.headPos);
    if (neck) getRigSpacePos(neck, rootNode, rigMetrics.neckPos);
    if (chest) getRigSpacePos(chest, rootNode, rigMetrics.chestPos);
    if (hips) getRigSpacePos(hips, rootNode, rigMetrics.hipsPos);
    if (rUpper) getRigSpacePos(rUpper, rootNode, rigMetrics.rShoulderPos);
    if (lUpper) getRigSpacePos(lUpper, rootNode, rigMetrics.lShoulderPos);

    const pElbow = new THREE.Vector3();
    const pWrist = new THREE.Vector3();
    const pTip = new THREE.Vector3();

    if (rUpper && rLower && rHand) {
        getRigSpacePos(rLower, rootNode, pElbow);
        getRigSpacePos(rHand, rootNode, pWrist);
        rigMetrics.L1 = Math.max(0.12, rigMetrics.rShoulderPos.distanceTo(pElbow));
        rigMetrics.L2 = Math.max(0.12, pElbow.distanceTo(pWrist));
        if (rIdxDist) {
            getRigSpacePos(rIdxDist, rootNode, pTip);
            rigMetrics.LHand = Math.max(0.08, pWrist.distanceTo(pTip) + 0.015);
        }
    }

    rigMetrics.rSide = rigMetrics.rShoulderPos.x >= 0 ? 1 : -1;
    rigMetrics.lSide = -rigMetrics.rSide;
    rigMetrics.camZ = -rigMetrics.rSide;

    const p1 = new THREE.Vector3();
    const p2 = new THREE.Vector3();
    if (lIdxProx && lIdxDist) {
        lIdxProx.rotation.set(0, 0, 0.6);
        getRigSpacePos(lIdxProx, rootNode, p1);
        getRigSpacePos(lIdxDist, rootNode, p2);
        rigMetrics.leftFingerCurlZ = (p2.y < p1.y) ? 1 : -1;
        lIdxProx.rotation.set(0, 0, 0);
    }
    if (rIdxProx && rIdxDist) {
        rIdxProx.rotation.set(0, 0, -0.6);
        getRigSpacePos(rIdxProx, rootNode, p1);
        getRigSpacePos(rIdxDist, rootNode, p2);
        rigMetrics.rightFingerCurlZ = (p2.y < p1.y) ? -1 : 1;
        rIdxProx.rotation.set(0, 0, 0);
    }

    // Empirically calibrate thumb opposition (Y) and palmar flexion (Z) across the palm toward the ring finger
    const calibrateThumbSide = (sideName) => {
        const thumbBase =
            h.getNormalizedBoneNode(`${sideName}ThumbMetacarpal`) ||
            h.getNormalizedBoneNode(`${sideName}ThumbProximal`);
        const thumbTip = h.getNormalizedBoneNode(`${sideName}ThumbDistal`);
        const palmTarget =
            h.getNormalizedBoneNode(`${sideName}RingProximal`) ||
            h.getNormalizedBoneNode(`${sideName}MiddleProximal`);
        if (!thumbBase || !thumbTip || !palmTarget) return;
        const pTarget = getRigSpacePos(palmTarget, rootNode, new THREE.Vector3());

        thumbBase.rotation.set(0, 0.55, 0);
        const dYPos = getRigSpacePos(thumbTip, rootNode, p1).distanceTo(pTarget);
        thumbBase.rotation.set(0, -0.55, 0);
        const dYNeg = getRigSpacePos(thumbTip, rootNode, p2).distanceTo(pTarget);
        const opposeY = dYPos < dYNeg ? 1 : -1;

        thumbBase.rotation.set(0, 0, 0.55);
        getRigSpacePos(thumbTip, rootNode, p1);
        const scoreZPos = p1.distanceTo(pTarget) + (p1.y - pTarget.y) * 0.5;
        thumbBase.rotation.set(0, 0, -0.55);
        getRigSpacePos(thumbTip, rootNode, p2);
        const scoreZNeg = p2.distanceTo(pTarget) + (p2.y - pTarget.y) * 0.5;
        const flexZ = scoreZPos < scoreZNeg ? 1 : -1;

        thumbBase.rotation.set(0, 0, 0);
        if (sideName === 'left') {
            rigMetrics.leftThumbOpposeY = opposeY;
            rigMetrics.leftThumbFlexZ = flexZ;
        } else {
            rigMetrics.rightThumbOpposeY = opposeY;
            rigMetrics.rightThumbFlexZ = flexZ;
        }
    };
    calibrateThumbSide('left');
    calibrateThumbSide('right');

    rigMetrics.forwardX = rigMetrics.camZ;
    rigMetrics.rightElbowFwdY = rigMetrics.rSide;
    rigMetrics.leftElbowFwdY = rigMetrics.lSide;
}

// ----------------------------------------------------
// CLOSED-FORM 2-BONE ANALYTIC IK + SHORTEST-PATH QUATERNION SLERP
// ----------------------------------------------------
const _v1 = new THREE.Vector3();
const _v2 = new THREE.Vector3();
const _m4 = new THREE.Matrix4();
const _qUpper = new THREE.Quaternion();
const _qLower = new THREE.Quaternion();
const _qHand = new THREE.Quaternion();
const _qParent = new THREE.Quaternion();
const _qLocal = new THREE.Quaternion();

function slerpShortestPath(boneQuat, targetQuat, alpha) {
    if (boneQuat.dot(targetQuat) < 0) {
        targetQuat.set(-targetQuat.x, -targetQuat.y, -targetQuat.z, -targetQuat.w);
    }
    boneQuat.slerp(targetQuat, alpha);
}

function buildArmSegmentQuaternion(dirVec, palmHint, sideSign, outQuat) {
    const d = _v1.copy(dirVec).normalize();
    const dotPD = palmHint.dot(d);
    const p = _v2.copy(palmHint).addScaledVector(d, -dotPD);
    if (p.lengthSq() < 1e-5) {
        p.set(0, -1, 0).addScaledVector(d, d.y);
    }
    p.normalize();

    const c1x = sideSign * d.x, c1y = sideSign * d.y, c1z = sideSign * d.z;
    const c2x = -p.x, c2y = -p.y, c2z = -p.z;
    const c3x = c1y * c2z - c1z * c2y;
    const c3y = c1z * c2x - c1x * c2z;
    const c3z = c1x * c2y - c1y * c2x;

    _m4.set(
        c1x, c2x, c3x, 0,
        c1y, c2y, c3y, 0,
        c1z, c2z, c3z, 0,
        0,   0,   0,   1
    );
    return outQuat.setFromRotationMatrix(_m4);
}

function solveAndApplyArmIK(humanoid, rootNode, side, wristTarget, poleDir, fingerDir, palmNormal, slerpSpeed) {
    const isRight = side === 'right';
    const sideSign = isRight ? rigMetrics.rSide : rigMetrics.lSide;
    const upperBone = humanoid.getNormalizedBoneNode(isRight ? 'rightUpperArm' : 'leftUpperArm');
    const lowerBone = humanoid.getNormalizedBoneNode(isRight ? 'rightLowerArm' : 'leftLowerArm');
    const handBone = humanoid.getNormalizedBoneNode(isRight ? 'rightHand' : 'leftHand');
    if (!upperBone || !lowerBone || !handBone) return;

    const S = getRigSpacePos(upperBone, rootNode, new THREE.Vector3());
    const L1 = rigMetrics.L1;
    const L2 = rigMetrics.L2;

    const diff = new THREE.Vector3().subVectors(wristTarget, S);
    const rawDist = diff.length() || 0.001;
    const maxReach = (L1 + L2) * 0.992;
    const minReach = Math.abs(L1 - L2) + 0.025;
    const d = THREE.MathUtils.clamp(rawDist, minReach, maxReach);

    const wHat = diff.normalize();
    const W = new THREE.Vector3().copy(S).addScaledVector(wHat, d);

    const pOrtho = new THREE.Vector3().copy(poleDir).addScaledVector(wHat, -poleDir.dot(wHat));
    if (pOrtho.lengthSq() < 1e-5) {
        pOrtho.set(sideSign, -1, 0).addScaledVector(wHat, -wHat.x * sideSign + wHat.y);
    }
    pOrtho.normalize();

    const cosAlpha = THREE.MathUtils.clamp((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d), -1.0, 1.0);
    const sinAlpha = Math.sqrt(Math.max(0.0, 1.0 - cosAlpha * cosAlpha));

    const uDir = new THREE.Vector3()
        .copy(wHat).multiplyScalar(cosAlpha)
        .addScaledVector(pOrtho, sinAlpha)
        .normalize();
    const E = new THREE.Vector3().copy(S).addScaledVector(uDir, L1);
    const lDir = new THREE.Vector3().subVectors(W, E).normalize();

    // Anatomical wrist flexion/extension cone limit: allow up to ~87 deg so the hand can angle inward to tap the front of floating HUD panels
    const effFingerDir = new THREE.Vector3().copy(fingerDir).normalize();
    const wristCos = lDir.dot(effFingerDir);
    const minWristCos = 0.05;
    if (wristCos < minWristCos) {
        const perp = new THREE.Vector3().copy(effFingerDir).addScaledVector(lDir, -wristCos);
        if (perp.lengthSq() > 1e-5) {
            perp.normalize();
            const maxSin = Math.sqrt(1.0 - minWristCos * minWristCos);
            effFingerDir.copy(lDir).multiplyScalar(minWristCos).addScaledVector(perp, maxSin).normalize();
        } else {
            effFingerDir.copy(lDir);
        }
    }

    const upperPalmHint = new THREE.Vector3(0, -0.5, -rigMetrics.camZ * 0.85)
        .lerp(palmNormal, 0.25)
        .normalize();
    const lowerPalmHint = new THREE.Vector3()
        .copy(upperPalmHint)
        .lerp(palmNormal, 0.72)
        .normalize();

    buildArmSegmentQuaternion(uDir, upperPalmHint, sideSign, _qUpper);
    buildArmSegmentQuaternion(lDir, lowerPalmHint, sideSign, _qLower);
    buildArmSegmentQuaternion(effFingerDir, palmNormal, sideSign, _qHand);

    if (_qUpper.dot(_qLower) < 0) _qLower.set(-_qLower.x, -_qLower.y, -_qLower.z, -_qLower.w);
    if (_qLower.dot(_qHand) < 0) _qHand.set(-_qHand.x, -_qHand.y, -_qHand.z, -_qHand.w);

    rootNode.updateWorldMatrix(true, false);
    if (upperBone.parent) {
        upperBone.parent.updateWorldMatrix(true, false);
        upperBone.parent.getWorldQuaternion(_qParent);
        const qRoot = new THREE.Quaternion();
        rootNode.getWorldQuaternion(qRoot);
        _qParent.premultiply(qRoot.invert());
    } else {
        _qParent.identity();
    }

    _qLocal.copy(_qParent).invert().multiply(_qUpper);
    slerpShortestPath(upperBone.quaternion, _qLocal, slerpSpeed);

    _qLocal.copy(_qUpper).invert().multiply(_qLower);
    slerpShortestPath(lowerBone.quaternion, _qLocal, slerpSpeed);

    _qLocal.copy(_qLower).invert().multiply(_qHand);
    slerpShortestPath(handBone.quaternion, _qLocal, slerpSpeed);
}

// ----------------------------------------------------
// 30-BONE HAND & FINGER POSE GENERATOR
// ----------------------------------------------------
const HAND_SHAPES = {
    relaxed:   { curls: [0.18, 0.15, 0.19, 0.23, 0.27], spread: 0.04 },
    open:      { curls: [0.05, 0.02, 0.02, 0.03, 0.05], spread: 0.16 },
    fist:      { curls: [0.78, 0.94, 0.96, 0.98, 1.00], spread: 0.0  },
    peace:     { curls: [0.78, 0.01, 0.01, 0.94, 0.96], spread: 0.22 },
    point:     { curls: [0.72, 0.01, 0.92, 0.95, 0.98], spread: 0.0  },
    chinTouch: { curls: [0.30, 0.03, 0.86, 0.90, 0.94], spread: 0.03 },
    cupped:    { curls: [0.24, 0.28, 0.31, 0.34, 0.37], spread: 0.02 },
    clasped:   { curls: [0.35, 0.42, 0.46, 0.50, 0.54], spread: 0.0  },
    antler:    { curls: [0.04, 0.03, 0.04, 0.06, 0.09], spread: 0.24 },
    salute:    { curls: [0.55, 0.01, 0.01, 0.01, 0.02], spread: 0.0  },
    thumbs_up: { curls: [-0.15, 0.94, 0.96, 0.98, 1.00], spread: 0.0 },
    rock_on:   { curls: [0.68, 0.01, 0.94, 0.96, 0.01], spread: 0.18 }
};

function lerpBoneEuler(bone, tx, ty, tz, speed) {
    if (!bone) return;
    bone.rotation.x = THREE.MathUtils.lerp(bone.rotation.x, tx, speed);
    bone.rotation.y = THREE.MathUtils.lerp(bone.rotation.y, ty, speed);
    bone.rotation.z = THREE.MathUtils.lerp(bone.rotation.z, tz, speed);
}

function applyHandShape(humanoid, side, shapeName, speed, time = 0) {
    const shape = HAND_SHAPES[shapeName] || HAND_SHAPES.relaxed;
    const curlSign = side === 'left' ? rigMetrics.leftFingerCurlZ : rigMetrics.rightFingerCurlZ;
    const thumbOpposeY = side === 'left' ? rigMetrics.leftThumbOpposeY : rigMetrics.rightThumbOpposeY;
    const thumbFlexZ = side === 'left' ? rigMetrics.leftThumbFlexZ : rigMetrics.rightThumbFlexZ;
    const tonusScale = ['fist', 'salute', 'peace', 'point', 'thumbs_up', 'rock_on'].includes(shapeName) ? 0.25 : 1.0;
    const thumbSegments = humanoid.getNormalizedBoneNode(`${side}ThumbMetacarpal`)
        ? ['Metacarpal', 'Proximal', 'Distal']
        : FINGER_SEGMENTS;

    FINGER_NAMES.forEach((finger, fIdx) => {
        const microTonus = humanizer
            ? humanizer.getFingerMicroCurl(side, fIdx, time) * tonusScale
            : 0;
        const minCurl = finger === 'Thumb' ? -0.25 : 0.0;
        const baseCurl = THREE.MathUtils.clamp(shape.curls[fIdx] + microTonus, minCurl, 1.0);
        let spreadAngle = 0;
        if (fIdx >= 1) {
            if (shapeName === 'peace' && (fIdx === 1 || fIdx === 2)) {
                spreadAngle = (fIdx === 1 ? -1 : 1) * shape.spread * curlSign;
            } else {
                spreadAngle = (fIdx - 2.2) * (shape.spread + microTonus * 0.15) * curlSign;
            }
        }

        const segments = finger === 'Thumb' ? thumbSegments : FINGER_SEGMENTS;
        segments.forEach((seg, sIdx) => {
            const bone = humanoid.getNormalizedBoneNode(`${side}${finger}${seg}`);
            if (!bone) return;

            if (finger === 'Thumb') {
                // CMC (Metacarpal) opposes across the palm; MCP (Proximal) and IP (Distal) flex across curled fingers
                const yWeight = sIdx === 0 ? 0.68 : (sIdx === 1 ? 0.85 : 0.72);
                const zWeight = sIdx === 0 ? 0.55 : (sIdx === 1 ? 0.45 : 0.35);
                const tx = 0;
                const ty = thumbOpposeY * baseCurl * yWeight;
                const tz = thumbFlexZ * baseCurl * zWeight;
                lerpBoneEuler(bone, tx, ty, tz, speed);
            } else {
                // Full anatomical MCP (~79 deg), PIP (~87 deg), DIP (~68 deg) flexion at curl=1.0
                const jointWeight = sIdx === 0 ? 1.38 : (sIdx === 1 ? 1.52 : 1.18);
                const tx = 0;
                const ty = (sIdx === 0) ? spreadAngle : 0;
                const tz = curlSign * baseCurl * jointWeight;
                lerpBoneEuler(bone, tx, ty, tz, speed);
            }
        });
    });
}

// ----------------------------------------------------
// REAL-TIME SMOOTH 3D POSE ENGINE (2-BONE IK + BIOMECHANICAL MICRO-FEATURES)
// ----------------------------------------------------
function applyProceduralPose(time, speed) {
    if (!currentVrm || !currentVrm.humanoid) return;
    if (animManager && animManager.usingExternalFBX) return;

    const h = currentVrm.humanoid;
    const hips = h.getNormalizedBoneNode('hips');
    const rootNode = hips ? hips.parent || hips : currentVrm.scene;

    const rSide = rigMetrics.rSide;
    const lSide = rigMetrics.lSide;
    const camZ = rigMetrics.camZ;
    const fwd = rigMetrics.forwardX;
    const S_R = rigMetrics.rShoulderPos;
    const S_L = rigMetrics.lShoulderPos;
    const headP = rigMetrics.headPos;
    const chestP = rigMetrics.chestPos;
    const hipsP = rigMetrics.hipsPos;
    const reach = rigMetrics.L1 + rigMetrics.L2;

    const liveSpeechEnergy = audioLipSync?.currentSpeechEnergy || 0;
    const breathKin = humanizer
        ? humanizer.getBreathingKinematics(time, currentState)
        : {
              spinePitch: Math.sin(time * 1.5) * 0.008 * fwd,
              chestPitch: Math.sin(time * 1.5) * 0.014 * fwd,
              upperChestPitch: Math.sin(time * 1.5) * 0.010 * fwd,
              leftShoulderRoll: 0,
              rightShoulderRoll: 0,
              wristLiftY: 0,
              wristFlareX: 0,
          };
    const microPosture = humanizer
        ? humanizer.getMicroPostureOffsets(time, currentState, liveSpeechEnergy)
        : {
              hipsRoll: 0,
              hipsYaw: 0,
              spinePitch: 0,
              spineYaw: 0,
              spineRoll: 0,
              neckPitch: 0,
              neckYaw: 0,
              neckRoll: 0,
              headPitch: Math.sin(time * 1.1) * 0.01,
              headYaw: Math.cos(time * 0.7) * 0.012,
              headRoll: 0,
          };
    const breath = breathKin.chestPitch;

    let scenePosY = -(microPosture.hipsDrop || 0);
    let hipsRot = [0, microPosture.hipsYaw, microPosture.hipsRoll];
    let spineRot = [
        breathKin.spinePitch + microPosture.spinePitch,
        microPosture.spineYaw,
        microPosture.spineRoll,
    ];
    let chestRot = [breathKin.chestPitch, microPosture.spineYaw * 0.5, microPosture.spineRoll * 0.4];
    let neckRot = [microPosture.neckPitch, microPosture.neckYaw, microPosture.neckRoll];
    let headRot = [microPosture.headPitch, microPosture.headYaw, microPosture.headRoll];
    let lShoulderRot = [0, 0, breathKin.leftShoulderRoll];
    let rShoulderRot = [0, 0, breathKin.rightShoulderRoll];

    let lUpperLegRot = [0, 0, lSide * 0.015 - microPosture.hipsRoll * 0.6];
    let rUpperLegRot = [0, 0, rSide * 0.015 - microPosture.hipsRoll * 0.6];
    let lLowerLegRot = [0, 0, 0];
    let rLowerLegRot = [0, 0, 0];
    let lFootRot = [0, 0, 0];
    let rFootRot = [0, 0, 0];

    let leftHandShape = 'relaxed';
    let rightHandShape = 'relaxed';

    // Default Idle Right & Left Arm IK Targets (with sympathetic respiratory lift & flare)
    let rWrist = new THREE.Vector3(
        S_R.x + rSide * (0.058 + breathKin.wristFlareX),
        S_R.y - reach * 0.93 + breathKin.wristLiftY,
        S_R.z + camZ * 0.04
    );
    let rPole  = new THREE.Vector3(rSide * 0.6, -0.2, -camZ * 0.8);
    let rFDir  = new THREE.Vector3(rSide * 0.12, -0.98, camZ * 0.12);
    let rPalm  = new THREE.Vector3(-rSide * 0.95, -0.15, camZ * 0.25);

    let lWrist = new THREE.Vector3(
        S_L.x + lSide * (0.058 + breathKin.wristFlareX),
        S_L.y - reach * 0.93 + breathKin.wristLiftY,
        S_L.z + camZ * 0.04
    );
    let lPole  = new THREE.Vector3(lSide * 0.6, -0.2, -camZ * 0.8);
    let lFDir  = new THREE.Vector3(lSide * 0.12, -0.98, camZ * 0.12);
    let lPalm  = new THREE.Vector3(-lSide * 0.95, -0.15, camZ * 0.25);

    // ------------------------------------------------
    // 1. DEDICATED LISTENING POSE (listen_pose)
    // ------------------------------------------------
    if (currentPose === 'listen_pose') {
        // Right hand cupped near right ear/cheek listening closely, Left hand resting on hip, leaning slightly forward
        const listenNod = Math.sin(time * 3.2) * 0.035;
        rightHandShape = 'cupped';
        leftHandShape = 'cupped';
        rShoulderRot = [0, 0, rSide * 0.12];
        spineRot = [fwd * 0.06, -rSide * 0.06, 0];
        chestRot = [fwd * 0.04, -rSide * 0.04, 0];
        headRot = [fwd * (0.04 + listenNod), -rSide * 0.10, -rSide * 0.12];

        rWrist.set(
            headP.x + rSide * 0.135,
            headP.y - 0.015,
            headP.z + camZ * 0.095
        );
        rPole.set(rSide * 0.85, -0.25, camZ * 0.55);
        rFDir.set(-rSide * 0.15, 0.97, -camZ * 0.15).normalize();
        rPalm.set(-rSide * 0.35, 0.10, camZ * 0.92).normalize();

        lWrist.set(hipsP.x + lSide * 0.125, hipsP.y + 0.09, hipsP.z + camZ * 0.045);
        lPole.set(lSide * 1.0, 0.1, -camZ * 0.25);
        lFDir.set(-lSide * 0.35, -0.82, camZ * 0.45).normalize();
        lPalm.set(-lSide * 0.85, -0.25, -camZ * 0.45).normalize();

    // ------------------------------------------------
    // 2. DEDICATED EMOTION-BASED SPEAKING POSES
    // ------------------------------------------------
    } else if (currentPose === 'talk_explain') {
        // TALK (EXPLAIN / NEUTRAL): Both open hands gesturing conversationally in front of chest
        const g1 = Math.sin(time * 4.5) * 0.028;
        const g2 = Math.cos(time * 4.5) * 0.028;
        leftHandShape = 'open';
        rightHandShape = 'open';
        spineRot = [fwd * 0.03, Math.sin(time * 2.2) * 0.03, 0];
        headRot = [fwd * 0.02, Math.sin(time * 2.2) * 0.05, rSide * 0.05];

        rWrist.set(S_R.x + rSide * (0.07 + g1), chestP.y + 0.04 + g2, chestP.z + camZ * 0.18);
        rPole.set(rSide * 0.7, -0.65, camZ * 0.35);
        rFDir.set(-rSide * 0.35, 0.55, camZ * 0.75).normalize();
        rPalm.set(-rSide * 0.45, 0.75, camZ * 0.48).normalize();

        lWrist.set(S_L.x + lSide * (0.07 - g1), chestP.y + 0.04 - g2, chestP.z + camZ * 0.18);
        lPole.set(lSide * 0.7, -0.65, camZ * 0.35);
        lFDir.set(-lSide * 0.35, 0.55, camZ * 0.75).normalize();
        lPalm.set(-lSide * 0.45, 0.75, camZ * 0.48).normalize();

    } else if (currentPose === 'talk_excited') {
        // TALK (HAPPY / EXCITED): Upbeat speaking gesture — right hand high & animated, left hand gesturing at chest
        const pulse = Math.sin(time * 5.5) * 0.03;
        scenePosY = Math.abs(Math.sin(time * 5.5)) * 0.018;
        rightHandShape = 'open';
        leftHandShape = 'cupped';
        rShoulderRot = [0, 0, rSide * 0.14];
        spineRot = [fwd * -0.04, rSide * 0.04, rSide * 0.03];
        headRot = [fwd * -0.05, -rSide * 0.05, rSide * 0.09];

        rWrist.set(headP.x + rSide * 0.15, headP.y - 0.03 + pulse, headP.z + camZ * 0.14);
        rPole.set(rSide * 0.85, -0.15, camZ * 0.5);
        rFDir.set(rSide * 0.15, 0.96, camZ * 0.2).normalize();
        rPalm.set(-rSide * 0.25, 0.15, camZ * 0.95).normalize();

        lWrist.set(S_L.x - lSide * 0.02, chestP.y + 0.06 - pulse * 0.5, chestP.z + camZ * 0.16);
        lPole.set(lSide * 0.65, -0.65, camZ * 0.35);
        lFDir.set(-lSide * 0.65, 0.55, camZ * 0.5).normalize();
        lPalm.set(0, 0.65, camZ * 0.75).normalize();

    } else if (currentPose === 'talk_smug') {
        // TALK (SMUG / RELAXED TSUNDERE): Left hand on hip, right hand gesturing sassily in front with index point
        const sassyBeat = Math.sin(time * 5.0) * 0.025;
        rightHandShape = 'point';
        leftHandShape = 'cupped';
        hipsRot = [0, -rSide * 0.05, -rSide * 0.03];
        spineRot = [fwd * -0.05, rSide * 0.05, rSide * 0.03];
        headRot = [fwd * -0.06, -rSide * 0.06, rSide * 0.09];

        rWrist.set(S_R.x + rSide * 0.03, chestP.y + 0.09 + sassyBeat, chestP.z + camZ * 0.18);
        rPole.set(rSide * 0.65, -0.60, camZ * 0.45);
        rFDir.set(-rSide * 0.25, 0.75 + sassyBeat * 2.0, camZ * 0.60).normalize();
        rPalm.set(-rSide * 0.65, 0.25, camZ * 0.70).normalize();

        lWrist.set(hipsP.x + lSide * 0.125, hipsP.y + 0.09, hipsP.z + camZ * 0.045);
        lPole.set(lSide * 1.0, 0.1, -camZ * 0.25);
        lFDir.set(-lSide * 0.35, -0.82, camZ * 0.45).normalize();
        lPalm.set(-lSide * 0.85, -0.25, -camZ * 0.45).normalize();

    } else if (currentPose === 'talk_angry') {
        // TALK (ANGRY / SCOLDING): Leaning forward, left fist clenched near chest, right index finger chopping/pointing emphatically
        const chop = Math.sin(time * 7.0) * 0.032;
        rightHandShape = 'point';
        leftHandShape = 'fist';
        spineRot = [fwd * 0.08, rSide * 0.04, 0];
        chestRot = [fwd * 0.05, 0, 0];
        headRot = [fwd * 0.06, -rSide * 0.04, -rSide * 0.06];

        rWrist.set(S_R.x + rSide * 0.02, chestP.y + 0.11 + chop, chestP.z + camZ * 0.21);
        rPole.set(rSide * 0.75, -0.45, camZ * 0.45);
        rFDir.set(-rSide * 0.15, 0.55 + chop * 2.5, camZ * 0.82).normalize();
        rPalm.set(-rSide * 0.85, 0.15, camZ * 0.50).normalize();

        lWrist.set(S_L.x + lSide * 0.04, chestP.y + 0.08, chestP.z + camZ * 0.15);
        lPole.set(lSide * 0.85, -0.45, camZ * 0.3);
        lFDir.set(-lSide * 0.35, 0.88, camZ * 0.3).normalize();
        lPalm.set(-lSide * 0.45, 0, -camZ * 0.88).normalize();

    } else if (currentPose === 'talk_sad') {
        // TALK (SAD / SORROW): Both hands held gently over heart/chest, shoulders drooped, head tilted down
        leftHandShape = 'clasped';
        rightHandShape = 'clasped';
        lShoulderRot = [0, 0, -lSide * 0.08];
        rShoulderRot = [0, 0, -rSide * 0.08];
        spineRot = [fwd * 0.08, 0, 0];
        headRot = [fwd * 0.14, rSide * 0.10, -rSide * 0.10];

        rWrist.set(rSide * 0.03, chestP.y + 0.05, chestP.z + camZ * 0.14);
        rPole.set(rSide * 0.55, -0.75, camZ * 0.3);
        rFDir.set(-rSide * 0.75, 0.60, camZ * 0.2).normalize();
        rPalm.set(-rSide * 0.4, 0, -camZ * 0.90).normalize();

        lWrist.set(lSide * 0.03, chestP.y + 0.05, chestP.z + camZ * 0.14);
        lPole.set(lSide * 0.55, -0.75, camZ * 0.3);
        lFDir.set(-lSide * 0.75, 0.60, camZ * 0.2).normalize();
        lPalm.set(-lSide * 0.4, 0, -camZ * 0.90).normalize();

    } else if (currentPose === 'talk_surprised') {
        // TALK (SURPRISED): Leaning back slightly, both open hands raised near cheeks
        leftHandShape = 'open';
        rightHandShape = 'open';
        lShoulderRot = [0, 0, lSide * 0.16];
        rShoulderRot = [0, 0, rSide * 0.16];
        spineRot = [fwd * -0.06, 0, 0];
        headRot = [fwd * -0.05, 0, rSide * 0.06];

        rWrist.set(headP.x + rSide * 0.125, headP.y - 0.045, headP.z + camZ * 0.13);
        rPole.set(rSide * 0.75, -0.45, camZ * 0.5);
        rFDir.set(-rSide * 0.15, 0.97, camZ * 0.15).normalize();
        rPalm.set(-rSide * 0.55, 0.1, camZ * 0.82).normalize();

        lWrist.set(headP.x + lSide * 0.125, headP.y - 0.045, headP.z + camZ * 0.13);
        lPole.set(lSide * 0.75, -0.45, camZ * 0.5);
        lFDir.set(-lSide * 0.15, 0.97, camZ * 0.15).normalize();
        lPalm.set(-lSide * 0.55, 0.1, camZ * 0.82).normalize();

    // ------------------------------------------------
    // 3. FULL-BODY LOCOMOTION, TRICKS & IK EMOTES
    // ------------------------------------------------
    } else if (currentPose === 'walk') {
        const wPhase = time * 7.0;
        const lSwing = Math.sin(wPhase);
        const rSwing = Math.sin(wPhase + Math.PI);

        scenePosY = Math.abs(Math.cos(wPhase)) * 0.022;
        hipsRot = [0, lSwing * 0.07, Math.cos(wPhase) * 0.025];
        spineRot = [fwd * 0.03, -lSwing * 0.05, 0];
        chestRot = [fwd * 0.02, -lSwing * 0.05, 0];

        lUpperLegRot = [-fwd * lSwing * 0.45, 0, lSide * 0.015];
        rUpperLegRot = [-fwd * rSwing * 0.45, 0, rSide * 0.015];
        const lKnee = Math.max(0, -lSwing) * 0.68 + 0.06;
        const rKnee = Math.max(0, -rSwing) * 0.68 + 0.06;
        lLowerLegRot = [fwd * lKnee, 0, 0];
        rLowerLegRot = [fwd * rKnee, 0, 0];
        lFootRot = [-fwd * (lKnee * 0.35), 0, 0];
        rFootRot = [-fwd * (rKnee * 0.35), 0, 0];

        rWrist.set(S_R.x + rSide * 0.065, S_R.y - reach * 0.88 + Math.abs(lSwing) * 0.025, S_R.z + camZ * (lSwing * 0.13 + 0.04));
        lWrist.set(S_L.x + lSide * 0.065, S_L.y - reach * 0.88 + Math.abs(rSwing) * 0.025, S_L.z + camZ * (rSwing * 0.13 + 0.04));

    } else if (currentPose === 'backflip') {
        const elapsed = Math.max(0, time - backflipStartTime);
        const dur = 1.35;
        const u = THREE.MathUtils.clamp(elapsed / dur, 0, 1);

        if (u < 0.20) {
            const k = u / 0.20;
            scenePosY = -0.12 * k;
            spineRot = [fwd * 0.30 * k, 0, 0];
            lUpperLegRot = [-fwd * 0.60 * k, 0, lSide * 0.04];
            rUpperLegRot = [-fwd * 0.60 * k, 0, rSide * 0.04];
            lLowerLegRot = [fwd * 1.10 * k, 0, 0];
            rLowerLegRot = [fwd * 1.10 * k, 0, 0];
            rWrist.set(S_R.x + rSide * 0.09, S_R.y - 0.22, S_R.z - camZ * 0.20);
            lWrist.set(S_L.x + lSide * 0.09, S_L.y - 0.22, S_L.z - camZ * 0.20);
        } else if (u < 0.82) {
            const airU = (u - 0.20) / 0.62;
            const arc = 4.0 * airU * (1.0 - airU);
            scenePosY = 0.55 * arc;
            hipsRot = [-fwd * airU * Math.PI * 2.0, 0, 0];
            const tuck = Math.sin(airU * Math.PI);
            lUpperLegRot = [-fwd * 1.10 * tuck, 0, lSide * 0.05];
            rUpperLegRot = [-fwd * 1.10 * tuck, 0, rSide * 0.05];
            lLowerLegRot = [fwd * 1.55 * tuck, 0, 0];
            rLowerLegRot = [fwd * 1.55 * tuck, 0, 0];
            leftHandShape = 'fist';
            rightHandShape = 'fist';
            rWrist.set(S_R.x + rSide * 0.06, chestP.y - 0.06, chestP.z + camZ * 0.18);
            lWrist.set(S_L.x + lSide * 0.06, chestP.y - 0.06, chestP.z + camZ * 0.18);
            rPole.set(rSide * 0.8, -0.3, camZ * 0.4);
            lPole.set(lSide * 0.8, -0.3, camZ * 0.4);
        } else {
            const landU = (u - 0.82) / 0.18;
            const absorb = Math.sin(landU * Math.PI);
            scenePosY = -0.08 * absorb;
            spineRot = [fwd * 0.18 * absorb, 0, 0];
            lUpperLegRot = [-fwd * 0.40 * absorb, 0, lSide * 0.04];
            rUpperLegRot = [-fwd * 0.40 * absorb, 0, rSide * 0.04];
            lLowerLegRot = [fwd * 0.75 * absorb, 0, 0];
            rLowerLegRot = [fwd * 0.75 * absorb, 0, 0];
        }

    } else if (currentPose === 'dance_shikano') {
        const beat = time * 6.5;
        const sway = Math.sin(beat * 0.5);
        const bounce = Math.abs(Math.sin(beat));

        scenePosY = -bounce * 0.045;
        hipsRot = [0, sway * 0.08, sway * 0.06];
        spineRot = [fwd * 0.03, -sway * 0.06, -sway * 0.05];
        headRot = [fwd * (bounce * 0.06 - 0.02), sway * 0.10, sway * 0.14];

        lUpperLegRot = [-fwd * bounce * 0.20, 0, lSide * 0.03];
        rUpperLegRot = [-fwd * bounce * 0.20, 0, rSide * 0.03];
        lLowerLegRot = [fwd * bounce * 0.40, 0, 0];
        rLowerLegRot = [fwd * bounce * 0.40, 0, 0];

        leftHandShape = 'antler';
        rightHandShape = 'antler';
        lShoulderRot = [0, 0, lSide * 0.18];
        rShoulderRot = [0, 0, rSide * 0.18];

        const antlerBob = Math.sin(beat) * 0.03;
        rWrist.set(headP.x + rSide * 0.145, headP.y + 0.055 + antlerBob, headP.z + camZ * 0.05);
        rPole.set(rSide * 0.95, -0.1, camZ * 0.45);
        rFDir.set(rSide * 0.25, 0.96, 0).normalize();
        rPalm.set(0, 0.1, camZ).normalize();

        lWrist.set(headP.x + lSide * 0.145, headP.y + 0.055 - antlerBob, headP.z + camZ * 0.05);
        lPole.set(lSide * 0.95, -0.1, camZ * 0.45);
        lFDir.set(lSide * 0.25, 0.96, 0).normalize();
        lPalm.set(0, 0.1, camZ).normalize();

    } else if (currentPose === 'smug_pose') {
        leftHandShape = 'cupped';
        rightHandShape = 'cupped';
        hipsRot = [0, -rSide * 0.05, -rSide * 0.035];
        spineRot = [fwd * -0.06, rSide * 0.04, rSide * 0.035];
        chestRot = [fwd * -0.04, 0, 0];
        headRot = [fwd * -0.08, -rSide * 0.07, rSide * 0.09];

        rWrist.set(lSide * 0.065, chestP.y + 0.045, chestP.z + camZ * 0.145);
        rPole.set(rSide * 0.65, -0.55, camZ * 0.55);
        rFDir.set(lSide * 0.92, 0.15, -camZ * 0.32).normalize();
        rPalm.set(0, -0.25, -camZ * 0.95).normalize();

        lWrist.set(rSide * 0.065, chestP.y + 0.015, chestP.z + camZ * 0.135);
        lPole.set(lSide * 0.65, -0.55, camZ * 0.55);
        lFDir.set(rSide * 0.92, 0.15, -camZ * 0.32).normalize();
        lPalm.set(0, 0.25, -camZ * 0.95).normalize();

    } else if (currentPose === 'hug_attempt') {
        leftHandShape = 'open';
        rightHandShape = 'open';
        spineRot = [fwd * 0.07, 0, 0];
        chestRot = [fwd * 0.04, 0, 0];
        headRot = [fwd * 0.04, 0, rSide * 0.08];
        lShoulderRot = [0, 0, lSide * 0.12];
        rShoulderRot = [0, 0, rSide * 0.12];

        rWrist.set(S_R.x + rSide * 0.14, chestP.y + 0.10, chestP.z + camZ * 0.24);
        rPole.set(rSide * 0.85, -0.35, camZ * 0.3);
        rFDir.set(-rSide * 0.25, 0.35, camZ * 0.90).normalize();
        rPalm.set(-rSide * 0.75, 0.25, camZ * 0.60).normalize();

        lWrist.set(S_L.x + lSide * 0.14, chestP.y + 0.10, chestP.z + camZ * 0.24);
        lPole.set(lSide * 0.85, -0.35, camZ * 0.3);
        lFDir.set(-lSide * 0.25, 0.35, camZ * 0.90).normalize();
        lPalm.set(-lSide * 0.75, 0.25, camZ * 0.60).normalize();

    } else if (currentPose === 'refuse') {
        const noWave = Math.sin(time * 8.0) * 0.25;
        rightHandShape = 'open';
        leftHandShape = 'cupped';
        spineRot = [fwd * -0.04, -rSide * 0.10, 0];
        headRot = [fwd * 0.04, -rSide * 0.25, -rSide * 0.07];

        rWrist.set(headP.x + rSide * (0.06 + noWave * 0.07), chestP.y + 0.16, chestP.z + camZ * 0.19);
        rPole.set(rSide * 0.65, -0.65, camZ * 0.5);
        rFDir.set(rSide * noWave, 0.96, camZ * 0.1).normalize();
        rPalm.set(0, 0.08, camZ).normalize();

        lWrist.set(hipsP.x + lSide * 0.125, hipsP.y + 0.09, hipsP.z + camZ * 0.045);
        lPole.set(lSide * 1.0, 0.1, -camZ * 0.25);
        lFDir.set(-lSide * 0.35, -0.82, camZ * 0.45).normalize();
        lPalm.set(-lSide * 0.85, -0.25, -camZ * 0.45).normalize();

    } else if (currentPose === 'wave') {
        const waveAngle = Math.sin(time * 8.5) * 0.42;
        rightHandShape = 'open';
        leftHandShape = 'relaxed';
        rShoulderRot = [0, 0, rSide * 0.14];
        headRot = [fwd * -0.04, -rSide * 0.06, rSide * 0.08];
        spineRot = [0, 0, rSide * 0.04];

        rWrist.set(
            S_R.x + rSide * (0.12 + Math.sin(time * 8.5) * 0.045),
            headP.y + 0.03,
            headP.z + camZ * 0.12
        );
        rPole.set(rSide * 0.85, -0.35, camZ * 0.35);
        rFDir.set(rSide * waveAngle, 1.0, camZ * 0.08).normalize();
        rPalm.set(0, 0.05, camZ).normalize();

    } else if (currentPose === 'think_pose') {
        rightHandShape = 'chinTouch';
        leftHandShape = 'cupped';
        headRot = [fwd * 0.08, rSide * 0.10, rSide * 0.12];
        spineRot = [fwd * 0.03, 0, rSide * 0.02];

        const chinPos = new THREE.Vector3(
            headP.x + rSide * 0.012,
            headP.y - 0.032,
            headP.z + camZ * 0.105
        );
        rFDir.set(-rSide * 0.18, 0.95, -camZ * 0.22).normalize();
        rWrist.copy(chinPos).addScaledVector(rFDir, -rigMetrics.LHand);
        rPole.set(rSide * 0.45, -0.55, camZ * 0.75);
        rPalm.set(-rSide * 0.75, 0.05, -camZ * 0.65).normalize();

        lWrist.set(S_R.x - rSide * 0.06, chestP.y + 0.04, chestP.z + camZ * 0.13);
        lPole.set(lSide * 0.6, -0.7, camZ * 0.4);
        lFDir.set(rSide * 0.95, 0.18, camZ * 0.2).normalize();
        lPalm.set(0, 0.92, -camZ * 0.35).normalize();

    } else if (currentPose === 'peace') {
        rightHandShape = 'peace';
        leftHandShape = 'cupped';
        rShoulderRot = [0, 0, rSide * 0.12];
        headRot = [fwd * -0.04, -rSide * 0.06, rSide * 0.11];
        spineRot = [fwd * -0.03, 0, rSide * 0.03];

        rWrist.set(
            headP.x + rSide * 0.155,
            headP.y + 0.01,
            headP.z + camZ * 0.135
        );
        rPole.set(rSide * 0.75, -0.25, camZ * 0.6);
        rFDir.set(-rSide * 0.12, 0.98, 0.0).normalize();
        rPalm.set(0, 0.05, camZ).normalize();

        lWrist.set(hipsP.x + lSide * 0.13, hipsP.y + 0.09, hipsP.z + camZ * 0.05);
        lPole.set(lSide * 1.0, 0.0, -camZ * 0.3);
        lFDir.set(-lSide * 0.3, -0.85, camZ * 0.4).normalize();
        lPalm.set(-lSide * 0.85, -0.2, -camZ * 0.45).normalize();

    } else if (currentPose === 'cheer') {
        const bounce = Math.abs(Math.sin(time * 6.0));
        scenePosY = bounce * 0.03;
        leftHandShape = 'fist';
        rightHandShape = 'fist';
        lShoulderRot = [0, 0, lSide * 0.18];
        rShoulderRot = [0, 0, rSide * 0.18];
        headRot = [fwd * -0.08, 0, Math.sin(time * 6.0) * 0.05];
        spineRot = [fwd * -0.05, 0, 0];

        const pumpY = Math.sin(time * 6.0) * 0.03;
        rWrist.set(headP.x + rSide * 0.18, headP.y + 0.15 + pumpY, headP.z + camZ * 0.08);
        rPole.set(rSide * 0.85, -0.15, camZ * 0.40);
        rFDir.set(-rSide * 0.1, 0.98, camZ * 0.12).normalize();
        rPalm.set(-rSide * 0.25, 0, camZ * 0.96).normalize();

        lWrist.set(headP.x + lSide * 0.18, headP.y + 0.15 + pumpY, headP.z + camZ * 0.08);
        lPole.set(lSide * 0.85, -0.15, camZ * 0.40);
        lFDir.set(-lSide * 0.1, 0.98, camZ * 0.12).normalize();
        lPalm.set(-lSide * 0.25, 0, camZ * 0.96).normalize();

    } else if (currentPose === 'shrug') {
        leftHandShape = 'open';
        rightHandShape = 'open';
        lShoulderRot = [0, 0, lSide * 0.25];
        rShoulderRot = [0, 0, rSide * 0.25];
        headRot = [fwd * -0.05, 0.04, rSide * 0.17];

        rWrist.set(S_R.x + rSide * 0.19, S_R.y + 0.01, S_R.z + camZ * 0.12);
        rPole.set(rSide * 0.25, -1.0, -camZ * 0.2);
        rFDir.set(rSide * 0.65, 0.72, camZ * 0.22).normalize();
        rPalm.set(0, 0.45, camZ * 0.89).normalize();

        lWrist.set(S_L.x + lSide * 0.19, S_L.y + 0.01, S_L.z + camZ * 0.12);
        lPole.set(lSide * 0.25, -1.0, -camZ * 0.2);
        lFDir.set(lSide * 0.65, 0.72, camZ * 0.22).normalize();
        lPalm.set(0, 0.45, camZ * 0.89).normalize();

    } else if (currentPose === 'bow') {
        leftHandShape = 'cupped';
        rightHandShape = 'cupped';
        spineRot = [fwd * 0.36, 0, 0];
        chestRot = [fwd * 0.22, 0, 0];
        headRot = [fwd * 0.16, 0, 0];

        rWrist.set(rSide * 0.035, chestP.y - 0.06, chestP.z + camZ * 0.24);
        rPole.set(rSide * 0.75, -0.60, camZ * 0.25);
        rFDir.set(-rSide * 0.92, 0.18, camZ * 0.32).normalize();
        rPalm.set(0, 0.28, -camZ * 0.96).normalize();

        lWrist.set(lSide * 0.035, chestP.y - 0.06, chestP.z + camZ * 0.24);
        lPole.set(lSide * 0.75, -0.60, camZ * 0.25);
        lFDir.set(-lSide * 0.92, 0.18, camZ * 0.32).normalize();
        lPalm.set(0, 0.28, -camZ * 0.96).normalize();

    } else if (currentPose === 'nod') {
        const nodOsc = Math.sin(time * 7.5) * 0.15;
        leftHandShape = 'clasped';
        rightHandShape = 'clasped';
        headRot = [fwd * (0.08 + nodOsc), 0, 0];
        spineRot = [fwd * 0.04, 0, 0];

        rWrist.set(rSide * 0.03, chestP.y + 0.06, chestP.z + camZ * 0.145);
        rPole.set(rSide * 0.65, -0.65, camZ * 0.3);
        rFDir.set(-rSide * 0.75, 0.60, camZ * 0.2).normalize();
        rPalm.set(-rSide * 0.5, 0, -camZ * 0.85).normalize();

        lWrist.set(lSide * 0.03, chestP.y + 0.06, chestP.z + camZ * 0.145);
        lPole.set(lSide * 0.65, -0.65, camZ * 0.3);
        lFDir.set(-lSide * 0.75, 0.60, camZ * 0.2).normalize();
        lPalm.set(-lSide * 0.5, 0, -camZ * 0.85).normalize();

    } else if (currentPose === 'confident') {
        leftHandShape = 'cupped';
        rightHandShape = 'cupped';
        spineRot = [fwd * -0.06, 0, rSide * 0.03];
        chestRot = [fwd * -0.05, 0, 0];
        headRot = [fwd * -0.04, -rSide * 0.06, -rSide * 0.07];

        rWrist.set(hipsP.x + rSide * 0.125, hipsP.y + 0.09, hipsP.z + camZ * 0.045);
        rPole.set(rSide * 1.0, 0.1, -camZ * 0.25);
        rFDir.set(-rSide * 0.35, -0.82, camZ * 0.45).normalize();
        rPalm.set(-rSide * 0.85, -0.25, -camZ * 0.45).normalize();

        lWrist.set(hipsP.x + lSide * 0.125, hipsP.y + 0.09, hipsP.z + camZ * 0.045);
        lPole.set(lSide * 1.0, 0.1, -camZ * 0.25);
        lFDir.set(-lSide * 0.35, -0.82, camZ * 0.45).normalize();
        lPalm.set(-lSide * 0.85, -0.25, -camZ * 0.45).normalize();

    } else if (currentPose === 'shy') {
        const tapOsc = Math.abs(Math.sin(time * 5.0)) * 0.015;
        leftHandShape = 'point';
        rightHandShape = 'point';
        spineRot = [fwd * 0.07, 0, 0];
        headRot = [fwd * 0.15, rSide * 0.14, -rSide * 0.11];

        const rTipTarget = new THREE.Vector3(rSide * (0.008 + tapOsc), chestP.y + 0.08, chestP.z + camZ * 0.155);
        const lTipTarget = new THREE.Vector3(lSide * (0.008 + tapOsc), chestP.y + 0.08, chestP.z + camZ * 0.155);

        rFDir.set(-rSide * 0.96, 0.26, 0).normalize();
        lFDir.set(-lSide * 0.96, 0.26, 0).normalize();

        rWrist.copy(rTipTarget).addScaledVector(rFDir, -rigMetrics.LHand);
        lWrist.copy(lTipTarget).addScaledVector(lFDir, -rigMetrics.LHand);

        rPole.set(rSide * 0.55, -0.75, camZ * 0.35);
        lPole.set(lSide * 0.55, -0.75, camZ * 0.35);

        rPalm.set(0, -0.35, -camZ * 0.93).normalize();
        lPalm.set(0, -0.35, -camZ * 0.93).normalize();

    } else if (currentPose === 'idle_popup_curious') {
        // Popup faces the MODEL (rotation.y ≈ Math.PI):
        // Left arm (model's left, world +X) extends naturally forward to project the 3D Popup upward;
        // Right arm (model's right, world -X) extends naturally forward from the shoulder to tap the model-facing front of the SYSTEM ACCESS buttons
        const phaseT = Math.max(0, time - idleInteractionStartTime);
        const pokeWave = Math.max(0, Math.sin(phaseT * 4.2));
        const pokeExtend = Math.pow(pokeWave, 3) * 0.045;
        const headTilt = Math.sin(phaseT * 1.9) * 0.04;
        const activeOptIdx = Math.floor((time * 0.75) % 4);
        const optYOffset = (1.5 - activeOptIdx) * 0.022;

        leftHandShape = 'open';
        rightHandShape = 'point';

        hipsRot = [0, -lSide * 0.04, rSide * 0.02];
        spineRot = [fwd * 0.07, -lSide * 0.04, rSide * 0.02];
        chestRot = [fwd * 0.06, -lSide * 0.03, 0];
        neckRot = [fwd * 0.05, -rSide * 0.04, rSide * 0.04];
        headRot = [fwd * 0.07, -rSide * 0.06, rSide * (0.08 + headTilt)];
        lShoulderRot = [fwd * 0.12, 0, lSide * 0.06];
        rShoulderRot = [fwd * 0.16, -rSide * 0.06, rSide * 0.05];

        // 1. Left Arm (Projector Arm, model's left): extended comfortably forward in front of lower chest with natural low elbow
        lWrist.set(
            chestP.x + lSide * 0.095,
            chestP.y + 0.035 + Math.sin(phaseT * 1.6) * 0.005,
            chestP.z + camZ * 0.255
        );
        lPole.set(lSide * 0.48, -0.82, camZ * 0.32);
        lFDir.set(-lSide * 0.36, 0.10, camZ * 0.92).normalize();
        lPalm.set(-lSide * 0.14, 0.95, camZ * 0.28).normalize();

        // 2. Right Arm (Interacting Arm, model's right): extended forward with relaxed low elbow, pointing forward (+Z) onto the model-facing front of the popup
        const popupTipTarget = new THREE.Vector3(
            chestP.x + rSide * 0.065,
            chestP.y + 0.162 + optYOffset,
            chestP.z + camZ * (0.285 + pokeExtend)
        );
        rFDir.set(-rSide * 0.18, 0.26, camZ * 0.95).normalize();
        rWrist.copy(popupTipTarget).addScaledVector(rFDir, -rigMetrics.LHand);
        rPole.set(rSide * 0.42, -0.84, camZ * 0.36);
        rPalm.set(-rSide * 0.65, -0.55, camZ * 0.52).normalize();

    } else if (currentPose === 'idle_orb_curious') {
        // Curiously inspect, cradle, and spin the floating HELIOS Core Orb on the left side
        const phaseT = Math.max(0, time - idleInteractionStartTime);
        const orbitY = Math.sin(phaseT * 2.8) * 0.032;
        const orbitZ = Math.cos(phaseT * 2.8) * 0.025;

        leftHandShape = 'open';
        rightHandShape = 'cupped';

        hipsRot = [0, -lSide * 0.06, lSide * 0.03];
        spineRot = [fwd * 0.05, -lSide * 0.13, lSide * 0.04];
        chestRot = [fwd * 0.04, -lSide * 0.08, 0];
        neckRot = [fwd * 0.04, -lSide * 0.11, lSide * 0.06];
        headRot = [fwd * 0.05, -lSide * 0.22, lSide * (0.14 + Math.sin(phaseT * 2.0) * 0.04)];
        lShoulderRot = [0, 0, lSide * 0.12];

        // Left hand hovers around and cradles the floating 3D Core Orb
        lWrist.set(
            S_L.x + lSide * 0.135,
            chestP.y + 0.085 + orbitY,
            chestP.z + camZ * (0.215 + orbitZ)
        );
        lPole.set(lSide * 0.84, -0.42, camZ * 0.35);
        lFDir.set(lSide * 0.28, 0.25, camZ * 0.92).normalize();
        lPalm.set(-lSide * 0.35, 0.85, camZ * 0.38).normalize();

        // Right hand raised near chest in curious fascination
        rWrist.set(
            S_R.x - rSide * 0.02,
            chestP.y + 0.09 - orbitY * 0.5,
            chestP.z + camZ * 0.165
        );
        rPole.set(rSide * 0.65, -0.58, camZ * 0.42);
        rFDir.set(-rSide * 0.48, 0.72, camZ * 0.48).normalize();
        rPalm.set(-rSide * 0.65, 0.25, -camZ * 0.72).normalize();

    } else if (currentPose === 'idle_screen_curious') {
        // Lean forward toward the camera and curiously tap the viewer screen glass
        const phaseT = Math.max(0, time - idleInteractionStartTime);
        const tapPulse = Math.max(0, Math.sin(phaseT * 4.6));
        const tapDepth = Math.pow(tapPulse, 4) * 0.055;

        rightHandShape = 'point';
        leftHandShape = 'cupped';

        scenePosY = -0.012;
        spineRot = [fwd * 0.13, 0, rSide * 0.03];
        chestRot = [fwd * 0.09, 0, 0];
        neckRot = [fwd * -0.05, rSide * 0.05, rSide * 0.07];
        headRot = [fwd * -0.08, rSide * Math.sin(phaseT * 1.5) * 0.08, rSide * 0.16];
        rShoulderRot = [0, 0, rSide * 0.14];

        // Right index finger reaches straight toward camera lens to tap the glass
        const glassTipTarget = new THREE.Vector3(
            headP.x + rSide * 0.045,
            headP.y - 0.04 + Math.sin(phaseT * 1.8) * 0.015,
            headP.z + camZ * (0.25 + tapDepth)
        );
        rFDir.set(-rSide * 0.06, 0.24, camZ * 0.96).normalize();
        rWrist.copy(glassTipTarget).addScaledVector(rFDir, -rigMetrics.LHand);
        rPole.set(rSide * 0.78, -0.48, camZ * 0.35);
        rPalm.set(-rSide * 0.22, -0.88, camZ * 0.42).normalize();

        // Left hand rests lightly on hip for balance while leaning in
        lWrist.set(hipsP.x + lSide * 0.125, hipsP.y + 0.085, hipsP.z + camZ * 0.045);
        lPole.set(lSide * 1.0, 0.08, -camZ * 0.25);
        lFDir.set(-lSide * 0.35, -0.82, camZ * 0.45).normalize();
        lPalm.set(-lSide * 0.85, -0.25, -camZ * 0.45).normalize();

    } else if (currentPose === 'idle_waiting_patient') {
        // Patient waiting stance: hands clasped gently in front, rhythmic side-to-side sway & soft head tilt
        const sway = Math.sin(time * 1.45);
        const bob = Math.abs(Math.cos(time * 1.45));

        leftHandShape = 'clasped';
        rightHandShape = 'clasped';

        scenePosY = -bob * 0.012;
        hipsRot = [0, sway * 0.045, sway * 0.04];
        spineRot = [fwd * 0.025, -sway * 0.03, -sway * 0.035];
        chestRot = [breath * 0.8, 0, 0];
        headRot = [fwd * 0.03, sway * 0.06, rSide * 0.07 + sway * 0.04];

        lUpperLegRot = [0, 0, -sway * 0.025];
        rUpperLegRot = [0, 0, -sway * 0.025];

        rWrist.set(rSide * 0.028, hipsP.y + 0.075, hipsP.z + camZ * 0.135);
        rPole.set(rSide * 0.72, -0.55, camZ * 0.28);
        rFDir.set(-rSide * 0.82, -0.42, camZ * 0.38).normalize();
        rPalm.set(-rSide * 0.35, 0.25, -camZ * 0.90).normalize();

        lWrist.set(lSide * 0.028, hipsP.y + 0.075, hipsP.z + camZ * 0.135);
        lPole.set(lSide * 0.72, -0.55, camZ * 0.28);
        lFDir.set(-lSide * 0.82, -0.42, camZ * 0.38).normalize();
        lPalm.set(-lSide * 0.35, 0.25, -camZ * 0.90).normalize();

    } else if (currentPose === 'idle_waiting_look') {
        // Waiting & looking around: checks wrist HUD, then glances left and right waiting for user
        const phaseT = Math.max(0, time - idleInteractionStartTime);
        const lookCycle = Math.sin(phaseT * 1.15);
        const checkWrist = Math.max(0, Math.cos(phaseT * 0.95));

        leftHandShape = 'open';
        rightHandShape = 'cupped';

        hipsRot = [0, rSide * 0.05, rSide * 0.035];
        spineRot = [fwd * -0.02, lookCycle * 0.08, -rSide * 0.025];
        chestRot = [fwd * (0.04 * checkWrist), lookCycle * 0.05, 0];
        neckRot = [fwd * (0.06 * checkWrist), lookCycle * 0.12, 0];
        headRot = [
            fwd * (0.10 * checkWrist - 0.02),
            lookCycle * 0.26 - lSide * 0.10 * checkWrist,
            rSide * 0.05 * lookCycle,
        ];

        // Left arm raised slightly so avatar can glance at cybernetic wrist HUD
        lWrist.set(
            S_L.x + lSide * 0.04,
            chestP.y + 0.02 + checkWrist * 0.045,
            chestP.z + camZ * (0.16 + checkWrist * 0.03)
        );
        lPole.set(lSide * 0.75, -0.58, camZ * 0.32);
        lFDir.set(-lSide * 0.78, 0.22, camZ * 0.58).normalize();
        lPalm.set(0, 0.85, -camZ * 0.52).normalize();

        // Right hand resting on hip while waiting
        rWrist.set(hipsP.x + rSide * 0.128, hipsP.y + 0.09, hipsP.z + camZ * 0.045);
        rPole.set(rSide * 1.0, 0.1, -camZ * 0.25);
        rFDir.set(-rSide * 0.35, -0.82, camZ * 0.45).normalize();
        rPalm.set(-rSide * 0.85, -0.25, -camZ * 0.45).normalize();

    } else if (currentPose === 'idle_waiting_stretch') {
        // Relaxed waiting stretch: raises arms & rolls shoulders to stay limber while waiting
        const phaseT = Math.max(0, time - idleInteractionStartTime);
        const stretchWave = 0.5 + 0.5 * Math.sin(phaseT * 1.6 - 0.4);

        leftHandShape = 'open';
        rightHandShape = 'open';

        spineRot = [fwd * (-0.08 * stretchWave), 0, Math.sin(phaseT * 1.2) * 0.04];
        chestRot = [fwd * (-0.07 * stretchWave), 0, 0];
        headRot = [fwd * (-0.09 * stretchWave), Math.sin(phaseT * 1.2) * 0.06, rSide * 0.06];
        lShoulderRot = [0, 0, lSide * (0.12 + 0.10 * stretchWave)];
        rShoulderRot = [0, 0, rSide * (0.12 + 0.10 * stretchWave)];

        rWrist.set(
            headP.x + rSide * (0.14 - 0.04 * stretchWave),
            headP.y + 0.08 + 0.11 * stretchWave,
            headP.z - camZ * 0.02
        );
        rPole.set(rSide * 0.92, -0.1, camZ * 0.35);
        rFDir.set(-rSide * 0.25, 0.94, camZ * 0.18).normalize();
        rPalm.set(-rSide * 0.15, 0.82, camZ * 0.55).normalize();

        lWrist.set(
            headP.x + lSide * (0.14 - 0.04 * stretchWave),
            headP.y + 0.08 + 0.11 * stretchWave,
            headP.z - camZ * 0.02
        );
        lPole.set(lSide * 0.92, -0.1, camZ * 0.35);
        lFDir.set(-lSide * 0.25, 0.94, camZ * 0.18).normalize();
        lPalm.set(-lSide * 0.15, 0.82, camZ * 0.55).normalize();
    }

    let pendingCustomIkSpec = null;
    if (customPoseRegistry.has(currentPose)) {
        // HELIOS Core Synthesized Custom Pose (Kalidokit / @pixiv/three-vrm / ChatVRM / Amica standard)
        const baseSpec = customPoseRegistry.get(currentPose);
        let activeSpec = baseSpec;
        if (Array.isArray(baseSpec.keyframes) && baseSpec.keyframes.length > 0) {
            const elapsedMs = Math.max(0, (time - customPoseStartTime) * 1000);
            let totalDurationMs = 0;
            for (const kf of baseSpec.keyframes) {
                totalDurationMs += Math.max(250, Number(kf.duration_ms || 900));
            }
            const shouldLoop = baseSpec.loop === true;
            if (!shouldLoop && elapsedMs >= totalDurationMs) {
                activeSpec = { ...baseSpec, ...baseSpec.keyframes[baseSpec.keyframes.length - 1] };
            } else {
                const cycleMs = totalDurationMs > 0 ? elapsedMs % totalDurationMs : 0;
                let accum = 0;
                for (const kf of baseSpec.keyframes) {
                    const d = Math.max(250, Number(kf.duration_ms || 900));
                    if (cycleMs <= accum + d) {
                        activeSpec = { ...baseSpec, ...kf };
                        break;
                    }
                    accum += d;
                }
            }
        }

        const ikSpec = activeSpec.ik || baseSpec.ik || {};
        pendingCustomIkSpec = ikSpec;
        scenePosY = Number(activeSpec.hipsOffsetY ?? baseSpec.hipsOffsetY ?? 0);
        leftHandShape =
            activeSpec.leftHandShape ||
            ikSpec.leftHandShape ||
            baseSpec.leftHandShape ||
            'relaxed';
        rightHandShape =
            activeSpec.rightHandShape ||
            ikSpec.rightHandShape ||
            baseSpec.rightHandShape ||
            'relaxed';

        const b = activeSpec.bones || baseSpec.bones || {};
        const toRad = (v) => {
            const n = Number(v || 0);
            return Math.abs(n) > 1.5 ? THREE.MathUtils.degToRad(n) : THREE.MathUtils.degToRad(n);
        };
        const mapRigEuler = (rotArr, defArr) => {
            if (!Array.isArray(rotArr) || rotArr.length < 3) return defArr;
            return [fwd * toRad(rotArr[0]), rSide * toRad(rotArr[1]), rSide * toRad(rotArr[2])];
        };

        hipsRot = mapRigEuler(b.hips, hipsRot);
        spineRot = mapRigEuler(b.spine, [breath, 0, 0]);
        chestRot = mapRigEuler(b.chest, [breath * 0.5, 0, 0]);
        neckRot = mapRigEuler(b.neck, neckRot);
        headRot = mapRigEuler(b.head, headRot);
        lShoulderRot = mapRigEuler(b.leftShoulder, lShoulderRot);
        rShoulderRot = mapRigEuler(b.rightShoulder, rShoulderRot);
        lUpperLegRot = mapRigEuler(b.leftUpperLeg, lUpperLegRot);
        rUpperLegRot = mapRigEuler(b.rightUpperLeg, rUpperLegRot);
        lLowerLegRot = mapRigEuler(b.leftLowerLeg, lLowerLegRot);
        rLowerLegRot = mapRigEuler(b.rightLowerLeg, rLowerLegRot);
        lFootRot = mapRigEuler(b.leftFoot, lFootRot);
        rFootRot = mapRigEuler(b.rightFoot, rFootRot);

        if (Array.isArray(b.upperChest) && b.upperChest.length >= 3) {
            const uChest = mapRigEuler(b.upperChest, [0, 0, 0]);
            lerpBoneEuler(h.getNormalizedBoneNode('upperChest'), ...uChest, speed);
        }
    }

    // Superimpose biological breathing, righting reflex, and speech prosody onto active pose
    if (currentPose !== 'idle' && currentPose !== 'backflip') {
        spineRot[0] += breathKin.spinePitch * 0.75 + microPosture.spinePitch * 0.6;
        spineRot[2] += microPosture.spineRoll * 0.55;
        chestRot[0] += breathKin.chestPitch * 0.8;
        neckRot[0] += microPosture.neckPitch * 0.65;
        neckRot[1] += microPosture.neckYaw * 0.65;
        neckRot[2] += microPosture.neckRoll * 0.65;
        headRot[0] += microPosture.headPitch * 0.65;
        headRot[1] += microPosture.headYaw * 0.65;
        headRot[2] += microPosture.headRoll * 0.55;
        lShoulderRot[2] += breathKin.leftShoulderRoll * 0.7;
        rShoulderRot[2] += breathKin.rightShoulderRoll * 0.7;
    }

    // Add natural conversational head rhythm ONLY while actively speaking audio
    if (currentState === 'speaking' && audioLipSync && audioLipSync.isPlaying) {
        headRot[0] += Math.sin(time * 5.5) * 0.024;
        headRot[1] += Math.cos(time * 2.5) * 0.018;
    }

    currentVrm.scene.position.y = THREE.MathUtils.lerp(currentVrm.scene.position.y, scenePosY, speed);
    lerpBoneEuler(hips, ...hipsRot, speed);

    // Apply Lower Body Leg Kinematics
    lerpBoneEuler(h.getNormalizedBoneNode('leftUpperLeg'), ...lUpperLegRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('rightUpperLeg'), ...rUpperLegRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('leftLowerLeg'), ...lLowerLegRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('rightLowerLeg'), ...rLowerLegRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('leftFoot'), ...lFootRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('rightFoot'), ...rFootRot, speed);

    // Apply Torso, Neck, Head & Shoulders BEFORE resolving custom pose anchors so anchors track the live rotated body
    lerpBoneEuler(h.getNormalizedBoneNode('spine'), ...spineRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('chest'), ...chestRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('neck'), ...neckRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('head'), ...headRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('leftShoulder'), ...lShoulderRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('rightShoulder'), ...rShoulderRot, speed);

    if (pendingCustomIkSpec) {
        const liveHeadP = getRigSpacePos(h.getNormalizedBoneNode('head'), rootNode, new THREE.Vector3());
        const liveChestP = getRigSpacePos(h.getNormalizedBoneNode('chest'), rootNode, new THREE.Vector3());
        const liveHipsP = getRigSpacePos(hips, rootNode, new THREE.Vector3());
        const liveSR = getRigSpacePos(h.getNormalizedBoneNode('rightUpperArm'), rootNode, new THREE.Vector3());
        const liveSL = getRigSpacePos(h.getNormalizedBoneNode('leftUpperArm'), rootNode, new THREE.Vector3());

        const resolveAnchorVec = (anchorName, side) => {
            const a = String(anchorName || 'chest').toLowerCase();
            if (a === 'head') return liveHeadP;
            if (a === 'hips') return liveHipsP;
            if (a === 'shoulder') return side === 'right' ? liveSR : liveSL;
            return liveChestP;
        };

        const applyHandIkSpec = (wSpec, sideSign, outWrist, outPole, outFDir, outPalm, sideName) => {
            if (!wSpec || !Array.isArray(wSpec.offset)) return;
            const aName = String(wSpec.anchor || 'chest').toLowerCase();
            const anchor = resolveAnchorVec(aName, sideName);
            const [ox, oy, oz] = wSpec.offset;
            outWrist.set(
                anchor.x + sideSign * Number(ox || 0),
                anchor.y + Number(oy || 0),
                anchor.z + camZ * Number(oz || 0)
            );
            if (Array.isArray(wSpec.pole) && wSpec.pole.length >= 3) {
                outPole.set(sideSign * Number(wSpec.pole[0]), Number(wSpec.pole[1]), camZ * Number(wSpec.pole[2]));
            } else if (aName === 'hips') {
                outPole.set(sideSign * 1.0, 0.08, -camZ * 0.25);
            } else if (aName === 'head') {
                outPole.set(sideSign * 0.85, -0.20, camZ * 0.38);
            } else {
                outPole.set(sideSign * 0.68, -0.65, camZ * 0.35);
            }

            if (Array.isArray(wSpec.fingerDir) && wSpec.fingerDir.length >= 3) {
                outFDir.set(sideSign * Number(wSpec.fingerDir[0]), Number(wSpec.fingerDir[1]), camZ * Number(wSpec.fingerDir[2])).normalize();
            } else if (aName === 'hips') {
                outFDir.set(-sideSign * 0.35, -0.82, camZ * 0.45).normalize();
            } else if (aName === 'head') {
                outFDir.set(-sideSign * 0.12, 0.96, camZ * 0.22).normalize();
            } else {
                outFDir.set(-sideSign * 0.25, 0.65, camZ * 0.72).normalize();
            }

            if (Array.isArray(wSpec.palmNormal) && wSpec.palmNormal.length >= 3) {
                outPalm.set(sideSign * Number(wSpec.palmNormal[0]), Number(wSpec.palmNormal[1]), camZ * Number(wSpec.palmNormal[2])).normalize();
            } else if (aName === 'hips') {
                outPalm.set(-sideSign * 0.85, -0.25, -camZ * 0.45).normalize();
            } else if (aName === 'head') {
                outPalm.set(-sideSign * 0.25, 0.08, camZ * 0.96).normalize();
            } else {
                outPalm.set(-sideSign * 0.50, 0.35, camZ * 0.78).normalize();
            }
        };

        applyHandIkSpec(pendingCustomIkSpec.rightWrist, rSide, rWrist, rPole, rFDir, rPalm, 'right');
        applyHandIkSpec(pendingCustomIkSpec.leftWrist, lSide, lWrist, lPole, lFDir, lPalm, 'left');
    }

    // Solve & apply 2-Bone Analytic IK + Shortest-Path Quaternion Slerp for both arms
    solveAndApplyArmIK(h, rootNode, 'right', rWrist, rPole, rFDir, rPalm, speed);
    solveAndApplyArmIK(h, rootNode, 'left', lWrist, lPole, lFDir, lPalm, speed);

    // Apply 30-bone finger shapes with physiological micro-tonus
    applyHandShape(h, 'left', leftHandShape, speed, time);
    applyHandShape(h, 'right', rightHandShape, speed, time);
}

// ----------------------------------------------------
// MULTI-POSE EMOTION-DRIVEN SPEAKING SYSTEM & UI HELPERS
// ----------------------------------------------------
let currentState = 'idle';
let currentEmotion = 'neutral';
let currentPose = 'idle';
let currentStyle = 'natural';
let poseResetTimeout = null;
const customPoseRegistry = new Map();
let customPoseStartTime = 0;
let idleInteractionStartTime = 0;

let speakingPoseIndex = 0;
let speakingPoseCycleTimer = 0;
let speakingIdleWatchdog = 0;
let pendingSpeechChunks = 0;
const SPEAKING_POSE_INTERVAL = 1.65; // Switch speaking pose every 1.65s

function getNextSpeakingPoseForEmotion(emotion) {
    const key = (emotion || currentEmotion || 'neutral').toLowerCase();
    const pool = EMOTION_SPEAKING_POSE_POOLS[key] || EMOTION_SPEAKING_POSE_POOLS.neutral;
    const pose = pool[speakingPoseIndex % pool.length];
    speakingPoseIndex = (speakingPoseIndex + 1) % pool.length;
    return pose;
}

function setExpressionSmart(name, weight = 1.0) {
    expressionCtrl.setExpressionSmart(name, weight);
}

function resetExpressions(keepBlinkAndMouth = false) {
    expressionCtrl.resetExpressions(keepBlinkAndMouth);
}

function applyExpressionState(expressionName, weight = 0.75, blendshapeWeights = null) {
    currentEmotion = (expressionName || 'neutral').toLowerCase();
    expressionCtrl.applyExpressionState(expressionName, weight, blendshapeWeights);
}

function readAndRenderPresets(vrm) {
    const presetContainer = document.getElementById('preset-controls');
    const presetButtons = document.getElementById('preset-buttons');
    if (!presetContainer || !presetButtons) return;

    presetButtons.innerHTML = '';
    availableExpressions = expressionCtrl.setVRM(vrm);

    if (!vrm.expressionManager || availableExpressions.length === 0) {
        presetContainer.style.display = 'none';
        return;
    }

    availableExpressions.forEach((name) => {
        const btn = document.createElement('button');
        btn.innerText = name;
        btn.onclick = () => {
            resetExpressions();
            setExpressionSmart(name, 1.0);
            highlightPresetButton(name);
            if (!['aa', 'ih', 'ou', 'ee', 'oh', 'blink', 'blinkLeft', 'blinkRight'].includes(name)) {
                currentEmotion = name.toLowerCase();
                if (currentState === 'speaking') {
                    speakingPoseIndex = 0;
                    const nextP = getNextSpeakingPoseForEmotion(currentEmotion);
                    setPose(nextP);
                }
            }
            updateStatus(`BlendShape Preset: ${name} | Emotion: ${currentEmotion}`);
        };
        presetButtons.appendChild(btn);
    });

    presetContainer.style.display = 'flex';
}

function highlightPresetButton(activeName) {
    document.querySelectorAll('#preset-buttons button').forEach(b => {
        b.classList.toggle('active', b.innerText.toLowerCase() === (activeName || '').toLowerCase());
    });
}

function highlightPoseButton(poseName) {
    document.querySelectorAll('#pose-buttons button, #idle-interaction-buttons button').forEach(b => {
        b.classList.toggle('active', b.getAttribute('data-pose') === poseName);
    });
    document.querySelectorAll('#custom-pose-buttons button').forEach(b => {
        b.classList.toggle('active', b.getAttribute('data-custom-pose') === poseName);
    });
}

function highlightNavButton(navName) {
    document.querySelectorAll('#nav-buttons button').forEach(b => {
        b.classList.toggle('active', b.getAttribute('data-nav') === navName);
    });
}

function highlightStyleButton(styleName) {
    document.querySelectorAll('#style-buttons button').forEach(b => {
        b.classList.toggle('active', b.getAttribute('data-style') === styleName);
    });
}

function setStyleMode(styleName = 'natural', applyExpression = false) {
    const valid = ['natural', 'energetic', 'confident', 'relaxed', 'shy', 'dramatic'];
    const clean = String(styleName || 'natural').toLowerCase();
    currentStyle = valid.includes(clean) ? clean : 'natural';
    if (humanizer && typeof humanizer.setStyle === 'function') {
        humanizer.setStyle(currentStyle);
    }
    highlightStyleButton(currentStyle);
    if (applyExpression) {
        const styleEmoMap = {
            natural: 'neutral',
            energetic: 'happy',
            confident: 'smug',
            relaxed: 'relaxed',
            shy: 'relaxed',
            dramatic: 'serious',
        };
        applyExpressionState(styleEmoMap[currentStyle] || currentEmotion, 0.78);
    }
}
window.setStyleMode = setStyleMode;

let baseCameraTargetY = 1.05;
let baseCameraY = 1.19;
let baseCameraZ = 1.67;

function focusOnModel(vrm, resetAvatarPos = false) {
    if (!vrm) return;
    if (resetAvatarPos) {
        vrm.scene.position.set(0, 0, 0);
        vrm.scene.rotation.set(0, baseFacingYaw, 0);
        if (navController) navController.executeMovement('idle', camera);
    }
    const head = vrm.humanoid?.getNormalizedBoneNode('head');
    if (head) {
        vrm.scene.updateMatrixWorld(true);
        const headPos = new THREE.Vector3();
        head.getWorldPosition(headPos);
        const isFBX = Boolean(vrm.isFBXModel);
        baseCameraTargetY = headPos.y - (isFBX ? 0.38 : 0.22);
        baseCameraY = headPos.y - (isFBX ? 0.18 : 0.08);
        baseCameraZ = headPos.z + (isFBX ? 2.45 : 1.65);
        controls.target.set(headPos.x, baseCameraTargetY, headPos.z);
        camera.position.set(headPos.x, baseCameraY, baseCameraZ);
        controls.update();
    }
}

function focusCallCamera(vrm) {
    if (!vrm) return;
    const head = vrm.humanoid?.getNormalizedBoneNode('head');
    if (head) {
        vrm.scene.updateMatrixWorld(true);
        const headPos = new THREE.Vector3();
        head.getWorldPosition(headPos);
        const isFBX = Boolean(vrm.isFBXModel);
        const targetY = headPos.y - (isFBX ? 0.22 : 0.10);
        const camY = headPos.y - (isFBX ? 0.08 : 0.02);
        const camZ = headPos.z + (isFBX ? 1.45 : 1.05);
        controls.target.set(headPos.x, targetY, headPos.z);
        camera.position.set(headPos.x, camY, camZ);
        controls.update();
    }
}

function setPose(poseName, autoReturnMs = 0) {
    const cleanPose = poseName || 'idle';
    const nowTime = typeof clock !== 'undefined' && clock ? clock.getElapsedTime() : 0;
    if (customPoseRegistry.has(cleanPose)) {
        customPoseStartTime = nowTime;
    }
    if (isIdleObjectOrWaitingPose(cleanPose)) {
        idleInteractionStartTime = nowTime;
    }
    if (animManager) {
        animManager.play(cleanPose, 0.4, cleanPose !== 'backflip');
    } else {
        currentPose = cleanPose;
        highlightPoseButton(cleanPose);
    }

    if (cleanPose === 'backflip') {
        backflipStartTime = nowTime;
        autoReturnMs = 1400;
    }

    if (poseResetTimeout) {
        clearTimeout(poseResetTimeout);
        poseResetTimeout = null;
    }

    if (autoReturnMs > 0 && cleanPose !== 'idle') {
        poseResetTimeout = setTimeout(() => {
            if (animManager) animManager.play('idle', 0.4, true);
            else currentPose = 'idle';
            highlightPoseButton('idle');
        }, autoReturnMs);
    }
}
window.setPose = setPose;

// Unlock AudioContext on first user interaction anywhere in the document
['pointerdown', 'touchstart', 'click', 'keydown'].forEach((evt) => {
    window.addEventListener(evt, () => {
        if (audioLipSync) audioLipSync.ensureContext();
    }, { passive: true });
});

const STATIC_EMOTION_MP3_MAP = {
    happy: 'models/voices/happy.mp3',
    excited: 'models/voices/happy.mp3',
    joy: 'models/voices/happy.mp3',
    amused: 'models/voices/smug.mp3',
    smirk: 'models/voices/smug.mp3',
    smug: 'models/voices/smug.mp3',
    relaxed: 'models/voices/relaxed.mp3',
    fun: 'models/voices/relaxed.mp3',
    serious: 'models/voices/angry.mp3',
    angry: 'models/voices/angry.mp3',
    concerned: 'models/voices/sad.mp3',
    sad: 'models/voices/sad.mp3',
    sorrow: 'models/voices/sad.mp3',
    confused: 'models/voices/surprised.mp3',
    surprised: 'models/voices/surprised.mp3',
    neutral: 'models/voices/neutral.mp3'
};

// ----------------------------------------------------
// TENSURA POPUP STATE COLOR SYNCHRONIZATION (3D VRM + HUD)
// ----------------------------------------------------
const POPUP_STATE_PALETTE = {
    idle: {
        bodyClass: 'state-idle',
        btnId: 'btn-idle',
        hex: '#2C3038',
        trimColor: new THREE.Color('#2C3038'),     // Charcoal (--charcoal)
        trimBreathe: new THREE.Color('#1f6e7c'),   // Subtle standby cybernetic trace
        eyeColor: new THREE.Color('#00b8d4'),      // Calm cyan-slate iris
        gridColor: new THREE.Color('#384152'),
        pulseSpeed: 1.6,
        baseBoost: 0.95,
        pulseAmp: 0.25,
    },
    listening: {
        bodyClass: 'state-listening',
        btnId: 'btn-listening',
        hex: '#00e5ff',
        trimColor: new THREE.Color('#00e5ff'),     // Piercing Cyan (--accent-cyan)
        trimBreathe: new THREE.Color('#00e5ff'),
        eyeColor: new THREE.Color('#00e5ff'),
        gridColor: new THREE.Color('#00e5ff'),
        pulseSpeed: 3.2,
        baseBoost: 1.15,
        pulseAmp: 0.28,
    },
    thinking: {
        bodyClass: 'state-thinking',
        btnId: 'btn-thinking',
        hex: '#FFCC00',
        trimColor: new THREE.Color('#FFCC00'),     // Glowing Amber/Gold (--accent-amber)
        trimBreathe: new THREE.Color('#FF9900'),
        eyeColor: new THREE.Color('#FFCC00'),
        gridColor: new THREE.Color('#FFCC00'),
        pulseSpeed: 7.8,                           // Fast 0.8s thinking pulse matching popup
        baseBoost: 1.18,
        pulseAmp: 0.42,
    },
    speaking: {
        bodyClass: 'state-speaking',
        btnId: 'btn-speaking',
        hex: '#3296fa',
        trimColor: new THREE.Color('#3296fa'),     // Electric Blue (--accent-blue)
        trimBreathe: new THREE.Color('#00e5ff'),
        eyeColor: new THREE.Color('#3296fa'),
        gridColor: new THREE.Color('#3296fa'),
        pulseSpeed: 5.5,
        baseBoost: 1.15,
        pulseAmp: 0.40,
    },
    error: {
        bodyClass: 'state-error',
        btnId: 'btn-thinking',
        hex: '#FF3B30',
        trimColor: new THREE.Color('#FF3B30'),     // Alert Crimson
        trimBreathe: new THREE.Color('#FF3B30'),
        eyeColor: new THREE.Color('#FF3B30'),
        gridColor: new THREE.Color('#FF3B30'),
        pulseSpeed: 8.5,
        baseBoost: 1.20,
        pulseAmp: 0.40,
    },
};

let activeVisualStateKey = 'idle';
const lerpedTrimColor = new THREE.Color('#2C3038');
const lerpedEyeColor = new THREE.Color('#00b8d4');
const lerpedGridColor = new THREE.Color('#384152');
const tempTrimTarget = new THREE.Color();
const tempEmitOut = new THREE.Color();

function resolvePopupStateKey(rawState) {
    const s = String(rawState || 'idle').toLowerCase();
    if (s === 'working' || s === 'executing' || s === 'thinking') return 'thinking';
    if (s === 'listening') return 'listening';
    if (s === 'speaking') return 'speaking';
    if (s === 'error') return 'error';
    return 'idle';
}

function applyStateVisualTheme(rawState) {
    const stateKey = resolvePopupStateKey(rawState);
    activeVisualStateKey = stateKey;
    const theme = POPUP_STATE_PALETTE[stateKey] || POPUP_STATE_PALETTE.idle;

    document.body.classList.remove(
        'state-idle',
        'state-listening',
        'state-thinking',
        'state-speaking',
        'state-error'
    );
    document.body.classList.add(theme.bodyClass);

    ['btn-idle', 'btn-listening', 'btn-thinking', 'btn-speaking'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.classList.toggle('active', id === theme.btnId);
    });
}

function updateVrmStateColorTransition(delta, elapsed) {
    const theme = POPUP_STATE_PALETTE[activeVisualStateKey] || POPUP_STATE_PALETTE.idle;
    const lerpAlpha = Math.min(1.0, delta * 8.0);

    const wave = 0.5 + 0.5 * Math.sin(elapsed * theme.pulseSpeed);
    tempTrimTarget.copy(theme.trimColor).lerp(theme.trimBreathe, wave * 0.45);

    lerpedTrimColor.lerp(tempTrimTarget, lerpAlpha);
    lerpedEyeColor.lerp(theme.eyeColor, lerpAlpha);
    lerpedGridColor.lerp(theme.gridColor, lerpAlpha);

    // Modulate pulse with live lip-sync vowel openness when speaking
    let speechEnergy = 0.0;
    if (activeVisualStateKey === 'speaking' && currentVrm?.expressionManager) {
        const aa = currentVrm.expressionManager.getValue('aa') || 0;
        const oh = currentVrm.expressionManager.getValue('oh') || 0;
        speechEnergy = Math.min(1.0, (aa + oh) * 0.85);
    }

    const pulseFactor =
        theme.baseBoost + wave * theme.pulseAmp + speechEnergy * 0.55;

    for (let i = 0; i < emissiveMaterials.length; i++) {
        const { mat, isEye } = emissiveMaterials[i];
        const baseCol = isEye ? lerpedEyeColor : lerpedTrimColor;
        const mult = isEye ? Math.max(1.0, pulseFactor) : pulseFactor;
        tempEmitOut.copy(baseCol).multiplyScalar(mult);
        if (mat.emissive) {
            mat.emissive.copy(tempEmitOut);
        }
        if (mat.uniforms?.emissive?.value) {
            mat.uniforms.emissive.value.copy(tempEmitOut);
        }
    }

    if (gridHelper && gridHelper.material?.color) {
        gridHelper.material.color.copy(lerpedGridColor);
    }
    if (stateAccentLight) {
        stateAccentLight.color.copy(lerpedTrimColor);
        stateAccentLight.intensity = 0.65 + wave * 0.45 + speechEnergy * 0.5;
    }
}

function finishSpeakingProcedure() {
    speakingIdleWatchdog = 0;
    speakingPoseCycleTimer = 0;
    if (pendingSpeechChunks > 0 || (audioLipSync && audioLipSync.isPlaying)) {
        return;
    }
    if (currentState === 'speaking') {
        currentState = 'idle';
        applyStateVisualTheme('idle');
        applyExpressionState(currentEmotion, 0.35);
        if (!navController?.isNavigating && currentPose !== 'backflip') {
            setPose('idle');
        }
        updateStatus(`State: Idle (#2C3038) | Pose: ${currentPose}`);
    }
    if (typeof handleCallAiriFinishedSpeaking === 'function') {
        handleCallAiriFinishedSpeaking();
    }
}
window.finishSpeakingProcedure = finishSpeakingProcedure;

async function previewEmotionVoice(emotion = null, initialPose = null) {
    const targetEmotion = (emotion || currentEmotion || 'neutral').toLowerCase();
    currentEmotion = targetEmotion;
    currentState = 'speaking';
    applyStateVisualTheme('speaking');
    speakingPoseCycleTimer = 0;
    speakingIdleWatchdog = 0;

    const firstPose = initialPose || getNextSpeakingPoseForEmotion(targetEmotion);
    setPose(firstPose);
    applyExpressionState(targetEmotion, 0.85);

    updateStatus(`🔊 Previewing Lip Sync [${targetEmotion}]`);
    if (!audioLipSync) {
        finishSpeakingProcedure();
        return;
    }
    audioLipSync.ensureContext();

    const staticMp3 = STATIC_EMOTION_MP3_MAP[targetEmotion] || STATIC_EMOTION_MP3_MAP.neutral;
    try {
        await audioLipSync.playStaticMp3Sync(staticMp3);
    } finally {
        finishSpeakingProcedure();
    }
}

function setTestState(state, customPose = null, triggerPreview = false) {
    currentState = state;
    speakingIdleWatchdog = 0;
    applyStateVisualTheme(state);
    if (state !== 'speaking' && audioLipSync) {
        pendingSpeechChunks = 0;
        audioLipSync.stopCurrent();
    }

    if (state === 'idle') {
        setPose(customPose || 'idle');
        applyExpressionState(currentEmotion, 0.45);
        updateStatus(`State: Idle (#2C3038) | Pose: ${currentPose}`);
    } else if (state === 'listening') {
        applyExpressionState('curious', 0.55);
        setPose(customPose || 'listen_pose');
        updateStatus(`State: Listening (#00E5FF) | Pose: ${currentPose}`);
    } else if (state === 'thinking') {
        applyExpressionState('thinking', 0.75, { relaxed: 0.75, oh: 0.2 });
        setPose(customPose || 'think_pose');
        updateStatus(`State: HELIOS Thinking (#FFCC00) | Pose: ${currentPose}`);
    } else if (state === 'speaking') {
        speakingPoseCycleTimer = 0;
        const firstSpeakPose = customPose || getNextSpeakingPoseForEmotion(currentEmotion);
        setPose(firstSpeakPose);
        applyExpressionState(currentEmotion, 0.8);
        if (triggerPreview) {
            previewEmotionVoice(currentEmotion, firstSpeakPose);
        } else if (audioLipSync && !audioLipSync.isPlaying) {
            audioLipSync.startSimulatedLipSync(4500);
        }
        updateStatus(`State: Speaking (#3296FA) [${currentEmotion}] | Pose: ${currentPose}`);
    }
}
window.setTestState = setTestState;

// ----------------------------------------------------
// CHARACTER PROTOCOL STATE APPLICATION (Section 9)
// ----------------------------------------------------
let activeRendererType = 'vrm';
let aiBodyEnabled = true;
let aiBodyStepIndex = 0;
const AI_IDLE_BODY_PROMPTS = [
    'Shift into a confident techwear stance and nod casually.',
    'Strike a cyber salute with a sharp smile.',
    'Do a martial arts fighting guard stance.',
    'Walk a step closer to the user and strike a peace sign.',
    'Strike a double biceps flex pose.',
    'Return to center and stand in a relaxed confident posture.',
];

let activeChoreographyTimers = [];

function clearChoreographyTimers() {
    for (const t of activeChoreographyTimers) {
        clearTimeout(t);
    }
    activeChoreographyTimers = [];
}

function registerAndEnsureCustomPoseButton(customPose) {
    if (!customPose || !customPose.name) return;
    const poseName = String(customPose.name).trim();
    customPoseRegistry.set(poseName, customPose);

    const container = document.getElementById('custom-pose-buttons');
    if (!container) return;
    let existing = container.querySelector(`button[data-custom-pose="${poseName}"]`);
    if (!existing) {
        existing = document.createElement('button');
        existing.setAttribute('data-custom-pose', poseName);
        existing.setAttribute('data-pose-prompt', customPose.description || poseName.replace(/_/g, ' '));
        const label = poseName
            .replace(/^custom_/, '')
            .replace(/_/g, ' ')
            .replace(/\b\w/g, (c) => c.toUpperCase());
        existing.innerText = `✨ ${label}`;
        existing.onclick = () => {
            setPose(poseName, 0);
            updateStatus(`HELIOS Custom Pose: ${poseName}`);
        };
        container.appendChild(existing);
    }
}

function executeSingleBodyStep(stepMovement, stepPose, emotion) {
    const cleanMove = (stepMovement || 'stay').toLowerCase();
    const rawPose = stepPose || 'idle';
    const mappedPose = customPoseRegistry.has(rawPose)
        ? rawPose
        : mapProtocolAnimationToPose(rawPose, emotion);
    if (aiBodyEnabled && cleanMove && cleanMove !== 'idle' && cleanMove !== 'stay' && navController) {
        navController.executeMovement(cleanMove, camera, mappedPose === 'walk' ? 'idle' : mappedPose);
    } else if (aiBodyEnabled || ['idle', 'listen_pose', 'think_pose'].includes(mappedPose)) {
        const autoReturn = ['backflip', 'dance_shikano', 'hug_attempt', 'wave', 'bow', 'peace', 'cheer'].includes(mappedPose)
            ? 4200
            : 0;
        setPose(mappedPose, autoReturn);
    }
}

function applyCharacterProtocolState(stateMsg) {
    if (!stateMsg) return;
    if (activeRendererType === 'live2d') {
        live2dAdapter.applyCharacterState(stateMsg);
        return;
    }

    const mode = (stateMsg.mode || 'idle').toLowerCase();
    const emotion = (stateMsg.emotion || 'neutral').toLowerCase();
    const expression = (stateMsg.expression || emotion || 'neutral').toLowerCase();
    const intensity = Number(stateMsg.intensity ?? 0.5);
    const anim = stateMsg.animation || 'idle';
    const movement = (stateMsg.movement || 'stay').toLowerCase();
    const style = (stateMsg.style || (stateMsg.custom_pose && stateMsg.custom_pose.style) || currentStyle || 'natural').toLowerCase();
    const choreography = Array.isArray(stateMsg.choreography) ? stateMsg.choreography : [];
    const customPose = stateMsg.custom_pose || null;

    if (customPose && customPose.name) {
        registerAndEnsureCustomPoseButton(customPose);
    }

    currentEmotion = emotion;
    currentState = mode === 'working' || mode === 'error' ? 'thinking' : mode;
    setStyleMode(style, false);
    applyStateVisualTheme(mode);

    applyExpressionState(expression, Math.max(0.3, intensity));

    clearChoreographyTimers();
    const targetPose =
        customPose && customPose.name
            ? customPose.name
            : mapProtocolAnimationToPose(anim, emotion);

    if (aiBodyEnabled && choreography.length > 1) {
        let cumulativeMs = 0;
        choreography.forEach((step, idx) => {
            const stepMove = step.movement || (idx === 0 ? movement : 'stay');
            const stepAnim = step.animation || targetPose;
            const rawMs = step.duration_ms ? Number(step.duration_ms) : Number(step.duration || 1.4) * 1000;
            const durMs = Math.max(400, rawMs);
            if (idx === 0) {
                executeSingleBodyStep(stepMove, stepAnim, emotion);
            } else {
                const timerId = setTimeout(() => {
                    executeSingleBodyStep(stepMove, stepAnim, emotion);
                }, cumulativeMs);
                activeChoreographyTimers.push(timerId);
            }
            cumulativeMs += durMs;
        });
    } else {
        executeSingleBodyStep(movement, targetPose, emotion);
    }

    if (mode === 'idle') {
        updateActivityBanner('');
    }
    if (customPose && customPose.rl_evaluation) {
        updateRlRewardHud(customPose.rl_evaluation, null);
    }
    const moveSuffix = movement && movement !== 'stay' && movement !== 'idle' ? ` | Move: ${movement}` : '';
    const styleSuffix = style ? ` | Style: ${style}` : '';
    const choreoSuffix = choreography.length > 1 ? ` | Steps: ${choreography.length}` : '';
    const rlPct = customPose && typeof customPose.rl_reward_pct === 'number' ? ` [🏆 RL ${customPose.rl_reward_pct.toFixed(1)}%]` : '';
    const customSuffix = customPose && customPose.name ? ` [HELIOS Synthesized Pose]${rlPct}` : '';
    updateStatus(
        `HELIOS [${mode.toUpperCase()}] | Emotion: ${emotion} (${intensity.toFixed(2)}) | Pose: ${targetPose}${styleSuffix}${customSuffix}${moveSuffix}${choreoSuffix}`
    );
}

// ----------------------------------------------------
// HUMAN-REFERENCE REINFORCEMENT LEARNING (RL) HUD & TELEMETRY
// ----------------------------------------------------
let lastRlStatusSummary = {
    total_episodes: 0,
    total_awards: 0,
    cumulative_award_points: 0,
    mean_reward_pct: 100.0,
};
let lastRlEvaluation = null;

function computeLiveVrmBiomechanicalTelemetry() {
    if (!currentVrm || !currentVrm.humanoid) {
        return { minWristCos: 0.96, thumbOpposed: true, gazeHorizonCos: 0.95 };
    }
    currentVrm.scene.updateMatrixWorld(true);
    const getPos = (name) => {
        const n =
            currentVrm.humanoid.getRawBoneNode(name) ||
            currentVrm.humanoid.getNormalizedBoneNode(name);
        if (!n) return null;
        const v = new THREE.Vector3();
        n.getWorldPosition(v);
        return v;
    };

    let minWristCos = 0.98;
    for (const side of ['right', 'left']) {
        const pElbow = getPos(`${side}LowerArm`);
        const pWrist = getPos(`${side}Hand`);
        const pMid = getPos(`${side}MiddleProximal`) || getPos(`${side}IndexProximal`);
        if (pElbow && pWrist && pMid) {
            const forearmDir = pWrist.clone().sub(pElbow).normalize();
            const handDir = pMid.clone().sub(pWrist).normalize();
            const c = forearmDir.dot(handDir);
            if (c < minWristCos) minWristCos = c;
        }
    }

    let gazeHorizonCos = 0.96;
    const headNode =
        currentVrm.humanoid.getNormalizedBoneNode('head') ||
        currentVrm.humanoid.getRawBoneNode('head');
    if (headNode) {
        const q = new THREE.Quaternion();
        headNode.getWorldQuaternion(q);
        const fwdVec = new THREE.Vector3(0, 0, 1).applyQuaternion(q).normalize();
        const horiz = new THREE.Vector3(fwdVec.x, 0, fwdVec.z);
        if (horiz.lengthSq() > 1e-5) {
            horiz.normalize();
            gazeHorizonCos = Math.abs(fwdVec.dot(horiz));
        }
    }

    return {
        minWristCos: Number(THREE.MathUtils.clamp(minWristCos, -1.0, 1.0).toFixed(4)),
        thumbOpposed: true,
        gazeHorizonCos: Number(THREE.MathUtils.clamp(gazeHorizonCos, 0.0, 1.0).toFixed(4)),
    };
}

function updateRlRewardHud(evalObj = null, statusObj = null) {
    if (statusObj) {
        lastRlStatusSummary = {
            total_episodes: statusObj.total_episodes ?? lastRlStatusSummary.total_episodes,
            total_awards: statusObj.total_awards ?? lastRlStatusSummary.total_awards,
            cumulative_award_points: statusObj.cumulative_award_points ?? lastRlStatusSummary.cumulative_award_points,
            mean_reward_pct: statusObj.mean_reward_pct ?? lastRlStatusSummary.mean_reward_pct,
        };
    }
    if (evalObj) {
        lastRlEvaluation = evalObj;
        if (typeof evalObj.policy_episodes === 'number') {
            lastRlStatusSummary.total_episodes = evalObj.policy_episodes;
        }
        if (typeof evalObj.policy_total_awards === 'number') {
            lastRlStatusSummary.total_awards = evalObj.policy_total_awards;
        }
        if (typeof evalObj.policy_cumulative_points === 'number') {
            lastRlStatusSummary.cumulative_award_points = evalObj.policy_cumulative_points;
        }
    }

    const badgeEl = document.getElementById('rl-reward-badge');
    const barEl = document.getElementById('rl-reward-bar-fill');
    const detailEl = document.getElementById('rl-telemetry-detail');

    const rewardPct = lastRlEvaluation
        ? Number(lastRlEvaluation.reward_pct ?? 100.0)
        : Number(lastRlStatusSummary.mean_reward_pct ?? 100.0);
    const awards = lastRlStatusSummary.total_awards ?? 0;
    const pts = Math.round(lastRlStatusSummary.cumulative_award_points ?? 0);

    if (badgeEl) {
        const matchIcon = rewardPct >= 88.0 ? '🏆' : '🎯';
        badgeEl.innerText = `${matchIcon} RL Match: ${rewardPct.toFixed(1)}% | Awards: ${awards} (+${pts} pts)`;
        badgeEl.style.color = rewardPct >= 88.0 ? '#00ff88' : '#ffcc00';
        badgeEl.style.borderColor =
            rewardPct >= 88.0 ? 'rgba(0, 255, 136, 0.35)' : 'rgba(255, 204, 0, 0.35)';
    }
    if (barEl) {
        barEl.style.width = `${Math.max(5, Math.min(100, rewardPct))}%`;
    }
    if (detailEl && lastRlEvaluation && lastRlEvaluation.components) {
        const c = lastRlEvaluation.components;
        const pPct = Math.round((c.r_pose ?? c.pose_joint_reward ?? 1) * 100);
        const ikPct = Math.round((c.r_endeff ?? c.end_effector_reward ?? 1) * 100);
        const wPct = Math.round((c.r_wrist_anatomy ?? c.wrist_hand_anatomy_reward ?? 1) * 100);
        const gPct = Math.round((c.r_com_gaze ?? c.com_gaze_balance_reward ?? 1) * 100);
        const sPct = Math.round((c.r_expressive_style ?? c.expressive_style_reward ?? 1) * 100);
        const refName = lastRlEvaluation.reference_pose || currentPose;
        detailEl.innerText = `Ref: ${refName} · Pose:${pPct}% IK:${ikPct}% Wrist:${wPct}% Gaze:${gPct}% Style:${sPct}%`;
    } else if (detailEl && statusObj) {
        const numRef = statusObj.poses ? Object.keys(statusObj.poses).length : 24;
        detailEl.innerText = `Policy Ep: ${lastRlStatusSummary.total_episodes} · Mean Human Match: ${rewardPct.toFixed(1)}% (${numRef} Ref Poses & Styles)`;
    }
}

async function fetchRlPoseStatus() {
    try {
        const res = await fetch('/api/character/rl-status');
        if (res.ok) {
            const st = await res.json();
            if (st && !st.offline) {
                updateRlRewardHud(null, st);
            }
        }
    } catch (e) {}
}

async function triggerRlPoseTraining(poseName = null, episodes = 18, simulateCurriculum = true) {
    const targetPose =
        poseName ||
        (customPoseRegistry.has(currentPose) ? currentPose : 'cyber_salute');
    updateStatus(`⚡ RL Policy Training on Human Reference "${targetPose}" (${episodes} episodes)...`);
    try {
        const res = await fetch('/api/character/rl-train', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pose_name: targetPose,
                episodes,
                simulate_curriculum: simulateCurriculum,
            }),
        });
        if (res.ok) {
            const data = await res.json();
            if (data.character_state) {
                applyCharacterProtocolState(data.character_state);
            }
            if (Array.isArray(data.results) && data.results.length > 0) {
                const lastRes = data.results[data.results.length - 1];
                const finalEval = lastRes.final_evaluation || null;
                updateRlRewardHud(finalEval, {
                    total_episodes: data.policy_total_episodes,
                    total_awards: data.policy_total_awards,
                    cumulative_award_points: data.policy_cumulative_points,
                    mean_reward_pct: finalEval ? finalEval.reward_pct : 100.0,
                });
                const ptsAwarded = Math.round(data.total_award_points_earned || 0);
                updateStatus(
                    `🏆 RL Trained "${lastRes.pose_name}": ${lastRes.initial_reward_pct}% → ${lastRes.final_reward_pct}% | Awarded +${ptsAwarded} pts!`
                );
                return data;
            }
        }
    } catch (e) {}
    updateStatus('⚠️ RL Pose Trainer unreachable — check HELIOS Core (:8000).');
    return null;
}

async function submitRlPoseFeedback(awardDelta = 100.0, poseOverride = null) {
    const targetPose =
        poseOverride ||
        (customPoseRegistry.has(currentPose) ? currentPose : 'cyber_salute');
    const telemetry = computeLiveVrmBiomechanicalTelemetry();
    try {
        const res = await fetch('/api/character/rl-feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pose_name: targetPose,
                user_award_delta: awardDelta,
                browser_telemetry: telemetry,
            }),
        });
        if (res.ok) {
            const data = await res.json();
            if (data.character_state) {
                applyCharacterProtocolState(data.character_state);
            }
            if (data.evaluation) {
                updateRlRewardHud(data.evaluation, {
                    total_episodes: data.policy_total_episodes,
                    total_awards: data.policy_total_awards,
                    cumulative_award_points: data.policy_cumulative_points,
                    mean_reward_pct: data.evaluation.reward_pct,
                });
            }
            const sign = awardDelta >= 0 ? `+${awardDelta}` : `${awardDelta}`;
            updateStatus(
                `${awardDelta >= 0 ? '🏆 Awarded' : '⚠️ Corrected'} "${data.pose_name}" (${sign} RL pts) | Match: ${data.evaluation?.reward_pct ?? 100}%`
            );
        }
    } catch (e) {}
}

async function requestHeliosCustomPose(promptText) {
    const cleanPrompt = (promptText || '').trim();
    if (!cleanPrompt) return;
    if (audioLipSync && audioLipSync.isPlaying) {
        audioLipSync.stopCurrent();
    }
    if (currentState === 'speaking') {
        currentState = 'idle';
    }
    updateStatus(`✨ HELIOS Core (:8000) synthesizing 3D pose: "${cleanPrompt}"...`);
    try {
        const res = await fetch('/api/character/generate-pose', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: cleanPrompt }),
        });
        if (res.ok) {
            const state = await res.json();
            if (state && state.type === 'character_state') {
                applyCharacterProtocolState(state);
                return;
            }
        } else {
            updateStatus(`⚠️ HELIOS Core (:8000) offline — body remains still without HELIOS.`);
        }
    } catch (e) {
        updateStatus(`⚠️ HELIOS Core (:8000) unreachable — body remains still without HELIOS.`);
    }
}

async function triggerSmallAiBodyStep(customPrompt = '') {
    if (!aiBodyEnabled) return;
    const promptText =
        customPrompt ||
        AI_IDLE_BODY_PROMPTS[aiBodyStepIndex++ % AI_IDLE_BODY_PROMPTS.length];
    try {
        const res = await fetch('/api/character/direct-body', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_text: promptText,
                assistant_text: '',
            }),
        });
        if (res.ok) {
            const state = await res.json();
            if (state && state.type === 'character_state') {
                applyCharacterProtocolState(state);
                return;
            }
        }
    } catch (e) {}
    updateStatus('⚠️ HELIOS Core (:8000) is offline — body does not act without HELIOS.');
}

// ----------------------------------------------------
// FILE IMPORT & UI BUTTON LISTENERS
// ----------------------------------------------------
const sidebarToggleBtn = document.getElementById('sidebar-toggle');
const sidebarToggleIcon = document.getElementById('sidebar-toggle-icon');
const sidebarPanel = document.getElementById('top-ui');

if (sidebarToggleBtn && sidebarPanel) {
    sidebarToggleBtn.onclick = () => {
        const isCollapsed = sidebarPanel.classList.toggle('collapsed');
        if (sidebarToggleIcon) {
            sidebarToggleIcon.innerText = isCollapsed ? '▶' : '◀';
        }
    };
}

const btnModelHelios = document.getElementById('btn-model-helios');
const btnModelBase = document.getElementById('btn-model-base');
const btnModelTwin = document.getElementById('btn-model-twin');
const btnModelMeshy = document.getElementById('btn-model-meshy');

const TWIN_VRM_URL = 'models/Helios_Twin.vrm';

function clearModelActiveStates() {
    if (btnModelHelios) btnModelHelios.classList.remove('active');
    if (btnModelBase)   btnModelBase.classList.remove('active');
    if (btnModelTwin)   btnModelTwin.classList.remove('active');
    if (btnModelMeshy)  btnModelMeshy.classList.remove('active');
}

if (btnModelHelios) {
    btnModelHelios.onclick = () => {
        clearModelActiveStates();
        btnModelHelios.classList.add('active');
        loadVRM(DEFAULT_VRM_URL);
    };
}

if (btnModelTwin) {
    btnModelTwin.onclick = () => {
        clearModelActiveStates();
        btnModelTwin.classList.add('active');
        loadVRM(TWIN_VRM_URL);
    };
}

if (btnModelMeshy) {
    btnModelMeshy.onclick = () => {
        clearModelActiveStates();
        btnModelMeshy.classList.add('active');
        loadFBXModel(MESHY_FBX_URL);
    };
}

if (btnModelBase) {
    btnModelBase.onclick = () => {
        clearModelActiveStates();
        btnModelBase.classList.add('active');
        loadVRM(BASE_VRM_URL);
    };
}

const fileInput = document.getElementById('vrm-file-input');
if (fileInput) {
    fileInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (!file) return;
        clearModelActiveStates();
        updateStatus(`Reading ${file.name}...`);
        loadVRM(URL.createObjectURL(file), true);
    });
}

const fbxInput = document.getElementById('fbx-file-input');
if (fbxInput) {
    fbxInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (!file) return;
        updateStatus(`Inspecting FBX: ${file.name}...`);
        const blobUrl = URL.createObjectURL(file);
        fbxLoader.load(
            blobUrl,
            (fbxAsset) => {
                let hasMeshes = false;
                let totalVertices = 0;
                fbxAsset.traverse((child) => {
                    if (child.isMesh && child.geometry) {
                        hasMeshes = true;
                        const pos = child.geometry.attributes.position;
                        if (pos) totalVertices += pos.count;
                    }
                });

                const hasAnimations = Boolean(fbxAsset.animations && fbxAsset.animations.length > 0);

                // If FBX contains 3D character mesh (> 200 vertices), auto-rig and load as character avatar!
                if (hasMeshes && totalVertices > 200 && (!hasAnimations || fbxAsset.children.length > 0)) {
                    clearModelActiveStates();
                    updateStatus(`Auto-Rigging & Loading FBX Model: ${file.name} (${totalVertices.toLocaleString()} vertices)...`);
                    loadFBXModel(blobUrl, true);
                } else if (hasAnimations && currentVrm && animManager) {
                    const clipName = file.name.replace(/\.fbx$/i, '');
                    const clip = extractMixamoFBXClip(fbxAsset, currentVrm, clipName, rigMetrics);
                    if (clip) {
                        animManager.registerClip(clipName, clip);
                        animManager.play(clipName, 0.4, true);
                        updateStatus(`Playing Retargeted Mixamo FBX: ${clipName}`);
                    } else {
                        updateStatus(`Could not find Mixamo tracks in ${file.name}`);
                    }
                    URL.revokeObjectURL(blobUrl);
                } else {
                    updateStatus(`Could not detect mesh or animation in FBX: ${file.name}`);
                    URL.revokeObjectURL(blobUrl);
                }
            },
            undefined,
            (err) => {
                updateStatus('Error loading FBX: ' + err.message);
                URL.revokeObjectURL(blobUrl);
            }
        );
    });
}

document.getElementById('btn-idle').onclick = () => {
    currentEmotion = 'neutral';
    if (navController) navController.executeMovement('idle', camera);
    setTestState('idle', 'idle');
};
document.getElementById('btn-listening').onclick = () => setTestState('listening', 'listen_pose');
document.getElementById('btn-thinking').onclick = () => setTestState('thinking', 'think_pose');
document.getElementById('btn-speaking').onclick = () => {
    speakingPoseIndex = 0;
    setTestState('speaking', null, true);
};
document.getElementById('btn-reset-cam').onclick = () => {
    if (currentVrm) focusOnModel(currentVrm, true);
};

// Voice Controls Listeners
const voiceSelectEl = document.getElementById('voice-select');
if (voiceSelectEl) {
    voiceSelectEl.addEventListener('change', () => {
        selectedVoiceId = voiceSelectEl.value || 'af_heart';
        previewEmotionVoice(currentEmotion);
    });
}

const btnTestVoice = document.getElementById('btn-test-voice');
if (btnTestVoice) {
    btnTestVoice.onclick = () => {
        speakingPoseIndex = 0;
        previewEmotionVoice(currentEmotion);
    };
}

const btnMuteVoice = document.getElementById('btn-mute-voice');
if (btnMuteVoice) {
    btnMuteVoice.onclick = () => {
        voiceMuted = !voiceMuted;
        btnMuteVoice.classList.toggle('active', !voiceMuted);
        btnMuteVoice.innerText = voiceMuted ? '🔇 Lip-Sync: OFF' : '🔊 Lip-Sync: ON';
        if (audioLipSync) {
            audioLipSync.setMuted(voiceMuted);
        }
    };
}

// HELIOS Add-On Bridge & Edition Controls (Full Spec vs. Just the Character)
const heliosStatusPill = document.getElementById('helios-status-pill');
const brainModeSelect = document.getElementById('brain-mode-select');
const btnMirrorHelios = document.getElementById('btn-mirror-helios');
const btnAiBody = document.getElementById('btn-ai-body');
const btnAiBodyStep = document.getElementById('btn-ai-body-step');
const btnEditionFull = document.getElementById('btn-edition-full');
const btnEditionCharacter = document.getElementById('btn-edition-character');
const btnSidebarFullSpec = document.getElementById('btn-sidebar-full-spec');
const btnSidebarCharOnly = document.getElementById('btn-sidebar-char-only');
let mirrorHeliosEvents = true;
let activeHeliosEdition = 'auto';

function updateEditionButtonsUI(edition, connected = false) {
    const isCharOnly = edition === 'character_only' || (!connected && edition !== 'full_spec');
    if (btnEditionFull) {
        btnEditionFull.style.background = !isCharOnly ? 'rgba(0, 229, 255, 0.22)' : 'transparent';
        btnEditionFull.style.color = !isCharOnly ? '#00e5ff' : '#94a3b8';
    }
    if (btnEditionCharacter) {
        btnEditionCharacter.style.background = isCharOnly ? 'rgba(0, 229, 255, 0.22)' : 'transparent';
        btnEditionCharacter.style.color = isCharOnly ? '#00e5ff' : '#94a3b8';
    }
    if (btnSidebarFullSpec) {
        btnSidebarFullSpec.classList.toggle('active', !isCharOnly);
    }
    if (btnSidebarCharOnly) {
        btnSidebarCharOnly.classList.toggle('active', isCharOnly);
    }
    const chatInputEl = document.getElementById('chat-input');
    if (chatInputEl) {
        chatInputEl.placeholder = isCharOnly
            ? 'Chat with HELIOS Character (Standalone AI + TTS)...'
            : 'Send message to HELIOS Full Spec Core (:8000)...';
    }
}

async function selectHeliosEdition(edition) {
    activeHeliosEdition = edition;
    await syncHeliosConfig({ edition });
    if (edition === 'character_only') {
        updateStatus('🎭 Switched to Just the Character (Standalone 3D VRM + Local Chat + Neural TTS)');
    } else {
        updateStatus('⚡ Switched to Full Spec Version (HELIOS Core :8000 + Tools + Sandbox + Character)');
    }
}

if (btnEditionFull) btnEditionFull.onclick = () => selectHeliosEdition('full_spec');
if (btnEditionCharacter) btnEditionCharacter.onclick = () => selectHeliosEdition('character_only');
if (btnSidebarFullSpec) btnSidebarFullSpec.onclick = () => selectHeliosEdition('full_spec');
if (btnSidebarCharOnly) btnSidebarCharOnly.onclick = () => selectHeliosEdition('character_only');

if (btnAiBody) {
    btnAiBody.onclick = () => {
        aiBodyEnabled = !aiBodyEnabled;
        btnAiBody.classList.toggle('active', aiBodyEnabled);
        btnAiBody.innerText = aiBodyEnabled ? '🤖 AI Body: ON' : '🤖 AI Body: OFF';
        updateStatus(`AI Body Director: ${aiBodyEnabled ? 'ENABLED' : 'DISABLED'}`);
    };
}

if (btnAiBodyStep) {
    btnAiBodyStep.onclick = () => {
        aiBodyEnabled = true;
        if (btnAiBody) {
            btnAiBody.classList.add('active');
            btnAiBody.innerText = '🤖 AI Body: ON';
        }
        triggerSmallAiBodyStep();
    };
}

function applyHeliosAddonStatus(status) {
    if (!status) return;
    if (status.renderer) {
        activeRendererType = status.renderer;
        if (brainModeSelect) brainModeSelect.value = status.renderer;
    }
    if (status.edition) {
        activeHeliosEdition = status.edition;
    }
    if (typeof status.mirror_events === 'boolean') {
        mirrorHeliosEvents = status.mirror_events;
        if (btnMirrorHelios) {
            btnMirrorHelios.classList.toggle('active', mirrorHeliosEvents);
            btnMirrorHelios.innerText = mirrorHeliosEvents ? '🔄 Sync State' : '⏸️ Mirror: OFF';
        }
    }
    updateEditionButtonsUI(status.configured_edition || status.edition || activeHeliosEdition, Boolean(status.connected));
    if (heliosStatusPill) {
        if (status.character_only || status.configured_edition === 'character_only') {
            heliosStatusPill.className = 'addon-pill online';
            heliosStatusPill.innerText = '🎭 Just the Character (Standalone)';
        } else if (status.connected) {
            heliosStatusPill.className = 'addon-pill online';
            heliosStatusPill.innerText = '🟢 Full Spec: HELIOS (:8000)';
        } else {
            heliosStatusPill.className = 'addon-pill online';
            heliosStatusPill.innerText = '🎭 Character Standalone (:8000 Off)';
        }
    }
}

async function syncHeliosConfig(patch = {}) {
    try {
        const res = await fetch('/api/helios/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(patch)
        });
        if (res.ok) {
            const st = await res.json();
            applyHeliosAddonStatus(st);
        }
    } catch (e) {}
}

if (brainModeSelect) {
    brainModeSelect.addEventListener('change', () => {
        activeRendererType = brainModeSelect.value || 'vrm';
        syncHeliosConfig({ renderer: activeRendererType });
    });
}

if (btnMirrorHelios) {
    btnMirrorHelios.onclick = () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'character_sync' }));
        }
        mirrorHeliosEvents = !mirrorHeliosEvents;
        syncHeliosConfig({ mirror_events: mirrorHeliosEvents });
    };
}

if (heliosStatusPill) {
    heliosStatusPill.style.cursor = 'pointer';
    heliosStatusPill.onclick = async () => {
        try {
            const res = await fetch('/api/helios/status');
            if (res.ok) applyHeliosAddonStatus(await res.json());
        } catch (e) {}
    };
}

document.querySelectorAll('#nav-buttons button').forEach(btn => {
    btn.onclick = () => {
        const navMode = btn.getAttribute('data-nav');
        if (navController) navController.executeMovement(navMode, camera, 'idle');
    };
});

const IDLE_INTERACTION_DESCRIPTIONS = {
    idle_popup_curious: {
        status: '🪟 Curious Idle: Inspecting & poking the floating HELIOS Popup HUD',
        popupBadge: 'INSPECTING',
        popupBody: 'HELIOS avatar is curiously inspecting & poking the telemetry popup...',
        emotion: 'curious',
    },
    idle_orb_curious: {
        status: '🔮 Curious Idle: Cradling & spinning the floating HELIOS Core Orb',
        popupBadge: 'CORE ORB',
        popupBody: 'HELIOS avatar is curiously interacting with the floating Core Data Orb...',
        emotion: 'curious',
    },
    idle_screen_curious: {
        status: '👆 Curious Idle: Leaning in & tapping the viewer glass',
        popupBadge: 'GLASS TAP',
        popupBody: 'Operator detected! Curiously tapping the viewport glass...',
        emotion: 'curious',
    },
    idle_waiting_patient: {
        status: '⏳ Waiting Idle: Patiently waiting with clasped hands & gentle sway',
        popupBadge: 'WAITING',
        popupBody: 'Standing by patiently with clasped hands, ready for your command.',
        emotion: 'relaxed',
    },
    idle_waiting_look: {
        status: '👀 Waiting Idle: Glancing around the room & checking wrist HUD',
        popupBadge: 'SCANNING',
        popupBody: 'Checking wrist telemetry HUD and looking around while waiting...',
        emotion: 'neutral',
    },
    idle_waiting_stretch: {
        status: '🙆‍♀️ Waiting Idle: Doing a relaxed shoulder & arm stretch while waiting',
        popupBadge: 'STRETCHING',
        popupBody: 'Taking a relaxed shoulder & arm stretch while waiting on standby.',
        emotion: 'relaxed',
    },
};

let autoIdleEnabled = true;
let autoIdleTimer = 0;
let autoIdlePoseIndex = 0;
const AUTO_IDLE_REST_DURATION = 5.5;
const AUTO_IDLE_ACTION_DURATION = 6.2;

function triggerIdleObjectOrWaitingAnimation(poseName, manual = false) {
    const cleanPose = poseName || 'idle_popup_curious';
    if (audioLipSync && audioLipSync.isPlaying) {
        audioLipSync.stopCurrent();
    }
    pendingSpeechChunks = 0;
    currentState = 'idle';
    applyStateVisualTheme('idle');
    setPose(cleanPose, manual ? 0 : Math.round(AUTO_IDLE_ACTION_DURATION * 1000));
    const meta = IDLE_INTERACTION_DESCRIPTIONS[cleanPose];
    if (meta) {
        applyExpressionState(meta.emotion || 'curious', 0.58);
        updateStatus(meta.status);
    } else {
        updateStatus(`Idle Animation: ${cleanPose}`);
    }
}
window.triggerIdleObjectOrWaitingAnimation = triggerIdleObjectOrWaitingAnimation;

const btnAutoIdle = document.getElementById('btn-auto-idle');
if (btnAutoIdle) {
    btnAutoIdle.onclick = () => {
        autoIdleEnabled = !autoIdleEnabled;
        btnAutoIdle.classList.toggle('active', autoIdleEnabled);
        btnAutoIdle.innerText = autoIdleEnabled ? '🔄 Auto-Idle: ON' : '⏸️ Auto-Idle: OFF';
        autoIdleTimer = 0;
        if (!autoIdleEnabled && isIdleObjectOrWaitingPose(currentPose)) {
            setPose('idle');
        }
        updateStatus(`Autonomous Curious/Waiting Idle: ${autoIdleEnabled ? 'ENABLED' : 'PAUSED'}`);
    };
}

document.querySelectorAll('#idle-interaction-buttons button').forEach(btn => {
    btn.onclick = () => {
        const p = btn.getAttribute('data-pose');
        autoIdleTimer = 0;
        triggerIdleObjectOrWaitingAnimation(p, true);
    };
});

const heliosInteractivePopupEl = document.getElementById('helios-interactive-popup');
const heliosPopupBadgeEl = document.getElementById('helios-popup-badge');
const heliosPopupBodyEl = document.getElementById('helios-popup-body');
const screenTapRippleEl = document.getElementById('screen-tap-ripple');

if (heliosInteractivePopupEl) {
    heliosInteractivePopupEl.onclick = () => {
        autoIdleTimer = 0;
        triggerIdleObjectOrWaitingAnimation('idle_popup_curious', true);
    };
}

document.querySelectorAll('#pose-buttons button').forEach(btn => {
    btn.onclick = () => {
        const p = btn.getAttribute('data-pose');
        autoIdleTimer = 0;
        setPose(p);
        if (p === 'talk_explain') {
            previewEmotionVoice('neutral', 'talk_explain');
        } else if (p === 'talk_excited') {
            previewEmotionVoice('happy', 'talk_excited');
        } else if (p === 'talk_smug') {
            previewEmotionVoice('smug', 'talk_smug');
        } else if (p === 'talk_angry') {
            previewEmotionVoice('angry', 'talk_angry');
        } else if (p === 'talk_sad') {
            previewEmotionVoice('sad', 'talk_sad');
        } else if (p === 'talk_surprised') {
            previewEmotionVoice('surprised', 'talk_surprised');
        } else if (p === 'smug_pose') {
            applyExpressionState('smug');
            updateStatus(`Pose: ${p} | State: ${currentState}`);
        } else {
            updateStatus(`Pose: ${p} | State: ${currentState}`);
        }
    };
});

document.querySelectorAll('#style-buttons button').forEach(btn => {
    btn.onclick = () => {
        const s = btn.getAttribute('data-style') || 'natural';
        setStyleMode(s, true);
        updateStatus(`🎭 Human Posture Style: ${s.toUpperCase()} | Pose: ${currentPose} | Emotion: ${currentEmotion}`);
    };
});

let lastSelectedCustomPose = 'cyber_salute';

document.querySelectorAll('#custom-pose-buttons button').forEach(btn => {
    btn.onclick = () => {
        const customKey = btn.getAttribute('data-custom-pose');
        if (customKey) lastSelectedCustomPose = customKey;
        const prompt = btn.getAttribute('data-pose-prompt') || customKey || '';
        if (customPoseRegistry.has(customKey)) {
            const cachedPose = customPoseRegistry.get(customKey);
            setPose(customKey, 0);
            if (cachedPose && cachedPose.style) {
                setStyleMode(cachedPose.style, false);
            }
            if (cachedPose && cachedPose.rl_evaluation) {
                updateRlRewardHud(cachedPose.rl_evaluation, null);
            }
            const rlBadge = cachedPose && typeof cachedPose.rl_reward_pct === 'number'
                ? ` [🏆 RL ${cachedPose.rl_reward_pct.toFixed(1)}%]`
                : '';
            const styleBadge = cachedPose && cachedPose.style ? ` | Style: ${cachedPose.style}` : '';
            updateStatus(`HELIOS Custom Pose: ${customKey}${styleBadge}${rlBadge}`);
        } else {
            requestHeliosCustomPose(prompt);
        }
    };
});

const customPoseInputEl = document.getElementById('custom-pose-input');
const btnCreatePoseEl = document.getElementById('btn-create-pose');
if (btnCreatePoseEl && customPoseInputEl) {
    btnCreatePoseEl.onclick = () => {
        const prompt = customPoseInputEl.value.trim();
        if (prompt) {
            requestHeliosCustomPose(prompt);
        }
    };
    customPoseInputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const prompt = customPoseInputEl.value.trim();
            if (prompt) {
                requestHeliosCustomPose(prompt);
            }
        }
    });
}

// RL Pose Trainer & Online Reward Listeners
const btnRlTrain = document.getElementById('btn-rl-train');
const btnRlTrainAll = document.getElementById('btn-rl-train-all');
const btnRlAward = document.getElementById('btn-rl-award');
const btnRlPenalize = document.getElementById('btn-rl-penalize');

if (btnRlTrain) {
    btnRlTrain.onclick = () => {
        const target = lastSelectedCustomPose || (customPoseRegistry.has(currentPose) ? currentPose : 'cyber_salute');
        triggerRlPoseTraining(target, 18, true);
    };
}
if (btnRlTrainAll) {
    btnRlTrainAll.onclick = () => {
        triggerRlPoseTraining('all', 5, true);
    };
}
if (btnRlAward) {
    btnRlAward.onclick = () => {
        submitRlPoseFeedback(100.0, lastSelectedCustomPose);
    };
}
if (btnRlPenalize) {
    btnRlPenalize.onclick = () => {
        submitRlPoseFeedback(-50.0, lastSelectedCustomPose);
    };
}

// ----------------------------------------------------
// INTERACTIVE 3D CHARACTER OBJECTS & AUTONOMOUS IDLE DIRECTOR
// ----------------------------------------------------
let lastScreenTapState = false;
const _charBoneWorldPos = new THREE.Vector3();
const _charPopupTargetPos = new THREE.Vector3();
const _charOrbTargetPos = new THREE.Vector3();
const _raycaster3D = new THREE.Raycaster();
const _pointerNDC = new THREE.Vector2();

// Allow clicking directly on the character's 3D Holographic Popup or 3D Core Orb in the 3D scene
if (container) {
    container.addEventListener('pointerdown', (e) => {
        if (!interactiveSceneObjects || !camera) return;
        const rect = container.getBoundingClientRect();
        _pointerNDC.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        _pointerNDC.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
        _raycaster3D.setFromCamera(_pointerNDC, camera);
        const targets = [
            interactiveSceneObjects.panelMesh,
            interactiveSceneObjects.coreMesh,
            interactiveSceneObjects.innerMesh,
        ].filter(Boolean);
        const hits = _raycaster3D.intersectObjects(targets, false);
        if (hits.length > 0) {
            const hitType = hits[0].object?.userData?.interactiveType;
            autoIdleTimer = 0;
            if (hitType === 'orb') {
                triggerIdleObjectOrWaitingAnimation('idle_orb_curious', true);
            } else {
                triggerIdleObjectOrWaitingAnimation('idle_popup_curious', true);
            }
        }
    });
}

// Exact Canvas renderer for the AI Core Black Hole SVG (viewBox 0 0 240 240)
function drawBlackHoleSvgOnCanvas(ctx, cx, cy, scale, elapsed, accentColor, horizonGlowColor, waveOpacity = 0.45) {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.scale(scale, scale);

    // 1. Expanding speak-wave-1 & speak-wave-2 circles (cx=120, cy=120, r=42 in 240x240 space)
    if (waveOpacity > 0.01) {
        for (let wIdx = 0; wIdx < 2; wIdx++) {
            const phase = ((elapsed + wIdx * 0.6) % 1.8) / 1.8;
            const waveScale = 0.8 + phase * 1.7; // 0.8 -> 2.5
            const alpha = (1.0 - phase) * waveOpacity;
            ctx.beginPath();
            ctx.arc(0, 0, 42 * waveScale, 0, Math.PI * 2);
            ctx.strokeStyle = accentColor;
            ctx.globalAlpha = Math.max(0, alpha);
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }
        ctx.globalAlpha = 1.0;
    }

    // 2. Rotated -15deg accretion disk & Event Horizon (<g transform="rotate(-15 120 120)">)
    ctx.save();
    ctx.rotate((-15 * Math.PI) / 180);

    // Back outer elliptical arc: M 20,120 A 100,30 0 0,1 220,120 (ring-back, #2C3038, stroke-width 1)
    ctx.beginPath();
    ctx.ellipse(0, 0, 100, 30, 0, Math.PI, Math.PI * 2, false);
    ctx.strokeStyle = '#2C3038';
    ctx.lineWidth = 1.0;
    ctx.setLineDash([]);
    ctx.stroke();

    // Back middle elliptical arc: M 35,120 A 85,22 0 0,1 205,120 (ring-back spin-slow, #2C3038, stroke-width 1.5)
    ctx.beginPath();
    ctx.ellipse(0, 0, 85, 22, 0, Math.PI, Math.PI * 2, false);
    ctx.strokeStyle = '#2C3038';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([60, 120]);
    ctx.lineDashOffset = -(elapsed * 45) % 360;
    ctx.stroke();

    // Event Horizon: <circle cx="120" cy="120" r="44" class="event-horizon" />
    ctx.setLineDash([]);
    ctx.save();
    ctx.beginPath();
    ctx.arc(0, 0, 44, 0, Math.PI * 2);
    ctx.fillStyle = '#050507';
    ctx.shadowColor = horizonGlowColor;
    ctx.shadowBlur = 20;
    ctx.fill();
    ctx.lineWidth = 2.0;
    ctx.strokeStyle = '#2C3038';
    ctx.stroke();
    ctx.restore();

    // Front inner photon ring: M 50,120 A 70,16 0 0,0 190,120 (stroke-dasharray="2 6", opacity 0.5)
    ctx.beginPath();
    ctx.ellipse(0, 0, 70, 16, 0, 0, Math.PI, false);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
    ctx.lineWidth = 1.0;
    ctx.setLineDash([2, 6]);
    ctx.lineDashOffset = 0;
    ctx.stroke();

    // Front outer spinning ring: M 20,120 A 100,30 0 0,0 220,120 (spin-slow, #FFFFFF, stroke-width 1.5)
    ctx.beginPath();
    ctx.ellipse(0, 0, 100, 30, 0, 0, Math.PI, false);
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([60, 120]);
    ctx.lineDashOffset = -(elapsed * 45) % 360;
    ctx.stroke();

    // Front middle fast-spinning ring: M 35,120 A 85,22 0 0,0 205,120 (spin-fast, accent-color, stroke-width 2)
    ctx.beginPath();
    ctx.ellipse(0, 0, 85, 22, 0, 0, Math.PI, false);
    ctx.strokeStyle = accentColor;
    ctx.lineWidth = 2.0;
    ctx.setLineDash([10, 30]);
    ctx.lineDashOffset = (elapsed * 75) % 360;
    ctx.stroke();

    ctx.setLineDash([]);
    ctx.restore();

    // 3. Crosshair Reticle Ticks (<line ... stroke="#EBF0F5" stroke-width="1" opacity="0.4"/>)
    ctx.strokeStyle = 'rgba(235, 240, 245, 0.45)';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    // Top: (120,65) -> (120,70) => (0,-55) -> (0,-50)
    ctx.moveTo(0, -55);
    ctx.lineTo(0, -50);
    // Bottom: (120,170) -> (120,175) => (0,50) -> (0,55)
    ctx.moveTo(0, 50);
    ctx.lineTo(0, 55);
    // Left: (65,120) -> (70,120) => (-55,0) -> (-50,0)
    ctx.moveTo(-55, 0);
    ctx.lineTo(-50, 0);
    // Right: (170,120) -> (175,120) => (50,0) -> (55,0)
    ctx.moveTo(50, 0);
    ctx.lineTo(55, 0);
    ctx.stroke();

    ctx.restore();
}

// Render the 3D Black Hole Orb canvas texture (matches black-hole-svg from the popup)
function render3dBlackHoleOrbCanvas(ctx, canvas, elapsed) {
    if (!ctx || !canvas) return;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const accentColor =
        currentState === 'thinking'
            ? '#FFCC00'
            : currentState === 'speaking'
            ? '#3296fa'
            : '#00e5ff';
    const glowColor =
        currentState === 'thinking'
            ? 'rgba(255, 204, 0, 0.38)'
            : currentState === 'speaking'
            ? 'rgba(50, 150, 250, 0.42)'
            : 'rgba(0, 229, 255, 0.35)';

    drawBlackHoleSvgOnCanvas(ctx, w * 0.5, h * 0.5, (w / 240) * 0.96, elapsed, accentColor, glowColor, 0.55);
}

// Render the exact AI Core Popup (body.mode-menu .widget-container 650x320) onto the 3D CanvasTexture
function render3dHeliosPopupCanvas(ctx, canvas, elapsed, pokeImpact, isPopupCurious) {
    if (!ctx || !canvas) return;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Coordinate system: 650x320 scaled 2x to 1300x640
    const dpi = w / 650;
    ctx.save();
    ctx.scale(dpi, dpi);

    const stateAccent =
        currentState === 'thinking'
            ? '#FFCC00'
            : currentState === 'speaking'
            ? '#3296fa'
            : '#00e5ff';
    const glowRgba =
        currentState === 'thinking'
            ? 'rgba(255, 204, 0, 0.3)'
            : currentState === 'speaking'
            ? 'rgba(50, 150, 250, 0.4)'
            : 'rgba(0, 229, 255, 0.25)';

    // 1. Rounded .widget-container (650x320, border-radius: 20px, linear-gradient(135deg, #1a1c23 0%, #0D0E12 100%))
    ctx.beginPath();
    if (ctx.roundRect) {
        ctx.roundRect(2, 2, 646, 316, 20);
    } else {
        ctx.rect(2, 2, 646, 316);
    }
    ctx.save();
    ctx.clip();

    const bgGrad = ctx.createLinearGradient(0, 0, 650, 320);
    bgGrad.addColorStop(0, '#1a1c23');
    bgGrad.addColorStop(1, '#0D0E12');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, 650, 320);

    // Subtle diagonal split-card shear & kinetic watermark inside the widget
    ctx.fillStyle = 'rgba(8, 9, 12, 0.55)';
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(650, 0);
    ctx.lineTo(650, 58);
    ctx.lineTo(0, 262);
    ctx.closePath();
    ctx.fill();

    ctx.font = '900 72px "Helvetica Neue", Arial, sans-serif';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.025)';
    const kineticWord =
        currentState === 'thinking'
            ? 'PARADOX'
            : currentState === 'speaking'
            ? 'PROMISE'
            : 'RESONANCE';
    ctx.fillText(kineticWord, 18, 78);

    // 2. Left Side: .widget-inner (left: 160px, top: 150px, scale(0.85)) with .black-hole-svg
    drawBlackHoleSvgOnCanvas(ctx, 160, 144, 0.85, elapsed, stateAccent, glowRgba, 0.45);

    // 3. Attached .status-badge (left: 160px, bottom: 25px, border-radius: 20px)
    const statusLabel = (currentState === 'idle' ? 'RESONANCE' : currentState).toUpperCase();
    ctx.font = '700 10px "Helvetica Neue", Arial, sans-serif';
    const badgeW = Math.max(96, ctx.measureText(statusLabel).width + 48);
    const badgeX = 160 - badgeW * 0.5;
    const badgeY = 320 - 25 - 28;
    ctx.beginPath();
    if (ctx.roundRect) {
        ctx.roundRect(badgeX, badgeY, badgeW, 28, 20);
    } else {
        ctx.rect(badgeX, badgeY, badgeW, 28);
    }
    ctx.fillStyle = '#0D0E12';
    ctx.fill();
    ctx.lineWidth = 1;
    ctx.strokeStyle = '#2C3038';
    ctx.stroke();

    // Pulsing .status-dot (6x6 square)
    const pulseScale = 0.85 + 0.35 * Math.abs(Math.sin(elapsed * 2.6));
    const dotSize = 6 * pulseScale;
    ctx.save();
    ctx.fillStyle = stateAccent;
    ctx.shadowColor = stateAccent;
    ctx.shadowBlur = 8;
    ctx.fillRect(badgeX + 16 - dotSize * 0.5, badgeY + 14 - dotSize * 0.5, dotSize, dotSize);
    ctx.restore();

    ctx.fillStyle = '#EBF0F5';
    ctx.font = '700 10px "Helvetica Neue", Arial, sans-serif';
    ctx.fillText(statusLabel.split('').join(' '), badgeX + 30, badgeY + 18);

    // 4. Right Side: .options-panel (right: 40px, width: 300px => x = 310..610)
    const panelX = 310;
    const panelW = 300;
    ctx.font = '700 10px "Helvetica Neue", Arial, sans-serif';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.fillText('S Y S T E M   A C C E S S', panelX, 54);
    ctx.beginPath();
    ctx.moveTo(panelX, 62);
    ctx.lineTo(panelX + panelW, 62);
    ctx.strokeStyle = '#2C3038';
    ctx.lineWidth = 1;
    ctx.stroke();

    const menuChoices = [
        '01 // NEURAL SYNC',
        '02 // TACTICAL GRID',
        '03 // PARADOX ENGINE',
        '04 // STANDBY MODE',
    ];
    // Highlight the option button the character is currently inspecting/poking
    const activeIdx = Math.floor((elapsed * 0.75) % menuChoices.length);

    menuChoices.forEach((label, idx) => {
        const btnY = 76 + idx * 52;
        const btnH = 42;
        const isHovered = isPopupCurious && idx === activeIdx;

        ctx.fillStyle = isHovered ? 'rgba(255, 255, 255, 0.08)' : 'rgba(255, 255, 255, 0.02)';
        ctx.fillRect(panelX, btnY, panelW, btnH);
        ctx.strokeStyle = isHovered ? stateAccent : '#2C3038';
        ctx.lineWidth = isHovered ? 1.5 : 1.0;
        ctx.strokeRect(panelX, btnY, panelW, btnH);

        ctx.font = '600 11px "Helvetica Neue", Arial, sans-serif';
        ctx.fillStyle = isHovered ? '#FFFFFF' : '#EBF0F5';
        const textPadLeft = isHovered ? 28 : 20;
        ctx.fillText(label, panelX + textPadLeft, btnY + 25);

        // '+' indicator on the right of each .option-btn
        ctx.font = '300 16px "Helvetica Neue", Arial, sans-serif';
        ctx.fillStyle = isHovered ? stateAccent : 'rgba(235, 240, 245, 0.5)';
        ctx.fillText('+', panelX + panelW - 26, btnY + 26);

        // Touch ripple on the active option button when character's fingertip pokes it
        if (isHovered && pokeImpact > 0.15) {
            const rx = panelX + panelW * 0.55;
            const ry = btnY + btnH * 0.5;
            const rad = 8 + pokeImpact * 34;
            ctx.beginPath();
            ctx.arc(rx, ry, rad, 0, Math.PI * 2);
            ctx.strokeStyle = stateAccent;
            ctx.globalAlpha = Math.max(0, 0.9 - pokeImpact * 0.65);
            ctx.lineWidth = 2;
            ctx.stroke();
            ctx.globalAlpha = 1.0;
        }
    });

    ctx.restore();

    // Outer rounded border of .widget-container
    ctx.beginPath();
    if (ctx.roundRect) {
        ctx.roundRect(2, 2, 646, 316, 20);
    } else {
        ctx.rect(2, 2, 646, 316);
    }
    ctx.strokeStyle = isPopupCurious ? 'rgba(0, 229, 255, 0.45)' : '#2C3038';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.restore();
}

function updateInteractiveObjectsAndHud(delta, elapsed) {
    if (!interactiveSceneObjects) return;
    const {
        popupGroup,
        panelMat,
        popupCanvas,
        popupCtx,
        popupTexture,
        touchRing,
        ringMat,
        projectorGroup,
        projectorEmitterRing,
        projectorEmitterMat,
        projectorBeamGeo,
        projectorBeamMat,
        orbGroup,
        orbCanvas,
        orbCtx,
        orbTexture,
        coreMesh,
        coreMat,
        innerMesh,
        innerMat,
        gyroRing,
        gyroRing2,
        gyroMat,
        screenRingGroup,
        glassOuterRing,
        glassInnerRing,
        glassRingMat,
        glassInnerMat,
        wristHudGroup,
        wristPlaneMat,
        wristEdgeMat,
    } = interactiveSceneObjects;

    const h = currentVrm?.humanoid;
    if (currentVrm?.scene) {
        currentVrm.scene.updateMatrixWorld(true);
    }

    const isPopupCurious = currentPose === 'idle_popup_curious';
    const isOrbCurious = currentPose === 'idle_orb_curious';
    const isScreenCurious = currentPose === 'idle_screen_curious';
    const isWristLook = currentPose === 'idle_waiting_look';

    const phaseT = Math.max(0, elapsed - idleInteractionStartTime);
    const pokeWave = isPopupCurious ? Math.max(0, Math.sin(phaseT * 4.2)) : 0;
    const pokeImpact = isPopupCurious ? Math.pow(pokeWave, 4) : 0;

    const rTipBone =
        h?.getNormalizedBoneNode('rightIndexDistal') || h?.getNormalizedBoneNode('rightHand');
    const lTipBone =
        h?.getNormalizedBoneNode('leftIndexDistal') || h?.getNormalizedBoneNode('leftHand');
    const rHandBone = h?.getNormalizedBoneNode('rightHand');
    const lHandBone = h?.getNormalizedBoneNode('leftHand');

    // 1. Update 3D AI Core Popup Widget — Faces the MODEL (rotation.y ≈ Math.PI), Projected by Left Arm, Interacted with by Right Arm
    const targetPanelOpacity = isPopupCurious ? 0.88 : 0.0;
    panelMat.opacity = THREE.MathUtils.lerp(panelMat.opacity, targetPanelOpacity, delta * 8.0);
    if (projectorEmitterMat) {
        projectorEmitterMat.opacity = THREE.MathUtils.lerp(
            projectorEmitterMat.opacity,
            isPopupCurious ? 0.88 : 0.0,
            delta * 8.0
        );
    }
    if (projectorBeamMat) {
        projectorBeamMat.opacity = THREE.MathUtils.lerp(
            projectorBeamMat.opacity,
            isPopupCurious ? 0.52 : 0.0,
            delta * 8.0
        );
    }

    if (panelMat.opacity > 0.01) {
        popupGroup.visible = true;
        if (projectorGroup) projectorGroup.visible = true;

        let emitterX = 0.085;
        let emitterY = 1.00;
        let emitterZ = 0.21;
        if (lHandBone) {
            lHandBone.getWorldPosition(_charBoneWorldPos);
            emitterX = _charBoneWorldPos.x;
            emitterY = _charBoneWorldPos.y + 0.022;
            emitterZ = _charBoneWorldPos.z + 0.012;
        }

        // Position the 3D Popup in front of the model facing the model (rotation.y ≈ Math.PI)
        // so the model's right index finger (rTipBone) taps the model-facing front surface of the SYSTEM ACCESS buttons
        const activeOptIdx = Math.floor((elapsed * 0.75) % 4);
        const optLocalY = (1.5 - activeOptIdx) * 0.022;
        if (isPopupCurious && rTipBone) {
            rTipBone.getWorldPosition(_charBoneWorldPos);
            _charPopupTargetPos.set(
                _charBoneWorldPos.x + 0.085,
                emitterY + 0.152,
                _charBoneWorldPos.z + 0.008 + pokeImpact * 0.012
            );
            popupGroup.position.lerp(_charPopupTargetPos, Math.min(1.0, delta * 9.0));
        } else {
            _charPopupTargetPos.set(emitterX - 0.06, emitterY + 0.152, emitterZ + 0.02);
            popupGroup.position.lerp(_charPopupTargetPos, Math.min(1.0, delta * 9.0));
        }

        // Rotate ~180 deg around Y (Math.PI) so the FRONT of the popup faces the MODEL (not the user)
        popupGroup.rotation.set(
            0.03 - pokeImpact * 0.07,
            Math.PI - 0.05 + pokeImpact * 0.08,
            Math.sin(elapsed * 1.5) * 0.012
        );
        const targetPopupScale = isPopupCurious ? 0.94 : 0.60;
        popupGroup.scale.lerp(
            new THREE.Vector3(targetPopupScale, targetPopupScale, targetPopupScale),
            Math.min(1.0, delta * 7.0)
        );

        // Update Left-Wrist Holographic Projector Emitter Ring & 5 Projection Frustum Rays -> Popup Bottom Edge
        if (projectorEmitterRing) {
            projectorEmitterRing.position.set(emitterX, emitterY, emitterZ);
            const pulseS = 0.9 + 0.2 * Math.sin(elapsed * 6.0);
            projectorEmitterRing.scale.set(pulseS, pulseS, 1);
        }
        if (projectorBeamGeo) {
            const posAttr = projectorBeamGeo.getAttribute('position');
            const px = popupGroup.position.x;
            const py = popupGroup.position.y;
            const pz = popupGroup.position.z;
            const hw = 0.175 * popupGroup.scale.x;
            const hh = 0.086 * popupGroup.scale.y;
            const corners = [
                [px - hw, py - hh, pz],
                [px - hw * 0.5, py - hh, pz],
                [px, py - hh, pz],
                [px + hw * 0.5, py - hh, pz],
                [px + hw, py - hh, pz],
            ];
            corners.forEach((c, idx) => {
                const base = idx * 2;
                posAttr.setXYZ(base, emitterX, emitterY, emitterZ);
                posAttr.setXYZ(base + 1, c[0], c[1], c[2]);
            });
            posAttr.needsUpdate = true;
        }

        render3dHeliosPopupCanvas(popupCtx, popupCanvas, elapsed, pokeImpact, isPopupCurious);
        if (popupTexture) popupTexture.needsUpdate = true;

        // Place 3D touchRing on the model-facing front (+Z local = -Z world) of the SYSTEM ACCESS button being poked by the right index finger
        touchRing.position.set(0.085, optLocalY, 0.004);
        if (isPopupCurious && pokeImpact > 0.25) {
            const ringScale = 0.65 + pokeImpact * 1.5;
            touchRing.scale.set(ringScale, ringScale, 1);
            ringMat.opacity = (1.0 - (pokeImpact - 0.25) / 0.75) * 0.9;
        } else {
            ringMat.opacity = THREE.MathUtils.lerp(ringMat.opacity, 0.0, delta * 8.0);
        }
    } else {
        popupGroup.visible = false;
        if (projectorGroup) projectorGroup.visible = false;
        ringMat.opacity = 0.0;
    }

    // 2. Update 3D Black Hole Orb — ONLY visible when being interacted with (idle_orb_curious)
    const targetOrbOpacity = isOrbCurious ? 0.98 : 0.0;
    coreMat.opacity = THREE.MathUtils.lerp(coreMat.opacity, targetOrbOpacity, delta * 8.0);
    innerMat.opacity = THREE.MathUtils.lerp(innerMat.opacity, isOrbCurious ? 0.98 : 0.0, delta * 8.0);
    gyroMat.opacity = THREE.MathUtils.lerp(gyroMat.opacity, isOrbCurious ? 0.45 : 0.0, delta * 8.0);

    if (coreMat.opacity > 0.01) {
        orbGroup.visible = true;
        if (isOrbCurious && lHandBone) {
            lHandBone.getWorldPosition(_charBoneWorldPos);
            _charOrbTargetPos.set(
                _charBoneWorldPos.x - 0.015,
                _charBoneWorldPos.y + 0.08 + Math.sin(elapsed * 3.0) * 0.012,
                _charBoneWorldPos.z + 0.045
            );
            orbGroup.position.lerp(_charOrbTargetPos, Math.min(1.0, delta * 9.0));
        }
        if (camera) {
            coreMesh.lookAt(camera.position);
        }
        render3dBlackHoleOrbCanvas(orbCtx, orbCanvas, elapsed);
        if (orbTexture) orbTexture.needsUpdate = true;

        gyroRing.rotation.z = THREE.MathUtils.degToRad(-15) + Math.sin(elapsed * 1.8) * 0.08;
        if (gyroRing2) {
            gyroRing2.rotation.z = THREE.MathUtils.degToRad(-15) - Math.cos(elapsed * 1.8) * 0.08;
        }
        const orbScale = isOrbCurious ? 1.05 + Math.sin(elapsed * 4.0) * 0.05 : 0.5;
        orbGroup.scale.lerp(new THREE.Vector3(orbScale, orbScale, orbScale), Math.min(1.0, delta * 7.0));
    } else {
        orbGroup.visible = false;
    }

    // 3. Update 3D Viewport Glass Touch Ring — ONLY visible during idle_screen_curious
    const tapPulse = isScreenCurious ? Math.max(0, Math.sin(phaseT * 4.6)) : 0;
    const tapStrength = isScreenCurious ? Math.pow(tapPulse, 4) : 0;
    if (isScreenCurious && rTipBone && screenRingGroup) {
        screenRingGroup.visible = true;
        rTipBone.getWorldPosition(_charBoneWorldPos);
        screenRingGroup.position.set(
            _charBoneWorldPos.x,
            _charBoneWorldPos.y,
            _charBoneWorldPos.z + 0.015
        );
        screenRingGroup.lookAt(camera.position);
        const outerScale = 0.85 + tapStrength * 1.65;
        glassOuterRing.scale.set(outerScale, outerScale, 1);
        glassInnerRing.scale.setScalar(0.8 + Math.sin(elapsed * 6.0) * 0.2);
        glassRingMat.opacity = THREE.MathUtils.lerp(
            glassRingMat.opacity,
            0.45 + tapStrength * 0.55,
            delta * 10.0
        );
        glassInnerMat.opacity = THREE.MathUtils.lerp(glassInnerMat.opacity, 0.85, delta * 10.0);
    } else if (screenRingGroup) {
        glassRingMat.opacity = THREE.MathUtils.lerp(glassRingMat.opacity, 0.0, delta * 8.0);
        glassInnerMat.opacity = THREE.MathUtils.lerp(glassInnerMat.opacity, 0.0, delta * 8.0);
        if (glassRingMat.opacity <= 0.01) {
            screenRingGroup.visible = false;
        }
    }

    if (screenTapRippleEl) {
        const isTappingNow = isScreenCurious && tapStrength > 0.58;
        if (isTappingNow && !lastScreenTapState) {
            screenTapRippleEl.classList.remove('active');
            void screenTapRippleEl.offsetWidth;
            screenTapRippleEl.classList.add('active');
        }
        lastScreenTapState = isTappingNow;
    }

    // 4. Update 3D Cybernetic Wrist Hologram — ONLY visible during idle_waiting_look
    if (isWristLook && lHandBone && wristHudGroup) {
        wristHudGroup.visible = true;
        lHandBone.getWorldPosition(_charBoneWorldPos);
        wristHudGroup.position.set(
            _charBoneWorldPos.x,
            _charBoneWorldPos.y + 0.055,
            _charBoneWorldPos.z + 0.02
        );
        wristHudGroup.rotation.set(-0.35, -0.25, Math.sin(elapsed * 3.0) * 0.04);
        wristPlaneMat.opacity = THREE.MathUtils.lerp(wristPlaneMat.opacity, 0.55, delta * 8.0);
        wristEdgeMat.opacity = THREE.MathUtils.lerp(wristEdgeMat.opacity, 0.92, delta * 8.0);
    } else if (wristHudGroup) {
        wristPlaneMat.opacity = THREE.MathUtils.lerp(wristPlaneMat.opacity, 0.0, delta * 8.0);
        wristEdgeMat.opacity = THREE.MathUtils.lerp(wristEdgeMat.opacity, 0.0, delta * 8.0);
        if (wristEdgeMat.opacity <= 0.01) {
            wristHudGroup.visible = false;
        }
    }
}

function updateAutonomousIdleDirector(delta) {
    if (
        !autoIdleEnabled ||
        currentState !== 'idle' ||
        (audioLipSync && audioLipSync.isPlaying) ||
        pendingSpeechChunks > 0 ||
        (navController && navController.isNavigating) ||
        customPoseRegistry.has(currentPose) ||
        isSpecialTrickPose(currentPose)
    ) {
        autoIdleTimer = 0;
        return;
    }

    autoIdleTimer += delta;
    if (currentPose === 'idle' && autoIdleTimer >= AUTO_IDLE_REST_DURATION) {
        autoIdleTimer = 0;
        const nextIdlePose =
            IDLE_OBJECT_AND_WAITING_POSES[autoIdlePoseIndex % IDLE_OBJECT_AND_WAITING_POSES.length];
        autoIdlePoseIndex = (autoIdlePoseIndex + 1) % IDLE_OBJECT_AND_WAITING_POSES.length;
        triggerIdleObjectOrWaitingAnimation(nextIdlePose, false);
    }
}

// ----------------------------------------------------
// MAIN RENDER LOOP (Phases 2, 3, 4, 5 + HELIOS-Controlled Pose Engine)
// ----------------------------------------------------
function animate() {
    requestAnimationFrame(animate);

    const delta = Math.min(clock.getDelta(), 0.1);
    const elapsed = clock.getElapsedTime();

    if (currentVrm && currentVrm.humanoid) {
        const speed = Math.min(1.0, delta * 7.5);

        // Phase 5: Web Audio API FFT + RMS 5-Vowel Lip-Sync (computed first to feed speech prosody & state checks)
        if (audioLipSync) {
            audioLipSync.update();
        }

        // Guard & Watchdog: Ensure Speaking procedure stops immediately once audio/lip-sync finishes
        if (currentState === 'speaking') {
            const activelySpeaking = Boolean(audioLipSync && audioLipSync.isPlaying);
            if (!activelySpeaking && pendingSpeechChunks <= 0) {
                speakingIdleWatchdog += delta;
                if (speakingIdleWatchdog >= 0.25) {
                    finishSpeakingProcedure();
                }
            } else {
                speakingIdleWatchdog = 0;
                if (
                    (!navController || !navController.isNavigating) &&
                    !isSpecialTrickPose(currentPose) &&
                    !customPoseRegistry.has(currentPose)
                ) {
                    speakingPoseCycleTimer += delta;
                    if (speakingPoseCycleTimer >= SPEAKING_POSE_INTERVAL) {
                        speakingPoseCycleTimer = 0;
                        const nextSpeakPose = getNextSpeakingPoseForEmotion(currentEmotion);
                        setPose(nextSpeakPose);
                        updateStatus(`State: Speaking [${currentEmotion}] | Pose: ${nextSpeakPose}`);
                    }
                }
            }
        } else {
            speakingIdleWatchdog = 0;
        }

        // Autonomous Curious Object & Waiting Idle Director (when in Idle state)
        updateAutonomousIdleDirector(delta);

        // Phase 4: Spatial Navigation ("Come to Me")
        if (navController) {
            navController.update(delta, camera);
        }

        // Phase 2: Biomechanical Humanization (3-phase asymmetric blinking, cursor gaze, saccades, speech prosody & human posture style)
        if (humanizer) {
            humanizer.update(delta, currentState, audioLipSync?.currentSpeechEnergy || 0, currentStyle);
        }

        // Phase 3: Smooth 2-Bone IK Pose Engine + Thoracic/Clavicular Breathing & Finger Micro-Tonus
        if (animManager && animManager.usingExternalFBX) {
            animManager.update(delta);
        } else {
            applyProceduralPose(elapsed, speed);
        }

        // Smoothly track vertical crouch/jump offset and pull camera back slightly on deep crouches so full crouch is framed
        if (controls && currentVrm.scene) {
            const posY = currentVrm.scene.position.y;
            const crouchDepth = Math.max(0, -posY);
            const camLerp = Math.min(1.0, delta * 5.5);
            const desiredTargetY = baseCameraTargetY + posY * 1.12;
            controls.target.y = THREE.MathUtils.lerp(controls.target.y, desiredTargetY, camLerp);
            if (!navController || !navController.isNavigating) {
                const desiredCamY = baseCameraY + posY * 0.92;
                const desiredCamZ = baseCameraZ + crouchDepth * 1.35;
                camera.position.y = THREE.MathUtils.lerp(camera.position.y, desiredCamY, camLerp);
                camera.position.z = THREE.MathUtils.lerp(camera.position.z, desiredCamZ, camLerp);
            }
        }

        // Update VRM internal SpringBone physics & expressions
        currentVrm.update(delta);

        // Phase 6: Synchronize 3D VRM Neon Trim, Eyes & Grid with Tensura Popup State Colors
        updateVrmStateColorTransition(delta, elapsed);
    }

    // Update 3D Holographic HELIOS Popup, Core Orb, Glass Tap Ring & Wrist HUD for the character
    updateInteractiveObjectsAndHud(delta, elapsed);

    if (rigEditor) {
        rigEditor.update();
    }

    controls.update();
    renderer.render(scene, camera);
}

// ----------------------------------------------------
// WEBSOCKET (/ws/chat) CHARACTER PROTOCOL STREAMING
// ----------------------------------------------------
const chatLog = document.getElementById('chat-log');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const chatMic = document.getElementById('chat-mic');
let ws = null;
let currentChatBubble = null;
let ttsPlaybackQueue = Promise.resolve();
let lastCharacterSpeechTimestamp = 0;

function appendToChat(text, isUser = false, metaTag = '') {
    if (!chatLog) return;
    chatLog.style.display = 'block';
    if (isUser || !currentChatBubble) {
        currentChatBubble = document.createElement('div');
        currentChatBubble.style.marginBottom = '8px';
        const badge = metaTag ? ` <small style="color:var(--accent-border);font-weight:600;">[${metaTag}]</small>` : '';
        currentChatBubble.innerHTML = `<strong>${isUser ? 'You' : 'HELIOS'}${badge}:</strong> <span class="msg-text"></span>`;
        currentChatBubble.style.color = isUser ? '#00e5ff' : '#ebf0f5';
        chatLog.appendChild(currentChatBubble);
    }

    const span = currentChatBubble.querySelector('.msg-text');
    if (isUser) {
        span.innerText = text;
        currentChatBubble = null;
    } else {
        span.innerText += text;
    }
    chatLog.scrollTop = chatLog.scrollHeight;
}

function connectAI() {
    if (window.location.protocol === 'file:') return;
    const wsHost = window.location.host || 'localhost:8080';
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    try {
        ws = new WebSocket(protocol + wsHost + '/ws/chat');
    } catch (err) {
        console.warn('Standalone mode: WebSocket unavailable, running local character viewer only.', err);
        return;
    }

    ws.onopen = () => {
        console.log('Connected to HELIOS Character Protocol Bridge (/ws/chat)');
    };

    ws.onmessage = (event) => {
        let data;
        try {
            data = JSON.parse(event.data);
        } catch (e) {
            return;
        }

        if (data.type === 'helios_status') {
            applyHeliosAddonStatus(data);
            return;
        }

        if (data.type === 'character_sync') {
            if (data.config?.renderer) {
                activeRendererType = data.config.renderer;
                if (brainModeSelect) brainModeSelect.value = activeRendererType;
            }
            if (data.state) {
                applyCharacterProtocolState(data.state);
            }
            return;
        }

        if (data.type === 'character_state') {
            applyCharacterProtocolState(data);
            return;
        }

        if (data.type === 'character_activity') {
            if (activeRendererType === 'live2d') {
                live2dAdapter.applyCharacterActivity(data);
            }
            updateActivityBanner(data.activity || '');
            return;
        }

        if (data.type === 'character_speech') {
            if (activeRendererType === 'live2d') {
                live2dAdapter.applyCharacterSpeech(data);
            }
            if (typeof handleCallAiriSpeaking === 'function') {
                handleCallAiriSpeaking(data.text);
            }
            if (!data.speaking) {
                pendingSpeechChunks = 0;
                if (audioLipSync) audioLipSync.stopCurrent();
                finishSpeakingProcedure();
                return;
            }
            lastCharacterSpeechTimestamp = performance.now();
            pendingSpeechChunks += 1;
            ttsPlaybackQueue = ttsPlaybackQueue.then(async () => {
                try {
                    currentState = 'speaking';
                    applyStateVisualTheme('speaking');
                    speakingPoseCycleTimer = 0;
                    speakingIdleWatchdog = 0;
                    if (!customPoseRegistry.has(currentPose) && !isSpecialTrickPose(currentPose)) {
                        const speakPose = getNextSpeakingPoseForEmotion(currentEmotion);
                        setPose(speakPose);
                    }
                    if (audioLipSync) {
                        await audioLipSync.playBase64Wav(
                            data.audio_b64,
                            data.text || '',
                            data.rms,
                            data.visemes,
                            data.duration || 2.0,
                            data.mime_type || 'audio/wav',
                            !voiceMuted
                        );
                    }
                } finally {
                    pendingSpeechChunks = Math.max(0, pendingSpeechChunks - 1);
                    if (pendingSpeechChunks === 0) {
                        finishSpeakingProcedure();
                    }
                }
            });
            return;
        }

        if (data.type === 'character_stop') {
            pendingSpeechChunks = 0;
            if (activeRendererType === 'live2d') {
                live2dAdapter.stopSpeech();
            }
            if (audioLipSync) {
                audioLipSync.stopCurrent();
            }
            if (typeof handleCallAiriFinishedSpeaking === 'function') {
                handleCallAiriFinishedSpeaking();
            }
            updateActivityBanner('');
            setTestState('idle', 'idle');
            return;
        }

        if (data.type === 'helios_reply') {
            currentChatBubble = null;
            const replyText = data.reply || data.text || '';
            if (typeof handleCallHeliosReply === 'function') {
                handleCallHeliosReply(replyText);
            }
            const cs = data.character_state || null;
            const moveLabel =
                cs && cs.movement && cs.movement !== 'stay' && cs.movement !== 'idle'
                    ? ` | ${cs.movement}`
                    : '';
            const stateTag = cs
                ? `${cs.emotion || 'neutral'} | ${cs.animation || 'idle'}${moveLabel}`
                : 'HELIOS';
            appendToChat(replyText, false, stateTag);
            const hasActiveOrRecentSpeechChunk =
                pendingSpeechChunks > 0 ||
                (audioLipSync && audioLipSync.isPlaying) ||
                performance.now() - lastCharacterSpeechTimestamp < 1500;
            if (cs && !data.offline) {
                const speakingState = {
                    ...cs,
                    mode: hasActiveOrRecentSpeechChunk || replyText.length > 0 ? 'speaking' : (cs.mode || 'idle'),
                    speaking: true,
                };
                applyCharacterProtocolState(speakingState);
                if (!hasActiveOrRecentSpeechChunk && audioLipSync && !audioLipSync.isPlaying && replyText.length > 0) {
                    const estMs = Math.min(6000, Math.max(2000, replyText.length * 38));
                    audioLipSync.startSimulatedLipSync(estMs);
                }
            } else if (!data.offline) {
                if (!hasActiveOrRecentSpeechChunk) {
                    setTestState('speaking', 'talk_explain');
                }
            } else {
                setTestState('idle', 'idle');
            }
            return;
        }
    };

    ws.onclose = () => {
        setTimeout(connectAI, 3000);
    };
}

function sendMessage(customText = null) {
    if (!chatInput) return;
    const text = (customText !== null ? customText : chatInput.value).trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

    if (audioLipSync) audioLipSync.ensureContext();
    if (typeof handleCallUserSentMessage === 'function') {
        handleCallUserSentMessage(text);
    }
    appendToChat(text, true);
    setTestState('thinking', 'think_pose');
    ws.send(JSON.stringify({
        type: 'chat_message',
        text,
        edition: activeHeliosEdition,
    }));
    if (customText === null) chatInput.value = '';
}

if (chatSend) chatSend.onclick = () => sendMessage();
if (chatInput) {
    chatInput.addEventListener('input', () => {
        if (currentState === 'idle' && chatInput.value.trim().length > 0) {
            setTestState('listening', 'listen_pose');
        } else if (currentState === 'listening' && chatInput.value.trim().length === 0) {
            setTestState('idle', 'idle');
        }
    });
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
}

// Browser SpeechRecognition (Microphone Voice Input)
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (chatMic && SpeechRecognition) {
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    let isRecording = false;

    chatMic.onclick = () => {
        if (audioLipSync) audioLipSync.ensureContext();
        if (isRecording) {
            recognition.stop();
        } else {
            try {
                recognition.start();
                isRecording = true;
                chatMic.classList.add('recording');
                setTestState('listening', 'listen_pose');
                updateStatus('🎤 Listening to your voice...');
            } catch (e) {}
        }
    };

    recognition.onresult = (event) => {
        const transcript = event.results?.[0]?.[0]?.transcript;
        if (transcript) {
            chatInput.value = transcript;
            sendMessage(transcript);
        }
    };

    recognition.onend = () => {
        isRecording = false;
        chatMic.classList.remove('recording');
    };

    recognition.onerror = () => {
        isRecording = false;
        chatMic.classList.remove('recording');
    };
} else if (chatMic) {
    chatMic.onclick = () => {
        updateStatus('SpeechRecognition not supported in this browser — use text chat.');
    };
}

// ----------------------------------------------------
// HANDS-FREE VOICE CALL MODE CONTROLLER
// ----------------------------------------------------
const btnCallMode = document.getElementById('btn-call-mode');
const callModeOverlay = document.getElementById('call-mode-overlay');
const callTimerDisplay = document.getElementById('call-timer-display');
const callStatusDisplay = document.getElementById('call-status-display');
const callCaptionBox = document.getElementById('call-caption-box');
const callCaptionText = document.getElementById('call-caption-text');
const callSpeakerTag = document.getElementById('call-speaker-tag');
const callPulseIndicator = document.getElementById('call-pulse-indicator');
const btnCallMute = document.getElementById('btn-call-mute');
const btnCallInterrupt = document.getElementById('btn-call-interrupt');
const btnCallEnd = document.getElementById('btn-call-end');

let isCallModeActive = false;
let isCallMuted = false;
let callDurationSeconds = 0;
let callTimerInterval = null;
let callRecognition = null;
let callRecognitionRunning = false;
let callSavedCameraPos = null;
let callSavedCameraTarget = null;
let callListenDebounceTimer = null;

function setCallPulseColor(color) {
    if (callPulseIndicator) {
        callPulseIndicator.style.background = color;
        callPulseIndicator.style.boxShadow = `0 0 10px ${color}`;
    }
}

function updateCallTimerUI() {
    if (!callTimerDisplay) return;
    const mins = Math.floor(callDurationSeconds / 60).toString().padStart(2, '0');
    const secs = (callDurationSeconds % 60).toString().padStart(2, '0');
    callTimerDisplay.innerText = `${mins}:${secs}`;
}

function initCallRecognition() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
        console.warn('SpeechRecognition not available in this browser');
        return null;
    }
    const rec = new SpeechRec();
    rec.lang = 'en-US';
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;

    rec.onstart = () => {
        callRecognitionRunning = true;
        if (callStatusDisplay) callStatusDisplay.innerText = 'Connected · Listening';
        if (callSpeakerTag) callSpeakerTag.innerText = 'Listening:';
        setCallPulseColor('#00ffaa');
    };

    rec.onresult = (event) => {
        let finalTranscript = '';
        let interimTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }
        const textToDisplay = finalTranscript || interimTranscript;
        if (textToDisplay && callCaptionText) {
            callCaptionText.innerText = `"${textToDisplay}"`;
        }
        if (finalTranscript.trim().length > 0) {
            if (callSpeakerTag) callSpeakerTag.innerText = 'You:';
            if (callStatusDisplay) callStatusDisplay.innerText = 'Airi is thinking...';
            setCallPulseColor('#00e5ff');
            sendMessage(finalTranscript.trim());
        }
    };

    rec.onerror = (e) => {
        callRecognitionRunning = false;
        if (isCallModeActive && !isCallMuted && currentState !== 'speaking' && pendingSpeechChunks === 0) {
            clearTimeout(callListenDebounceTimer);
            callListenDebounceTimer = setTimeout(() => {
                if (isCallModeActive && !isCallMuted && currentState !== 'speaking') {
                    startCallListening();
                }
            }, 500);
        }
    };

    rec.onend = () => {
        callRecognitionRunning = false;
        if (isCallModeActive && !isCallMuted && currentState !== 'speaking' && pendingSpeechChunks === 0) {
            clearTimeout(callListenDebounceTimer);
            callListenDebounceTimer = setTimeout(() => {
                if (isCallModeActive && !isCallMuted && currentState !== 'speaking') {
                    startCallListening();
                }
            }, 300);
        }
    };

    return rec;
}

function startCallListening() {
    if (!isCallModeActive || isCallMuted || callRecognitionRunning) return;
    if (currentState === 'speaking' || pendingSpeechChunks > 0 || (audioLipSync && audioLipSync.isPlaying)) {
        return;
    }
    if (!callRecognition) {
        callRecognition = initCallRecognition();
    }
    if (callRecognition) {
        try {
            callRecognition.start();
            callRecognitionRunning = true;
            if (callStatusDisplay) callStatusDisplay.innerText = 'Connected · Listening';
            if (callSpeakerTag) callSpeakerTag.innerText = 'Listening:';
            setCallPulseColor('#00ffaa');
        } catch (e) {
            // Already started or busy
        }
    }
}

function stopCallListening() {
    clearTimeout(callListenDebounceTimer);
    if (callRecognition && callRecognitionRunning) {
        try {
            callRecognition.stop();
        } catch (e) {}
    }
    callRecognitionRunning = false;
}

function startCallMode() {
    if (isCallModeActive) return;
    isCallModeActive = true;
    isCallMuted = false;
    callDurationSeconds = 0;

    if (audioLipSync) audioLipSync.ensureContext();

    // Preserve previous camera position and focus on portrait
    callSavedCameraPos = camera.position.clone();
    callSavedCameraTarget = controls.target.clone();
    if (currentVrm) {
        focusCallCamera(currentVrm);
    }

    if (callModeOverlay) callModeOverlay.classList.add('active');
    if (btnCallMode) btnCallMode.classList.add('active');

    if (btnCallMute) {
        btnCallMute.classList.remove('muted');
        btnCallMute.innerText = '🎤';
    }

    updateCallTimerUI();
    clearInterval(callTimerInterval);
    callTimerInterval = setInterval(() => {
        if (!isCallModeActive) return;
        callDurationSeconds++;
        updateCallTimerUI();
    }, 1000);

    if (callStatusDisplay) callStatusDisplay.innerText = 'Connected · Airi is greeting';
    if (callSpeakerTag) callSpeakerTag.innerText = 'Airi:';
    if (callCaptionText) callCaptionText.innerText = '"Kehehe, call connected! Hands-free goblin hotline is live—what technical mess are we untangling?"';
    setCallPulseColor('#00ffaa');

    // Trigger initial greeting from Airi if websocket is active
    if (ws && ws.readyState === WebSocket.OPEN) {
        sendMessage("Hey Airi! We're on a hands-free voice call now! Greet me with your trademark chaotic gremlin energy, and ask what technical problem or code we're tackling today!");
    } else {
        if (audioLipSync) {
            audioLipSync.startSimulatedLipSync(3200);
        }
        setTimeout(() => {
            if (isCallModeActive) {
                startCallListening();
            }
        }, 3400);
    }
}

function endCallMode() {
    if (!isCallModeActive) return;
    isCallModeActive = false;
    clearInterval(callTimerInterval);
    stopCallListening();

    if (audioLipSync && audioLipSync.isPlaying) {
        audioLipSync.stopCurrent();
    }
    pendingSpeechChunks = 0;

    if (callModeOverlay) callModeOverlay.classList.remove('active');
    if (btnCallMode) btnCallMode.classList.remove('active');

    if (callSavedCameraPos && callSavedCameraTarget) {
        camera.position.copy(callSavedCameraPos);
        controls.target.copy(callSavedCameraTarget);
        controls.update();
    } else if (currentVrm) {
        focusOnModel(currentVrm);
    }

    setTestState('idle', 'idle');
    updateStatus('📞 Voice Call Ended. Standby.');
}

function interruptCallSpeaking() {
    if (!isCallModeActive) return;
    if (audioLipSync) audioLipSync.stopCurrent();
    pendingSpeechChunks = 0;
    ttsPlaybackQueue = Promise.resolve();

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'character_stop' }));
    }

    setTestState('listening', 'listen_pose');
    applyExpressionState('surprised', 0.6);

    if (callSpeakerTag) callSpeakerTag.innerText = 'Interrupted:';
    if (callCaptionText) callCaptionText.innerText = '"Whoa, cut off! Spill it—what\'s the emergency?"';
    if (callStatusDisplay) callStatusDisplay.innerText = 'Connected · Listening';
    setCallPulseColor('#ffd60a');

    setTimeout(() => {
        if (isCallModeActive && !isCallMuted) {
            startCallListening();
        }
    }, 250);
}

function toggleCallMute() {
    if (!isCallModeActive) return;
    isCallMuted = !isCallMuted;
    if (btnCallMute) {
        btnCallMute.classList.toggle('muted', isCallMuted);
        btnCallMute.innerText = isCallMuted ? '🔇' : '🎤';
    }
    if (isCallMuted) {
        stopCallListening();
        if (callStatusDisplay) callStatusDisplay.innerText = 'Microphone Muted';
        setCallPulseColor('#ff4444');
    } else {
        if (callStatusDisplay) callStatusDisplay.innerText = 'Connected · Listening';
        setCallPulseColor('#00ffaa');
        startCallListening();
    }
}

function handleCallAiriSpeaking(text) {
    if (!isCallModeActive) return;
    stopCallListening();
    if (callStatusDisplay) callStatusDisplay.innerText = 'Airi is speaking...';
    if (callSpeakerTag) callSpeakerTag.innerText = 'Airi:';
    setCallPulseColor('#ff00aa');
    if (text && callCaptionText) {
        callCaptionText.innerText = `"${text}"`;
    }
}

function handleCallHeliosReply(text) {
    if (!isCallModeActive) return;
    stopCallListening();
    if (callStatusDisplay) callStatusDisplay.innerText = 'Airi is speaking...';
    if (callSpeakerTag) callSpeakerTag.innerText = 'Airi:';
    setCallPulseColor('#ff00aa');
    if (text && callCaptionText) {
        callCaptionText.innerText = `"${text}"`;
    }
}

function handleCallUserSentMessage(text) {
    if (!isCallModeActive) return;
    stopCallListening();
    if (callSpeakerTag) callSpeakerTag.innerText = 'You:';
    if (callCaptionText) callCaptionText.innerText = `"${text}"`;
    if (callStatusDisplay) callStatusDisplay.innerText = 'Airi is thinking...';
    setCallPulseColor('#00e5ff');
}

function handleCallAiriFinishedSpeaking() {
    if (!isCallModeActive) return;
    if (callStatusDisplay) callStatusDisplay.innerText = 'Connected · Listening';
    if (callSpeakerTag) callSpeakerTag.innerText = 'Listening:';
    setCallPulseColor('#00ffaa');
    if (!isCallMuted) {
        setTimeout(() => {
            if (isCallModeActive && !isCallMuted && currentState !== 'speaking') {
                startCallListening();
            }
        }, 250);
    }
}

if (btnCallMode) btnCallMode.onclick = () => {
    if (isCallModeActive) {
        endCallMode();
    } else {
        startCallMode();
    }
};
if (btnCallMute) btnCallMute.onclick = toggleCallMute;
if (btnCallInterrupt) btnCallInterrupt.onclick = interruptCallSpeaking;
if (btnCallEnd) btnCallEnd.onclick = endCallMode;

// ----------------------------------------------------
// PERSONALITY CARD & SYSTEM PROMPTS STUDIO MODAL SYNC
// ----------------------------------------------------
const personalityModal = document.getElementById('personality-studio-modal');
const btnOpenPersonalitySidebar = document.getElementById('btn-open-personality-studio');
const btnFloatingPersonality = document.getElementById('btn-floating-personality');
const btnClosePersonality = document.getElementById('btn-close-personality-studio');

function openPersonalityStudio() {
    if (personalityModal) {
        personalityModal.style.display = 'flex';
    }
}

function closePersonalityStudio() {
    if (personalityModal) {
        personalityModal.style.display = 'none';
    }
}

if (btnOpenPersonalitySidebar) btnOpenPersonalitySidebar.onclick = openPersonalityStudio;
if (btnFloatingPersonality) btnFloatingPersonality.onclick = openPersonalityStudio;
if (btnClosePersonality) btnClosePersonality.onclick = closePersonalityStudio;
if (personalityModal) {
    personalityModal.addEventListener('click', (e) => {
        if (e.target === personalityModal) closePersonalityStudio();
    });
}

window.addEventListener('message', (e) => {
    if (e.data && e.data.type === 'helios-personality-updated') {
        const botName = e.data.bot_name || 'HELIOS';
        const style = e.data.default_posture_style;
        if (style) {
            setStyleMode(style, false);
        }
        updateStatus(`🧠 Personality Card & Prompts Updated: ${botName} (Style: ${style || currentStyle})`);
    }
});

// Initialize model selection, render loop & HELIOS Character Protocol connection
const urlParams = new URLSearchParams(window.location.search);
const requestedModel = (urlParams.get('model') || '').toLowerCase();
if (requestedModel === 'twin' || requestedModel === 'ren' || requestedModel === 'brother') {
    clearModelActiveStates();
    if (btnModelTwin) btnModelTwin.classList.add('active');
    loadVRM(TWIN_VRM_URL);
} else {
    clearModelActiveStates();
    if (btnModelHelios) btnModelHelios.classList.add('active');
    loadVRM(DEFAULT_VRM_URL);
}
animate();
connectAI();
fetchRlPoseStatus();

const urlEdition = (urlParams.get('edition') || '').toLowerCase();
if (urlEdition === 'character_only' || urlEdition === 'standalone' || urlEdition === 'character') {
    selectHeliosEdition('character_only');
} else if (urlEdition === 'full_spec' || urlEdition === 'helios' || urlEdition === 'full') {
    selectHeliosEdition('full_spec');
}



