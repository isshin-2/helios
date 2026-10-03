/**
 * HELIOS Character Addon — VRM Three.js Renderer Module (Section 12)
 * Responsible for:
 * - Three.js WebGLRenderer, Scene, Camera, OrbitControls, Lighting
 * - VRM loading via @pixiv/three-vrm
 * - Skeleton rest-pose calibration
 * - Render loop management
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

export function createVRMRendererContext(containerEl) {
    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(
        30,
        window.innerWidth / window.innerHeight,
        0.1,
        25.0
    );
    camera.position.set(0.0, 1.35, 1.65);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    if (containerEl) {
        containerEl.appendChild(renderer.domElement);
    }

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.screenSpacePanning = true;
    controls.target.set(0.0, 1.15, 0.0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.update();

    // Lighting
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
    dirLight.position.set(1.0, 2.0, 1.0).normalize();
    scene.add(dirLight);

    const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
    scene.add(ambientLight);

    // Subtle spatial floor grid with state-reactive technological accents
    const gridHelper = new THREE.PolarGridHelper(2.5, 16, 6, 64, 0xffffff, 0x64748b);
    gridHelper.position.y = 0.002;
    gridHelper.material.transparent = true;
    gridHelper.material.opacity = 0.26;
    gridHelper.material.color.setHex(0x00e5ff);
    scene.add(gridHelper);

    // State-reactive cybernetic rim/accent light matching Tensura Popup states
    const stateAccentLight = new THREE.PointLight(0x00e5ff, 0.85, 4.5);
    stateAccentLight.position.set(0.0, 1.35, -0.95);
    scene.add(stateAccentLight);

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    const fbxLoader = new FBXLoader();

    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    return {
        scene,
        camera,
        renderer,
        controls,
        loader,
        fbxLoader,
        VRMUtils,
        gridHelper,
        stateAccentLight,
    };
}
