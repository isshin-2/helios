import * as THREE from 'three';
window.THREE = THREE;
import { createVRMRendererContext } from './vrm/renderer.js';
import { Humanizer } from './vrm/humanizer.js?v=14';
import {
    MIXAMO_TO_VRM_MAP,
    EMOTION_SPEAKING_POSE_POOLS,
    getSpeakingPosePoolForCharacter,
    IDLE_OBJECT_AND_WAITING_POSES,
    PROTOCOL_ANIMATION_MAP,
    mapProtocolAnimationToPose,
    isSpecialTrickPose,
    isIdleObjectOrWaitingPose,
    extractMixamoFBXClip,
    AnimationManager,
    NavigationController,
} from './vrm/animation.js?v=17';
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
// ----------------------------------------------------
// UNIVERSAL USER-ADJUSTABLE CALIBRATION FOR ALL 3D PROPS & GADGETS
// ----------------------------------------------------
const PROPS_CONFIG = {
    monocle: {
        name: "Ren's Neural Monocle HUD (MN-01)",
        hasPath: false,
        labels: { x: "Left / Right (X):", y: "Up / Down (Y):", z: "Forward / Back (Z):", scale: "Scale Size:" },
        ranges: {
            x: { min: 0.010, max: 0.060, step: 0.001, unit: "m" },
            y: { min: 0.030, max: 0.090, step: 0.001, unit: "m" },
            z: { min: 0.040, max: 0.120, step: 0.001, unit: "m" },
            scale: { min: 0.70, max: 1.40, step: 0.02, unit: "x" }
        },
        defaults: { x: 0.0336, y: 0.0575, z: 0.0760, scale: 1.00, rotX: 0, rotY: 0, rotZ: 0, pathMode: 'none', speed: 1.00 }
    },
    drone: {
        name: "Ren's Tactical Recon Drone (SD-04 Ghosteye)",
        hasPath: true,
        labels: { x: "Offset X (Lateral):", y: "Offset Y (Altitude):", z: "Offset Z (Depth):", scale: "Drone Scale:" },
        ranges: {
            x: { min: -0.40, max: 0.40, step: 0.01, unit: "m" },
            y: { min: -0.30, max: 0.50, step: 0.01, unit: "m" },
            z: { min: -0.40, max: 0.40, step: 0.01, unit: "m" },
            scale: { min: 0.60, max: 1.80, step: 0.05, unit: "x" }
        },
        defaults: { x: 0.00, y: 0.00, z: 0.00, scale: 1.00, rotX: 0, rotY: 0, rotZ: 0, pathMode: 'recon_orbit', speed: 1.00 }
    },
    butterfly: {
        name: "Airi's Bio-Quantum Butterfly (SD-01)",
        hasPath: true,
        labels: { x: "Offset X (Lateral):", y: "Offset Y (Height):", z: "Offset Z (Depth):", scale: "Wing Scale:" },
        ranges: {
            x: { min: -0.25, max: 0.25, step: 0.01, unit: "m" },
            y: { min: -0.20, max: 0.35, step: 0.01, unit: "m" },
            z: { min: -0.25, max: 0.25, step: 0.01, unit: "m" },
            scale: { min: 0.60, max: 1.80, step: 0.05, unit: "x" }
        },
        defaults: { x: 0.00, y: 0.00, z: 0.00, scale: 1.00, rotX: 0, rotY: 0, rotZ: 0, pathMode: 'hover_perch', speed: 1.00 }
    },
    console: {
        name: "Arcade Cyber Deck (HEL-DCK-01)",
        hasPath: false,
        labels: { x: "Offset X (Grip):", y: "Offset Y (Height):", z: "Offset Z (Distance):", scale: "Device Scale:" },
        ranges: {
            x: { min: -0.20, max: 0.20, step: 0.005, unit: "m" },
            y: { min: -0.15, max: 0.20, step: 0.005, unit: "m" },
            z: { min: -0.15, max: 0.25, step: 0.005, unit: "m" },
            scale: { min: 0.70, max: 1.50, step: 0.02, unit: "x" }
        },
        defaults: { x: 0.00, y: 0.00, z: 0.00, scale: 1.00, rotX: 0, rotY: 0, rotZ: 0, pathMode: 'none', speed: 1.00 }
    },
    katana: {
        name: "Tactical Plasma Blade (HEL-BLD-01 / 02)",
        hasPath: false,
        labels: { x: "Offset X (Hilt):", y: "Offset Y (Elevation):", z: "Offset Z (Reach):", scale: "Blade Scale:" },
        ranges: {
            x: { min: -0.25, max: 0.25, step: 0.005, unit: "m" },
            y: { min: -0.20, max: 0.25, step: 0.005, unit: "m" },
            z: { min: -0.20, max: 0.25, step: 0.005, unit: "m" },
            scale: { min: 0.70, max: 1.60, step: 0.02, unit: "x" }
        },
        defaults: { x: 0.00, y: 0.00, z: 0.00, scale: 1.00, rotX: 0, rotY: 0, rotZ: 0, pathMode: 'none', speed: 1.00 }
    },
    holodice: {
        name: "Airi's Quantum Holo-Dice (HEL-RNG-01)",
        hasPath: true,
        labels: { x: "Offset X (Lateral):", y: "Offset Y (Height):", z: "Offset Z (Depth):", scale: "Dice Scale:" },
        ranges: {
            x: { min: -0.25, max: 0.25, step: 0.01, unit: "m" },
            y: { min: -0.20, max: 0.35, step: 0.01, unit: "m" },
            z: { min: -0.25, max: 0.25, step: 0.01, unit: "m" },
            scale: { min: 0.60, max: 2.00, step: 0.05, unit: "x" }
        },
        defaults: { x: 0.00, y: 0.00, z: 0.00, scale: 1.00, rotX: 0, rotY: 0, rotZ: 0, pathMode: 'hover_perch', speed: 1.00 }
    },
    datapad: {
        name: "Ren's Tactical Datapad (HEL-PAD-02)",
        hasPath: false,
        labels: { x: "Offset X (Grip):", y: "Offset Y (Height):", z: "Offset Z (Distance):", scale: "Pad Scale:" },
        ranges: {
            x: { min: -0.20, max: 0.20, step: 0.005, unit: "m" },
            y: { min: -0.15, max: 0.20, step: 0.005, unit: "m" },
            z: { min: -0.15, max: 0.25, step: 0.005, unit: "m" },
            scale: { min: 0.70, max: 1.50, step: 0.02, unit: "x" }
        },
        defaults: { x: 0.00, y: 0.00, z: 0.00, scale: 1.00, rotX: 0, rotY: 0, rotZ: 0, pathMode: 'none', speed: 1.00 }
    },
    orb: {
        name: "HELIOS Black Hole Core Orb",
        hasPath: true,
        labels: { x: "Offset X (Orbit X):", y: "Offset Y (Float Y):", z: "Offset Z (Orbit Z):", scale: "Singularity Scale:" },
        ranges: {
            x: { min: -0.30, max: 0.30, step: 0.01, unit: "m" },
            y: { min: -0.25, max: 0.35, step: 0.01, unit: "m" },
            z: { min: -0.30, max: 0.30, step: 0.01, unit: "m" },
            scale: { min: 0.60, max: 1.80, step: 0.05, unit: "x" }
        },
        defaults: { x: 0.00, y: 0.00, z: 0.00, scale: 1.00, rotX: 0, rotY: 0, rotZ: 0, pathMode: 'recon_orbit', speed: 1.00 }
    },
    popup: {
        name: "Left-Wrist Holographic Popup HUD",
        hasPath: false,
        labels: { x: "Offset X (Lateral):", y: "Offset Y (Height):", z: "Offset Z (Distance):", scale: "HUD Size:" },
        ranges: {
            x: { min: -0.30, max: 0.30, step: 0.01, unit: "m" },
            y: { min: -0.25, max: 0.35, step: 0.01, unit: "m" },
            z: { min: -0.25, max: 0.35, step: 0.01, unit: "m" },
            scale: { min: 0.60, max: 1.60, step: 0.02, unit: "x" }
        },
        defaults: { x: 0.00, y: 0.00, z: 0.00, scale: 1.00, rotX: 0, rotY: 0, rotZ: 0, pathMode: 'none', speed: 1.00 }
    }
};

let propsCalibration = {};
for (const key of Object.keys(PROPS_CONFIG)) {
    propsCalibration[key] = { ...PROPS_CONFIG[key].defaults };
}

try {
    const saved = localStorage.getItem('helios_props_calibration');
    if (saved) {
        const parsed = JSON.parse(saved);
        for (const key of Object.keys(PROPS_CONFIG)) {
            if (parsed[key]) {
                propsCalibration[key] = { ...PROPS_CONFIG[key].defaults, ...parsed[key] };
            }
        }
    } else {
        // Migration from legacy monocle calibration if present
        const oldMonocle = localStorage.getItem('helios_monocle_calibration');
        if (oldMonocle) {
            propsCalibration.monocle = { ...PROPS_CONFIG.monocle.defaults, ...JSON.parse(oldMonocle) };
        }
    }
} catch (e) {
    console.warn('Could not read saved props calibration:', e);
}

// Keep backwards compatibility for any external references
let monocleCalibration = propsCalibration.monocle;
window.propsCalibration = propsCalibration;
window.PROPS_CONFIG = PROPS_CONFIG;
window.monocleCalibration = monocleCalibration;

window.savePropsCalibration = () => {
    try {
        localStorage.setItem('helios_props_calibration', JSON.stringify(propsCalibration));
        localStorage.setItem('helios_monocle_calibration', JSON.stringify(propsCalibration.monocle));
        return true;
    } catch (e) {
        console.error('Failed to save props calibration:', e);
        return false;
    }
};

window.resetPropCalibration = (propId) => {
    if (PROPS_CONFIG[propId]) {
        propsCalibration[propId] = { ...PROPS_CONFIG[propId].defaults };
        window.savePropsCalibration();
        if (window.syncActivePropSlidersUI) window.syncActivePropSlidersUI();
    }
};

window.setPropCalibration = (propId, opts = {}) => {
    if (propsCalibration[propId]) {
        Object.assign(propsCalibration[propId], opts);
        if (propId === 'monocle') {
            Object.assign(monocleCalibration, opts);
        }
    }
};

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
    const innerGeo = new THREE.SphereGeometry(0.029, 32, 32);
    const innerMat = new THREE.MeshStandardMaterial({
        color: 0x050508,
        roughness: 0.9,
        metalness: 0.1,
        transparent: true,
        opacity: 0.0,
    });
    const innerMesh = new THREE.Mesh(innerGeo, innerMat);
    innerMesh.userData.interactiveType = 'orb';
    orbGroup.add(innerMesh);

    // 3D Tilted (-15deg) Accretion Disk Rings around the 3D Event Horizon sphere
    const gyroGeo = new THREE.TorusGeometry(0.068, 0.0018, 16, 64);
    const gyroMat = new THREE.MeshStandardMaterial({
        color: 0x00e5ff,
        emissive: 0x00e5ff,
        emissiveIntensity: 1.4,
        roughness: 0.2,
        metalness: 0.8,
        transparent: true,
        opacity: 0.0,
    });
    const gyroRing = new THREE.Mesh(gyroGeo, gyroMat);
    gyroRing.rotation.set(Math.PI * 0.42, 0, THREE.MathUtils.degToRad(-15));
    orbGroup.add(gyroRing);

    const gyroGeo2 = new THREE.TorusGeometry(0.082, 0.0014, 16, 64);
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

    // 5. Airi Unique Companion: High-Rendered 3D Bio-Quantum Butterfly — Model: SD-01
    // Segmented metallic cyber-body, dual-layer iridescent wings with circuit veins, photon nucleus
    const butterflyGroup = new THREE.Group();
    butterflyGroup.name = 'AiriCyberButterfly3D';
    butterflyGroup.visible = false;

    // Segmented Cyber Body (Head, Thorax, Abdomen)
    const bBodyMat = new THREE.MeshStandardMaterial({
        color: 0x181c26,
        metalness: 0.9,
        roughness: 0.22,
        transparent: true,
        opacity: 0.0,
    });
    const bHead = new THREE.Mesh(new THREE.SphereGeometry(0.0055, 16, 16), bBodyMat);
    bHead.position.set(0, 0, 0.015);
    butterflyGroup.add(bHead);

    const bThorax = new THREE.Mesh(new THREE.CylinderGeometry(0.0045, 0.0055, 0.014, 16), bBodyMat);
    bThorax.rotation.x = Math.PI * 0.5;
    bThorax.position.set(0, 0, 0.003);
    butterflyGroup.add(bThorax);

    const bAbdomen = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.002, 0.022, 16), bBodyMat);
    bAbdomen.rotation.x = Math.PI * 0.5;
    bAbdomen.position.set(0, -0.002, -0.014);
    butterflyGroup.add(bAbdomen);

    // Micro Antennae
    const antMat = new THREE.LineBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.0 });
    const antGeoL = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(0, 0.002, 0.016),
        new THREE.Vector3(-0.006, 0.010, 0.024),
        new THREE.Vector3(-0.012, 0.014, 0.028)
    ]);
    const antMeshL = new THREE.Line(antGeoL, antMat);
    butterflyGroup.add(antMeshL);
    const antGeoR = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(0, 0.002, 0.016),
        new THREE.Vector3(0.006, 0.010, 0.024),
        new THREE.Vector3(0.012, 0.014, 0.028)
    ]);
    const antMeshR = new THREE.Line(antGeoR, antMat);
    butterflyGroup.add(antMeshR);

    // Photon Energy Core
    const bCoreGeo = new THREE.SphereGeometry(0.012, 24, 24);
    const bCoreMat = new THREE.MeshStandardMaterial({
        color: 0x00ffff,
        emissive: 0x00e5ff,
        emissiveIntensity: 2.0,
        roughness: 0.1,
        metalness: 0.2,
        transparent: true,
        opacity: 0.0,
    });
    const butterflyCoreMesh = new THREE.Mesh(bCoreGeo, bCoreMat);
    butterflyGroup.add(butterflyCoreMesh);

    // Left Wing (Dual-layer shaped wing: structural frame + iridescent membrane)
    const wingShape = new THREE.Shape();
    wingShape.moveTo(0, 0);
    wingShape.bezierCurveTo(0.018, 0.040, 0.060, 0.062, 0.082, 0.036);
    wingShape.bezierCurveTo(0.092, 0.018, 0.076, -0.024, 0.050, -0.040);
    wingShape.bezierCurveTo(0.028, -0.050, 0.010, -0.028, 0, 0);

    const wingGeo = new THREE.ShapeGeometry(wingShape, 16);
    const bWingMatL = new THREE.MeshStandardMaterial({
        color: 0x00e5ff,
        emissive: 0x0088ff,
        emissiveIntensity: 1.0,
        roughness: 0.15,
        metalness: 0.5,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.0,
    });
    const bWingMeshL = new THREE.Mesh(wingGeo, bWingMatL);
    bWingMeshL.scale.set(0.72, 0.72, 0.72);
    butterflyGroup.add(bWingMeshL);

    // Right Wing
    const bWingMatR = new THREE.MeshStandardMaterial({
        color: 0xff00d4,
        emissive: 0xbb0099,
        emissiveIntensity: 1.0,
        roughness: 0.15,
        metalness: 0.5,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.0,
    });
    const bWingMeshR = new THREE.Mesh(wingGeo, bWingMatR);
    bWingMeshR.scale.set(-0.72, 0.72, 0.72);
    butterflyGroup.add(bWingMeshR);

    // Prismatic Energy Aura Ring
    const bAuraGeo = new THREE.TorusGeometry(0.024, 0.0016, 16, 48);
    const bAuraMat = new THREE.MeshStandardMaterial({
        color: 0x00ffff,
        emissive: 0x00e5ff,
        emissiveIntensity: 1.4,
        roughness: 0.1,
        metalness: 0.5,
        transparent: true,
        opacity: 0.0,
    });
    const bAuraMesh = new THREE.Mesh(bAuraGeo, bAuraMat);
    bAuraMesh.rotation.x = Math.PI * 0.5;
    butterflyGroup.add(bAuraMesh);
    parentScene.add(butterflyGroup);

    // 6. Ren Unique Companion: High-Rendered 3D Tactical Recon Drone — Model: SD-04 "GHOSTEYE"
    // PBR stealth carbon-composite chassis, counter-rotating ducted fan rotors,
    // gimballed amber optical aperture dome, canted V-tail stabilizers, telemetry antennas.
    // NOTE: All blue lights completely removed — 100% tactical amber/gold optics and indicators!
    const droneGroup = new THREE.Group();
    droneGroup.name = 'RenTacticalDrone3D';
    droneGroup.visible = false;

    // Materials (High-Rendered PBR, Zero Blue Light)
    const droneChassisMat = new THREE.MeshStandardMaterial({
        color: 0x141824, // Carbon-composite stealth charcoal
        roughness: 0.35,
        metalness: 0.88,
        transparent: true,
        opacity: 0.0,
    });
    const droneEdgeMat = new THREE.LineBasicMaterial({
        color: 0xffa000, // Tactical warm amber panel seam wireframe (NO BLUE)
        transparent: true,
        opacity: 0.0,
    });
    const droneEyeMat = new THREE.MeshStandardMaterial({
        color: 0xff9900, // Tactical amber/infrared optical lens (NO BLUE)
        emissive: 0xff8800,
        emissiveIntensity: 1.8,
        roughness: 0.15,
        metalness: 0.25,
        transparent: true,
        opacity: 0.0,
    });
    const droneRotorMat = new THREE.MeshStandardMaterial({
        color: 0x1c202a, // High-RPM carbon composite prop
        roughness: 0.4,
        metalness: 0.7,
        transparent: true,
        opacity: 0.0,
    });
    const droneRingMat1 = new THREE.MeshStandardMaterial({
        color: 0xffaa00, // Tactical gold/amber telemetry lidar ring (NO BLUE)
        emissive: 0xff8800,
        emissiveIntensity: 1.3,
        roughness: 0.2,
        metalness: 0.8,
        transparent: true,
        opacity: 0.0,
    });
    const droneRingMat2 = new THREE.MeshStandardMaterial({
        color: 0xff6600, // Tactical deep amber outer telemetry ring (NO BLUE)
        emissive: 0xff4400,
        emissiveIntensity: 1.0,
        roughness: 0.2,
        metalness: 0.8,
        transparent: true,
        opacity: 0.0,
    });

    // 6a. Main Fuselage (Faceted stealth lifting body)
    const droneChassisGeo = new THREE.BoxGeometry(0.082, 0.018, 0.145);
    const droneChassisMesh = new THREE.Mesh(droneChassisGeo, droneChassisMat);
    droneGroup.add(droneChassisMesh);

    const droneEdges = new THREE.EdgesGeometry(droneChassisGeo);
    const droneEdgeMesh = new THREE.LineSegments(droneEdges, droneEdgeMat);
    droneGroup.add(droneEdgeMesh);

    // 6b. Blended Wings / Ducted Fan Nacelles (Left and Right)
    const droneWingGeo = new THREE.BoxGeometry(0.20, 0.009, 0.075);
    droneWingGeo.translate(0, 0, 0.005);
    const droneWingMesh = new THREE.Mesh(droneWingGeo, droneChassisMat);
    droneGroup.add(droneWingMesh);
    const droneWingEdges = new THREE.EdgesGeometry(droneWingGeo);
    const droneWingEdgeMesh = new THREE.LineSegments(droneWingEdges, droneEdgeMat);
    droneGroup.add(droneWingEdgeMesh);

    // Left Ducted Rotor Shroud with aerodynamic lip
    const ductGeoL = new THREE.CylinderGeometry(0.028, 0.026, 0.016, 24, 1, true);
    const ductMeshL = new THREE.Mesh(ductGeoL, droneChassisMat);
    ductMeshL.position.set(-0.065, 0, 0.008);
    droneGroup.add(ductMeshL);
    const ductEdgeL = new THREE.LineSegments(new THREE.EdgesGeometry(ductGeoL), droneEdgeMat);
    ductEdgeL.position.copy(ductMeshL.position);
    droneGroup.add(ductEdgeL);

    // Right Ducted Rotor Shroud
    const ductGeoR = new THREE.CylinderGeometry(0.028, 0.026, 0.016, 24, 1, true);
    const ductMeshR = new THREE.Mesh(ductGeoR, droneChassisMat);
    ductMeshR.position.set(0.065, 0, 0.008);
    droneGroup.add(ductMeshR);
    const ductEdgeR = new THREE.LineSegments(new THREE.EdgesGeometry(ductGeoR), droneEdgeMat);
    ductEdgeR.position.copy(ductMeshR.position);
    droneGroup.add(ductEdgeR);

    // Enclosed Spinning Rotors (Left & Right 4-blade fans with central spinner hub)
    const rotorGeoL = new THREE.CylinderGeometry(0.024, 0.024, 0.003, 4);
    const droneRotorMeshL = new THREE.Mesh(rotorGeoL, droneRotorMat);
    droneRotorMeshL.position.copy(ductMeshL.position);
    droneGroup.add(droneRotorMeshL);

    const rotorGeoR = new THREE.CylinderGeometry(0.024, 0.024, 0.003, 4);
    const droneRotorMeshR = new THREE.Mesh(rotorGeoR, droneRotorMat);
    droneRotorMeshR.position.copy(ductMeshR.position);
    droneGroup.add(droneRotorMeshR);

    // 6c. Forward Camera-Sensor Turret Dome (Amber optical lens, zero blue)
    const droneEyeGeo = new THREE.SphereGeometry(0.013, 24, 24);
    const droneEyeMesh = new THREE.Mesh(droneEyeGeo, droneEyeMat);
    droneEyeMesh.position.set(0, -0.007, 0.072);
    droneGroup.add(droneEyeMesh);

    // 6d. Canted V-Tail Stabilizers
    const finGeoL = new THREE.BoxGeometry(0.004, 0.030, 0.042);
    finGeoL.translate(0, 0.015, 0);
    const finMeshL = new THREE.Mesh(finGeoL, droneChassisMat);
    finMeshL.position.set(-0.034, 0.007, -0.058);
    finMeshL.rotation.z = -0.32;
    droneGroup.add(finMeshL);
    const finEdgeL = new THREE.LineSegments(new THREE.EdgesGeometry(finGeoL), droneEdgeMat);
    finEdgeL.position.copy(finMeshL.position);
    finEdgeL.rotation.copy(finMeshL.rotation);
    droneGroup.add(finEdgeL);

    const finGeoR = new THREE.BoxGeometry(0.004, 0.030, 0.042);
    finGeoR.translate(0, 0.015, 0);
    const finMeshR = new THREE.Mesh(finGeoR, droneChassisMat);
    finMeshR.position.set(0.034, 0.007, -0.058);
    finMeshR.rotation.z = 0.32;
    droneGroup.add(finMeshR);
    const finEdgeR = new THREE.LineSegments(new THREE.EdgesGeometry(finGeoR), droneEdgeMat);
    finEdgeR.position.copy(finMeshR.position);
    finEdgeR.rotation.copy(finMeshR.rotation);
    droneGroup.add(finEdgeR);

    // 6e. Wingtip Telemetry LEDs (Warm tactical amber/ruby navigation beacons, NO BLUE)
    const ledMat = new THREE.MeshStandardMaterial({
        color: 0xff4400,
        emissive: 0xff3300,
        emissiveIntensity: 1.8,
        transparent: true,
        opacity: 0.0,
    });
    const ledGeo = new THREE.SphereGeometry(0.0035, 12, 12);
    const ledMeshL = new THREE.Mesh(ledGeo, ledMat);
    ledMeshL.position.set(-0.102, 0, 0.005);
    droneGroup.add(ledMeshL);
    const ledMeshR = new THREE.Mesh(ledGeo, ledMat);
    ledMeshR.position.set(0.102, 0, 0.005);
    droneGroup.add(ledMeshR);

    // Dual Telemetry Field / Lidar Orbit Rings (Amber/gold gradient)
    const droneRingGeo1 = new THREE.TorusGeometry(0.072, 0.0016, 12, 48);
    const droneRing1 = new THREE.Mesh(droneRingGeo1, droneRingMat1);
    droneRing1.rotation.x = Math.PI * 0.5;
    droneGroup.add(droneRing1);

    const droneRingGeo2 = new THREE.TorusGeometry(0.086, 0.0014, 12, 48);
    const droneRing2 = new THREE.Mesh(droneRingGeo2, droneRingMat2);
    droneRing2.rotation.x = Math.PI * 0.5;
    droneGroup.add(droneRing2);
    parentScene.add(droneGroup);

    // 7. Cyber Handheld Console / Arcade Deck — Model: HEL-DCK-01
    // High-Rendered PBR chassis with textured rubber grips, dynamic retro arcade canvas display,
    // tactile D-Pad, dual concave thumbsticks with knurled rims, ABXY micro buttons, and shoulder bumpers
    const consoleGroup = new THREE.Group();
    consoleGroup.name = 'CyberHandheldConsole3D';
    consoleGroup.visible = false;

    // Main Body Chassis
    const consoleBodyGeo = new THREE.BoxGeometry(0.192, 0.088, 0.020);
    const consoleBodyMat = new THREE.MeshStandardMaterial({
        color: 0x141824,
        roughness: 0.35,
        metalness: 0.85,
        transparent: true,
        opacity: 0.0,
    });
    const consoleBodyMesh = new THREE.Mesh(consoleBodyGeo, consoleBodyMat);
    consoleGroup.add(consoleBodyMesh);

    // Rubberized Ergonomic Side Grips (Left & Right)
    const gripGeoL = new THREE.BoxGeometry(0.026, 0.090, 0.023);
    const gripMat = new THREE.MeshStandardMaterial({
        color: 0x090b10,
        roughness: 0.94,
        metalness: 0.08,
        transparent: true,
        opacity: 0.0,
    });
    const gripMeshL = new THREE.Mesh(gripGeoL, gripMat);
    gripMeshL.position.set(-0.086, 0, 0.001);
    consoleGroup.add(gripMeshL);
    const gripMeshR = new THREE.Mesh(gripGeoL, gripMat);
    gripMeshR.position.set(0.086, 0, 0.001);
    consoleGroup.add(gripMeshR);

    // Chassis Tactical Wireframe Edges
    const consoleEdges = new THREE.EdgesGeometry(consoleBodyGeo);
    const consoleEdgeMat = new THREE.LineBasicMaterial({
        color: 0x00e5ff,
        transparent: true,
        opacity: 0.0,
    });
    const consoleEdgeMesh = new THREE.LineSegments(consoleEdges, consoleEdgeMat);
    consoleGroup.add(consoleEdgeMesh);

    // Dynamic High-DPI Arcade Screen Canvas & Texture
    const dckCanvas = document.createElement('canvas');
    dckCanvas.width = 512;
    dckCanvas.height = 288;
    const dckCtx = dckCanvas.getContext('2d');
    const dckTexture = new THREE.CanvasTexture(dckCanvas);
    dckTexture.colorSpace = THREE.SRGBColorSpace;
    dckTexture.needsUpdate = true;

    const consoleScreenGeo = new THREE.PlaneGeometry(0.118, 0.066);
    const consoleScreenMat = new THREE.MeshStandardMaterial({
        map: dckTexture,
        roughness: 0.1,
        metalness: 0.15,
        emissive: 0x00e5ff,
        emissiveIntensity: 0.6,
        transparent: true,
        opacity: 0.0,
        side: THREE.DoubleSide,
    });
    const consoleScreenMesh = new THREE.Mesh(consoleScreenGeo, consoleScreenMat);
    consoleScreenMesh.position.set(0, 0, 0.011);
    consoleGroup.add(consoleScreenMesh);

    // Left D-Pad Cross
    const dpadMat = new THREE.MeshStandardMaterial({
        color: 0x1e2432,
        roughness: 0.4,
        metalness: 0.8,
        transparent: true,
        opacity: 0.0,
    });
    const dpadH = new THREE.Mesh(new THREE.BoxGeometry(0.022, 0.007, 0.004), dpadMat);
    dpadH.position.set(-0.068, 0.016, 0.012);
    consoleGroup.add(dpadH);
    const dpadV = new THREE.Mesh(new THREE.BoxGeometry(0.007, 0.022, 0.004), dpadMat);
    dpadV.position.set(-0.068, 0.016, 0.012);
    consoleGroup.add(dpadV);

    // Dual Concave Analog Thumbsticks with knurled rims
    const stickMat = new THREE.MeshStandardMaterial({
        color: 0x222834,
        roughness: 0.5,
        metalness: 0.6,
        transparent: true,
        opacity: 0.0,
    });
    const stickGeo = new THREE.CylinderGeometry(0.009, 0.009, 0.008, 16);
    const stickL = new THREE.Mesh(stickGeo, stickMat);
    stickL.rotation.x = Math.PI * 0.5;
    stickL.position.set(-0.068, -0.018, 0.012);
    consoleGroup.add(stickL);

    const stickR = new THREE.Mesh(stickGeo, stickMat);
    stickR.rotation.x = Math.PI * 0.5;
    stickR.position.set(0.068, -0.018, 0.012);
    consoleGroup.add(stickR);

    // Right Action Buttons (ABXY) with emissive colored dots
    const btnDiamondOffsets = [
        { x: 0, y: 0.010, c: 0xffbb00 },  // Y (Amber)
        { x: 0, y: -0.010, c: 0x00ff88 }, // A (Green)
        { x: -0.010, y: 0, c: 0x00e5ff }, // X (Cyan)
        { x: 0.010, y: 0, c: 0xff3366 }   // B (Red)
    ];
    btnDiamondOffsets.forEach(b => {
        const bMat = new THREE.MeshStandardMaterial({
            color: b.c,
            emissive: b.c,
            emissiveIntensity: 1.2,
            roughness: 0.2,
            transparent: true,
            opacity: 0.0
        });
        const bMesh = new THREE.Mesh(new THREE.SphereGeometry(0.0035, 12, 12), bMat);
        bMesh.position.set(0.068 + b.x, 0.016 + b.y, 0.012);
        consoleGroup.add(bMesh);
    });

    // Top Shoulder Bumpers (L1/R1)
    const bumperGeo = new THREE.BoxGeometry(0.038, 0.006, 0.016);
    const bumperL = new THREE.Mesh(bumperGeo, stickMat);
    bumperL.position.set(-0.064, 0.046, 0);
    consoleGroup.add(bumperL);
    const bumperR = new THREE.Mesh(bumperGeo, stickMat);
    bumperR.position.set(0.064, 0.046, 0);
    consoleGroup.add(bumperR);

    parentScene.add(consoleGroup);

    // 8. Cyber Tactical Plasma Blades — Models: HEL-BLD-01 (Airi Wakizashi) & HEL-BLD-02 (Ren Saber)
    // High-Rendered titanium hilt wrap, emitter guard, high-frequency plasma blade with fuller energy core
    const bladeGroup = new THREE.Group();
    bladeGroup.name = 'CyberTacticalBlade3D';
    bladeGroup.visible = false;

    // Hilt / Grip with CNC Machined Pattern
    const hiltGeo = new THREE.CylinderGeometry(0.011, 0.013, 0.18, 16);
    const hiltMat = new THREE.MeshStandardMaterial({
        color: 0x141822,
        roughness: 0.45,
        metalness: 0.8,
        transparent: true,
        opacity: 0.0,
    });
    const hiltMesh = new THREE.Mesh(hiltGeo, hiltMat);
    hiltMesh.position.set(0, -0.09, 0);
    bladeGroup.add(hiltMesh);

    // Pommel Cap with Photon Conduit
    const pommelGeo = new THREE.CylinderGeometry(0.014, 0.011, 0.016, 8);
    const pommelMesh = new THREE.Mesh(pommelGeo, hiltMat);
    pommelMesh.position.set(0, -0.185, 0);
    bladeGroup.add(pommelMesh);

    // Emitter Guard / Tsuba with Circuit Breaker Details
    const guardGeo = new THREE.BoxGeometry(0.046, 0.010, 0.026);
    const guardMat = new THREE.MeshStandardMaterial({
        color: 0x00e5ff,
        roughness: 0.25,
        metalness: 0.9,
        emissive: 0x00e5ff,
        emissiveIntensity: 1.4,
        transparent: true,
        opacity: 0.0,
    });
    const guardMesh = new THREE.Mesh(guardGeo, guardMat);
    guardMesh.position.set(0, 0, 0);
    bladeGroup.add(guardMesh);

    // Plasma Energy Blade (Hex-tapered bevel cutting edge)
    const bladeGeo = new THREE.BoxGeometry(0.016, 0.74, 0.005);
    bladeGeo.translate(0, 0.37, 0);
    const bladeMat = new THREE.MeshStandardMaterial({
        color: 0x00e5ff,
        roughness: 0.15,
        metalness: 0.3,
        emissive: 0x00e5ff,
        emissiveIntensity: 2.2,
        transparent: true,
        opacity: 0.0,
    });
    const bladeMesh = new THREE.Mesh(bladeGeo, bladeMat);
    bladeGroup.add(bladeMesh);

    // Titanium Spine Core (High-reflectivity metallic back)
    const spineGeo = new THREE.BoxGeometry(0.006, 0.72, 0.006);
    spineGeo.translate(-0.005, 0.36, 0);
    const spineMat = new THREE.MeshStandardMaterial({
        color: 0xd0d8e2,
        roughness: 0.12,
        metalness: 0.96,
        transparent: true,
        opacity: 0.0,
    });
    const spineMesh = new THREE.Mesh(spineGeo, spineMat);
    bladeGroup.add(spineMesh);

    // Plasma Aura / Edge Glow
    const bladeEdgeGeo = new THREE.EdgesGeometry(bladeGeo);
    const bladeEdgeMat = new THREE.LineBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.0,
    });
    const bladeEdgeMesh = new THREE.LineSegments(bladeEdgeGeo, bladeEdgeMat);
    bladeGroup.add(bladeEdgeMesh);
    parentScene.add(bladeGroup);

    // 8b. Ren's Cyber Tactical Plasma Blade (HEL-BLD-02 Amber Variant for Dual Synergy)
    const bladeGroupRen = new THREE.Group();
    bladeGroupRen.name = 'CyberTacticalBlade3D_Ren';
    bladeGroupRen.visible = false;

    const hiltMatRen = hiltMat.clone();
    const hiltMeshRen = new THREE.Mesh(hiltGeo, hiltMatRen);
    hiltMeshRen.position.set(0, -0.09, 0);
    bladeGroupRen.add(hiltMeshRen);

    const pommelMeshRen = new THREE.Mesh(pommelGeo, hiltMatRen);
    pommelMeshRen.position.set(0, -0.185, 0);
    bladeGroupRen.add(pommelMeshRen);

    const guardMatRen = new THREE.MeshStandardMaterial({
        color: 0xff9900,
        roughness: 0.25,
        metalness: 0.9,
        emissive: 0xff9900,
        emissiveIntensity: 1.4,
        transparent: true,
        opacity: 0.0,
    });
    const guardMeshRen = new THREE.Mesh(guardGeo, guardMatRen);
    guardMeshRen.position.set(0, 0, 0);
    bladeGroupRen.add(guardMeshRen);

    const bladeMatRen = new THREE.MeshStandardMaterial({
        color: 0xff9900,
        roughness: 0.15,
        metalness: 0.3,
        emissive: 0xff9900,
        emissiveIntensity: 2.2,
        transparent: true,
        opacity: 0.0,
    });
    const bladeMeshRen = new THREE.Mesh(bladeGeo, bladeMatRen);
    bladeGroupRen.add(bladeMeshRen);

    const spineMeshRen = new THREE.Mesh(spineGeo, spineMat);
    bladeGroupRen.add(spineMeshRen);

    const bladeEdgeMatRen = new THREE.LineBasicMaterial({
        color: 0xffe082,
        transparent: true,
        opacity: 0.0,
    });
    const bladeEdgeMeshRen = new THREE.LineSegments(bladeEdgeGeo, bladeEdgeMatRen);
    bladeGroupRen.add(bladeEdgeMeshRen);
    parentScene.add(bladeGroupRen);

    // 9. Ren's Cyber Tactical Monocle HUD & Collar Mic — Models: HEL-MIC-02 / MN-01
    // High-Rendered titanium ocular optic, anti-reflective sapphire prism lens,
    // retinal HUD targeting reticle, lateral sensor pod, and articulated collar boom mic
    const monocleGroup = new THREE.Group();
    monocleGroup.name = 'RenCyberMonocle3D';
    monocleGroup.visible = false;

    // Materials (High-Rendered Holographic PBR - Zero Black Line or Square Clutter)
    const monocleRimMat = new THREE.MeshStandardMaterial({
        color: 0x00e5ff,
        emissive: 0x0088aa,
        emissiveIntensity: 0.8,
        roughness: 0.15,
        metalness: 0.85,
        transparent: true,
        opacity: 0.0,
    });
    const monocleAccentMat = new THREE.MeshStandardMaterial({
        color: 0x00e5ff,
        roughness: 0.25,
        metalness: 0.85,
        transparent: true,
        opacity: 0.0,
    });
    const monocleLensMat = new THREE.MeshStandardMaterial({
        color: 0x00e5ff,
        emissive: 0x006688,
        emissiveIntensity: 0.5,
        roughness: 0.08,
        metalness: 0.15,
        transparent: true,
        opacity: 0.0,
        side: THREE.DoubleSide,
    });
    const monocleEdgeMat = new THREE.LineBasicMaterial({
        color: 0x00ffff,
        transparent: true,
        opacity: 0.0,
    });
    const monocleLedMat = new THREE.MeshStandardMaterial({
        color: 0x00ffff,
        emissive: 0x00e5ff,
        emissiveIntensity: 1.6,
        transparent: true,
        opacity: 0.0,
    });

    // 1. Main Ocular HUD Glass (Sapphire AR prism optic)
    const monocleLensGeo = new THREE.CircleGeometry(0.017, 32);
    const monocleLensMesh = new THREE.Mesh(monocleLensGeo, monocleLensMat);
    monocleGroup.add(monocleLensMesh);

    // 2. Titanium Ocular Bezel Ring
    const monocleRimGeo = new THREE.TorusGeometry(0.017, 0.0022, 16, 36);
    const monocleRimMesh = new THREE.Mesh(monocleRimGeo, monocleRimMat);
    monocleGroup.add(monocleRimMesh);

    // Glowing rim wireframe
    const monocleEdgeMesh = new THREE.LineSegments(new THREE.EdgesGeometry(monocleRimGeo), monocleEdgeMat);
    monocleGroup.add(monocleEdgeMesh);

    // 3. Concentric Telemetry Target Ring
    const innerRingGeo = new THREE.RingGeometry(0.009, 0.010, 24);
    const innerRingMesh = new THREE.Mesh(innerRingGeo, monocleLensMat);
    innerRingMesh.position.z = 0.0005;
    monocleGroup.add(innerRingMesh);

    // 4. Retinal Tracking Crosshair Reticle & Tick Marks
    const reticleGeo = new THREE.BufferGeometry();
    const reticleVerts = new Float32Array([
        -0.014, 0, 0.001,   -0.005, 0, 0.001,
         0.005, 0, 0.001,    0.014, 0, 0.001,
         0, -0.014, 0.001,   0, -0.005, 0.001,
         0,  0.005, 0.001,   0,  0.014, 0.001,
    ]);
    reticleGeo.setAttribute('position', new THREE.BufferAttribute(reticleVerts, 3));
    const monocleReticleMesh = new THREE.LineSegments(reticleGeo, monocleEdgeMat);
    monocleGroup.add(monocleReticleMesh);

    parentScene.add(monocleGroup);

    // 10. Airi's Quantum Holo-Dice — Model: HEL-RNG-01
    // Floating D20 icosahedron holographic wireframe with nested quantum core
    const holoDiceGroup = new THREE.Group();
    holoDiceGroup.name = 'AiriQuantumHoloDice3D';
    holoDiceGroup.visible = false;

    const diceMat = new THREE.MeshStandardMaterial({
        color: 0x00ffff,
        emissive: 0x00e5ff,
        emissiveIntensity: 1.6,
        wireframe: true,
        transparent: true,
        opacity: 0.0,
    });
    const diceMesh = new THREE.Mesh(new THREE.IcosahedronGeometry(0.026, 0), diceMat);
    holoDiceGroup.add(diceMesh);

    const diceCoreMat = new THREE.MeshStandardMaterial({
        color: 0x00e5ff,
        emissive: 0x00e5ff,
        emissiveIntensity: 2.2,
        roughness: 0.1,
        transparent: true,
        opacity: 0.0,
    });
    const diceCoreMesh = new THREE.Mesh(new THREE.IcosahedronGeometry(0.012, 1), diceCoreMat);
    holoDiceGroup.add(diceCoreMesh);

    const diceRingGeo = new THREE.TorusGeometry(0.034, 0.0012, 12, 36);
    const diceRingMesh = new THREE.Mesh(diceRingGeo, diceMat);
    diceRingMesh.rotation.x = Math.PI * 0.5;
    holoDiceGroup.add(diceRingMesh);
    parentScene.add(holoDiceGroup);

    // 11. Ren's Tactical Datapad — Model: HEL-PAD-02
    // Ruggedized tablet with animated mission telemetry canvas HUD
    const datapadGroup = new THREE.Group();
    datapadGroup.name = 'RenTacticalDatapad3D';
    datapadGroup.visible = false;

    const padChassisMat = new THREE.MeshStandardMaterial({
        color: 0x141824,
        roughness: 0.35,
        metalness: 0.85,
        transparent: true,
        opacity: 0.0,
    });
    const padChassis = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.13, 0.012), padChassisMat);
    datapadGroup.add(padChassis);

    const padCanvas = document.createElement('canvas');
    padCanvas.width = 512;
    padCanvas.height = 384;
    const padCtx = padCanvas.getContext('2d');
    const padTexture = new THREE.CanvasTexture(padCanvas);
    padTexture.colorSpace = THREE.SRGBColorSpace;
    padTexture.needsUpdate = true;

    const padScreenMat = new THREE.MeshStandardMaterial({
        map: padTexture,
        roughness: 0.1,
        metalness: 0.2,
        emissive: 0xffaa00,
        emissiveIntensity: 0.6,
        transparent: true,
        opacity: 0.0,
    });
    const padScreen = new THREE.Mesh(new THREE.PlaneGeometry(0.16, 0.11), padScreenMat);
    padScreen.position.set(0, 0, 0.007);
    datapadGroup.add(padScreen);
    parentScene.add(datapadGroup);

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
        butterflyGroup,
        butterflyCoreMesh,
        bCoreMat,
        bWingMeshL,
        bWingMeshR,
        bWingMatL,
        bWingMatR,
        bAuraMesh,
        bAuraMat,
        droneGroup,
        droneChassisMesh,
        droneChassisMat,
        droneEdgeMat,
        droneEyeMat,
        droneRing1,
        droneRing2,
        droneRingMat1,
        droneRingMat2,
        droneRotorMeshL,
        droneRotorMeshR,
        droneRotorMat,
        scanConeMesh: null,
        scanConeMat: null,
        consoleGroup,
        consoleBodyMesh,
        consoleBodyMat,
        consoleEdgeMat,
        consoleScreenMesh,
        consoleScreenMat,
        stickMat,
        bladeGroup,
        hiltMesh,
        hiltMat,
        guardMesh,
        guardMat,
        bladeMesh,
        bladeMat,
        bladeEdgeMat,
        bladeGroupRen,
        hiltMatRen,
        guardMatRen,
        bladeMatRen,
        bladeEdgeMatRen,
        monocleGroup,
        monocleLensMesh,
        monocleLensMat,
        monocleRimMat,
        monocleAccentMat,
        monocleLedMat,
        monocleEdgeMat,
        monocleBeamMesh: null,
        monocleBeamMat: null,
        // Added Blueprint Props
        dckCanvas,
        dckCtx,
        dckTexture,
        holoDiceGroup,
        diceMat,
        diceCoreMat,
        datapadGroup,
        padChassisMat,
        padScreenMat,
        padCanvas,
        padCtx,
        padTexture,
    };
}

const interactiveSceneObjects = createInteractiveIdleObjects(scene);
window.interactiveSceneObjects = interactiveSceneObjects;

// ----------------------------------------------------
// VRM MODEL LOADER & EXACT SKELETON CALIBRATION
let currentVrm = null;
let secondaryVrm = null;
let dualTwinModeActive = false;
let activeModelId = 'airi'; // 'airi' | 'twin' | 'dual'
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

function isRenActive() {
    return activeModelId === 'twin' || (currentVrm && (currentVrm.meta?.title?.toLowerCase().includes('twin') || currentVrm.meta?.title?.toLowerCase().includes('ren')));
}
window.isRenActive = isRenActive;


const renTacticalEmissiveCache = {};
const tacticalTexLoader = new THREE.TextureLoader();
function getRenTacticalEmissiveTexture(type) {
    if (!renTacticalEmissiveCache[type]) {
        const fileMap = {
            top: 'models/ren_tactical_jacket_emissive.png',
            bottom: 'models/ren_tactical_pants_emissive.png',
            body: 'models/ren_tactical_gloves_emissive.png',
            shoe: 'models/ren_tactical_shoes_emissive.png',
            iris: 'models/ren_tactical_iris_emissive.png',
        };
        const path = fileMap[type];
        if (path) {
            const tex = tacticalTexLoader.load(path);
            tex.flipY = false;
            tex.colorSpace = THREE.SRGBColorSpace;
            renTacticalEmissiveCache[type] = tex;
        }
    }
    return renTacticalEmissiveCache[type];
}

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
            const name = (mat.name || '').toLowerCase();
            const isEye = /eyeiris/i.test(name);
            const isHair = /hair/i.test(name);
            const isCloth = /(cloth|top|bottom|shoe|onepiece|hoodie|jacket|cargo)/i.test(name);
            const isBody = /body/i.test(name);

            // Check if current emissiveMap is a dummy 8x8 black texture (e.g. Shader_NoneBlack)
            const emitMap = mat.emissiveMap || mat.uniforms?.emissiveMap?.value;
            const isDummyBlack = emitMap && (
                emitMap.name === 'Shader_NoneBlack' ||
                (emitMap.image && emitMap.image.width <= 8 && emitMap.image.height <= 8)
            );

            // If dummy black texture or missing on tactical cybernetic meshes, attach dedicated tactical emissive map
            if (isDummyBlack || (!emitMap && (isCloth || isBody || isEye))) {
                let type = null;
                if (isEye) type = 'iris';
                else if (/top|jacket|hoodie/i.test(name)) type = 'top';
                else if (/bottom|cargo|pants/i.test(name)) type = 'bottom';
                else if (/shoe/i.test(name)) type = 'shoe';
                else if (isBody) type = 'body';

                if (type) {
                    const tacticalTex = getRenTacticalEmissiveTexture(type);
                    if (tacticalTex) {
                        mat.emissiveMap = tacticalTex;
                        if (mat.uniforms?.emissiveMap) {
                            mat.uniforms.emissiveMap.value = tacticalTex;
                        }
                        mat.needsUpdate = true;
                    }
                }
            }

            const hasEmissiveMap = Boolean(
                mat.emissiveMap || mat.uniforms?.emissiveMap?.value
            );
            const hasEmissiveColor = Boolean(
                mat.emissive && (mat.emissive.r > 0.001 || mat.emissive.g > 0.001 || mat.emissive.b > 0.001)
            );
            // Collect any material with emissive properties or character accents (eyes, hair, cybernetic cloth, tactical gloves)
            if (hasEmissiveMap || hasEmissiveColor || isEye || isCloth || isHair || isBody) {
                // Ensure material has an active emissive color object so shader updates immediately
                if (!mat.emissive) {
                    mat.emissive = new THREE.Color(isEye ? '#00e5ff' : '#00b8d4');
                }
                list.push({
                    mat,
                    isEye,
                    isHair,
                    isCloth,
                    isBody,
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
window.rigMetrics = rigMetrics;


const FINGER_NAMES = ['Thumb', 'Index', 'Middle', 'Ring', 'Little'];
const FINGER_SEGMENTS = ['Proximal', 'Intermediate', 'Distal'];

const DEFAULT_VRM_URL = 'models/Helios_Airi.vrm';
const BASE_VRM_URL = 'models/Helios_Airi.vrm';

function disposeCurrentAvatar() {
    if (secondaryVrm) {
        scene.remove(secondaryVrm.scene);
        try {
            VRMUtils.deepDispose(secondaryVrm.scene);
        } catch (e) {
            console.warn('secondaryVrm deepDispose fallback:', e);
        }
        secondaryVrm = null;
        window.secondaryVrm = null;
    }
    dualTwinModeActive = false;

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

function calibrateSkeletonAndRestPose(vrm, isPrimary = true) {
    if (!vrm || !vrm.humanoid) return;
    const h = vrm.humanoid;

    const hips = h.getNormalizedBoneNode('hips');
    if (hips) {
        hips.traverse(obj => obj.quaternion.identity());
        hips.updateWorldMatrix(true, true);
    }
    vrm.humanoid.update();
    vrm.scene.updateMatrixWorld(true);

    if (!isPrimary || (currentVrm && vrm !== currentVrm)) {
        return;
    }

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

    } else if (currentPose === 'natural_weight_shift' || currentPose === 'backflip' || currentPose === 'dance_shikano') {
        // Natural contrapposto weight shift: organic pelvic tilt, subtle spinal S-curve, asymmetric arm rests
        const sway = Math.sin(time * 0.95);
        const shiftX = Math.sin(time * 0.95) * 0.035;

        hipsRot = [0, -rSide * 0.035 + sway * 0.02, rSide * 0.045];
        spineRot = [fwd * 0.02, rSide * 0.025, -rSide * 0.035];
        chestRot = [breath * 0.8, 0, -rSide * 0.02];
        headRot = [fwd * 0.02, -rSide * 0.04, rSide * 0.045];

        lUpperLegRot = [0, 0, lSide * 0.03];
        rUpperLegRot = [0, 0, rSide * 0.06];
        lLowerLegRot = [0, 0, 0];
        rLowerLegRot = [fwd * 0.06, 0, 0];

        leftHandShape = 'relaxed';
        rightHandShape = 'relaxed';

        rWrist.set(hipsP.x + rSide * 0.12, hipsP.y + 0.04, hipsP.z + camZ * 0.05);
        rPole.set(rSide * 0.85, -0.25, camZ * 0.25);
        rFDir.set(-rSide * 0.20, -0.92, camZ * 0.35).normalize();
        rPalm.set(-rSide * 0.75, -0.15, -camZ * 0.64).normalize();

        lWrist.set(hipsP.x + lSide * 0.11, hipsP.y + 0.03, hipsP.z + camZ * 0.05);
        lPole.set(lSide * 0.85, -0.25, camZ * 0.25);
        lFDir.set(-lSide * 0.20, -0.92, camZ * 0.35).normalize();
        lPalm.set(-lSide * 0.75, -0.15, -camZ * 0.64).normalize();

    } else if (currentPose === 'arms_folded_relaxed') {
        // Natural folded arms across lower chest with relaxed shoulders and gentle breathing sympathy
        const reachScale = Math.max(0.85, Math.min(1.35, reach / 0.397));
        const sOffset = Math.abs(S_R.x) > 0.12 ? 0.05 : 0.0;
        hipsRot = [0, rSide * 0.02, 0];
        spineRot = [fwd * -0.025, 0, 0];
        chestRot = [fwd * -0.015, 0, 0];
        headRot = [fwd * 0.01, rSide * 0.02, -rSide * 0.03];
        lShoulderRot = [0, 0, lSide * 0.04];
        rShoulderRot = [0, 0, rSide * 0.04];

        leftHandShape = 'cupped';
        rightHandShape = 'cupped';

        // Right hand folds across to tuck naturally over left biceps/forearm
        rWrist.set(lSide * (0.08 * reachScale + sOffset), chestP.y - 0.05 * reachScale, chestP.z + camZ * (0.17 * reachScale));
        rPole.set(rSide * 0.75, -0.60, camZ * 0.45);
        rFDir.set(-rSide * 0.90, 0.12, camZ * 0.40).normalize();
        rPalm.set(0, -0.75, -camZ * 0.65).normalize();

        // Left hand folds underneath and rests near right lower ribs/elbow
        lWrist.set(rSide * (0.08 * reachScale + sOffset), chestP.y - 0.08 * reachScale, chestP.z + camZ * (0.15 * reachScale));
        lPole.set(lSide * 0.75, -0.60, camZ * 0.45);
        lFDir.set(rSide * 0.90, 0.12, camZ * 0.40).normalize();
        lPalm.set(0, 0.75, -camZ * 0.65).normalize();

    } else if (currentPose === 'hands_pocket_relaxed') {
        // Casual stance with hands resting near pocket level with natural clearance from hips
        const reachScale = Math.max(0.85, Math.min(1.35, reach / 0.397));
        const sOffset = Math.abs(S_R.x) > 0.12 ? 0.04 : 0.0;
        hipsRot = [0, -rSide * 0.02, rSide * 0.03];
        spineRot = [0, 0, -rSide * 0.02];
        headRot = [fwd * 0.02, rSide * 0.03, rSide * 0.03];
        lShoulderRot = [0, 0, lSide * 0.02];
        rShoulderRot = [0, 0, rSide * 0.02];

        leftHandShape = 'cupped';
        rightHandShape = 'cupped';

        rWrist.set(hipsP.x + rSide * (0.145 * reachScale + sOffset), hipsP.y + 0.06 * reachScale, hipsP.z + camZ * 0.05);
        rPole.set(rSide * 0.90, -0.15, camZ * 0.25);
        rFDir.set(-rSide * 0.15, -0.94, camZ * 0.30).normalize();
        rPalm.set(-rSide * 0.85, -0.10, -camZ * 0.52).normalize();

        lWrist.set(hipsP.x + lSide * (0.145 * reachScale + sOffset), hipsP.y + 0.06 * reachScale, hipsP.z + camZ * 0.05);
        lPole.set(lSide * 0.90, -0.15, camZ * 0.25);
        lFDir.set(-lSide * 0.15, -0.94, camZ * 0.30).normalize();
        lPalm.set(-lSide * 0.85, -0.10, -camZ * 0.52).normalize();

    } else if (currentPose === 'thoughtful_chin_touch') {
        // Soft conversational chin/jaw touch
        const reachScale = Math.max(0.85, Math.min(1.35, reach / 0.397));
        const sOffset = Math.abs(S_R.x) > 0.12 ? 0.03 : 0.0;
        headRot = [fwd * 0.04, rSide * 0.08, rSide * 0.06];
        spineRot = [fwd * -0.015, 0, 0];
        rightHandShape = 'chinTouch';
        leftHandShape = 'relaxed';

        rWrist.set(headP.x + rSide * (0.085 * reachScale), headP.y - 0.06 * reachScale, headP.z + camZ * (0.13 * reachScale));
        rPole.set(rSide * 0.70, -0.50, camZ * 0.40);
        rFDir.set(-rSide * 0.25, 0.88, camZ * 0.38).normalize();
        rPalm.set(-rSide * 0.65, 0.15, -camZ * 0.74).normalize();

        lWrist.set(hipsP.x + lSide * (0.13 * reachScale + sOffset), hipsP.y + 0.05 * reachScale, hipsP.z + camZ * 0.04);
        lPole.set(lSide * 0.95, -0.10, -camZ * 0.15);
        lFDir.set(-lSide * 0.25, -0.88, camZ * 0.38).normalize();
        lPalm.set(-lSide * 0.85, -0.15, -camZ * 0.50).normalize();

    } else if (currentPose === 'tactical_stand_at_ease') {
        // Ren: Disciplined at-ease posture with clasped hands low in front and upright spine
        const reachScale = Math.max(0.85, Math.min(1.35, reach / 0.397));
        spineRot = [fwd * -0.035, 0, 0];
        chestRot = [fwd * -0.03, 0, 0];
        headRot = [fwd * -0.015, 0, 0];
        rShoulderRot = [0, 0, rSide * 0.05];
        lShoulderRot = [0, 0, lSide * 0.05];
        rightHandShape = 'clasped';
        leftHandShape = 'clasped';

        // Hands resting naturally in front of pelvis/belt with clearance from tactical clothing
        rWrist.set(rSide * 0.032, hipsP.y + 0.055 * reachScale, hipsP.z + camZ * (0.12 * reachScale));
        rPole.set(rSide * 0.75, -0.45, camZ * 0.35);
        rFDir.set(-rSide * 0.75, -0.48, camZ * 0.45).normalize();
        rPalm.set(-rSide * 0.45, 0.15, -camZ * 0.88).normalize();

        lWrist.set(lSide * 0.032, hipsP.y + 0.055 * reachScale, hipsP.z + camZ * (0.12 * reachScale));
        lPole.set(lSide * 0.75, -0.45, camZ * 0.35);
        lFDir.set(-lSide * 0.75, -0.48, camZ * 0.45).normalize();
        lPalm.set(-lSide * 0.45, 0.15, -camZ * 0.88).normalize();

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

    } else if (currentPose === 'idle_airi_butterfly') {
        // Airi Unique Idle: Gently extends right hand forward with finger perched, head tilted curiously tracking the Cyber-Butterfly
        const phaseT = Math.max(0, time - idleInteractionStartTime);
        const flutterBob = Math.sin(phaseT * 3.5) * 0.015;

        rightHandShape = 'point';
        leftHandShape = 'cupped';

        hipsRot = [0, -lSide * 0.04, lSide * 0.03];
        spineRot = [fwd * 0.04, -lSide * 0.08, lSide * 0.03];
        chestRot = [fwd * 0.05, -lSide * 0.05, 0];
        neckRot = [fwd * -0.02, -rSide * 0.08, rSide * 0.08];
        headRot = [
            fwd * -0.05,
            -rSide * (0.15 + Math.sin(phaseT * 1.5) * 0.05),
            rSide * (0.12 + Math.sin(phaseT * 2.0) * 0.03),
        ];
        rShoulderRot = [fwd * 0.12, -rSide * 0.04, rSide * 0.08];

        // Right hand reaches gently forward and upward, finger extended for butterfly perch
        const perchTarget = new THREE.Vector3(
            chestP.x + rSide * 0.16,
            chestP.y + 0.12 + flutterBob,
            chestP.z + camZ * 0.26
        );
        rFDir.set(-rSide * 0.12, 0.35, camZ * 0.93).normalize();
        rWrist.copy(perchTarget).addScaledVector(rFDir, -rigMetrics.LHand);
        rPole.set(rSide * 0.55, -0.75, camZ * 0.35);
        rPalm.set(-rSide * 0.35, 0.88, camZ * 0.32).normalize();

        // Left hand rests gently at lower waist/hip
        lWrist.set(hipsP.x + lSide * 0.13, hipsP.y + 0.07, hipsP.z + camZ * 0.05);
        lPole.set(lSide * 0.95, -0.1, -camZ * 0.28);
        lFDir.set(-lSide * 0.35, -0.85, camZ * 0.38).normalize();
        lPalm.set(-lSide * 0.82, -0.22, -camZ * 0.52).normalize();

    } else if (currentPose === 'idle_ren_drone') {
        // Ren Unique Idle: Tactical upright command posture, left hand directs tactical drone, right hand on utility belt
        const phaseT = Math.max(0, time - idleInteractionStartTime);
        const scanPulse = Math.sin(phaseT * 2.0) * 0.012;

        leftHandShape = 'open';
        rightHandShape = 'fist';

        hipsRot = [0, rSide * 0.06, 0];
        spineRot = [fwd * -0.03, rSide * 0.08, -rSide * 0.02];
        chestRot = [fwd * 0.04, rSide * 0.05, 0];
        neckRot = [fwd * 0.02, rSide * 0.08, 0];
        headRot = [fwd * 0.02, rSide * (0.16 + scanPulse), -rSide * 0.03];
        lShoulderRot = [fwd * 0.15, lSide * 0.06, lSide * 0.12];
        rShoulderRot = [fwd * 0.05, 0, rSide * 0.04];

        // Left arm raised forward-left at shoulder height, issuing tactical guidance command
        const droneDirectTarget = new THREE.Vector3(
            chestP.x + lSide * 0.22,
            chestP.y + 0.14 + scanPulse,
            chestP.z + camZ * 0.24
        );
        lFDir.set(lSide * 0.25, 0.32, camZ * 0.91).normalize();
        lWrist.copy(droneDirectTarget).addScaledVector(lFDir, -rigMetrics.LHand);
        lPole.set(lSide * 0.72, -0.62, camZ * 0.32);
        lPalm.set(0, -0.92, -camZ * 0.38).normalize();

        // Right hand anchored firmly at tactical utility waist/belt
        rWrist.set(hipsP.x + rSide * 0.145, hipsP.y + 0.04, hipsP.z + camZ * 0.03);
        rPole.set(rSide * 1.05, 0.05, -camZ * 0.35);
        rFDir.set(-rSide * 0.22, -0.92, camZ * 0.32).normalize();
        rPalm.set(-rSide * 0.88, -0.15, -camZ * 0.45).normalize();

    } else if (currentPose === 'idle_gaming_console') {
        // Dual-Grip Cyber Handheld Console Stance: Both hands grip console naturally at chest height with curved fingers around grips
        const phaseT = Math.max(0, time - idleInteractionStartTime);
        const thumbGamingTap = Math.sin(phaseT * 7.5) * 0.004;
        const reachScale = Math.max(0.85, Math.min(1.35, reach / 0.397));
        const sOffset = Math.abs(S_R.x) > 0.12 ? 0.025 : 0.0;

        leftHandShape = 'fist';
        rightHandShape = 'fist';

        spineRot = [fwd * 0.04, 0, 0];
        chestRot = [fwd * 0.03, 0, 0];
        neckRot = [fwd * 0.08, 0, 0];
        headRot = [fwd * 0.14, Math.sin(phaseT * 1.8) * 0.02, 0];
        lShoulderRot = [fwd * 0.06, 0, lSide * 0.03];
        rShoulderRot = [fwd * 0.06, 0, rSide * 0.03];

        // Ergonomic console hold: raised up, extended outward, and angled upward facing the avatar's eyes/face
        const consoleCenterY = chestP.y + 0.015 * reachScale;
        const consoleCenterZ = chestP.z + camZ * (0.315 * reachScale);

        rWrist.set(rSide * (0.098 + sOffset), consoleCenterY + thumbGamingTap, consoleCenterZ);
        rPole.set(rSide * 0.65, -0.65, camZ * 0.38);
        rFDir.set(-rSide * 0.15, 0.62, camZ * 0.77).normalize();
        rPalm.set(-rSide * 0.90, -0.42, camZ * 0.10).normalize();

        lWrist.set(lSide * (0.098 + sOffset), consoleCenterY - thumbGamingTap, consoleCenterZ);
        lPole.set(lSide * 0.65, -0.65, camZ * 0.38);
        lFDir.set(-lSide * 0.15, 0.62, camZ * 0.77).normalize();
        lPalm.set(-lSide * 0.90, -0.42, camZ * 0.10).normalize();

    } else if (currentPose === 'sword_guard_ready') {
        // 2-Handed Cyber Tactical Plasma Katana Guard: Anatomically aligned two-handed grip on the hilt
        const phaseT = Math.max(0, time - idleInteractionStartTime);
        const swordBreathing = Math.sin(phaseT * 1.8) * 0.005;
        const reachScale = Math.max(0.85, Math.min(1.35, reach / 0.397));
        const sOffset = Math.abs(S_R.x) > 0.12 ? 0.025 : 0.0;

        leftHandShape = 'fist';
        rightHandShape = 'fist';

        hipsRot = [0, -rSide * 0.12, rSide * 0.02];
        spineRot = [fwd * -0.02, -rSide * 0.08, 0];
        chestRot = [fwd * 0.02, -rSide * 0.07, 0];
        headRot = [fwd * -0.02, rSide * 0.12, -rSide * 0.03];
        rShoulderRot = [fwd * 0.12, 0, rSide * 0.06];
        lShoulderRot = [fwd * 0.10, 0, lSide * 0.06];

        // Guard centerline in front of torso: blade held upright tilted ~15° forward
        const guardLeadX = rSide * (0.045 + sOffset);
        const guardLeadY = chestP.y + 0.05 * reachScale + swordBreathing;
        const guardLeadZ = chestP.z + camZ * (0.235 * reachScale);

        // Right hand (dominant, top grip just beneath the tsuba guard):
        // Hand extends along the blade upward/forward; palm wraps hilt
        rWrist.set(guardLeadX, guardLeadY, guardLeadZ);
        rPole.set(rSide * 0.70, -0.60, camZ * 0.35);
        rFDir.set(-rSide * 0.08, 0.96, camZ * 0.25).normalize();
        rPalm.set(-rSide * 0.88, -0.12, -camZ * 0.45).normalize();

        // Left hand (subordinate, grips lower hilt 8cm beneath right hand along the same axis):
        lWrist.set(guardLeadX - rSide * 0.008, guardLeadY - 0.078 * reachScale, guardLeadZ - 0.020);
        lPole.set(lSide * 0.65, -0.70, camZ * 0.35);
        lFDir.set(-lSide * 0.08, 0.96, camZ * 0.25).normalize();
        lPalm.set(-lSide * 0.88, -0.12, -camZ * 0.45).normalize();

    } else if (currentPose === 'sword_sheathe_flourish') {
        // Tactical Plasma Blade Flourish: Right hand holds drawn blade angled outwards with palm pronation, Left hand rested naturally at waist
        const phaseT = Math.max(0, time - idleInteractionStartTime);
        const reachScale = Math.max(0.85, Math.min(1.35, reach / 0.397));
        const sOffset = Math.abs(S_R.x) > 0.12 ? 0.03 : 0.0;

        rightHandShape = 'fist';
        leftHandShape = 'relaxed';

        hipsRot = [0, rSide * 0.06, 0];
        spineRot = [fwd * -0.02, rSide * 0.03, -rSide * 0.02];
        chestRot = [fwd * -0.01, rSide * 0.02, 0];
        headRot = [fwd * -0.02, -rSide * 0.06, rSide * 0.03];
        rShoulderRot = [fwd * 0.06, 0, rSide * 0.10];
        lShoulderRot = [fwd * 0.03, 0, lSide * 0.04];

        // Right hand holds blade pointing down-right with wrist pronated so knuckles face viewer
        rWrist.set(rSide * (0.22 * reachScale + sOffset), hipsP.y + 0.08 * reachScale, hipsP.z + camZ * (0.17 * reachScale));
        rPole.set(rSide * 0.75, -0.55, camZ * 0.35);
        rFDir.set(rSide * 0.20, -0.88, camZ * 0.43).normalize();
        rPalm.set(-rSide * 0.60, 0.35, camZ * 0.72).normalize();

        // Left hand rests naturally on belt/hip
        lWrist.set(lSide * (0.13 * reachScale + sOffset), hipsP.y + 0.05 * reachScale, hipsP.z + camZ * 0.05);
        lPole.set(lSide * 0.90, -0.20, -camZ * 0.20);
        lFDir.set(-lSide * 0.25, -0.90, camZ * 0.35).normalize();
        lPalm.set(-lSide * 0.85, -0.20, -camZ * 0.48).normalize();

    } else if (currentPose === 'idle_airi_holodice') {
        // Airi Unique Prop Idle: Holds right hand gently cupped under floating quantum holo-dice
        const phaseT = Math.max(0, time - idleInteractionStartTime);
        const diceBob = Math.sin(phaseT * 3.2) * 0.012;

        rightHandShape = 'cupped';
        leftHandShape = 'relaxed';

        hipsRot = [0, -lSide * 0.04, lSide * 0.03];
        spineRot = [fwd * 0.04, -lSide * 0.06, lSide * 0.02];
        chestRot = [fwd * 0.05, -lSide * 0.04, 0];
        neckRot = [fwd * 0.04, -rSide * 0.06, rSide * 0.06];
        headRot = [fwd * 0.09, -rSide * 0.12, rSide * 0.10];
        rShoulderRot = [fwd * 0.08, -rSide * 0.03, rSide * 0.06];

        rWrist.set(chestP.x + rSide * 0.14, chestP.y + 0.03 + diceBob, chestP.z + camZ * 0.22);
        rPole.set(rSide * 0.65, -0.65, camZ * 0.35);
        rFDir.set(-rSide * 0.15, 0.45, camZ * 0.88).normalize();
        rPalm.set(-rSide * 0.25, 0.92, camZ * 0.28).normalize();

        lWrist.set(hipsP.x + lSide * 0.13, hipsP.y + 0.06, hipsP.z + camZ * 0.05);
        lPole.set(lSide * 0.95, -0.1, -camZ * 0.25);
        lFDir.set(-lSide * 0.35, -0.85, camZ * 0.38).normalize();
        lPalm.set(-lSide * 0.82, -0.22, -camZ * 0.52).normalize();

    } else if (currentPose === 'idle_ren_datapad') {
        // Ren Unique Prop Idle: Left hand holds tactical datapad, right hand ready to enter input
        const phaseT = Math.max(0, time - idleInteractionStartTime);
        const tapPulse = Math.sin(phaseT * 4.0) * 0.008;

        leftHandShape = 'cupped';
        rightHandShape = 'point';

        hipsRot = [0, rSide * 0.04, 0];
        spineRot = [fwd * 0.03, rSide * 0.04, -rSide * 0.02];
        chestRot = [fwd * 0.04, 0, 0];
        neckRot = [fwd * 0.06, 0, 0];
        headRot = [fwd * 0.14, rSide * 0.05, 0];
        lShoulderRot = [fwd * 0.08, 0, lSide * 0.04];
        rShoulderRot = [fwd * 0.08, 0, rSide * 0.04];

        // Left hand holds datapad at lower chest
        lWrist.set(chestP.x + lSide * 0.08, chestP.y - 0.01, chestP.z + camZ * 0.24);
        lPole.set(lSide * 0.70, -0.60, camZ * 0.35);
        lFDir.set(-lSide * 0.20, 0.55, camZ * 0.81).normalize();
        lPalm.set(0, 0.85, camZ * 0.52).normalize();

        // Right hand hovers over datapad screen to tap coordinates
        rWrist.set(chestP.x + rSide * 0.02, chestP.y + 0.05 + tapPulse, chestP.z + camZ * 0.26);
        rPole.set(rSide * 0.70, -0.60, camZ * 0.35);
        rFDir.set(-rSide * 0.25, 0.30, camZ * 0.92).normalize();
        rPalm.set(-rSide * 0.75, -0.35, camZ * 0.55).normalize();

    } else if (currentPose === 'twin_synergy_combat') {
        // Dual Twin Combat Stance: High-readiness tactical posture
        rightHandShape = 'fist';
        leftHandShape = 'fist';
        hipsRot = [0, -rSide * 0.08, rSide * 0.03];
        spineRot = [fwd * -0.02, -rSide * 0.05, 0];
        chestRot = [fwd * 0.03, -rSide * 0.04, 0];
        headRot = [fwd * -0.02, rSide * 0.08, -rSide * 0.02];
        rShoulderRot = [fwd * 0.10, 0, rSide * 0.08];
        lShoulderRot = [fwd * 0.08, 0, lSide * 0.06];

        rWrist.set(rSide * 0.08, chestP.y + 0.06, chestP.z + camZ * 0.22);
        rPole.set(rSide * 0.75, -0.55, camZ * 0.35);
        rFDir.set(-rSide * 0.10, 0.94, camZ * 0.32).normalize();
        rPalm.set(-rSide * 0.85, -0.15, -camZ * 0.50).normalize();

        lWrist.set(lSide * 0.10, chestP.y - 0.02, chestP.z + camZ * 0.18);
        lPole.set(lSide * 0.75, -0.55, camZ * 0.35);
        lFDir.set(lSide * 0.40, -0.80, camZ * 0.44).normalize();
        lPalm.set(-lSide * 0.75, -0.20, -camZ * 0.63).normalize();

    } else if (currentPose === 'twin_synergy_briefing') {
        // Dual Twin Briefing Stance: Coordinated mission analysis
        rightHandShape = 'point';
        leftHandShape = 'cupped';
        spineRot = [fwd * 0.03, -rSide * 0.04, 0];
        chestRot = [fwd * 0.02, 0, 0];
        headRot = [fwd * 0.04, rSide * 0.08, rSide * 0.04];

        rWrist.set(rSide * 0.10, chestP.y + 0.08, chestP.z + camZ * 0.23);
        rPole.set(rSide * 0.70, -0.55, camZ * 0.35);
        rFDir.set(-rSide * 0.25, 0.45, camZ * 0.85).normalize();
        rPalm.set(-rSide * 0.60, 0.35, camZ * 0.70).normalize();

        lWrist.set(lSide * 0.12, hipsP.y + 0.07, hipsP.z + camZ * 0.06);
        lPole.set(lSide * 0.90, -0.15, -camZ * 0.20);
        lFDir.set(-lSide * 0.30, -0.88, camZ * 0.36).normalize();
        lPalm.set(-lSide * 0.85, -0.15, -camZ * 0.50).normalize();

    // -----------------------------------------------------------------
    // 6. SEAMLESS INTERACTION & DYADIC POSES (Meta Seamless Dataset Priors)
    // -----------------------------------------------------------------
    } else if (currentPose === 'active_listening_nod') {
        // Expressive backchannel: rhythmic head nodding with slight tilt, attentive relaxed arms
        const nodWave = Math.sin(time * 6.2) * 0.09;
        const tiltWave = Math.sin(time * 2.1) * 0.05 * rSide;
        headRot = [fwd * (0.07 + nodWave), tiltWave * 0.5, tiltWave];
        spineRot = [fwd * 0.03, 0, 0];
        chestRot = [fwd * 0.02, 0, 0];
        rightHandShape = 'relaxed';
        leftHandShape = 'relaxed';

        rWrist.set(hipsP.x + rSide * 0.11, hipsP.y + 0.04, hipsP.z + camZ * 0.08);
        rPole.set(rSide * 0.75, -0.4, camZ * 0.25);
        rFDir.set(-rSide * 0.25, -0.85, camZ * 0.35).normalize();
        rPalm.set(-rSide * 0.75, -0.2, camZ * 0.6).normalize();

        lWrist.set(hipsP.x + lSide * 0.11, hipsP.y + 0.04, hipsP.z + camZ * 0.08);
        lPole.set(lSide * 0.75, -0.4, camZ * 0.25);
        lFDir.set(-lSide * 0.25, -0.85, camZ * 0.35).normalize();
        lPalm.set(-lSide * 0.75, -0.2, camZ * 0.6).normalize();

    } else if (currentPose === 'thoughtful_gaze_aversion') {
        // Formulating thoughts: head tilts upward and lateral, hand raised near chin/cheek
        const subtleDrift = Math.sin(time * 1.5) * 0.02;
        headRot = [fwd * -0.09 + subtleDrift, rSide * 0.18, rSide * 0.12];
        neckRot = [fwd * -0.04, rSide * 0.08, rSide * 0.05];
        spineRot = [fwd * 0.02, -rSide * 0.03, 0];
        rightHandShape = 'cupped';
        leftHandShape = 'relaxed';

        rWrist.set(headP.x + rSide * 0.10, headP.y - 0.07, headP.z + camZ * 0.14);
        rPole.set(rSide * 0.8, -0.5, camZ * 0.3);
        rFDir.set(-rSide * 0.3, 0.85, camZ * 0.4).normalize();
        rPalm.set(-rSide * 0.5, 0.3, -camZ * 0.8).normalize();

        lWrist.set(hipsP.x + lSide * 0.12, hipsP.y + 0.06, hipsP.z + camZ * 0.05);
        lPole.set(lSide * 0.9, 0.0, -camZ * 0.2);
        lFDir.set(-lSide * 0.3, -0.8, camZ * 0.4).normalize();
        lPalm.set(-lSide * 0.8, -0.2, -camZ * 0.4).normalize();

    } else if (currentPose === 'turn_yield_inquiry') {
        // Yielding turn: slight open-palm inquiry gesture leaning toward user
        scenePosY = -0.008;
        spineRot = [fwd * 0.04, 0, 0];
        chestRot = [fwd * 0.03, 0, 0];
        headRot = [fwd * 0.03, 0, rSide * 0.04];
        rightHandShape = 'open';
        leftHandShape = 'open';

        rWrist.set(S_R.x + rSide * 0.08, chestP.y - 0.02, chestP.z + camZ * 0.22);
        rPole.set(rSide * 0.7, -0.5, camZ * 0.3);
        rFDir.set(-rSide * 0.2, 0.4, camZ * 0.88).normalize();
        rPalm.set(0, 0.9, camZ * 0.4).normalize();

        lWrist.set(S_L.x + lSide * 0.08, chestP.y - 0.02, chestP.z + camZ * 0.22);
        lPole.set(lSide * 0.7, -0.5, camZ * 0.3);
        lFDir.set(-lSide * 0.2, 0.4, camZ * 0.88).normalize();
        lPalm.set(0, 0.9, camZ * 0.4).normalize();

    } else if (currentPose === 'barge_in_alert') {
        // Immediate conversational yield upon interruption: subtle surprise recoil and attentiveness
        headRot = [fwd * -0.06, 0, 0];
        spineRot = [fwd * -0.04, 0, 0];
        chestRot = [fwd * -0.03, 0, 0];
        rightHandShape = 'cupped';
        leftHandShape = 'cupped';

        rWrist.set(S_R.x + rSide * 0.06, chestP.y + 0.04, chestP.z + camZ * 0.16);
        rPole.set(rSide * 0.85, -0.3, camZ * 0.3);
        rFDir.set(-rSide * 0.3, 0.7, camZ * 0.6).normalize();
        rPalm.set(-rSide * 0.6, 0.2, camZ * 0.7).normalize();

        lWrist.set(S_L.x + lSide * 0.06, chestP.y + 0.04, chestP.z + camZ * 0.16);
        lPole.set(lSide * 0.85, -0.3, camZ * 0.3);
        lFDir.set(-lSide * 0.3, 0.7, camZ * 0.6).normalize();
        lPalm.set(-lSide * 0.6, 0.2, camZ * 0.7).normalize();

    } else if (currentPose === 'tactical_composure') {
        // Ren (Older brother tactical discipline): Broad shoulders, upright spine, disciplined ready stance
        spineRot = [fwd * -0.03, 0, 0];
        chestRot = [fwd * -0.04, 0, 0];
        headRot = [fwd * -0.02, 0, 0];
        rShoulderRot = [0, 0, rSide * 0.06];
        lShoulderRot = [0, 0, lSide * 0.06];
        rightHandShape = 'fist';
        leftHandShape = 'fist';

        rWrist.set(hipsP.x + rSide * 0.14, hipsP.y + 0.05, hipsP.z + camZ * 0.04);
        rPole.set(rSide * 0.95, 0.0, -camZ * 0.2);
        rFDir.set(-rSide * 0.25, -0.9, camZ * 0.3).normalize();
        rPalm.set(-rSide * 0.9, -0.15, camZ * 0.35).normalize();

        lWrist.set(hipsP.x + lSide * 0.14, hipsP.y + 0.05, hipsP.z + camZ * 0.04);
        lPole.set(lSide * 0.95, 0.0, -camZ * 0.2);
        lFDir.set(-lSide * 0.25, -0.9, camZ * 0.3).normalize();
        lPalm.set(-lSide * 0.9, -0.15, camZ * 0.35).normalize();
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

    // Direct Parametric Model Skeleton Control (AI Router / Neural Model Hybrid Director)
    if (activeSkeletonDirectives) {
        if (typeof activeSkeletonDirectives.spine_pitch === 'number') {
            spineRot[0] += fwd * activeSkeletonDirectives.spine_pitch;
        }
        if (typeof activeSkeletonDirectives.spine_yaw === 'number') {
            spineRot[1] += rSide * activeSkeletonDirectives.spine_yaw;
        }
        if (typeof activeSkeletonDirectives.spine_roll === 'number') {
            spineRot[2] += rSide * activeSkeletonDirectives.spine_roll;
        }
        if (typeof activeSkeletonDirectives.hips_roll === 'number') {
            hipsRot[2] += rSide * activeSkeletonDirectives.hips_roll;
        }
        if (typeof activeSkeletonDirectives.hips_drop === 'number') {
            scenePosY -= activeSkeletonDirectives.hips_drop;
        }
        if (typeof activeSkeletonDirectives.shoulder_tension === 'number') {
            const t = activeSkeletonDirectives.shoulder_tension;
            rShoulderRot[2] += rSide * t * 0.05;
            lShoulderRot[2] += lSide * t * 0.05;
        }
    }

    // Superimpose biological breathing, righting reflex, and speech prosody onto active pose
    if (currentPose !== 'idle') {
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

    // Biomechanical Studio Body Pose Adjustments (Real-time Parametric Slider Overrides)
    if (typeof activeBodyPoseAdjustments !== 'undefined' && activeBodyPoseAdjustments.enabled) {
        const isTargetMatch = activeBodyPoseAdjustments.target === 'active' || 
            (activeBodyPoseAdjustments.target === 'airi' && !isRenActive()) ||
            (activeBodyPoseAdjustments.target === 'ren' && isRenActive()) ||
            activeBodyPoseAdjustments.target === 'both';

        if (isTargetMatch) {
            // Head & Neck (radians from degrees)
            headRot[0] += fwd * (activeBodyPoseAdjustments.headPitch * Math.PI / 180);
            headRot[1] += rSide * (activeBodyPoseAdjustments.headYaw * Math.PI / 180);
            headRot[2] += rSide * (activeBodyPoseAdjustments.headRoll * Math.PI / 180);
            neckRot[0] += fwd * (activeBodyPoseAdjustments.neckPitch * Math.PI / 180);

            // Spine, Torso & Pelvis
            spineRot[0] += fwd * (activeBodyPoseAdjustments.spineLean * Math.PI / 180);
            spineRot[1] += rSide * (activeBodyPoseAdjustments.spineTwist * Math.PI / 180);
            spineRot[2] += rSide * (activeBodyPoseAdjustments.spineRoll * Math.PI / 180);
            chestRot[0] += fwd * activeBodyPoseAdjustments.chestBreath;
            hipsRot[1] += rSide * (activeBodyPoseAdjustments.pelvisSway * Math.PI / 180);
            hipsRot[2] += rSide * (activeBodyPoseAdjustments.pelvisTilt * Math.PI / 180);
            scenePosY += activeBodyPoseAdjustments.crouch;

            // Stance & Lower Body
            const sWidthRad = (activeBodyPoseAdjustments.stanceWidth * Math.PI / 180);
            lUpperLegRot[2] -= sWidthRad;
            rUpperLegRot[2] += sWidthRad;
            const kneeRad = (activeBodyPoseAdjustments.kneeBend * Math.PI / 180);
            lLowerLegRot[0] += kneeRad;
            rLowerLegRot[0] += kneeRad;

            // Arms & Hand Positions (offset in world/rig space)
            rWrist.y += activeBodyPoseAdjustments.rArmLift;
            rWrist.z += camZ * activeBodyPoseAdjustments.rArmReach;
            rWrist.x += rSide * activeBodyPoseAdjustments.rArmSide;
            rPole.x += rSide * activeBodyPoseAdjustments.rElbow;

            lWrist.y += activeBodyPoseAdjustments.lArmLift;
            lWrist.z += camZ * activeBodyPoseAdjustments.lArmReach;
            lWrist.x += lSide * activeBodyPoseAdjustments.lArmSide;
            lPole.x += lSide * activeBodyPoseAdjustments.lElbow;

            if (activeBodyPoseAdjustments.rHandShape && activeBodyPoseAdjustments.rHandShape !== 'auto') {
                rightHandShape = activeBodyPoseAdjustments.rHandShape;
            }
            if (activeBodyPoseAdjustments.lHandShape && activeBodyPoseAdjustments.lHandShape !== 'auto') {
                leftHandShape = activeBodyPoseAdjustments.lHandShape;
            }
        }
    }

    const targetAiriX = dualTwinModeActive ? -0.42 : 0;
    const targetAiriYaw = dualTwinModeActive ? (baseFacingYaw + 0.12) : baseFacingYaw;
    currentVrm.scene.position.x = THREE.MathUtils.lerp(currentVrm.scene.position.x, targetAiriX, speed);
    currentVrm.scene.position.y = THREE.MathUtils.lerp(currentVrm.scene.position.y, scenePosY, speed);
    currentVrm.scene.position.z = THREE.MathUtils.lerp(currentVrm.scene.position.z, 0, speed);
    currentVrm.scene.rotation.y = THREE.MathUtils.lerp(currentVrm.scene.rotation.y, targetAiriYaw, speed);
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

        if (typeof activeBodyPoseAdjustments !== 'undefined' && activeBodyPoseAdjustments.enabled) {
            rWrist.y += activeBodyPoseAdjustments.rArmLift;
            rWrist.z += camZ * activeBodyPoseAdjustments.rArmReach;
            rWrist.x += rSide * activeBodyPoseAdjustments.rArmSide;
            rPole.x += rSide * activeBodyPoseAdjustments.rElbow;

            lWrist.y += activeBodyPoseAdjustments.lArmLift;
            lWrist.z += camZ * activeBodyPoseAdjustments.lArmReach;
            lWrist.x += lSide * activeBodyPoseAdjustments.lArmSide;
            lPole.x += lSide * activeBodyPoseAdjustments.lElbow;
        }
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
let activeSkeletonDirectives = null;
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
    const activeChar = isRenActive() ? 'ren' : 'airi';
    const pool = getSpeakingPosePoolForCharacter(activeChar, key);
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
        const isMobile = window.innerWidth <= 768;
        const mobileDistMult = isMobile ? (window.innerHeight > window.innerWidth ? 1.35 : 1.15) : 1.0;
        baseCameraTargetY = headPos.y - (isFBX ? 0.38 : (isMobile ? 0.28 : 0.22));
        baseCameraY = headPos.y - (isFBX ? 0.18 : (isMobile ? 0.12 : 0.08));
        baseCameraZ = headPos.z + (isFBX ? 2.45 : 1.65) * mobileDistMult;
        controls.target.set(headPos.x, baseCameraTargetY, headPos.z);
        camera.position.set(headPos.x, baseCameraY, baseCameraZ);
        controls.update();
    }
}

window.setCameraFraming = (targetY, camY, camZ) => {
    if (typeof targetY === 'number') baseCameraTargetY = targetY;
    if (typeof camY === 'number') baseCameraY = camY;
    if (typeof camZ === 'number') baseCameraZ = camZ;
    if (controls) {
        controls.target.y = baseCameraTargetY;
        controls.update();
    }
    if (camera) {
        camera.position.y = baseCameraY;
        camera.position.z = baseCameraZ;
    }
};

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
window.getCurrentPose = () => currentPose;
window.applyCharacterProtocolState = applyCharacterProtocolState;
window.getActiveSkeletonDirectives = () => activeSkeletonDirectives;

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
        btnId: 'btn-error',
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

    ['btn-idle', 'btn-listening', 'btn-thinking', 'btn-speaking', 'btn-error'].forEach((id) => {
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
        const { mat, isEye, isHair, isCloth, isBody } = emissiveMaterials[i];
        
        let baseCol = lerpedTrimColor;
        let mult = pulseFactor;
        
        if (isEye) {
            baseCol = lerpedEyeColor;
            mult = Math.max(1.15, pulseFactor * 1.35);
        } else if (isHair) {
            // Subtle cybernetic hair sheen reacting to active state
            baseCol = lerpedTrimColor;
            mult = pulseFactor * 0.42;
        } else if (isCloth || isBody) {
            // Cybernetic clothing conduit lines and tactical glove knuckles
            baseCol = lerpedTrimColor;
            mult = Math.max(1.0, pulseFactor * 1.35);
        }

        tempEmitOut.copy(baseCol).multiplyScalar(mult);

        // Standard Three.js emissive color
        if (mat.emissive) {
            mat.emissive.copy(tempEmitOut);
        }
        // Three.js ShaderMaterial / MToon uniform emissive
        if (mat.uniforms?.emissive?.value) {
            mat.uniforms.emissive.value.copy(tempEmitOut);
        }
        // Direct MToon emissiveMultiplier or intensity
        if (typeof mat.emissiveIntensity === 'number') {
            mat.emissiveIntensity = mult;
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
    } else if (state === 'error') {
        applyExpressionState('angry', 0.85);
        setPose(customPose || 'refuse');
        updateStatus(`State: Error / Exception Alert (#FF3B30) | Pose: ${currentPose}`);
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

const AIRI_EXCLUSIVE_POSES = [
    'sassy_hip_pop',
    'heart_hands_love',
    'shy_bashful_tuck',
    'hand_to_heart_sincere',
    'excited_victory_jump',
    'idle_airi_butterfly',
];

const REN_EXCLUSIVE_POSES = [
    'tactical_stand_at_ease',
    'arms_folded_relaxed',
    'hands_pocket_relaxed',
    'thoughtful_chin_touch',
    'crossed_arms_think',
    'idle_ren_drone',
];

function updatePoseButtonsForActiveModel() {
    const isRen = isRenActive();
    const isDual = activeModelId === 'dual';
    // 1. Filter Synthesized / Custom Poses tab
    document.querySelectorAll('#custom-pose-buttons button').forEach(btn => {
        const pose = btn.getAttribute('data-custom-pose');
        if (!pose) return;
        if (isDual) {
            btn.style.display = '';
        } else if (isRen && AIRI_EXCLUSIVE_POSES.includes(pose)) {
            btn.style.display = 'none';
        } else if (!isRen && REN_EXCLUSIVE_POSES.includes(pose)) {
            btn.style.display = 'none';
        } else {
            btn.style.display = '';
        }
    });

    // 2. Filter 3D Props & Gadgets tab (e.g. Butterfly for Airi, Recon Drone for Ren)
    document.querySelectorAll('#idle-interaction-buttons button').forEach(btn => {
        const pose = btn.getAttribute('data-pose');
        if (!pose) return;
        if (isDual) {
            btn.style.display = '';
        } else if (isRen && AIRI_EXCLUSIVE_POSES.includes(pose)) {
            btn.style.display = 'none';
        } else if (!isRen && REN_EXCLUSIVE_POSES.includes(pose)) {
            btn.style.display = 'none';
        } else {
            btn.style.display = '';
        }
    });

    // Update RL Trainer Header Label to reflect the character-specific human reference poses
    const rlHeader = document.querySelector('#rl-trainer-controls .preset-label, #tab-rl .preset-label');
    if (rlHeader) {
        rlHeader.innerText = isRen
            ? '🛡️ Ren Tactical RL Pose & Style Trainer (19):'
            : '🌸 Airi Cyber Companion RL Pose & Style Trainer (19):';
    }

    const exclTitle = document.getElementById('exclusives-tab-title');
    if (exclTitle) {
        exclTitle.innerText = isRen
            ? '🛡️ Ren Tactical Exclusive & Synthesized Poses:'
            : '🌸 Airi Cyber Exclusive & Synthesized Poses:';
    }
}
window.updatePoseButtonsForActiveModel = updatePoseButtonsForActiveModel;

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
        updatePoseButtonsForActiveModel();
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
    const skeletonParams = stateMsg.skeleton_params || stateMsg.skeleton || null;

    if (customPose && customPose.name) {
        registerAndEnsureCustomPoseButton(customPose);
    }
    activeSkeletonDirectives = skeletonParams;

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
        const charKey = isRenActive() ? 'ren' : 'airi';
        const res = await fetch(`/api/character/rl-status?character=${charKey}`);
        if (res.ok) {
            const st = await res.json();
            if (st && !st.offline) {
                updateRlRewardHud(null, st);
            }
        }
    } catch (e) {}
}

async function triggerRlPoseTraining(poseName = null, episodes = 18, simulateCurriculum = true) {
    const charKey = isRenActive() ? 'ren' : 'airi';
    const defaultFallback = charKey === 'ren' ? 'tactical_stand_at_ease' : 'cyber_salute';
    const targetPose =
        poseName ||
        (customPoseRegistry.has(currentPose) ? currentPose : defaultFallback);
    updateStatus(`⚡ RL Policy Training [${charKey.toUpperCase()}] on Reference "${targetPose}" (${episodes} episodes)...`);
    try {
        const res = await fetch('/api/character/rl-train', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pose_name: targetPose,
                episodes,
                simulate_curriculum: simulateCurriculum,
                character: charKey,
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
                    `🏆 RL Trained [${charKey.toUpperCase()}] "${lastRes.pose_name}": ${lastRes.initial_reward_pct}% → ${lastRes.final_reward_pct}% | Awarded +${ptsAwarded} pts!`
                );
                return data;
            }
        }
    } catch (e) {}
    updateStatus('⚠️ RL Pose Trainer unreachable — check HELIOS Core (:8000).');
    return null;
}

async function submitRlPoseFeedback(awardDelta = 100.0, poseOverride = null) {
    const charKey = isRenActive() ? 'ren' : 'airi';
    const defaultFallback = charKey === 'ren' ? 'tactical_stand_at_ease' : 'cyber_salute';
    const targetPose =
        poseOverride ||
        (customPoseRegistry.has(currentPose) ? currentPose : defaultFallback);
    const telemetry = computeLiveVrmBiomechanicalTelemetry();
    try {
        const res = await fetch('/api/character/rl-feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pose_name: targetPose,
                user_award_delta: awardDelta,
                browser_telemetry: telemetry,
                character: charKey,
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
                `${awardDelta >= 0 ? '🏆 Awarded' : '⚠️ Corrected'} [${charKey.toUpperCase()}] "${data.pose_name}" (${sign} RL pts) | Match: ${data.evaluation?.reward_pct ?? 100}%`
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
const btnModelDual = document.getElementById('btn-model-dual');

const TWIN_VRM_URL = 'models/Helios_Twin.vrm';

function clearModelActiveStates() {
    if (btnModelHelios) btnModelHelios.classList.remove('active');
    if (btnModelBase)   btnModelBase.classList.remove('active');
    if (btnModelTwin)   btnModelTwin.classList.remove('active');
    if (btnModelMeshy)  btnModelMeshy.classList.remove('active');
    if (btnModelDual)   btnModelDual.classList.remove('active');
}

function startDualTwinSynergy() {
    clearModelActiveStates();
    if (btnModelDual) btnModelDual.classList.add('active');
    activeModelId = 'dual';
    window.activeModelId = 'dual';
    dualTwinModeActive = true;
    window.dualTwinModeActive = true;
    updatePoseButtonsForActiveModel();
    updateStatus('👥 Synchronizing Dual Twin System: Loading Airi & Ren side-by-side...');

    const setupAiriPosition = () => {
        if (currentVrm?.scene) {
            currentVrm.scene.position.set(-0.42, 0, 0);
            currentVrm.scene.rotation.set(0, baseFacingYaw + 0.12, 0);
        }
    };

    const setupRenPosition = (vrm) => {
        if (vrm?.scene) {
            vrm.scene.position.set(0.42, 0, 0);
            vrm.scene.rotation.set(0, baseFacingYaw - 0.12, 0);
        }
    };

    const adjustDualCamera = () => {
        baseCameraTargetY = 1.15;
        baseCameraY = 1.25;
        baseCameraZ = 2.45;
        if (controls) {
            controls.target.set(0, 1.15, 0);
            controls.update();
        }
        if (camera) {
            camera.position.set(0, 1.25, 2.45);
        }
    };

    const loadRenSecondary = () => {
        if (secondaryVrm) {
            setupRenPosition(secondaryVrm);
            adjustDualCamera();
            setPose('twin_synergy_briefing');
            updateStatus('👥 Dual Twin Synergy Active: Airi & Ren Synchronized (Tactical Link Established)');
            return;
        }

        updateStatus('Loading Twin (Ren) Tactical Companion VRM...');
        loader.load(
            TWIN_VRM_URL,
            (gltf) => {
                const vrm = gltf.userData.vrm;
                secondaryVrm = vrm;
                window.secondaryVrm = vrm;
                scene.add(vrm.scene);
                VRMUtils.rotateVRM0(vrm);
                setupRenPosition(vrm);
                calibrateSkeletonAndRestPose(vrm, false);
                adjustDualCamera();
                setPose('twin_synergy_briefing');
                updateStatus('👥 Dual Twin Synergy Active: Airi & Ren Synchronized (Tactical Link Established)');
            },
            undefined,
            (err) => {
                console.error('Failed to load secondary Twin VRM:', err);
                updateStatus('Dual Twin Error: ' + (err?.message || err));
            }
        );
    };

    const isAiriCurrent = currentVrm && !isRenActive() && !currentVrm.isFBXModel;
    if (isAiriCurrent) {
        setupAiriPosition();
        loadRenSecondary();
    } else {
        loadVRM(DEFAULT_VRM_URL);
        const checkAiriReady = setInterval(() => {
            if (currentVrm && !isRenActive()) {
                clearInterval(checkAiriReady);
                setupAiriPosition();
                loadRenSecondary();
            }
        }, 150);
    }
}
window.startDualTwinSynergy = startDualTwinSynergy;

if (btnModelHelios) {
    btnModelHelios.onclick = () => {
        clearModelActiveStates();
        btnModelHelios.classList.add('active');
        activeModelId = 'airi';
        window.activeModelId = 'airi';
        dualTwinModeActive = false;
        window.dualTwinModeActive = false;
        updatePoseButtonsForActiveModel();
        loadVRM(DEFAULT_VRM_URL);
        fetchRlPoseStatus();
    };
}

if (btnModelTwin) {
    btnModelTwin.onclick = () => {
        clearModelActiveStates();
        btnModelTwin.classList.add('active');
        activeModelId = 'twin';
        window.activeModelId = 'twin';
        dualTwinModeActive = false;
        window.dualTwinModeActive = false;
        updatePoseButtonsForActiveModel();
        loadVRM(TWIN_VRM_URL);
        fetchRlPoseStatus();
    };
}

if (btnModelDual) {
    btnModelDual.onclick = () => {
        startDualTwinSynergy();
    };
}

if (btnModelMeshy) {
    btnModelMeshy.onclick = () => {
        clearModelActiveStates();
        btnModelMeshy.classList.add('active');
        activeModelId = 'airi';
        window.activeModelId = 'airi';
        dualTwinModeActive = false;
        window.dualTwinModeActive = false;
        updatePoseButtonsForActiveModel();
        loadFBXModel(MESHY_FBX_URL);
        fetchRlPoseStatus();
    };
}

if (btnModelBase) {
    btnModelBase.onclick = () => {
        clearModelActiveStates();
        btnModelBase.classList.add('active');
        activeModelId = 'airi';
        window.activeModelId = 'airi';
        dualTwinModeActive = false;
        window.dualTwinModeActive = false;
        updatePoseButtonsForActiveModel();
        loadVRM(BASE_VRM_URL);
        fetchRlPoseStatus();
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
const btnErrorEl = document.getElementById('btn-error');
if (btnErrorEl) {
    btnErrorEl.onclick = () => setTestState('error', 'refuse');
}
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
    idle_airi_butterfly: {
        status: '🦋 Airi Companion: Interacting with Holographic Cyber-Butterfly',
        popupBadge: 'CYBER-BUTTERFLY',
        popupBody: 'Airi is curiously guiding and perching her glowing Cybernetic Data Butterfly...',
        emotion: 'curious',
    },
    idle_ren_drone: {
        status: '🛰️ Ren Companion: Directing Tactical Recon Scout Drone telemetry',
        popupBadge: 'TACTICAL RECON',
        popupBody: 'Ren is coordinating tactical telemetry scanner and scouting perimeter with drone...',
        emotion: 'serious',
    },
    natural_weight_shift: {
        status: '⚖️ Idle Stance: Contrapposto weight shift with gentle breathing',
        popupBadge: 'WEIGHT SHIFT',
        popupBody: 'Standing relaxed in a natural contrapposto weight shift posture...',
        emotion: 'relaxed',
    },
    arms_folded_relaxed: {
        status: '🪢 Idle Stance: Arms folded across chest with relaxed shoulders',
        popupBadge: 'FOLDED ARMS',
        popupBody: 'Observing attentively with arms comfortably crossed across chest...',
        emotion: 'neutral',
    },
    hands_pocket_relaxed: {
        status: '👖 Idle Stance: Casual posture with hands resting at pockets',
        popupBadge: 'POCKET REST',
        popupBody: 'Relaxing casually with hands resting near pocket seams...',
        emotion: 'relaxed',
    },
    thoughtful_chin_touch: {
        status: '🧐 Idle Stance: Thoughtful conversational chin and jaw rest',
        popupBadge: 'CHIN TOUCH',
        popupBody: 'Contemplating and listening closely with hand resting at jawline...',
        emotion: 'curious',
    },
    tactical_stand_at_ease: {
        status: '🛡️ Idle Stance: Disciplined tactical stand-at-ease posture',
        popupBadge: 'STAND AT EASE',
        popupBody: 'Maintaining disciplined tactical readiness with hands clasped low...',
        emotion: 'serious',
    },
    idle_gaming_console: {
        status: '🎮 Cyber Console: Playing handheld tactical deck with holographic screen',
        popupBadge: 'CYBER CONSOLE',
        popupBody: 'Testing code exploits on custom overclocked handheld cyber deck...',
        emotion: 'excited',
    },
    sword_guard_ready: {
        status: '⚔️ Sword Combat: 2-Handed Cyber Tactical Plasma Blade combat guard',
        popupBadge: 'PLASMA KATANA',
        popupBody: 'Plasma blade ignited at full harmonic resonance in two-handed tactical guard...',
        emotion: 'serious',
    },
    sword_sheathe_flourish: {
        status: '🗡️ Sword Flourish: One-handed plasma blade flourish and ready stance',
        popupBadge: 'BLADE FLOURISH',
        popupBody: 'Executing high-speed plasma flourish before locking into defensive stance...',
        emotion: 'smug',
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

// Pose Drawer Segmented Tabs Switching
document.querySelectorAll('.pose-tab-btn').forEach(btn => {
    btn.onclick = () => {
        const targetTabId = btn.getAttribute('data-tab');
        if (!targetTabId) return;

        // Toggle active button
        document.querySelectorAll('.pose-tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Toggle active pane
        document.querySelectorAll('.pose-tab-pane').forEach(pane => {
            if (pane.id === targetTabId) {
                pane.classList.add('active');
            } else {
                pane.classList.remove('active');
            }
        });

        if (targetTabId === 'tab-adjust' && typeof applySelectedPropToTwins === 'function') {
            applySelectedPropToTwins(activePropId);
        }
    };
});

const POSE_TO_PROP_MAP = {
    idle_gaming_console: 'console',
    sword_guard_ready: 'katana',
    sword_sheathe_flourish: 'katana',
    idle_airi_butterfly: 'butterfly',
    idle_ren_drone: 'drone',
    idle_popup_curious: 'popup',
    idle_orb_curious: 'orb',
    idle_airi_holodice: 'holodice',
    idle_ren_datapad: 'datapad',
    twin_synergy_combat: 'katana',
    twin_synergy_briefing: 'datapad'
};

document.querySelectorAll('#idle-interaction-buttons button').forEach(btn => {
    btn.onclick = () => {
        const p = btn.getAttribute('data-pose');
        autoIdleTimer = 0;
        triggerIdleObjectOrWaitingAnimation(p, true);
        if (POSE_TO_PROP_MAP[p]) {
            activePropId = POSE_TO_PROP_MAP[p];
            if (selectActiveProp) {
                selectActiveProp.value = activePropId;
            }
            if (typeof syncActivePropSlidersUI === 'function') {
                syncActivePropSlidersUI();
            }
        }
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

function updateCyberDeckCanvas(time) {
    if (!interactiveSceneObjects) return;
    const { dckCanvas, dckCtx, dckTexture } = interactiveSceneObjects;
    if (!dckCtx || !dckCanvas) return;
    const w = dckCanvas.width, h = dckCanvas.height;
    dckCtx.fillStyle = '#080b12';
    dckCtx.fillRect(0, 0, w, h);

    // Cyber grid
    dckCtx.strokeStyle = 'rgba(0, 229, 255, 0.18)';
    dckCtx.lineWidth = 1;
    const gridSize = 24;
    const offset = (time * 20) % gridSize;
    for (let x = 0; x < w; x += gridSize) {
        dckCtx.beginPath();
        dckCtx.moveTo(x, 0);
        dckCtx.lineTo(x, h);
        dckCtx.stroke();
    }
    for (let y = offset; y < h; y += gridSize) {
        dckCtx.beginPath();
        dckCtx.moveTo(0, y);
        dckCtx.lineTo(w, y);
        dckCtx.stroke();
    }

    // Header banner
    dckCtx.fillStyle = '#00e5ff';
    dckCtx.font = 'bold 16px "SF Mono", monospace';
    dckCtx.fillText('HEL-DCK-01 // ARCADE DECK', 20, 30);

    // Telemetry
    dckCtx.fillStyle = '#00ff88';
    dckCtx.font = '12px monospace';
    dckCtx.fillText('TWIN LINK: ACTIVE  |  144Hz  |  BUFFER: OK', 20, 52);

    // Waveform Oscilloscope
    dckCtx.strokeStyle = '#00e5ff';
    dckCtx.lineWidth = 2.5;
    dckCtx.beginPath();
    for (let x = 20; x < w - 20; x += 4) {
        const waveY = h / 2 + Math.sin(x * 0.04 + time * 6.0) * 28 + Math.cos(x * 0.08 - time * 4.0) * 12;
        if (x === 20) dckCtx.moveTo(x, waveY);
        else dckCtx.lineTo(x, waveY);
    }
    dckCtx.stroke();

    // Energy gauge
    dckCtx.fillStyle = 'rgba(0, 229, 255, 0.2)';
    dckCtx.fillRect(20, h - 35, w - 40, 14);
    const pulseWidth = ((Math.sin(time * 3.0) * 0.5 + 0.5) * (w - 44));
    dckCtx.fillStyle = '#00e5ff';
    dckCtx.fillRect(22, h - 33, pulseWidth, 10);

    // Scanlines
    dckCtx.fillStyle = 'rgba(0, 0, 0, 0.22)';
    for (let y = 0; y < h; y += 4) {
        dckCtx.fillRect(0, y, w, 2);
    }
    if (dckTexture) dckTexture.needsUpdate = true;
}

function updateDatapadCanvas(time) {
    if (!interactiveSceneObjects) return;
    const { padCanvas, padCtx, padTexture } = interactiveSceneObjects;
    if (!padCtx || !padCanvas) return;
    const w = padCanvas.width, h = padCanvas.height;
    padCtx.fillStyle = '#0c1018';
    padCtx.fillRect(0, 0, w, h);

    // Tactical Radar Sweep
    const cx = w * 0.28, cy = h * 0.5, r = 68;
    padCtx.strokeStyle = 'rgba(255, 170, 0, 0.3)';
    padCtx.lineWidth = 1.5;
    padCtx.beginPath();
    padCtx.arc(cx, cy, r, 0, Math.PI * 2);
    padCtx.stroke();
    padCtx.beginPath();
    padCtx.arc(cx, cy, r * 0.6, 0, Math.PI * 2);
    padCtx.stroke();

    const sweepAngle = time * 2.2;
    padCtx.strokeStyle = '#ffa000';
    padCtx.beginPath();
    padCtx.moveTo(cx, cy);
    padCtx.lineTo(cx + Math.cos(sweepAngle) * r, cy + Math.sin(sweepAngle) * r);
    padCtx.stroke();

    // Data text
    padCtx.fillStyle = '#ffaa00';
    padCtx.font = 'bold 15px "SF Mono", monospace';
    padCtx.fillText('HEL-PAD-02 // TACTICAL HUD', w * 0.54, 40);
    padCtx.fillStyle = '#cbd5e1';
    padCtx.font = '11px monospace';
    padCtx.fillText('RECON: SD-04 GHOSTEYE', w * 0.54, 66);
    padCtx.fillText('ALT: 1.42m | YAW: 104°', w * 0.54, 88);
    padCtx.fillText('DOWNLINK: 100% SECURE', w * 0.54, 110);
    padCtx.fillText('SYS: ENCRYPTED // Q-AES', w * 0.54, 132);

    if (padTexture) padTexture.needsUpdate = true;
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
        butterflyGroup,
        butterflyCoreMesh,
        bCoreMat,
        bWingMeshL,
        bWingMeshR,
        bWingMatL,
        bWingMatR,
        bAuraMesh,
        bAuraMat,
        droneGroup,
        droneChassisMesh,
        droneChassisMat,
        droneEdgeMat,
        droneEyeMat,
        droneRing1,
        droneRing2,
        droneRingMat1,
        droneRingMat2,
        droneRotorMeshL,
        droneRotorMeshR,
        droneRotorMat,
        scanConeMesh,
        scanConeMat,
        monocleGroup,
        monocleLensMat,
        monocleRimMat,
        monocleEdgeMat,
        monocleBeamMesh,
        monocleBeamMat,
    } = interactiveSceneObjects;

    const h = currentVrm?.humanoid;
    if (currentVrm?.scene) {
        currentVrm.scene.updateMatrixWorld(true);
    }

    const isPopupCurious = currentPose === 'idle_popup_curious';
    const isOrbCurious = currentPose === 'idle_orb_curious';
    const isScreenCurious = currentPose === 'idle_screen_curious';
    const isWristLook = currentPose === 'idle_waiting_look';
    const isAiriButterfly = currentPose === 'idle_airi_butterfly';
    const isRenDrone = currentPose === 'idle_ren_drone';

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
        const popupCalib = propsCalibration.popup || { x: 0, y: 0, z: 0, scale: 1 };
        if (isPopupCurious && rTipBone) {
            rTipBone.getWorldPosition(_charBoneWorldPos);
            _charPopupTargetPos.set(
                _charBoneWorldPos.x + 0.085 + popupCalib.x,
                emitterY + 0.152 + popupCalib.y,
                _charBoneWorldPos.z + 0.008 + pokeImpact * 0.012 + popupCalib.z
            );
            popupGroup.position.lerp(_charPopupTargetPos, Math.min(1.0, delta * 9.0));
        } else {
            _charPopupTargetPos.set(emitterX - 0.06 + popupCalib.x, emitterY + 0.152 + popupCalib.y, emitterZ + 0.02 + popupCalib.z);
            popupGroup.position.lerp(_charPopupTargetPos, Math.min(1.0, delta * 9.0));
        }

        // Rotate ~180 deg around Y (Math.PI) so the FRONT of the popup faces the MODEL (not the user)
        popupGroup.rotation.set(
            0.03 - pokeImpact * 0.07 + THREE.MathUtils.degToRad(popupCalib.rotX || 0),
            Math.PI - 0.05 + pokeImpact * 0.08 + THREE.MathUtils.degToRad(popupCalib.rotY || 0),
            Math.sin(elapsed * 1.5) * 0.012 + THREE.MathUtils.degToRad(popupCalib.rotZ || 0)
        );
        const targetPopupScale = (isPopupCurious ? 0.94 : 0.60) * popupCalib.scale;
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
        const orbCalib = propsCalibration.orb || { x: 0, y: 0, z: 0, scale: 1, rotX: 0, rotY: 0, rotZ: 0, pathMode: 'recon_orbit', speed: 1 };
        const orbSpeed = (orbCalib.speed || 1.0);
        const orbTime = elapsed * orbSpeed;

        if (isOrbCurious && lHandBone) {
            lHandBone.getWorldPosition(_charBoneWorldPos);
            let orbMotionX = 0;
            let orbMotionZ = 0;
            let orbMotionY = Math.sin(orbTime * 3.0) * 0.012;

            if (orbCalib.pathMode === 'figure8') {
                orbMotionX = Math.sin(orbTime * 1.6) * 0.04;
                orbMotionZ = Math.sin(orbTime * 3.2) * 0.02;
            } else if (orbCalib.pathMode === 'spiral_ascent') {
                orbMotionX = Math.sin(orbTime * 2.0) * 0.035;
                orbMotionZ = Math.cos(orbTime * 2.0) * 0.035;
                orbMotionY = Math.sin(orbTime * 2.5) * 0.025;
            } else if (orbCalib.pathMode === 'recon_orbit') {
                orbMotionX = Math.sin(orbTime * 2.2) * 0.03;
                orbMotionZ = Math.cos(orbTime * 2.2) * 0.03;
            }

            _charOrbTargetPos.set(
                _charBoneWorldPos.x - 0.015 + orbMotionX + orbCalib.x,
                _charBoneWorldPos.y + 0.08 + orbMotionY + orbCalib.y,
                _charBoneWorldPos.z + 0.045 + orbMotionZ + orbCalib.z
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
        orbGroup.rotation.set(
            THREE.MathUtils.degToRad(orbCalib.rotX || 0),
            THREE.MathUtils.degToRad(orbCalib.rotY || 0),
            THREE.MathUtils.degToRad(orbCalib.rotZ || 0)
        );
        const orbScale = (isOrbCurious ? 1.05 + Math.sin(elapsed * 4.0) * 0.05 : 0.5) * (orbCalib.scale || 1.0);
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

    // 5. Update Airi's Unique Companion: 3D Holographic Cyber-Butterfly (AiriCyberButterfly3D)
    // ONLY visible when Airi interacts with it (idle_airi_butterfly) or when Airi is active
    if (isAiriButterfly && rTipBone && butterflyGroup) {
        butterflyGroup.visible = true;
        rTipBone.getWorldPosition(_charBoneWorldPos);

        const bCalib = propsCalibration.butterfly || { x: 0, y: 0, z: 0, scale: 1, pathMode: 'hover_perch', speed: 1 };
        const bSpeed = (bCalib.speed || 1.0);
        const bTime = elapsed * bSpeed;

        // Kinematics based on pathMode
        let hoverX = 0;
        let hoverY = 0.055;
        let hoverZ = 0;

        if (bCalib.pathMode === 'recon_orbit') {
            hoverX = Math.sin(bTime * 2.0) * 0.12;
            hoverZ = Math.cos(bTime * 2.0) * 0.10;
            hoverY = Math.sin(bTime * 3.0) * 0.03 + 0.06;
        } else if (bCalib.pathMode === 'figure8') {
            hoverX = Math.sin(bTime * 1.8) * 0.08;
            hoverZ = Math.sin(bTime * 3.6) * 0.04;
            hoverY = Math.cos(bTime * 2.5) * 0.02 + 0.055;
        } else if (bCalib.pathMode === 'spiral_ascent') {
            hoverX = Math.sin(bTime * 2.4) * 0.07;
            hoverZ = Math.cos(bTime * 2.4) * 0.07;
            hoverY = (Math.sin(bTime * 1.5) * 0.05) + 0.07;
        } else {
            // Default hover_perch
            hoverX = Math.sin(bTime * 2.2) * 0.035;
            hoverY = Math.cos(bTime * 2.8) * 0.025 + 0.055;
            hoverZ = Math.sin(bTime * 1.8) * 0.025;
        }

        butterflyGroup.position.set(
            _charBoneWorldPos.x + hoverX + bCalib.x,
            _charBoneWorldPos.y + hoverY + bCalib.y,
            _charBoneWorldPos.z + hoverZ + bCalib.z
        );
        butterflyGroup.scale.setScalar(bCalib.scale || 1.0);
        butterflyGroup.rotation.set(
            THREE.MathUtils.degToRad(bCalib.rotX || 0),
            THREE.MathUtils.degToRad(bCalib.rotY || 0),
            THREE.MathUtils.degToRad(bCalib.rotZ || 0)
        );

        // Wing flap rotations (left and right wings mirror flap)
        const wingFlap = Math.sin(elapsed * 18.0 * bSpeed); // flutter speed scales
        bWingMeshL.rotation.y = wingFlap * 0.75;
        bWingMeshR.rotation.y = -wingFlap * 0.75;
        bAuraMesh.rotation.z = elapsed * 3.0;

        // Smooth opacity ramp-up
        bCoreMat.opacity = THREE.MathUtils.lerp(bCoreMat.opacity, 0.95, delta * 8.0);
        bWingMatL.opacity = THREE.MathUtils.lerp(bWingMatL.opacity, 0.75, delta * 8.0);
        bWingMatR.opacity = THREE.MathUtils.lerp(bWingMatR.opacity, 0.75, delta * 8.0);
        bAuraMat.opacity = THREE.MathUtils.lerp(bAuraMat.opacity, 0.55 + Math.sin(elapsed * 4.0) * 0.2, delta * 8.0);
    } else if (butterflyGroup) {
        bCoreMat.opacity = THREE.MathUtils.lerp(bCoreMat.opacity, 0.0, delta * 8.0);
        bWingMatL.opacity = THREE.MathUtils.lerp(bWingMatL.opacity, 0.0, delta * 8.0);
        bWingMatR.opacity = THREE.MathUtils.lerp(bWingMatR.opacity, 0.0, delta * 8.0);
        bAuraMat.opacity = THREE.MathUtils.lerp(bAuraMat.opacity, 0.0, delta * 8.0);
        if (bCoreMat.opacity <= 0.01) {
            butterflyGroup.visible = false;
        }
    }

    // 6. Update Ren's Unique Companion: 3D Tactical Recon Scout Drone (RenTacticalDrone3D)
    // and Cyber Tactical Monocle HUD (RenCyberMonocle3D)
    // ONLY visible when Ren interacts with it (idle_ren_drone) or when active with Ren
    const headBone = h?.getNormalizedBoneNode('head');
    const lEyeBone = h?.getNormalizedBoneNode('leftEye') || headBone;
    const lShoulderBone = h?.getNormalizedBoneNode('leftShoulder') || h?.getNormalizedBoneNode('leftUpperArm');

    const isDual = activeModelId === 'dual' && secondaryVrm?.humanoid;
    const renHeadBone = isDual
        ? secondaryVrm.humanoid.getNormalizedBoneNode('head')
        : (isRenActive() ? headBone : headBone);
    const renEyeBone = isDual
        ? (secondaryVrm.humanoid.getNormalizedBoneNode('leftEye') || renHeadBone)
        : (isRenActive() ? lEyeBone : lEyeBone);

    const isDroneActive = isRenDrone || (activeModelId === 'dual' && currentPose === 'twin_synergy_briefing');

    if (isDroneActive && droneGroup) {
        droneGroup.visible = true;

        const droneCalib = propsCalibration.drone || { x: 0, y: 0, z: 0, scale: 1, pathMode: 'recon_orbit', speed: 1 };
        const droneSpeed = (droneCalib.speed || 1.0);
        const orbitAngle = elapsed * 1.6 * droneSpeed;

        // Center orbit around Ren's upper chest / head position
        const centerPos = new THREE.Vector3();
        if (renHeadBone) {
            renHeadBone.getWorldPosition(centerPos);
        } else if (headBone) {
            headBone.getWorldPosition(centerPos);
        } else {
            centerPos.set(0, 1.25, 0);
        }

        const shoulderAnchorY = centerPos.y + 0.16 + Math.sin(elapsed * 2.8 * droneSpeed) * 0.035;
        let droneX = centerPos.x - 0.10;
        let droneY = shoulderAnchorY;
        let droneZ = centerPos.z + 0.05;
        let bankAngle = 0;
        let yawAngle = orbitAngle + Math.PI * 0.5;

        if (droneCalib.pathMode === 'figure8') {
            const f8Angle = elapsed * 1.4 * droneSpeed;
            droneX = centerPos.x + Math.sin(f8Angle) * 0.32;
            droneZ = centerPos.z + Math.sin(2.0 * f8Angle) * 0.18;
            bankAngle = Math.cos(f8Angle) * 0.35;
            yawAngle = Math.atan2(Math.cos(2.0 * f8Angle) * 0.36, Math.cos(f8Angle) * 0.32) + Math.PI * 0.5;
        } else if (droneCalib.pathMode === 'hover_perch') {
            droneX = centerPos.x - 0.22 + Math.sin(elapsed * 1.5 * droneSpeed) * 0.03;
            droneZ = centerPos.z + 0.12 + Math.cos(elapsed * 1.5 * droneSpeed) * 0.03;
            droneY = centerPos.y + 0.18 + Math.sin(elapsed * 2.2 * droneSpeed) * 0.02;
            bankAngle = Math.sin(elapsed * 1.5 * droneSpeed) * 0.08;
            yawAngle = 0.25;
        } else if (droneCalib.pathMode === 'spiral_ascent') {
            const rad = 0.22 + Math.sin(elapsed * 0.9 * droneSpeed) * 0.10;
            droneX = centerPos.x + Math.sin(orbitAngle) * rad - 0.05;
            droneZ = centerPos.z + Math.cos(orbitAngle) * rad + 0.05;
            droneY = shoulderAnchorY + Math.sin(elapsed * 1.2 * droneSpeed) * 0.09;
            bankAngle = Math.cos(orbitAngle) * 0.28;
            yawAngle = orbitAngle + Math.PI * 0.5;
        } else {
            // Default recon_orbit
            const orbitRadiusX = 0.32;
            const orbitRadiusZ = 0.28;
            droneX = centerPos.x + Math.sin(orbitAngle) * orbitRadiusX - 0.10;
            droneZ = centerPos.z + Math.cos(orbitAngle) * orbitRadiusZ + 0.05;
            bankAngle = Math.cos(orbitAngle) * 0.28;
        }

        droneGroup.position.set(
            droneX + droneCalib.x,
            droneY + droneCalib.y,
            droneZ + droneCalib.z
        );
        droneGroup.scale.setScalar(droneCalib.scale || 1.0);

        // Drone banks into its flight path tangentially + slight forward tilt + user calibrated rotation
        const pitchAngle = -0.12 + Math.sin(elapsed * 2.5) * 0.06;
        droneGroup.rotation.set(
            pitchAngle + THREE.MathUtils.degToRad(droneCalib.rotX || 0),
            yawAngle + THREE.MathUtils.degToRad(droneCalib.rotY || 0),
            bankAngle + THREE.MathUtils.degToRad(droneCalib.rotZ || 0)
        );

        // Enclosed counter-rotating ducted fan rotors
        if (droneRotorMeshL) droneRotorMeshL.rotation.y = elapsed * 24.0 * droneSpeed;
        if (droneRotorMeshR) droneRotorMeshR.rotation.y = -elapsed * 24.0 * droneSpeed;

        // Counter-rotating telemetry lidar rings
        droneRing1.rotation.z = elapsed * 4.2;
        droneRing2.rotation.z = -elapsed * 3.5;

        // Smooth opacity ramp-up
        droneChassisMat.opacity = THREE.MathUtils.lerp(droneChassisMat.opacity, 0.95, delta * 8.0);
        droneEdgeMat.opacity = THREE.MathUtils.lerp(droneEdgeMat.opacity, 0.92, delta * 8.0);
        droneEyeMat.opacity = THREE.MathUtils.lerp(droneEyeMat.opacity, 0.98, delta * 8.0);
        if (droneRotorMat) droneRotorMat.opacity = THREE.MathUtils.lerp(droneRotorMat.opacity, 0.85, delta * 8.0);
        droneRingMat1.opacity = THREE.MathUtils.lerp(droneRingMat1.opacity, 0.85, delta * 8.0);
        droneRingMat2.opacity = THREE.MathUtils.lerp(droneRingMat2.opacity, 0.85, delta * 8.0);

        // Update Ren's Cyber Tactical Monocle HUD (mounted directly over left eye)
        if (monocleGroup && (renHeadBone || renEyeBone)) {
            monocleGroup.visible = true;
            const mCalib = propsCalibration.monocle || { x: 0.0336, y: 0.0575, z: 0.0760, scale: 1.0, rotX: 0, rotY: 0, rotZ: 0 };

            if (renHeadBone) {
                const headPos = new THREE.Vector3();
                const headRotQ = new THREE.Quaternion();
                renHeadBone.getWorldPosition(headPos);
                renHeadBone.getWorldQuaternion(headRotQ);
                monocleGroup.quaternion.copy(headRotQ);

                if (mCalib.rotX || mCalib.rotY || mCalib.rotZ) {
                    const rotEuler = new THREE.Euler(
                        THREE.MathUtils.degToRad(mCalib.rotX || 0),
                        THREE.MathUtils.degToRad(mCalib.rotY || 0),
                        THREE.MathUtils.degToRad(mCalib.rotZ || 0),
                        'YXZ'
                    );
                    const rotQ = new THREE.Quaternion().setFromEuler(rotEuler);
                    monocleGroup.quaternion.multiply(rotQ);
                }

                // Calibrated anatomical offset in Ren's head local coordinates:
                const localOffset = new THREE.Vector3(
                    mCalib.x,
                    mCalib.y,
                    mCalib.z
                );
                localOffset.applyQuaternion(headRotQ);
                monocleGroup.position.copy(headPos).add(localOffset);
                monocleGroup.scale.setScalar(mCalib.scale);
            } else if (renEyeBone) {
                const eyePos = new THREE.Vector3();
                renEyeBone.getWorldPosition(eyePos);
                monocleGroup.position.set(
                    eyePos.x + mCalib.x,
                    eyePos.y + mCalib.y,
                    eyePos.z + mCalib.z
                );
                monocleGroup.rotation.set(
                    THREE.MathUtils.degToRad(mCalib.rotX || 0),
                    THREE.MathUtils.degToRad(mCalib.rotY || 0),
                    THREE.MathUtils.degToRad(mCalib.rotZ || 0)
                );
            }

            // Aim telemetry tracking beam from monocle towards orbiting drone
            if (monocleBeamMesh) {
                const toDrone = new THREE.Vector3().subVectors(droneGroup.position, monocleGroup.position).normalize();
                monocleBeamMesh.lookAt(droneGroup.position);
            }

            const hudPulse = 0.80 + 0.18 * Math.sin(elapsed * 7.0);
            monocleLensMat.opacity = THREE.MathUtils.lerp(monocleLensMat.opacity, hudPulse, delta * 8.0);
            monocleRimMat.opacity = THREE.MathUtils.lerp(monocleRimMat.opacity, 0.95, delta * 8.0);
            if (interactiveSceneObjects.monocleAccentMat) {
                interactiveSceneObjects.monocleAccentMat.opacity = THREE.MathUtils.lerp(interactiveSceneObjects.monocleAccentMat.opacity, 0.95, delta * 8.0);
            }
            if (interactiveSceneObjects.monocleLedMat) {
                const ledFlicker = 0.85 + 0.15 * Math.sin(elapsed * 12.0);
                interactiveSceneObjects.monocleLedMat.opacity = THREE.MathUtils.lerp(interactiveSceneObjects.monocleLedMat.opacity, ledFlicker, delta * 8.0);
            }
            monocleEdgeMat.opacity = THREE.MathUtils.lerp(monocleEdgeMat.opacity, 0.92, delta * 8.0);
        }
    } else {
        if (droneGroup) {
            droneChassisMat.opacity = THREE.MathUtils.lerp(droneChassisMat.opacity, 0.0, delta * 8.0);
            droneEdgeMat.opacity = THREE.MathUtils.lerp(droneEdgeMat.opacity, 0.0, delta * 8.0);
            droneEyeMat.opacity = THREE.MathUtils.lerp(droneEyeMat.opacity, 0.0, delta * 8.0);
            if (droneRotorMat) droneRotorMat.opacity = THREE.MathUtils.lerp(droneRotorMat.opacity, 0.0, delta * 8.0);
            droneRingMat1.opacity = THREE.MathUtils.lerp(droneRingMat1.opacity, 0.0, delta * 8.0);
            droneRingMat2.opacity = THREE.MathUtils.lerp(droneRingMat2.opacity, 0.0, delta * 8.0);
            if (droneChassisMat.opacity <= 0.01) {
                droneGroup.visible = false;
            }
        }
        if (monocleGroup) {
            monocleLensMat.opacity = THREE.MathUtils.lerp(monocleLensMat.opacity, 0.0, delta * 8.0);
            monocleRimMat.opacity = THREE.MathUtils.lerp(monocleRimMat.opacity, 0.0, delta * 8.0);
            if (interactiveSceneObjects.monocleAccentMat) {
                interactiveSceneObjects.monocleAccentMat.opacity = THREE.MathUtils.lerp(interactiveSceneObjects.monocleAccentMat.opacity, 0.0, delta * 8.0);
            }
            if (interactiveSceneObjects.monocleLedMat) {
                interactiveSceneObjects.monocleLedMat.opacity = THREE.MathUtils.lerp(interactiveSceneObjects.monocleLedMat.opacity, 0.0, delta * 8.0);
            }
            monocleEdgeMat.opacity = THREE.MathUtils.lerp(monocleEdgeMat.opacity, 0.0, delta * 8.0);
            if (monocleLensMat.opacity <= 0.01) {
                monocleGroup.visible = false;
            }
        }
    }

    // 7. Update Cyber Handheld Console (CyberHandheldConsole3D)
    // ONLY visible during idle_gaming_console
    const isGamingConsole = currentPose === 'idle_gaming_console';
    if (isGamingConsole && rHandBone && lHandBone && interactiveSceneObjects.consoleGroup) {
        const {
            consoleGroup,
            consoleBodyMat,
            consoleEdgeMat,
            consoleScreenMat,
            stickMat,
        } = interactiveSceneObjects;
        consoleGroup.visible = true;
        updateCyberDeckCanvas(elapsed);

        const cCalib = propsCalibration.console || { x: 0, y: 0, z: 0, scale: 1 };
        const rPos = new THREE.Vector3();
        const lPos = new THREE.Vector3();
        rHandBone.getWorldPosition(rPos);
        lHandBone.getWorldPosition(lPos);

        const mid = rPos.clone().add(lPos).multiplyScalar(0.5);
        consoleGroup.position.set(mid.x + cCalib.x, mid.y + 0.015 + cCalib.y, mid.z + 0.015 + cCalib.z);
        consoleGroup.scale.setScalar(cCalib.scale || 1.0);

        // Screen glows with subtle pulse while playing; bottom edge turns inward toward the body, screen tilted upward facing the avatar + user calibrated rotation
        const screenPulse = 0.85 + Math.sin(elapsed * 6.0) * 0.15;
        consoleGroup.rotation.set(
            0.68 + THREE.MathUtils.degToRad(cCalib.rotX || 0),
            Math.sin(elapsed * 2.0) * 0.04 + THREE.MathUtils.degToRad(cCalib.rotY || 0),
            THREE.MathUtils.degToRad(cCalib.rotZ || 0)
        );

        consoleBodyMat.opacity = THREE.MathUtils.lerp(consoleBodyMat.opacity, 0.95, delta * 8.0);
        consoleEdgeMat.opacity = THREE.MathUtils.lerp(consoleEdgeMat.opacity, 0.92, delta * 8.0);
        consoleScreenMat.opacity = THREE.MathUtils.lerp(consoleScreenMat.opacity, screenPulse, delta * 8.0);
        stickMat.opacity = THREE.MathUtils.lerp(stickMat.opacity, 0.95, delta * 8.0);
    } else if (interactiveSceneObjects.consoleGroup) {
        const {
            consoleGroup,
            consoleBodyMat,
            consoleEdgeMat,
            consoleScreenMat,
            stickMat,
        } = interactiveSceneObjects;
        consoleBodyMat.opacity = THREE.MathUtils.lerp(consoleBodyMat.opacity, 0.0, delta * 8.0);
        consoleEdgeMat.opacity = THREE.MathUtils.lerp(consoleEdgeMat.opacity, 0.0, delta * 8.0);
        consoleScreenMat.opacity = THREE.MathUtils.lerp(consoleScreenMat.opacity, 0.0, delta * 8.0);
        stickMat.opacity = THREE.MathUtils.lerp(stickMat.opacity, 0.0, delta * 8.0);
        if (consoleBodyMat.opacity <= 0.01) {
            consoleGroup.visible = false;
        }
    }

    // 8. Update Cyber Tactical Plasma Blade (CyberTacticalBlade3D)
    // ONLY visible during sword_guard_ready, sword_sheathe_flourish, or twin_synergy_combat
    const isSwordActive = currentPose === 'sword_guard_ready' ||
                          currentPose === 'sword_sheathe_flourish' ||
                          (activeModelId === 'dual' && currentPose === 'twin_synergy_combat');
    if (isSwordActive && rHandBone && interactiveSceneObjects.bladeGroup) {
        const {
            bladeGroup,
            hiltMat,
            guardMat,
            bladeMat,
            bladeEdgeMat,
        } = interactiveSceneObjects;
        bladeGroup.visible = true;

        const kCalib = propsCalibration.katana || { x: 0, y: 0, z: 0, scale: 1, rotX: 0, rotY: 0, rotZ: 0 };
        rHandBone.getWorldPosition(_charBoneWorldPos);
        const rHandRotQ = new THREE.Quaternion();
        rHandBone.getWorldQuaternion(rHandRotQ);

        const isGuard = currentPose === 'sword_guard_ready' || (activeModelId === 'dual' && currentPose === 'twin_synergy_combat');

        if (isGuard) {
            // Guard: Two-handed combat stance.
            // Sword blade points along the forearm/fist direction (+X world ≈ upright/slightly forward).
            // Blade local +Y (blade axis) aligns with hand +X direction (fingerDir vector).
            // Blade local +Z (flat of blade) aligns with hand palm normal.
            const hiltOffset = new THREE.Vector3(
                0.035 + kCalib.x,   // offset along hand +X (into the fist grip)
                -0.015 + kCalib.y,  // lateral palm offset
                0.010 + kCalib.z    // depth offset
            );
            hiltOffset.applyQuaternion(rHandRotQ);
            bladeGroup.position.copy(_charBoneWorldPos).add(hiltOffset);

            // Rotate so blade axis (+Y) aligns with hand +X and flat aligns with knuckles
            const qGrip = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0, -Math.PI * 0.5));
            bladeGroup.quaternion.copy(rHandRotQ).multiply(qGrip);
        } else {
            // Flourish: One-handed drawn sword stance pointing blade downwards-right.
            // Blade extends out from knuckles/thumb along +X direction, pointed down and away from body.
            const hiltOffset = new THREE.Vector3(
                -0.035 + kCalib.x,
                0.015 + kCalib.y,
                -0.012 + kCalib.z
            );
            hiltOffset.applyQuaternion(rHandRotQ);
            bladeGroup.position.copy(_charBoneWorldPos).add(hiltOffset);

            const qGrip = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0, Math.PI * 0.5));
            bladeGroup.quaternion.copy(rHandRotQ).multiply(qGrip);
        }
        if (kCalib.rotX || kCalib.rotY || kCalib.rotZ) {
            const kRotQ = new THREE.Quaternion().setFromEuler(new THREE.Euler(
                THREE.MathUtils.degToRad(kCalib.rotX || 0),
                THREE.MathUtils.degToRad(kCalib.rotY || 0),
                THREE.MathUtils.degToRad(kCalib.rotZ || 0),
                'YXZ'
            ));
            bladeGroup.quaternion.multiply(kRotQ);
        }
        bladeGroup.scale.setScalar(kCalib.scale || 1.0);

        // Color blade edge: Airi Cyan (#00e5ff) vs Ren Amber/Orange (#ff9900)
        const bladeColorHex = isRenActive() ? 0xff9900 : 0x00e5ff;
        guardMat.color.setHex(bladeColorHex);
        bladeMat.color.setHex(bladeColorHex);

        const plasmaPulse = 0.88 + Math.sin(elapsed * 12.0) * 0.12;
        hiltMat.opacity = THREE.MathUtils.lerp(hiltMat.opacity, 0.95, delta * 8.0);
        guardMat.opacity = THREE.MathUtils.lerp(guardMat.opacity, 0.95, delta * 8.0);
        bladeMat.opacity = THREE.MathUtils.lerp(bladeMat.opacity, plasmaPulse, delta * 8.0);
        bladeEdgeMat.opacity = THREE.MathUtils.lerp(bladeEdgeMat.opacity, 0.95, delta * 8.0);
    } else if (interactiveSceneObjects.bladeGroup) {
        const {
            bladeGroup,
            hiltMat,
            guardMat,
            bladeMat,
            bladeEdgeMat,
        } = interactiveSceneObjects;
        hiltMat.opacity = THREE.MathUtils.lerp(hiltMat.opacity, 0.0, delta * 8.0);
        guardMat.opacity = THREE.MathUtils.lerp(guardMat.opacity, 0.0, delta * 8.0);
        bladeMat.opacity = THREE.MathUtils.lerp(bladeMat.opacity, 0.0, delta * 8.0);
        bladeEdgeMat.opacity = THREE.MathUtils.lerp(bladeEdgeMat.opacity, 0.0, delta * 8.0);
        if (bladeMat.opacity <= 0.01) {
            bladeGroup.visible = false;
        }
    }

    // 8b. Update Ren's Amber Cyber Tactical Plasma Blade in Dual Synergy Combat
    const renRHandBone = (activeModelId === 'dual' && secondaryVrm?.humanoid)
        ? secondaryVrm.humanoid.getNormalizedBoneNode('rightHand')
        : null;

    if (activeModelId === 'dual' && currentPose === 'twin_synergy_combat' && renRHandBone && interactiveSceneObjects.bladeGroupRen) {
        const {
            bladeGroupRen,
            hiltMatRen,
            guardMatRen,
            bladeMatRen,
            bladeEdgeMatRen,
        } = interactiveSceneObjects;
        bladeGroupRen.visible = true;

        const kCalib = propsCalibration.katana || { x: 0, y: 0, z: 0, scale: 1, rotX: 0, rotY: 0, rotZ: 0 };
        const renPos = new THREE.Vector3();
        const renRotQ = new THREE.Quaternion();
        renRHandBone.getWorldPosition(renPos);
        renRHandBone.getWorldQuaternion(renRotQ);

        const hiltOffset = new THREE.Vector3(
            0.035 + kCalib.x,
            -0.015 + kCalib.y,
            0.010 + kCalib.z
        );
        hiltOffset.applyQuaternion(renRotQ);
        bladeGroupRen.position.copy(renPos).add(hiltOffset);

        const qGrip = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0, -Math.PI * 0.5));
        bladeGroupRen.quaternion.copy(renRotQ).multiply(qGrip);
        if (kCalib.rotX || kCalib.rotY || kCalib.rotZ) {
            const kRotQ = new THREE.Quaternion().setFromEuler(new THREE.Euler(
                THREE.MathUtils.degToRad(kCalib.rotX || 0),
                THREE.MathUtils.degToRad(kCalib.rotY || 0),
                THREE.MathUtils.degToRad(kCalib.rotZ || 0),
                'YXZ'
            ));
            bladeGroupRen.quaternion.multiply(kRotQ);
        }
        bladeGroupRen.scale.setScalar(kCalib.scale || 1.0);

        const plasmaPulseRen = 0.88 + Math.sin((elapsed + 0.5) * 12.0) * 0.12;
        hiltMatRen.opacity = THREE.MathUtils.lerp(hiltMatRen.opacity, 0.95, delta * 8.0);
        guardMatRen.opacity = THREE.MathUtils.lerp(guardMatRen.opacity, 0.95, delta * 8.0);
        bladeMatRen.opacity = THREE.MathUtils.lerp(bladeMatRen.opacity, plasmaPulseRen, delta * 8.0);
        bladeEdgeMatRen.opacity = THREE.MathUtils.lerp(bladeEdgeMatRen.opacity, 0.95, delta * 8.0);
    } else if (interactiveSceneObjects.bladeGroupRen) {
        const {
            bladeGroupRen,
            hiltMatRen,
            guardMatRen,
            bladeMatRen,
            bladeEdgeMatRen,
        } = interactiveSceneObjects;
        hiltMatRen.opacity = THREE.MathUtils.lerp(hiltMatRen.opacity, 0.0, delta * 8.0);
        guardMatRen.opacity = THREE.MathUtils.lerp(guardMatRen.opacity, 0.0, delta * 8.0);
        bladeMatRen.opacity = THREE.MathUtils.lerp(bladeMatRen.opacity, 0.0, delta * 8.0);
        bladeEdgeMatRen.opacity = THREE.MathUtils.lerp(bladeEdgeMatRen.opacity, 0.0, delta * 8.0);
        if (bladeMatRen.opacity <= 0.01) {
            bladeGroupRen.visible = false;
        }
    }

    // 9. Update Airi's Quantum Holo-Dice (HEL-RNG-01)
    const isHoloDice = currentPose === 'idle_airi_holodice' || (activeModelId === 'dual' && currentPose === 'twin_synergy_briefing');
    if (interactiveSceneObjects.holoDiceGroup) {
        const { holoDiceGroup, diceMat, diceCoreMat } = interactiveSceneObjects;
        if (isHoloDice && rHandBone) {
            holoDiceGroup.visible = true;
            const diceCalib = propsCalibration.holodice || { x: 0, y: 0, z: 0, scale: 1, rotX: 0, rotY: 0, rotZ: 0 };
            rHandBone.getWorldPosition(_charBoneWorldPos);

            const hoverY = 0.075 + Math.sin(elapsed * 3.2) * 0.015;
            holoDiceGroup.position.set(
                _charBoneWorldPos.x + diceCalib.x,
                _charBoneWorldPos.y + hoverY + diceCalib.y,
                _charBoneWorldPos.z + 0.05 + diceCalib.z
            );
            holoDiceGroup.scale.setScalar((diceCalib.scale || 1.0) * (0.92 + 0.08 * Math.sin(elapsed * 2.5)));
            holoDiceGroup.rotation.set(
                elapsed * 1.6 + THREE.MathUtils.degToRad(diceCalib.rotX || 0),
                elapsed * 2.2 + THREE.MathUtils.degToRad(diceCalib.rotY || 0),
                THREE.MathUtils.degToRad(diceCalib.rotZ || 0)
            );

            diceMat.opacity = THREE.MathUtils.lerp(diceMat.opacity, 0.92, delta * 8.0);
            diceCoreMat.opacity = THREE.MathUtils.lerp(diceCoreMat.opacity, 0.95, delta * 8.0);
        } else {
            diceMat.opacity = THREE.MathUtils.lerp(diceMat.opacity, 0.0, delta * 8.0);
            diceCoreMat.opacity = THREE.MathUtils.lerp(diceCoreMat.opacity, 0.0, delta * 8.0);
            if (diceMat.opacity <= 0.01) {
                holoDiceGroup.visible = false;
            }
        }
    }

    // 10. Update Ren's Tactical Datapad (HEL-PAD-02)
    const isDatapad = currentPose === 'idle_ren_datapad' || (activeModelId === 'dual' && currentPose === 'twin_synergy_briefing');
    if (interactiveSceneObjects.datapadGroup) {
        const { datapadGroup, padChassisMat, padScreenMat } = interactiveSceneObjects;
        if (isDatapad && (lHandBone || (secondaryVrm && secondaryVrm.humanoid))) {
            datapadGroup.visible = true;
            updateDatapadCanvas(elapsed);
            const padCalib = propsCalibration.datapad || { x: 0, y: 0, z: 0, scale: 1, rotX: 0, rotY: 0, rotZ: 0 };

            const anchorBone = (activeModelId === 'dual' && secondaryVrm?.humanoid)
                ? (secondaryVrm.humanoid.getNormalizedBoneNode('leftHand') || secondaryVrm.humanoid.getNormalizedBoneNode('chest'))
                : (lHandBone || rHandBone);

            if (anchorBone) {
                anchorBone.getWorldPosition(_charBoneWorldPos);
                datapadGroup.position.set(
                    _charBoneWorldPos.x + 0.04 + padCalib.x,
                    _charBoneWorldPos.y + 0.06 + padCalib.y,
                    _charBoneWorldPos.z + 0.08 + padCalib.z
                );
                datapadGroup.rotation.set(
                    0.65 + THREE.MathUtils.degToRad(padCalib.rotX || 0),
                    Math.sin(elapsed * 1.5) * 0.03 + THREE.MathUtils.degToRad(padCalib.rotY || 0),
                    THREE.MathUtils.degToRad(padCalib.rotZ || 0)
                );
                datapadGroup.scale.setScalar(padCalib.scale || 1.0);
            }

            padChassisMat.opacity = THREE.MathUtils.lerp(padChassisMat.opacity, 0.95, delta * 8.0);
            padScreenMat.opacity = THREE.MathUtils.lerp(padScreenMat.opacity, 0.92, delta * 8.0);
        } else {
            padChassisMat.opacity = THREE.MathUtils.lerp(padChassisMat.opacity, 0.0, delta * 8.0);
            padScreenMat.opacity = THREE.MathUtils.lerp(padScreenMat.opacity, 0.0, delta * 8.0);
            if (padChassisMat.opacity <= 0.01) {
                datapadGroup.visible = false;
            }
        }
    }
}

function updateAutonomousIdleDirector(delta) {
    const isAdjustTabOpen = document.getElementById('tab-adjust')?.classList.contains('active');
    if (
        isAdjustTabOpen ||
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
        // Tailor idle pool to active character: Airi gets butterfly, Ren gets tactical drone
        const isRen = isRenActive();
        const candidatePool = IDLE_OBJECT_AND_WAITING_POSES.filter((p) => {
            if (isRen && p === 'idle_airi_butterfly') return false;
            if (!isRen && p === 'idle_ren_drone') return false;
            return true;
        });
        const nextIdlePose = candidatePool[autoIdlePoseIndex % candidatePool.length];
        autoIdlePoseIndex = (autoIdlePoseIndex + 1) % candidatePool.length;
        triggerIdleObjectOrWaitingAnimation(nextIdlePose, false);
    }
}

function applySecondaryTwinPose(vrm, time, speed, delta) {
    if (!vrm || !vrm.humanoid) return;
    const h = vrm.humanoid;
    const isCombat = currentPose === 'twin_synergy_combat';
    const isBriefing = currentPose === 'twin_synergy_briefing';

    const hips = h.getNormalizedBoneNode('hips');
    const spine = h.getNormalizedBoneNode('spine');
    const chest = h.getNormalizedBoneNode('chest');
    const neck = h.getNormalizedBoneNode('neck');
    const head = h.getNormalizedBoneNode('head');
    const rShoulder = h.getNormalizedBoneNode('rightShoulder');
    const lShoulder = h.getNormalizedBoneNode('leftShoulder');
    const rUpper = h.getNormalizedBoneNode('rightUpperArm');
    const rLower = h.getNormalizedBoneNode('rightLowerArm');
    const rHand = h.getNormalizedBoneNode('rightHand');
    const lUpper = h.getNormalizedBoneNode('leftUpperArm');
    const lLower = h.getNormalizedBoneNode('leftLowerArm');
    const lHand = h.getNormalizedBoneNode('leftHand');
    const lUpperLeg = h.getNormalizedBoneNode('leftUpperLeg');
    const rUpperLeg = h.getNormalizedBoneNode('rightUpperLeg');
    const lLowerLeg = h.getNormalizedBoneNode('leftLowerLeg');
    const rLowerLeg = h.getNormalizedBoneNode('rightLowerLeg');
    const lFoot = h.getNormalizedBoneNode('leftFoot');
    const rFoot = h.getNormalizedBoneNode('rightFoot');

    const breath = Math.sin(time * 2.2) * 0.02;

    // Smoothly maintain Ren's world anchor position alongside Airi
    const targetRenY = (currentVrm?.scene ? currentVrm.scene.position.y : 0);
    vrm.scene.position.x = THREE.MathUtils.lerp(vrm.scene.position.x, 0.42, speed);
    vrm.scene.position.y = THREE.MathUtils.lerp(vrm.scene.position.y, targetRenY, speed);
    vrm.scene.position.z = THREE.MathUtils.lerp(vrm.scene.position.z, 0, speed);
    vrm.scene.rotation.y = THREE.MathUtils.lerp(vrm.scene.rotation.y, baseFacingYaw - 0.12, speed);

    let hipsRot = [0, 0, 0];
    let spineRot = [-0.02, 0, 0];
    let chestRot = [-0.02 + breath, 0, 0];
    let neckRot = [0, 0, 0];
    let headRot = [-0.015, Math.sin(time * 0.8) * 0.04, 0];
    let rShoulderRot = [0, 0, 0];
    let lShoulderRot = [0, 0, 0];
    let rUpperArmRot = [0, 0, 0.12];
    let rLowerArmRot = [0, 0.35, 0];
    let rHandRot = [0, 0, 0];
    let lUpperArmRot = [0, 0, -0.12];
    let lLowerArmRot = [0, -0.35, 0];
    let lHandRot = [0, 0, 0];

    // Solid grounded leg kinematics with natural posture
    let lUpperLegRot = [0.02, 0.02, -0.07];
    let rUpperLegRot = [0.02, -0.02, 0.07];
    let lLowerLegRot = [0.06, 0, 0];
    let rLowerLegRot = [0.06, 0, 0];
    let lFootRot = [-0.05, 0, 0.02];
    let rFootRot = [-0.05, 0, -0.02];

    let rHandShape = 'relaxed';
    let lHandShape = 'relaxed';

    if (isCombat) {
        // High-readiness tactical combat guard
        hipsRot = [0.02, -0.15, 0.02];
        spineRot = [-0.04, -0.08, 0];
        chestRot = [0.04 + breath, -0.02, 0];
        headRot = [-0.02, 0.12, -0.03];
        rShoulderRot = [0.08, 0, 0.06];
        lShoulderRot = [0.06, 0, -0.05];
        rUpperArmRot = [0.35, -0.15, 0.45];
        rLowerArmRot = [0.15, 0.85, 0];
        rHandRot = [0, 0.10, 0];
        lUpperArmRot = [-0.25, 0.20, -0.35];
        lLowerArmRot = [0.10, -0.45, 0];
        lHandRot = [0, -0.10, 0];
        rHandShape = 'fist';
        lHandShape = 'fist';

        // Braced, grounded combat stance
        lUpperLegRot = [-0.12, 0.05, -0.10];
        lLowerLegRot = [0.22, 0, 0];
        lFootRot = [-0.10, 0, 0.03];
        rUpperLegRot = [0.10, -0.05, 0.12];
        rLowerLegRot = [0.18, 0, 0];
        rFootRot = [-0.08, 0, -0.03];
    } else if (isBriefing) {
        // Tactical briefing posture: holding datapad in left hand, pointing with right
        hipsRot = [0, -0.06, 0];
        spineRot = [0.02, -0.04, 0];
        chestRot = [0.02 + breath, 0, 0];
        headRot = [0.10, -0.10, 0.02];
        lShoulderRot = [0.05, 0, -0.04];
        rShoulderRot = [0.04, 0, 0.03];
        lUpperArmRot = [0.45, 0.15, -0.25];
        lLowerArmRot = [0, -0.95, 0];
        lHandRot = [-0.12, 0.18, 0];
        rUpperArmRot = [0.35, -0.10, 0.20];
        rLowerArmRot = [0, 0.70, 0];
        rHandRot = [0.08, -0.08, 0];
        lHandShape = 'cupped';
        rHandShape = 'point';

        lUpperLegRot = [0.02, 0.02, -0.08];
        lLowerLegRot = [0.08, 0, 0];
        lFootRot = [-0.06, 0, 0.02];
        rUpperLegRot = [0.02, -0.02, 0.08];
        rLowerLegRot = [0.08, 0, 0];
        rFootRot = [-0.06, 0, -0.02];
    } else if (currentPose === 'idle_ren_drone') {
        headRot = [-0.08, 0.06, 0];
        lUpperArmRot = [0.55, 0.22, -0.20];
        lLowerArmRot = [0, -1.20, 0];
        lHandRot = [0.10, 0.15, 0];
        lHandShape = 'relaxed';
        rUpperArmRot = [0.06, 0, 0.12];
        rLowerArmRot = [0, 0.30, 0];
        rHandShape = 'relaxed';
    } else if (currentPose === 'idle_ren_datapad') {
        headRot = [0.14, -0.04, 0];
        lUpperArmRot = [0.45, 0.15, -0.22];
        lLowerArmRot = [0, -0.92, 0];
        lHandRot = [-0.12, 0.18, 0];
        lHandShape = 'cupped';
        rUpperArmRot = [0.32, -0.10, 0.18];
        rLowerArmRot = [0, 0.68, 0];
        rHandShape = 'point';
    }

    // Parametric Biomechanical Body Pose Tuner live overrides
    if (typeof activeBodyPoseAdjustments !== 'undefined' && activeBodyPoseAdjustments.enabled) {
        const appliesToRen = activeBodyPoseAdjustments.target === 'both' ||
                             activeBodyPoseAdjustments.target === 'ren' ||
                             activeBodyPoseAdjustments.target === 'active';

        if (appliesToRen) {
            headRot[0] += activeBodyPoseAdjustments.headPitch * Math.PI / 180;
            headRot[1] += activeBodyPoseAdjustments.headYaw * Math.PI / 180;
            headRot[2] += activeBodyPoseAdjustments.headRoll * Math.PI / 180;
            neckRot[0] += activeBodyPoseAdjustments.neckPitch * Math.PI / 180;

            spineRot[0] += activeBodyPoseAdjustments.spineLean * Math.PI / 180;
            spineRot[1] += activeBodyPoseAdjustments.spineTwist * Math.PI / 180;
            spineRot[2] += activeBodyPoseAdjustments.spineRoll * Math.PI / 180;
            chestRot[0] += activeBodyPoseAdjustments.chestBreath;

            hipsRot[1] += activeBodyPoseAdjustments.pelvisSway * Math.PI / 180;
            hipsRot[2] += activeBodyPoseAdjustments.pelvisTilt * Math.PI / 180;

            const sWidthRad = (activeBodyPoseAdjustments.stanceWidth * Math.PI / 180);
            lUpperLegRot[2] -= sWidthRad;
            rUpperLegRot[2] += sWidthRad;
            const kneeRad = (activeBodyPoseAdjustments.kneeBend * Math.PI / 180);
            lLowerLegRot[0] += kneeRad;
            rLowerLegRot[0] += kneeRad;

            rUpperArmRot[0] += activeBodyPoseAdjustments.rArmLift * 0.8;
            rUpperArmRot[1] += activeBodyPoseAdjustments.rArmReach * 0.6;
            rUpperArmRot[2] += activeBodyPoseAdjustments.rArmSide * 0.8;
            rLowerArmRot[1] += activeBodyPoseAdjustments.rElbow * 0.8;

            lUpperArmRot[0] += activeBodyPoseAdjustments.lArmLift * 0.8;
            lUpperArmRot[1] -= activeBodyPoseAdjustments.lArmReach * 0.6;
            lUpperArmRot[2] -= activeBodyPoseAdjustments.lArmSide * 0.8;
            lLowerArmRot[1] -= activeBodyPoseAdjustments.lElbow * 0.8;

            if (activeBodyPoseAdjustments.rHandShape && activeBodyPoseAdjustments.rHandShape !== 'auto') {
                rHandShape = activeBodyPoseAdjustments.rHandShape;
            }
            if (activeBodyPoseAdjustments.lHandShape && activeBodyPoseAdjustments.lHandShape !== 'auto') {
                lHandShape = activeBodyPoseAdjustments.lHandShape;
            }
        }
    }

    // Lerp all joints smoothly
    lerpBoneEuler(hips, ...hipsRot, speed);
    lerpBoneEuler(spine, ...spineRot, speed);
    lerpBoneEuler(chest, ...chestRot, speed);
    lerpBoneEuler(neck, ...neckRot, speed);
    lerpBoneEuler(head, ...headRot, speed);
    lerpBoneEuler(rShoulder, ...rShoulderRot, speed);
    lerpBoneEuler(lShoulder, ...lShoulderRot, speed);
    lerpBoneEuler(rUpper, ...rUpperArmRot, speed);
    lerpBoneEuler(rLower, ...rLowerArmRot, speed);
    lerpBoneEuler(rHand, ...rHandRot, speed);
    lerpBoneEuler(lUpper, ...lUpperArmRot, speed);
    lerpBoneEuler(lLower, ...lLowerArmRot, speed);
    lerpBoneEuler(lHand, ...lHandRot, speed);

    lerpBoneEuler(lUpperLeg, ...lUpperLegRot, speed);
    lerpBoneEuler(rUpperLeg, ...rUpperLegRot, speed);
    lerpBoneEuler(lLowerLeg, ...lLowerLegRot, speed);
    lerpBoneEuler(rLowerLeg, ...rLowerLegRot, speed);
    lerpBoneEuler(lFoot, ...lFootRot, speed);
    lerpBoneEuler(rFoot, ...rFootRot, speed);

    applyHandShape(h, 'right', rHandShape, speed, time);
    applyHandShape(h, 'left', lHandShape, speed, time);

    if (vrm.expressionManager) {
        const blinkVal = Math.sin(time * 0.7) > 0.96 ? 1.0 : 0.0;
        vrm.expressionManager.setValue('blink', blinkVal);
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

        // Update secondary twin avatar when dual twin synergy mode is active
        if (dualTwinModeActive && secondaryVrm && secondaryVrm.humanoid) {
            applySecondaryTwinPose(secondaryVrm, elapsed, speed, delta);
            secondaryVrm.update(delta);
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
    activeModelId = 'twin';
    if (btnModelTwin) btnModelTwin.classList.add('active');
    updatePoseButtonsForActiveModel();
    loadVRM(TWIN_VRM_URL);
} else {
    clearModelActiveStates();
    activeModelId = 'airi';
    if (btnModelHelios) btnModelHelios.classList.add('active');
    updatePoseButtonsForActiveModel();
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

// ----------------------------------------------------
// UNIVERSAL 3D PROPS & GADGETS CALIBRATION SUITE UI
// ----------------------------------------------------
const selectActiveProp = document.getElementById('select-active-prop');
const labelSlider1 = document.getElementById('label-slider-1');
const valSlider1 = document.getElementById('val-slider-1');
const sliderProp1 = document.getElementById('slider-prop-1');

const labelSlider2 = document.getElementById('label-slider-2');
const valSlider2 = document.getElementById('val-slider-2');
const sliderProp2 = document.getElementById('slider-prop-2');

const labelSlider3 = document.getElementById('label-slider-3');
const valSlider3 = document.getElementById('val-slider-3');
const sliderProp3 = document.getElementById('slider-prop-3');

const labelSlider4 = document.getElementById('label-slider-4');
const valSlider4 = document.getElementById('val-slider-4');
const sliderProp4 = document.getElementById('slider-prop-4');

const sliderPropRotX = document.getElementById('slider-prop-rot-x');
const valSliderRotX = document.getElementById('val-slider-rot-x');
const sliderPropRotY = document.getElementById('slider-prop-rot-y');
const valSliderRotY = document.getElementById('val-slider-rot-y');
const sliderPropRotZ = document.getElementById('slider-prop-rot-z');
const valSliderRotZ = document.getElementById('val-slider-rot-z');

const rowPropPathMode = document.getElementById('row-prop-path-mode');
const selectPropPathMode = document.getElementById('select-prop-path-mode');
const rowPropPathSpeed = document.getElementById('row-prop-path-speed');
const valSliderSpeed = document.getElementById('val-slider-speed');
const sliderPropSpeed = document.getElementById('slider-prop-speed');

const btnSavePropsCalib = document.getElementById('btn-save-props-calib');
const btnResetPropsCalib = document.getElementById('btn-reset-props-calib');
const propSaveFeedback = document.getElementById('prop-save-feedback');

let activePropId = 'monocle';

function syncActivePropSlidersUI() {
    const config = PROPS_CONFIG[activePropId] || PROPS_CONFIG.monocle;
    const calib = propsCalibration[activePropId] || config.defaults;

    if (labelSlider1) labelSlider1.innerText = config.labels.z;
    if (sliderProp1) {
        sliderProp1.min = config.ranges.z.min;
        sliderProp1.max = config.ranges.z.max;
        sliderProp1.step = config.ranges.z.step;
        sliderProp1.value = calib.z;
    }
    if (valSlider1) {
        const sign = calib.z >= 0 ? '+' : '';
        valSlider1.innerText = sign + calib.z.toFixed(3) + ' ' + config.ranges.z.unit;
    }

    if (labelSlider2) labelSlider2.innerText = config.labels.x;
    if (sliderProp2) {
        sliderProp2.min = config.ranges.x.min;
        sliderProp2.max = config.ranges.x.max;
        sliderProp2.step = config.ranges.x.step;
        sliderProp2.value = calib.x;
    }
    if (valSlider2) {
        const sign = calib.x >= 0 ? '+' : '';
        valSlider2.innerText = sign + calib.x.toFixed(3) + ' ' + config.ranges.x.unit;
    }

    if (labelSlider3) labelSlider3.innerText = config.labels.y;
    if (sliderProp3) {
        sliderProp3.min = config.ranges.y.min;
        sliderProp3.max = config.ranges.y.max;
        sliderProp3.step = config.ranges.y.step;
        sliderProp3.value = calib.y;
    }
    if (valSlider3) {
        const sign = calib.y >= 0 ? '+' : '';
        valSlider3.innerText = sign + calib.y.toFixed(3) + ' ' + config.ranges.y.unit;
    }

    if (labelSlider4) labelSlider4.innerText = config.labels.scale;
    if (sliderProp4) {
        sliderProp4.min = config.ranges.scale.min;
        sliderProp4.max = config.ranges.scale.max;
        sliderProp4.step = config.ranges.scale.step;
        sliderProp4.value = calib.scale;
    }
    if (valSlider4) {
        valSlider4.innerText = calib.scale.toFixed(2) + config.ranges.scale.unit;
    }

    // Prop Rotation (Pitch, Yaw, Roll)
    if (sliderPropRotX) sliderPropRotX.value = calib.rotX || 0;
    if (valSliderRotX) valSliderRotX.innerText = (calib.rotX || 0) + '°';

    if (sliderPropRotY) sliderPropRotY.value = calib.rotY || 0;
    if (valSliderRotY) valSliderRotY.innerText = (calib.rotY || 0) + '°';

    if (sliderPropRotZ) sliderPropRotZ.value = calib.rotZ || 0;
    if (valSliderRotZ) valSliderRotZ.innerText = (calib.rotZ || 0) + '°';

    // Path & Speed visibility
    if (rowPropPathMode) {
        rowPropPathMode.style.display = config.hasPath ? 'block' : 'none';
    }
    if (selectPropPathMode && config.hasPath) {
        selectPropPathMode.value = calib.pathMode || 'recon_orbit';
    }
    if (rowPropPathSpeed) {
        rowPropPathSpeed.style.display = config.hasPath ? 'block' : 'none';
    }
    if (sliderPropSpeed && config.hasPath) {
        sliderPropSpeed.value = calib.speed || 1.0;
        if (valSliderSpeed) valSliderSpeed.innerText = (calib.speed || 1.0).toFixed(2) + 'x';
    }
}
window.syncActivePropSlidersUI = syncActivePropSlidersUI;

function applySelectedPropToTwins(propId) {
    if (!propId) return;
    activePropId = propId;
    if (selectActiveProp && selectActiveProp.value !== propId) {
        selectActiveProp.value = propId;
    }
    syncActivePropSlidersUI();

    const isDual = activeModelId === 'dual';
    const isRen = isRenActive();

    switch (propId) {
        case 'monocle':
            if (isDual) {
                setPose('twin_synergy_briefing');
                updateStatus('👥 Monocle active on Ren in Dual Twin Tactical Briefing');
            } else if (isRen) {
                setPose('idle_ren_drone');
                updateStatus("🥽 Ren's Neural Monocle HUD Active");
            } else {
                triggerIdleObjectOrWaitingAnimation('idle_ren_drone', true);
                updateStatus("🥽 Monocle Telemetry Link Active");
            }
            break;

        case 'drone':
            if (isDual) {
                setPose('twin_synergy_briefing');
                updateStatus('👥 Tactical Recon Drone deployed in Dual Twin Briefing');
            } else {
                triggerIdleObjectOrWaitingAnimation('idle_ren_drone', true);
                updateStatus('🛸 Tactical Recon Drone (Ghosteye) Deployed');
            }
            break;

        case 'butterfly':
            triggerIdleObjectOrWaitingAnimation('idle_airi_butterfly', true);
            updateStatus("🦋 Airi's Bio-Quantum Butterfly Deployed");
            break;

        case 'console':
            triggerIdleObjectOrWaitingAnimation('idle_gaming_console', true);
            updateStatus('🎮 Arcade Cyber Deck Equipped');
            break;

        case 'katana':
            if (isDual) {
                setPose('twin_synergy_combat');
                updateStatus('👥 Dual Twin Combat Ready: Tactical Plasma Blades Drawn');
            } else {
                setPose('sword_guard_ready');
                updateStatus('⚔️ Tactical Plasma Blade Drawn (Combat Guard)');
            }
            break;

        case 'holodice':
            if (isDual) {
                setPose('twin_synergy_briefing');
                updateStatus('👥 Airi generating Quantum Holo-Dice in Dual Briefing');
            } else {
                triggerIdleObjectOrWaitingAnimation('idle_airi_holodice', true);
                updateStatus("🎲 Airi's Quantum Holo-Dice Active");
            }
            break;

        case 'datapad':
            if (isDual) {
                setPose('twin_synergy_briefing');
                updateStatus('👥 Ren accessing Tactical Datapad in Dual Briefing');
            } else {
                triggerIdleObjectOrWaitingAnimation('idle_ren_datapad', true);
                updateStatus("📱 Ren's Tactical Datapad Deployed");
            }
            break;

        case 'orb':
            triggerIdleObjectOrWaitingAnimation('idle_orb_curious', true);
            updateStatus('🔮 HELIOS Singularity Core Orb Active');
            break;

        case 'popup':
            triggerIdleObjectOrWaitingAnimation('idle_popup_curious', true);
            updateStatus('📑 Wrist Holographic HUD Projected');
            break;
    }
}
window.applySelectedPropToTwins = applySelectedPropToTwins;

if (selectActiveProp) {
    selectActiveProp.addEventListener('change', (e) => {
        applySelectedPropToTwins(e.target.value);
    });
}

if (sliderProp1) {
    sliderProp1.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        window.setPropCalibration(activePropId, { z: val });
        const config = PROPS_CONFIG[activePropId];
        if (valSlider1) valSlider1.innerText = (val >= 0 ? '+' : '') + val.toFixed(3) + ' ' + config.ranges.z.unit;
    });
}
if (sliderProp2) {
    sliderProp2.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        window.setPropCalibration(activePropId, { x: val });
        const config = PROPS_CONFIG[activePropId];
        if (valSlider2) valSlider2.innerText = (val >= 0 ? '+' : '') + val.toFixed(3) + ' ' + config.ranges.x.unit;
    });
}
if (sliderProp3) {
    sliderProp3.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        window.setPropCalibration(activePropId, { y: val });
        const config = PROPS_CONFIG[activePropId];
        if (valSlider3) valSlider3.innerText = (val >= 0 ? '+' : '') + val.toFixed(3) + ' ' + config.ranges.y.unit;
    });
}
if (sliderProp4) {
    sliderProp4.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        window.setPropCalibration(activePropId, { scale: val });
        const config = PROPS_CONFIG[activePropId];
        if (valSlider4) valSlider4.innerText = val.toFixed(2) + config.ranges.scale.unit;
    });
}

if (sliderPropRotX) {
    sliderPropRotX.addEventListener('input', (e) => {
        const val = parseInt(e.target.value, 10);
        window.setPropCalibration(activePropId, { rotX: val });
        if (valSliderRotX) valSliderRotX.innerText = val + '°';
    });
}
if (sliderPropRotY) {
    sliderPropRotY.addEventListener('input', (e) => {
        const val = parseInt(e.target.value, 10);
        window.setPropCalibration(activePropId, { rotY: val });
        if (valSliderRotY) valSliderRotY.innerText = val + '°';
    });
}
if (sliderPropRotZ) {
    sliderPropRotZ.addEventListener('input', (e) => {
        const val = parseInt(e.target.value, 10);
        window.setPropCalibration(activePropId, { rotZ: val });
        if (valSliderRotZ) valSliderRotZ.innerText = val + '°';
    });
}

if (selectPropPathMode) {
    selectPropPathMode.addEventListener('change', (e) => {
        window.setPropCalibration(activePropId, { pathMode: e.target.value });
    });
}

if (sliderPropSpeed) {
    sliderPropSpeed.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        window.setPropCalibration(activePropId, { speed: val });
        if (valSliderSpeed) valSliderSpeed.innerText = val.toFixed(2) + 'x';
    });
}

if (btnSavePropsCalib) {
    btnSavePropsCalib.addEventListener('click', () => {
        const ok = window.savePropsCalibration();
        if (propSaveFeedback) {
            propSaveFeedback.style.display = 'block';
            propSaveFeedback.innerText = ok ? '✓ Saved to Local Storage!' : '❌ Save Error';
            setTimeout(() => {
                propSaveFeedback.style.display = 'none';
            }, 2500);
        }
    });
}

if (btnResetPropsCalib) {
    btnResetPropsCalib.addEventListener('click', () => {
        window.resetPropCalibration(activePropId);
    });
}

// Initial UI synchronization
syncActivePropSlidersUI();

// ----------------------------------------------------
// DEDICATED 3D PROP & BIOMECHANICAL BODY POSE ADJUSTER STUDIO
// ----------------------------------------------------
const activeBodyPoseAdjustments = {
    enabled: true,
    target: 'active', // 'active', 'airi', 'ren', 'both'
    headPitch: 0,
    headYaw: 0,
    headRoll: 0,
    neckPitch: 0,
    spineLean: 0,
    spineTwist: 0,
    spineRoll: 0,
    chestBreath: 0,
    pelvisSway: 0,
    pelvisTilt: 0,
    crouch: 0,
    rArmLift: 0,
    rArmReach: 0,
    rArmSide: 0,
    rElbow: 0,
    rHandShape: 'auto',
    lArmLift: 0,
    lArmReach: 0,
    lArmSide: 0,
    lElbow: 0,
    lHandShape: 'auto',
    stanceWidth: 0,
    kneeBend: 0,
};
window.activeBodyPoseAdjustments = activeBodyPoseAdjustments;

// Adjuster Sub-Tab Switching (3D Prop Tuner vs Biomechanical Body Pose Tuner)
document.querySelectorAll('.adjust-subtab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const targetSubpaneId = btn.getAttribute('data-subtab');
        if (!targetSubpaneId) return;

        document.querySelectorAll('.adjust-subtab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        document.querySelectorAll('.adjust-subpane').forEach(p => {
            p.classList.toggle('active', p.id === targetSubpaneId);
        });

        if (targetSubpaneId === 'adjust-subpane-props') {
            applySelectedPropToTwins(activePropId);
        } else if (targetSubpaneId === 'adjust-subpane-body') {
            activeBodyPoseAdjustments.enabled = true;
            if (btnBodyToggleApply) {
                btnBodyToggleApply.classList.add('active');
                btnBodyToggleApply.innerText = '⚡ Live: ON';
            }
        }
    });
});

// Top Sidebar Studio Button trigger
const btnOpenAdjustMenu = document.getElementById('btn-open-adjust-menu');
if (btnOpenAdjustMenu) {
    btnOpenAdjustMenu.addEventListener('click', () => {
        const sidebar = document.getElementById('top-ui');
        if (sidebar && sidebar.classList.contains('collapsed')) {
            const toggle = document.getElementById('sidebar-toggle');
            if (toggle) toggle.click();
        }
        const adjustTabBtn = document.getElementById('tab-btn-adjust');
        if (adjustTabBtn) adjustTabBtn.click();
        const drawer = document.getElementById('poses-segmented-drawer');
        if (drawer) drawer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        applySelectedPropToTwins(activePropId);
    });
}

// Shortcut from Props Tab into Adjuster Studio
const btnGotoPropAdjust = document.getElementById('btn-goto-prop-adjust');
if (btnGotoPropAdjust) {
    btnGotoPropAdjust.addEventListener('click', () => {
        const adjustTabBtn = document.getElementById('tab-btn-adjust');
        if (adjustTabBtn) adjustTabBtn.click();
        const propsSubtabBtn = document.getElementById('subtab-btn-props');
        if (propsSubtabBtn) propsSubtabBtn.click();
    });
}

// Body Pose Sliders & Elements Binding
const selectBodyTarget = document.getElementById('select-body-target');
const btnBodyToggleApply = document.getElementById('btn-body-toggle-apply');
const btnBodyReset = document.getElementById('btn-body-reset');
const btnBodyCapture = document.getElementById('btn-body-capture');
const btnBodySave = document.getElementById('btn-body-save');
const bodySaveFeedback = document.getElementById('body-save-feedback');

const sliderBodyHeadPitch = document.getElementById('slider-body-head-pitch');
const valBodyHeadPitch = document.getElementById('val-body-head-pitch');
const sliderBodyHeadYaw = document.getElementById('slider-body-head-yaw');
const valBodyHeadYaw = document.getElementById('val-body-head-yaw');
const sliderBodyHeadRoll = document.getElementById('slider-body-head-roll');
const valBodyHeadRoll = document.getElementById('val-body-head-roll');
const sliderBodyNeckPitch = document.getElementById('slider-body-neck-pitch');
const valBodyNeckPitch = document.getElementById('val-body-neck-pitch');

const sliderBodySpineLean = document.getElementById('slider-body-spine-lean');
const valBodySpineLean = document.getElementById('val-body-spine-lean');
const sliderBodySpineTwist = document.getElementById('slider-body-spine-twist');
const valBodySpineTwist = document.getElementById('val-body-spine-twist');
const sliderBodySpineRoll = document.getElementById('slider-body-spine-roll');
const valBodySpineRoll = document.getElementById('val-body-spine-roll');
const sliderBodyChestBreath = document.getElementById('slider-body-chest-breath');
const valBodyChestBreath = document.getElementById('val-body-chest-breath');
const sliderBodyPelvisSway = document.getElementById('slider-body-pelvis-sway');
const valBodyPelvisSway = document.getElementById('val-body-pelvis-sway');
const sliderBodyPelvisTilt = document.getElementById('slider-body-pelvis-tilt');
const valBodyPelvisTilt = document.getElementById('val-body-pelvis-tilt');
const sliderBodyCrouch = document.getElementById('slider-body-crouch');
const valBodyCrouch = document.getElementById('val-body-crouch');

const sliderBodyRLift = document.getElementById('slider-body-r-lift');
const valBodyRLift = document.getElementById('val-body-r-lift');
const sliderBodyRReach = document.getElementById('slider-body-r-reach');
const valBodyRReach = document.getElementById('val-body-r-reach');
const sliderBodyRSide = document.getElementById('slider-body-r-side');
const valBodyRSide = document.getElementById('val-body-r-side');
const sliderBodyRElbow = document.getElementById('slider-body-r-elbow');
const valBodyRElbow = document.getElementById('val-body-r-elbow');
const selectBodyRHand = document.getElementById('select-body-r-hand');

const sliderBodyLLift = document.getElementById('slider-body-l-lift');
const valBodyLLift = document.getElementById('val-body-l-lift');
const sliderBodyLReach = document.getElementById('slider-body-l-reach');
const valBodyLReach = document.getElementById('val-body-l-reach');
const sliderBodyLSide = document.getElementById('slider-body-l-side');
const valBodyLSide = document.getElementById('val-body-l-side');
const sliderBodyLElbow = document.getElementById('slider-body-l-elbow');
const valBodyLElbow = document.getElementById('val-body-l-elbow');
const selectBodyLHand = document.getElementById('select-body-l-hand');

const sliderBodyStanceWidth = document.getElementById('slider-body-stance-width');
const valBodyStanceWidth = document.getElementById('val-body-stance-width');
const sliderBodyKneeBend = document.getElementById('slider-body-knee-bend');
const valBodyKneeBend = document.getElementById('val-body-knee-bend');

function syncBodyPoseSlidersUI() {
    const adj = activeBodyPoseAdjustments;
    if (sliderBodyHeadPitch) sliderBodyHeadPitch.value = adj.headPitch;
    if (valBodyHeadPitch) valBodyHeadPitch.innerText = adj.headPitch + '°';
    if (sliderBodyHeadYaw) sliderBodyHeadYaw.value = adj.headYaw;
    if (valBodyHeadYaw) valBodyHeadYaw.innerText = adj.headYaw + '°';
    if (sliderBodyHeadRoll) sliderBodyHeadRoll.value = adj.headRoll;
    if (valBodyHeadRoll) valBodyHeadRoll.innerText = adj.headRoll + '°';
    if (sliderBodyNeckPitch) sliderBodyNeckPitch.value = adj.neckPitch;
    if (valBodyNeckPitch) valBodyNeckPitch.innerText = adj.neckPitch + '°';

    if (sliderBodySpineLean) sliderBodySpineLean.value = adj.spineLean;
    if (valBodySpineLean) valBodySpineLean.innerText = adj.spineLean + '°';
    if (sliderBodySpineTwist) sliderBodySpineTwist.value = adj.spineTwist;
    if (valBodySpineTwist) valBodySpineTwist.innerText = adj.spineTwist + '°';
    if (sliderBodySpineRoll) sliderBodySpineRoll.value = adj.spineRoll;
    if (valBodySpineRoll) valBodySpineRoll.innerText = adj.spineRoll + '°';
    if (sliderBodyChestBreath) sliderBodyChestBreath.value = adj.chestBreath;
    if (valBodyChestBreath) valBodyChestBreath.innerText = adj.chestBreath.toFixed(2);
    if (sliderBodyPelvisSway) sliderBodyPelvisSway.value = adj.pelvisSway;
    if (valBodyPelvisSway) valBodyPelvisSway.innerText = adj.pelvisSway + '°';
    if (sliderBodyPelvisTilt) sliderBodyPelvisTilt.value = adj.pelvisTilt;
    if (valBodyPelvisTilt) valBodyPelvisTilt.innerText = adj.pelvisTilt + '°';
    if (sliderBodyCrouch) sliderBodyCrouch.value = adj.crouch;
    if (valBodyCrouch) valBodyCrouch.innerText = adj.crouch.toFixed(2) + ' m';

    if (sliderBodyRLift) sliderBodyRLift.value = adj.rArmLift;
    if (valBodyRLift) valBodyRLift.innerText = adj.rArmLift.toFixed(2) + ' m';
    if (sliderBodyRReach) sliderBodyRReach.value = adj.rArmReach;
    if (valBodyRReach) valBodyRReach.innerText = adj.rArmReach.toFixed(2) + ' m';
    if (sliderBodyRSide) sliderBodyRSide.value = adj.rArmSide;
    if (valBodyRSide) valBodyRSide.innerText = adj.rArmSide.toFixed(2) + ' m';
    if (sliderBodyRElbow) sliderBodyRElbow.value = adj.rElbow;
    if (valBodyRElbow) valBodyRElbow.innerText = adj.rElbow.toFixed(2);
    if (selectBodyRHand) selectBodyRHand.value = adj.rHandShape;

    if (sliderBodyLLift) sliderBodyLLift.value = adj.lArmLift;
    if (valBodyLLift) valBodyLLift.innerText = adj.lArmLift.toFixed(2) + ' m';
    if (sliderBodyLReach) sliderBodyLReach.value = adj.lArmReach;
    if (valBodyLReach) valBodyLReach.innerText = adj.lArmReach.toFixed(2) + ' m';
    if (sliderBodyLSide) sliderBodyLSide.value = adj.lArmSide;
    if (valBodyLSide) valBodyLSide.innerText = adj.lArmSide.toFixed(2) + ' m';
    if (sliderBodyLElbow) sliderBodyLElbow.value = adj.lElbow;
    if (valBodyLElbow) valBodyLElbow.innerText = adj.lElbow.toFixed(2);
    if (selectBodyLHand) selectBodyLHand.value = adj.lHandShape;

    if (sliderBodyStanceWidth) sliderBodyStanceWidth.value = adj.stanceWidth;
    if (valBodyStanceWidth) valBodyStanceWidth.innerText = adj.stanceWidth + '°';
    if (sliderBodyKneeBend) sliderBodyKneeBend.value = adj.kneeBend;
    if (valBodyKneeBend) valBodyKneeBend.innerText = adj.kneeBend + '°';

    if (selectBodyTarget) selectBodyTarget.value = adj.target;
    if (btnBodyToggleApply) {
        btnBodyToggleApply.classList.toggle('active', adj.enabled);
        btnBodyToggleApply.innerText = adj.enabled ? '⚡ Live: ON' : '⏸️ Live: OFF';
    }
}
window.syncBodyPoseSlidersUI = syncBodyPoseSlidersUI;

// Attach input listeners
if (selectBodyTarget) {
    selectBodyTarget.addEventListener('change', (e) => {
        activeBodyPoseAdjustments.target = e.target.value;
        activeBodyPoseAdjustments.enabled = true;
        if (btnBodyToggleApply) {
            btnBodyToggleApply.classList.add('active');
            btnBodyToggleApply.innerText = '⚡ Live: ON';
        }
        const targetLabel = {
            both: 'BOTH TWINS (Synchronized Kinematics)',
            airi: 'AIRI (Sister)',
            ren: 'REN (Brother)',
            active: 'ACTIVE AVATAR'
        }[e.target.value] || e.target.value;
        updateStatus(`🦾 Pose Adjuster: Target set to ${targetLabel} (Live Kinematics Active)`);
    });
}
if (btnBodyToggleApply) {
    btnBodyToggleApply.addEventListener('click', () => {
        activeBodyPoseAdjustments.enabled = !activeBodyPoseAdjustments.enabled;
        btnBodyToggleApply.classList.toggle('active', activeBodyPoseAdjustments.enabled);
        btnBodyToggleApply.innerText = activeBodyPoseAdjustments.enabled ? '⚡ Live: ON' : '⏸️ Live: OFF';
        updateStatus(`🦾 Pose Adjustment: ${activeBodyPoseAdjustments.enabled ? 'LIVE' : 'BYPASSED'}`);
    });
}

function bindBodySlider(sliderEl, valEl, key, formatFn) {
    if (!sliderEl) return;
    sliderEl.addEventListener('input', (e) => {
        const num = parseFloat(e.target.value);
        activeBodyPoseAdjustments[key] = num;
        if (!activeBodyPoseAdjustments.enabled) {
            activeBodyPoseAdjustments.enabled = true;
            if (btnBodyToggleApply) {
                btnBodyToggleApply.classList.add('active');
                btnBodyToggleApply.innerText = '⚡ Live: ON';
            }
        }
        if (valEl) valEl.innerText = formatFn ? formatFn(num) : num;
    });
}

bindBodySlider(sliderBodyHeadPitch, valBodyHeadPitch, 'headPitch', v => v + '°');
bindBodySlider(sliderBodyHeadYaw, valBodyHeadYaw, 'headYaw', v => v + '°');
bindBodySlider(sliderBodyHeadRoll, valBodyHeadRoll, 'headRoll', v => v + '°');
bindBodySlider(sliderBodyNeckPitch, valBodyNeckPitch, 'neckPitch', v => v + '°');

bindBodySlider(sliderBodySpineLean, valBodySpineLean, 'spineLean', v => v + '°');
bindBodySlider(sliderBodySpineTwist, valBodySpineTwist, 'spineTwist', v => v + '°');
bindBodySlider(sliderBodySpineRoll, valBodySpineRoll, 'spineRoll', v => v + '°');
bindBodySlider(sliderBodyChestBreath, valBodyChestBreath, 'chestBreath', v => v.toFixed(2));
bindBodySlider(sliderBodyPelvisSway, valBodyPelvisSway, 'pelvisSway', v => v + '°');
bindBodySlider(sliderBodyPelvisTilt, valBodyPelvisTilt, 'pelvisTilt', v => v + '°');
bindBodySlider(sliderBodyCrouch, valBodyCrouch, 'crouch', v => v.toFixed(2) + ' m');

bindBodySlider(sliderBodyRLift, valBodyRLift, 'rArmLift', v => v.toFixed(2) + ' m');
bindBodySlider(sliderBodyRReach, valBodyRReach, 'rArmReach', v => v.toFixed(2) + ' m');
bindBodySlider(sliderBodyRSide, valBodyRSide, 'rArmSide', v => v.toFixed(2) + ' m');
bindBodySlider(sliderBodyRElbow, valBodyRElbow, 'rElbow', v => v.toFixed(2));

bindBodySlider(sliderBodyLLift, valBodyLLift, 'lArmLift', v => v.toFixed(2) + ' m');
bindBodySlider(sliderBodyLReach, valBodyLReach, 'lArmReach', v => v.toFixed(2) + ' m');
bindBodySlider(sliderBodyLSide, valBodyLSide, 'lArmSide', v => v.toFixed(2) + ' m');
bindBodySlider(sliderBodyLElbow, valBodyLElbow, 'lElbow', v => v.toFixed(2));

bindBodySlider(sliderBodyStanceWidth, valBodyStanceWidth, 'stanceWidth', v => v + '°');
bindBodySlider(sliderBodyKneeBend, valBodyKneeBend, 'kneeBend', v => v + '°');

if (selectBodyRHand) {
    selectBodyRHand.addEventListener('change', (e) => {
        activeBodyPoseAdjustments.rHandShape = e.target.value;
    });
}
if (selectBodyLHand) {
    selectBodyLHand.addEventListener('change', (e) => {
        activeBodyPoseAdjustments.lHandShape = e.target.value;
    });
}

// Reset Pose Adjustments
if (btnBodyReset) {
    btnBodyReset.addEventListener('click', () => {
        Object.assign(activeBodyPoseAdjustments, {
            headPitch: 0,
            headYaw: 0,
            headRoll: 0,
            neckPitch: 0,
            spineLean: 0,
            spineTwist: 0,
            spineRoll: 0,
            chestBreath: 0,
            pelvisSway: 0,
            pelvisTilt: 0,
            crouch: 0,
            rArmLift: 0,
            rArmReach: 0,
            rArmSide: 0,
            rElbow: 0,
            rHandShape: 'auto',
            lArmLift: 0,
            lArmReach: 0,
            lArmSide: 0,
            lElbow: 0,
            lHandShape: 'auto',
            stanceWidth: 0,
            kneeBend: 0,
        });
        syncBodyPoseSlidersUI();
        updateStatus('↺ Body pose adjustments reset to neutral.');
    });
}

// Capture Live Pose into Sliders
if (btnBodyCapture) {
    btnBodyCapture.addEventListener('click', () => {
        if (!currentVrm || !currentVrm.humanoid) return;
        const h = currentVrm.humanoid;
        const headNode = h.getNormalizedBoneNode('head');
        const neckNode = h.getNormalizedBoneNode('neck');
        const spineNode = h.getNormalizedBoneNode('spine');
        const chestNode = h.getNormalizedBoneNode('chest');
        const hipsNode = h.getNormalizedBoneNode('hips');

        const toDeg = (rad) => Math.round(THREE.MathUtils.radToDeg(rad || 0));

        if (headNode) {
            activeBodyPoseAdjustments.headPitch = toDeg(headNode.rotation.x);
            activeBodyPoseAdjustments.headYaw = toDeg(headNode.rotation.y);
            activeBodyPoseAdjustments.headRoll = toDeg(headNode.rotation.z);
        }
        if (neckNode) {
            activeBodyPoseAdjustments.neckPitch = toDeg(neckNode.rotation.x);
        }
        if (spineNode) {
            activeBodyPoseAdjustments.spineLean = toDeg(spineNode.rotation.x);
            activeBodyPoseAdjustments.spineTwist = toDeg(spineNode.rotation.y);
            activeBodyPoseAdjustments.spineRoll = toDeg(spineNode.rotation.z);
        }
        if (chestNode) {
            activeBodyPoseAdjustments.chestBreath = Number(chestNode.rotation.x.toFixed(2));
        }
        if (hipsNode) {
            activeBodyPoseAdjustments.pelvisSway = toDeg(hipsNode.rotation.y);
            activeBodyPoseAdjustments.pelvisTilt = toDeg(hipsNode.rotation.z);
        }
        if (currentVrm.scene) {
            activeBodyPoseAdjustments.crouch = Number(currentVrm.scene.position.y.toFixed(2));
        }

        syncBodyPoseSlidersUI();
        updateStatus('📸 Live Model Pose captured into sliders!');
    });
}

// Save Custom Pose from Adjuster into Custom Poses list
if (btnBodySave) {
    btnBodySave.addEventListener('click', () => {
        const defaultName = `Custom Pose ${customPoseRegistry.size + 1}`;
        const poseName = prompt('Enter a label for this custom pose:', defaultName) || defaultName;
        if (!poseName || !poseName.trim()) return;

        const cleanKey = 'custom_' + poseName.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');
        const poseData = {
            label: poseName.trim(),
            bones: {
                head: [activeBodyPoseAdjustments.headPitch, activeBodyPoseAdjustments.headYaw, activeBodyPoseAdjustments.headRoll],
                neck: [activeBodyPoseAdjustments.neckPitch, 0, 0],
                spine: [activeBodyPoseAdjustments.spineLean, activeBodyPoseAdjustments.spineTwist, activeBodyPoseAdjustments.spineRoll],
                chest: [activeBodyPoseAdjustments.chestBreath * 20, 0, 0],
                hips: [0, activeBodyPoseAdjustments.pelvisSway, activeBodyPoseAdjustments.pelvisTilt],
                leftUpperLeg: [0, 0, -activeBodyPoseAdjustments.stanceWidth],
                rightUpperLeg: [0, 0, activeBodyPoseAdjustments.stanceWidth],
                leftLowerLeg: [activeBodyPoseAdjustments.kneeBend, 0, 0],
                rightLowerLeg: [activeBodyPoseAdjustments.kneeBend, 0, 0]
            },
            ik: {
                rightWrist: {
                    anchor: 'chest',
                    offset: [0.15 + activeBodyPoseAdjustments.rArmSide, activeBodyPoseAdjustments.rArmLift, 0.20 + activeBodyPoseAdjustments.rArmReach],
                    pole: [0.70 + activeBodyPoseAdjustments.rElbow, -0.40, 0.30]
                },
                leftWrist: {
                    anchor: 'chest',
                    offset: [-0.15 - activeBodyPoseAdjustments.lArmSide, activeBodyPoseAdjustments.lArmLift, 0.20 + activeBodyPoseAdjustments.lArmReach],
                    pole: [-0.70 - activeBodyPoseAdjustments.lElbow, -0.40, 0.30]
                },
                rightHandShape: activeBodyPoseAdjustments.rHandShape !== 'auto' ? activeBodyPoseAdjustments.rHandShape : 'relaxed',
                leftHandShape: activeBodyPoseAdjustments.lHandShape !== 'auto' ? activeBodyPoseAdjustments.lHandShape : 'relaxed',
            },
            hipsOffsetY: activeBodyPoseAdjustments.crouch
        };

        customPoseRegistry.set(cleanKey, poseData);

        // Store into localStorage
        try {
            const savedPoses = JSON.parse(localStorage.getItem('helios_studio_custom_poses') || '{}');
            savedPoses[cleanKey] = poseData;
            localStorage.setItem('helios_studio_custom_poses', JSON.stringify(savedPoses));
        } catch (e) {
            console.warn('Could not persist pose to localStorage:', e);
        }

        // Add button to #custom-pose-buttons
        const customGrid = document.getElementById('custom-pose-buttons');
        if (customGrid) {
            const btn = document.createElement('button');
            btn.setAttribute('data-custom-pose', cleanKey);
            btn.innerText = `🦾 ${poseName.trim()}`;
            btn.onclick = () => {
                document.querySelectorAll('#custom-pose-buttons button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                setPose(cleanKey);
            };
            customGrid.appendChild(btn);
        }

        if (bodySaveFeedback) {
            bodySaveFeedback.style.display = 'block';
            bodySaveFeedback.innerText = `✓ Saved "${poseName.trim()}" into Custom Poses!`;
            setTimeout(() => { bodySaveFeedback.style.display = 'none'; }, 3000);
        }
        updateStatus(`💾 Custom pose saved: ${poseName.trim()}`);
    });
}

// Initial Sync
syncBodyPoseSlidersUI();



