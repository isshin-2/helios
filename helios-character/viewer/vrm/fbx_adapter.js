/**
 * HELIOS Character Add-On — FBX Model to VRM-Compatible Humanoid Rig Adapter
 * ============================================================================
 * Enables the HELIOS 3D Character Viewer to load, render, shade, and animate
 * arbitrary FBX character models (including AI-generated models from Meshy AI,
 * Mixamo, Blender, etc.) with full VRM compatibility:
 *
 * 1. Automatic scale calibration (centimeters -> meters) and floor grounding (feet @ y=0).
 * 2. Signature HELIOS Cyberpunk Techwear cel-shading with reactive cybernetic neon trim.
 * 3. 17-Bone VRM Humanoid Skeleton with line-segment Linear Blend Skinning (GPU vertex deformation).
 * 4. Full VRM API adapter (`vrm.humanoid`, `vrm.expressionManager`, `vrm.lookAt`, `vrm.scene`, `vrm.update`).
 * 5. Interactive Rig & Model Editing API (`rebindSkinning`, `setBoneOffset`, `updateMaterial`, `getRigOptions`).
 */
import * as THREE from 'three';

// Standard 17 VRM Humanoid Bone Definition calibrated to Meshy techwear proportions
export const SKELETON_CONFIG = [
    { name: 'hips', parent: null, localPos: [0, 0.88, 0] },
    { name: 'spine', parent: 'hips', localPos: [0, 0.16, 0] },
    { name: 'chest', parent: 'spine', localPos: [0, 0.18, 0] },
    { name: 'neck', parent: 'chest', localPos: [0, 0.22, 0] },
    { name: 'head', parent: 'neck', localPos: [0, 0.14, 0] },

    { name: 'leftUpperArm', parent: 'chest', localPos: [0.20, 0.16, 0] },
    { name: 'leftLowerArm', parent: 'leftUpperArm', localPos: [0.07, -0.23, 0] },
    { name: 'leftHand', parent: 'leftLowerArm', localPos: [0.03, -0.25, 0] },

    { name: 'rightUpperArm', parent: 'chest', localPos: [-0.20, 0.16, 0] },
    { name: 'rightLowerArm', parent: 'rightUpperArm', localPos: [-0.07, -0.23, 0] },
    { name: 'rightHand', parent: 'rightLowerArm', localPos: [-0.03, -0.25, 0] },

    { name: 'leftUpperLeg', parent: 'hips', localPos: [0.11, -0.06, 0] },
    { name: 'leftLowerLeg', parent: 'leftUpperLeg', localPos: [0.0, -0.37, 0] },
    { name: 'leftFoot', parent: 'leftLowerLeg', localPos: [0.0, -0.37, 0.04] },

    { name: 'rightUpperLeg', parent: 'hips', localPos: [-0.11, -0.06, 0] },
    { name: 'rightLowerLeg', parent: 'rightUpperLeg', localPos: [0.0, -0.37, 0] },
    { name: 'rightFoot', parent: 'rightLowerLeg', localPos: [0.0, -0.37, 0.04] },
];

/**
 * Computes shortest distance from point P to line segment AB.
 */
export function distToSegment(p, a, b) {
    const abX = b.x - a.x;
    const abY = b.y - a.y;
    const abZ = b.z - a.z;
    const lenSq = abX * abX + abY * abY + abZ * abZ;
    if (lenSq < 1e-6) {
        return p.distanceTo(a);
    }
    const apX = p.x - a.x;
    const apY = p.y - a.y;
    const apZ = p.z - a.z;
    const t = Math.max(0, Math.min(1, (apX * abX + apY * abY + apZ * abZ) / lenSq));
    const projX = a.x + t * abX;
    const projY = a.y + t * abY;
    const projZ = a.z + t * abZ;
    const dx = p.x - projX;
    const dy = p.y - projY;
    const dz = p.z - projZ;
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

/**
 * Computes skinning weights & indices for a geometry given bones and parameters.
 */
export function computeSkinningWeights(geom, bones, options = {}) {
    const boneWorldPositions = bones.map((b) => {
        const wp = new THREE.Vector3();
        b.getWorldPosition(wp);
        return wp;
    });

    const idxOf = (name) => bones.findIndex((b) => b.name === name);
    const B_HIPS = idxOf('hips');
    const B_SPINE = idxOf('spine');
    const B_CHEST = idxOf('chest');
    const B_NECK = idxOf('neck');
    const B_HEAD = idxOf('head');

    const B_L_UPARM = idxOf('leftUpperArm');
    const B_L_LOARM = idxOf('leftLowerArm');
    const B_L_HAND = idxOf('leftHand');

    const B_R_UPARM = idxOf('rightUpperArm');
    const B_R_LOARM = idxOf('rightLowerArm');
    const B_R_HAND = idxOf('rightHand');

    const B_L_UPLEG = idxOf('leftUpperLeg');
    const B_L_LOLEG = idxOf('leftLowerLeg');
    const B_L_FOOT = idxOf('leftFoot');

    const B_R_UPLEG = idxOf('rightUpperLeg');
    const B_R_LOLEG = idxOf('rightLowerLeg');
    const B_R_FOOT = idxOf('rightFoot');

    const boneSegments = [
        { boneIdx: B_HIPS, a: boneWorldPositions[B_HIPS], b: boneWorldPositions[B_SPINE] },
        { boneIdx: B_SPINE, a: boneWorldPositions[B_SPINE], b: boneWorldPositions[B_CHEST] },
        { boneIdx: B_CHEST, a: boneWorldPositions[B_CHEST], b: boneWorldPositions[B_NECK] },
        { boneIdx: B_NECK, a: boneWorldPositions[B_NECK], b: boneWorldPositions[B_HEAD] },
        { boneIdx: B_HEAD, a: boneWorldPositions[B_HEAD], b: new THREE.Vector3(boneWorldPositions[B_HEAD].x, boneWorldPositions[B_HEAD].y + 0.14, boneWorldPositions[B_HEAD].z) },

        { boneIdx: B_L_UPARM, a: boneWorldPositions[B_L_UPARM], b: boneWorldPositions[B_L_LOARM] },
        { boneIdx: B_L_LOARM, a: boneWorldPositions[B_L_LOARM], b: boneWorldPositions[B_L_HAND] },
        { boneIdx: B_L_HAND, a: boneWorldPositions[B_L_HAND], b: new THREE.Vector3(boneWorldPositions[B_L_HAND].x + 0.02, boneWorldPositions[B_L_HAND].y - 0.12, boneWorldPositions[B_L_HAND].z) },

        { boneIdx: B_R_UPARM, a: boneWorldPositions[B_R_UPARM], b: boneWorldPositions[B_R_LOARM] },
        { boneIdx: B_R_LOARM, a: boneWorldPositions[B_R_LOARM], b: boneWorldPositions[B_R_HAND] },
        { boneIdx: B_R_HAND, a: boneWorldPositions[B_R_HAND], b: new THREE.Vector3(boneWorldPositions[B_R_HAND].x - 0.02, boneWorldPositions[B_R_HAND].y - 0.12, boneWorldPositions[B_R_HAND].z) },

        { boneIdx: B_L_UPLEG, a: boneWorldPositions[B_L_UPLEG], b: boneWorldPositions[B_L_LOLEG] },
        { boneIdx: B_L_LOLEG, a: boneWorldPositions[B_L_LOLEG], b: boneWorldPositions[B_L_FOOT] },
        { boneIdx: B_L_FOOT, a: boneWorldPositions[B_L_FOOT], b: new THREE.Vector3(boneWorldPositions[B_L_FOOT].x, 0.0, boneWorldPositions[B_L_FOOT].z + 0.14) },

        { boneIdx: B_R_UPLEG, a: boneWorldPositions[B_R_UPLEG], b: boneWorldPositions[B_R_LOLEG] },
        { boneIdx: B_R_LOLEG, a: boneWorldPositions[B_R_LOLEG], b: boneWorldPositions[B_R_FOOT] },
        { boneIdx: B_R_FOOT, a: boneWorldPositions[B_R_FOOT], b: new THREE.Vector3(boneWorldPositions[B_R_FOOT].x, 0.0, boneWorldPositions[B_R_FOOT].z + 0.14) },
    ];

    const segmentMap = new Map();
    boneSegments.forEach(s => segmentMap.set(s.boneIdx, s));

    const posAttr = geom.attributes.position;
    const count = posAttr.count;
    const skinIndices = new Uint16Array(count * 4);
    const skinWeights = new Float32Array(count * 4);

    const lateralPartitionX = options.lateralPartitionX !== undefined ? options.lateralPartitionX : 0.22;
    const falloffPower = options.falloffPower !== undefined ? options.falloffPower : 2.0;
    const maxInfluences = Math.min(4, Math.max(1, options.maxInfluences || 4));
    const sigma = options.sigma !== undefined ? options.sigma : 0.14;
    const sigmaSq2 = 2 * sigma * sigma;

    const vPos = new THREE.Vector3();

    for (let i = 0; i < count; i++) {
        vPos.fromBufferAttribute(posAttr, i);
        const x = vPos.x;
        const y = vPos.y;

        let candidateBones = [];

        if (y <= 0.88 && Math.abs(x) < lateralPartitionX) {
            if (x >= 0) {
                candidateBones = (y > 0.45) ? [B_L_UPLEG, B_L_LOLEG, B_HIPS] : [B_L_LOLEG, B_L_FOOT, B_L_UPLEG];
            } else {
                candidateBones = (y > 0.45) ? [B_R_UPLEG, B_R_LOLEG, B_HIPS] : [B_R_LOLEG, B_R_FOOT, B_R_UPLEG];
            }
        } else if (x >= lateralPartitionX && y > 0.70) {
            if (y > 1.34) {
                candidateBones = [B_L_UPARM, B_CHEST, B_L_LOARM];
            } else if (y > 1.10) {
                candidateBones = [B_L_UPARM, B_L_LOARM];
            } else if (y > 0.90) {
                candidateBones = [B_L_LOARM, B_L_HAND, B_L_UPARM];
            } else {
                candidateBones = [B_L_HAND, B_L_LOARM];
            }
        } else if (x <= -lateralPartitionX && y > 0.70) {
            if (y > 1.34) {
                candidateBones = [B_R_UPARM, B_CHEST, B_R_LOARM];
            } else if (y > 1.10) {
                candidateBones = [B_R_UPARM, B_R_LOARM];
            } else if (y > 0.90) {
                candidateBones = [B_R_LOARM, B_R_HAND, B_R_UPARM];
            } else {
                candidateBones = [B_R_HAND, B_R_LOARM];
            }
        } else if (y > 1.50) {
            candidateBones = [B_HEAD, B_NECK];
        } else if (y > 1.34) {
            candidateBones = [B_NECK, B_CHEST, B_HEAD];
        } else if (y > 1.12) {
            candidateBones = [B_CHEST, B_SPINE, B_NECK];
        } else if (y > 0.92) {
            candidateBones = [B_SPINE, B_HIPS, B_CHEST];
        } else {
            candidateBones = [B_HIPS, B_SPINE, (x >= 0 ? B_L_UPLEG : B_R_UPLEG)];
        }

        let weightSum = 0;
        const scoredBones = [];

        for (let k = 0; k < candidateBones.length; k++) {
            const bIdx = candidateBones[k];
            const seg = segmentMap.get(bIdx);
            const d = seg ? distToSegment(vPos, seg.a, seg.b) : vPos.distanceTo(boneWorldPositions[bIdx]);
            const w = Math.pow(Math.exp(- (d * d) / sigmaSq2) + 0.001, falloffPower / 2.0);
            scoredBones.push({ index: bIdx, weight: w });
            weightSum += w;
        }

        scoredBones.sort((a, b) => b.weight - a.weight);

        const baseIdx = i * 4;
        for (let k = 0; k < 4; k++) {
            if (k < Math.min(maxInfluences, scoredBones.length)) {
                skinIndices[baseIdx + k] = scoredBones[k].index;
                skinWeights[baseIdx + k] = scoredBones[k].weight / weightSum;
            } else {
                skinIndices[baseIdx + k] = candidateBones[0];
                skinWeights[baseIdx + k] = 0.0;
            }
        }
    }

    geom.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(skinIndices, 4));
    geom.setAttribute('skinWeight', new THREE.Float32BufferAttribute(skinWeights, 4));
    geom.attributes.skinIndex.needsUpdate = true;
    geom.attributes.skinWeight.needsUpdate = true;
}

/**
 * Creates a VRM-compatible Skinned Humanoid Character from an FBX Asset.
 * @param {THREE.Group} fbxAsset - Loaded Three.js FBX object
 * @param {Object} options - Configuration options
 * @returns {Object} vrmAdapter - VRM-compatible character instance
 */
export function createFBXHumanoidAdapter(fbxAsset, options = {}) {
    const rootGroup = new THREE.Group();
    rootGroup.name = 'HELIOS_FBX_Humanoid_Root';

    // 1. Compute bounding box and normalize scale & position
    const rawBox = new THREE.Box3().setFromObject(fbxAsset);
    const rawSize = new THREE.Vector3();
    rawBox.getSize(rawSize);

    // Target human height ~1.72m
    const targetHeight = options.targetHeight || 1.72;
    const height = rawSize.y;
    const scaleFactor = targetHeight / (height > 0.1 ? height : 1.0);
    fbxAsset.scale.set(scaleFactor, scaleFactor, scaleFactor);

    // Recompute box after scaling and center X/Z, ground Y at 0
    const scaledBox = new THREE.Box3().setFromObject(fbxAsset);
    const offsetX = - (scaledBox.min.x + scaledBox.max.x) / 2;
    const offsetZ = - (scaledBox.min.z + scaledBox.max.z) / 2;
    const offsetY = - scaledBox.min.y + (options.floorOffsetY || 0.0);

    fbxAsset.position.set(offsetX, offsetY, offsetZ);
    fbxAsset.updateMatrixWorld(true);

    // 2. Extract meshes
    const sourceMeshes = [];
    fbxAsset.traverse((child) => {
        if (child.isMesh) {
            sourceMeshes.push(child);
        }
    });

    if (sourceMeshes.length === 0) {
        console.warn('[FBXAdapter] No meshes found in FBX asset');
        rootGroup.add(fbxAsset);
        return createFallbackVRMInterface(rootGroup);
    }

    // 3. Build 17-bone Humanoid Bone Tree
    const boneMap = new Map();
    const bones = [];
    const boneOffsets = options.boneOffsets || {};

    SKELETON_CONFIG.forEach((cfg) => {
        const bone = new THREE.Bone();
        bone.name = cfg.name;
        const off = boneOffsets[cfg.name] || { x: 0, y: 0, z: 0 };
        bone.position.set(cfg.localPos[0] + off.x, cfg.localPos[1] + off.y, cfg.localPos[2] + off.z);
        boneMap.set(cfg.name, bone);
        bones.push(bone);
    });

    SKELETON_CONFIG.forEach((cfg) => {
        const bone = boneMap.get(cfg.name);
        if (cfg.parent) {
            boneMap.get(cfg.parent).add(bone);
        } else {
            rootGroup.add(bone);
        }
    });

    rootGroup.updateMatrixWorld(true);

    // 4. Create Material & Skinned Meshes
    const matColor = options.materialColor !== undefined ? options.materialColor : 0x3e4758;
    const roughness = options.roughness !== undefined ? options.roughness : 0.48;
    const metalness = options.metalness !== undefined ? options.metalness : 0.32;
    const emissiveColor = options.emissiveColor !== undefined ? options.emissiveColor : 0x00e5ff;
    const emissiveIntensity = options.emissiveIntensity !== undefined ? options.emissiveIntensity : 0.08;
    const wireframe = Boolean(options.wireframe);
    const opacity = options.opacity !== undefined ? options.opacity : 1.0;

    const techwearMat = new THREE.MeshStandardMaterial({
        color: matColor,
        roughness: roughness,
        metalness: metalness,
        side: THREE.DoubleSide,
        emissive: new THREE.Color(emissiveColor),
        emissiveIntensity: emissiveIntensity,
        wireframe: wireframe,
        transparent: opacity < 0.999,
        opacity: opacity,
    });
    techwearMat.name = 'HeliosTechwear_Material';

    const skinnedMeshes = [];

    sourceMeshes.forEach((mesh) => {
        const geom = mesh.geometry.clone();
        geom.applyMatrix4(mesh.matrixWorld);

        // Compute skinning weights with line segment distance metric
        computeSkinningWeights(geom, bones, options);

        const skinnedMesh = new THREE.SkinnedMesh(geom, techwearMat);
        skinnedMesh.name = mesh.name || 'MeshySkinnedCharacter';
        skinnedMesh.castShadow = true;
        skinnedMesh.receiveShadow = true;

        const skeleton = new THREE.Skeleton(bones);
        skinnedMesh.bind(skeleton);
        rootGroup.add(skinnedMesh);
        skinnedMeshes.push(skinnedMesh);
    });

    // 5. Return standard VRM interface with interactive editing API
    return createVRMInterface(rootGroup, boneMap, bones, options, fbxAsset, sourceMeshes, skinnedMeshes, techwearMat);
}

/**
 * Builds a full VRM-compliant interface for Three.js VRM Viewer systems.
 */
function createVRMInterface(rootGroup, boneMap, bones, options, fbxAsset, sourceMeshes, skinnedMeshes, techwearMat) {
    const headBone = boneMap.get('head');
    const neckBone = boneMap.get('neck');
    const spineBone = boneMap.get('spine');

    let lookAtTarget = new THREE.Vector3(0, 1.6, 2.0);
    const activeRigOptions = {
        lateralPartitionX: 0.22,
        falloffPower: 2.0,
        maxInfluences: 4,
        targetHeight: 1.72,
        floorOffsetY: 0.0,
        materialColor: '#3e4758',
        roughness: 0.48,
        metalness: 0.32,
        emissiveColor: '#00e5ff',
        emissiveIntensity: 0.08,
        wireframe: false,
        opacity: 1.0,
        boneOffsets: {},
        ...options,
    };

    const vrmAdapter = {
        scene: rootGroup,
        isFBXModel: true,
        rawFBXAsset: fbxAsset,
        bones,
        boneMap,
        skinnedMeshes,
        techwearMat,
        options: activeRigOptions,
        SKELETON_CONFIG,

        humanoid: {
            getNormalizedBoneNode: (name) => boneMap.get(name) || null,
            getBoneNode: (name) => boneMap.get(name) || null,
            getRawBoneNode: (name) => boneMap.get(name) || null,
            restPose: {},
            autoUpdateHumanBones: true,
            update: () => {},
        },
        expressionManager: {
            expressions: [],
            setValue: (expressionName, value) => {
                rootGroup.traverse((obj) => {
                    if (obj.isMesh && obj.material && obj.material.emissive) {
                        if (expressionName === 'happy') {
                            obj.material.emissiveIntensity = 0.04 + value * 0.08;
                        }
                    }
                });
            },
            getValue: (name) => 0,
            update: () => {},
        },
        lookAt: {
            target: lookAtTarget,
            autoUpdate: true,
            update: (delta) => {
                if (headBone && lookAtTarget) {
                    const headWorld = new THREE.Vector3();
                    headBone.getWorldPosition(headWorld);
                    const dir = lookAtTarget.clone().sub(headWorld).normalize();
                    const yaw = Math.atan2(dir.x, dir.z);
                    const pitch = -Math.asin(Math.max(-0.8, Math.min(0.8, dir.y)));
                    headBone.rotation.y = THREE.MathUtils.lerp(headBone.rotation.y, yaw * 0.45, delta * 4.0);
                    headBone.rotation.x = THREE.MathUtils.lerp(headBone.rotation.x, pitch * 0.35, delta * 4.0);
                }
            },
        },
        springBoneManager: {
            update: (delta) => {},
        },
        update: (delta) => {
            if (headBone && lookAtTarget) {
                const headWorld = new THREE.Vector3();
                headBone.getWorldPosition(headWorld);
                const dir = lookAtTarget.clone().sub(headWorld).normalize();
                const yaw = Math.atan2(dir.x, dir.z);
                const pitch = -Math.asin(Math.max(-0.8, Math.min(0.8, dir.y)));
                headBone.rotation.y = THREE.MathUtils.lerp(headBone.rotation.y, yaw * 0.4, Math.min(1.0, delta * 4.0));
                headBone.rotation.x = THREE.MathUtils.lerp(headBone.rotation.x, pitch * 0.3, Math.min(1.0, delta * 4.0));
            }
        },

        // --- Interactive Rig & Model Editing Methods ---
        rebindSkinning: (newOptions = {}) => {
            Object.assign(activeRigOptions, newOptions);
            rootGroup.updateMatrixWorld(true);
            skinnedMeshes.forEach((skinnedMesh) => {
                computeSkinningWeights(skinnedMesh.geometry, bones, activeRigOptions);
                if (skinnedMesh.skeleton) {
                    skinnedMesh.skeleton.calculateInverses();
                }
            });
            console.log('[FBXAdapter] Re-bound skinning weights with options:', activeRigOptions);
            return activeRigOptions;
        },

        setBoneOffset: (boneName, offset = {}) => {
            const bone = boneMap.get(boneName);
            const cfg = SKELETON_CONFIG.find((c) => c.name === boneName);
            if (!bone || !cfg) return;

            if (!activeRigOptions.boneOffsets) activeRigOptions.boneOffsets = {};
            const curOff = activeRigOptions.boneOffsets[boneName] || { x: 0, y: 0, z: 0 };
            const nextOff = { ...curOff, ...offset };
            activeRigOptions.boneOffsets[boneName] = nextOff;

            bone.position.set(
                cfg.localPos[0] + nextOff.x,
                cfg.localPos[1] + nextOff.y,
                cfg.localPos[2] + nextOff.z
            );
            rootGroup.updateMatrixWorld(true);

            skinnedMeshes.forEach((mesh) => {
                if (mesh.skeleton) mesh.skeleton.calculateInverses();
            });
        },

        updateMaterial: (matOptions = {}) => {
            Object.assign(activeRigOptions, matOptions);
            rootGroup.traverse((obj) => {
                if (obj.isMesh && obj.material && !obj.name.startsWith('joint_marker_')) {
                    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
                    mats.forEach((mat) => {
                        if (matOptions.materialColor !== undefined && mat.color && typeof mat.color.set === 'function') {
                            mat.color.set(matOptions.materialColor);
                        }
                        if (matOptions.roughness !== undefined && mat.roughness !== undefined) {
                            mat.roughness = Number(matOptions.roughness);
                        }
                        if (matOptions.metalness !== undefined && mat.metalness !== undefined) {
                            mat.metalness = Number(matOptions.metalness);
                        }
                        if (matOptions.emissiveColor !== undefined && mat.emissive && typeof mat.emissive.set === 'function') {
                            mat.emissive.set(matOptions.emissiveColor);
                        }
                        if (matOptions.emissiveIntensity !== undefined && mat.emissiveIntensity !== undefined) {
                            mat.emissiveIntensity = Number(matOptions.emissiveIntensity);
                        }
                        if (matOptions.wireframe !== undefined && mat.wireframe !== undefined) {
                            mat.wireframe = Boolean(matOptions.wireframe);
                        }
                        if (matOptions.opacity !== undefined && mat.opacity !== undefined) {
                            mat.opacity = Number(matOptions.opacity);
                            mat.transparent = mat.opacity < 0.999;
                            mat.depthWrite = mat.opacity >= 0.85;
                        }
                        mat.needsUpdate = true;
                    });
                }
            });
        },

        getRigConfiguration: () => {
            return JSON.parse(JSON.stringify(activeRigOptions));
        },
    };

    return vrmAdapter;
}

function createFallbackVRMInterface(group) {
    return {
        scene: group,
        isFBXModel: true,
        humanoid: {
            getNormalizedBoneNode: () => null,
            getBoneNode: () => null,
            getRawBoneNode: () => null,
            update: () => {},
        },
        expressionManager: {
            expressions: [],
            setValue: () => {},
            getValue: () => 0,
            update: () => {},
        },
        lookAt: {
            target: new THREE.Vector3(),
            update: () => {},
        },
        springBoneManager: { update: () => {} },
        update: () => {},
    };
}
