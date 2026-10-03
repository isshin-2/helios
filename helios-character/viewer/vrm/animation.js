/**
 * HELIOS Character Addon — VRM Animation & Navigation Module (Section 12)
 * Responsible for:
 * - Mixamo FBX retargeting & AnimationMixer blending
 * - Emotion-driven speaking pose pools
 * - Spatial Navigation ("walk_to_user", "step_back", "circle_user", "return_center")
 */
import * as THREE from 'three';

export const MIXAMO_TO_VRM_MAP = {
    mixamorigHips: 'hips',
    mixamorigSpine: 'spine',
    mixamorigSpine1: 'chest',
    mixamorigSpine2: 'upperChest',
    mixamorigNeck: 'neck',
    mixamorigHead: 'head',
    mixamorigLeftShoulder: 'leftShoulder',
    mixamorigLeftArm: 'leftUpperArm',
    mixamorigLeftForeArm: 'leftLowerArm',
    mixamorigLeftHand: 'leftHand',
    mixamorigLeftHandThumb1: 'leftThumbProximal',
    mixamorigLeftHandThumb2: 'leftThumbIntermediate',
    mixamorigLeftHandThumb3: 'leftThumbDistal',
    mixamorigLeftHandIndex1: 'leftIndexProximal',
    mixamorigLeftHandIndex2: 'leftIndexIntermediate',
    mixamorigLeftHandIndex3: 'leftIndexDistal',
    mixamorigLeftHandMiddle1: 'leftMiddleProximal',
    mixamorigLeftHandMiddle2: 'leftMiddleIntermediate',
    mixamorigLeftHandMiddle3: 'leftMiddleDistal',
    mixamorigLeftHandRing1: 'leftRingProximal',
    mixamorigLeftHandRing2: 'leftRingIntermediate',
    mixamorigLeftHandRing3: 'leftRingDistal',
    mixamorigLeftHandPinky1: 'leftLittleProximal',
    mixamorigLeftHandPinky2: 'leftLittleIntermediate',
    mixamorigLeftHandPinky3: 'leftLittleDistal',
    mixamorigRightShoulder: 'rightShoulder',
    mixamorigRightArm: 'rightUpperArm',
    mixamorigRightForeArm: 'rightLowerArm',
    mixamorigRightHand: 'rightHand',
    mixamorigRightHandThumb1: 'rightThumbProximal',
    mixamorigRightHandThumb2: 'rightThumbIntermediate',
    mixamorigRightHandThumb3: 'rightThumbDistal',
    mixamorigRightHandIndex1: 'rightIndexProximal',
    mixamorigRightHandIndex2: 'rightIndexIntermediate',
    mixamorigRightHandIndex3: 'rightIndexDistal',
    mixamorigRightHandMiddle1: 'rightMiddleProximal',
    mixamorigRightHandMiddle2: 'rightMiddleIntermediate',
    mixamorigRightHandMiddle3: 'rightMiddleDistal',
    mixamorigRightHandRing1: 'rightRingProximal',
    mixamorigRightHandRing2: 'rightRingIntermediate',
    mixamorigRightHandRing3: 'rightRingDistal',
    mixamorigRightHandPinky1: 'rightLittleProximal',
    mixamorigRightHandPinky2: 'rightLittleIntermediate',
    mixamorigRightHandPinky3: 'rightLittleDistal',
    mixamorigLeftUpLeg: 'leftUpperLeg',
    mixamorigLeftLeg: 'leftLowerLeg',
    mixamorigLeftFoot: 'leftFoot',
    mixamorigLeftToeBase: 'leftToes',
    mixamorigRightUpLeg: 'rightUpperLeg',
    mixamorigRightLeg: 'rightLowerLeg',
    mixamorigRightFoot: 'rightFoot',
    mixamorigRightToeBase: 'rightToes',
};

export const EMOTION_SPEAKING_POSE_POOLS = {
    happy: ['talk_excited', 'peace', 'cheer', 'wave', 'nod'],
    excited: ['talk_excited', 'cheer', 'peace', 'wave'],
    joy: ['talk_excited', 'peace', 'cheer', 'wave', 'nod'],
    amused: ['talk_smug', 'smug_pose', 'confident', 'shrug'],
    smirk: ['talk_smug', 'smug_pose', 'confident', 'shrug'],
    smug: ['talk_smug', 'smug_pose', 'confident', 'shrug'],
    curious: ['talk_explain', 'think_pose', 'nod'],
    relaxed: ['talk_smug', 'smug_pose', 'confident', 'talk_explain', 'shrug'],
    fun: ['talk_smug', 'smug_pose', 'confident', 'talk_explain', 'shrug'],
    serious: ['confident', 'talk_explain', 'refuse'],
    angry: ['talk_angry', 'refuse', 'confident', 'smug_pose'],
    concerned: ['talk_sad', 'think_pose', 'bow'],
    sad: ['talk_sad', 'shy', 'bow'],
    sorrow: ['talk_sad', 'shy', 'bow'],
    confused: ['talk_surprised', 'shrug', 'think_pose'],
    surprised: ['talk_surprised', 'shrug', 'talk_explain'],
    neutral: ['talk_explain', 'nod', 'confident', 'shrug'],
};

export const IDLE_OBJECT_AND_WAITING_POSES = [
    'idle_popup_curious',
    'idle_waiting_patient',
    'idle_orb_curious',
    'idle_waiting_look',
    'idle_screen_curious',
    'idle_waiting_stretch',
];

export const PROTOCOL_ANIMATION_MAP = {
    idle: 'idle',
    idle_popup_curious: 'idle_popup_curious',
    popup_curious: 'idle_popup_curious',
    inspect_popup: 'idle_popup_curious',
    idle_orb_curious: 'idle_orb_curious',
    orb_curious: 'idle_orb_curious',
    idle_screen_curious: 'idle_screen_curious',
    screen_curious: 'idle_screen_curious',
    tap_screen: 'idle_screen_curious',
    idle_waiting_patient: 'idle_waiting_patient',
    waiting: 'idle_waiting_patient',
    waiting_tap: 'idle_waiting_patient',
    idle_waiting_look: 'idle_waiting_look',
    waiting_look: 'idle_waiting_look',
    idle_waiting_stretch: 'idle_waiting_stretch',
    waiting_stretch: 'idle_waiting_stretch',
    listening: 'listen_pose',
    listen_pose: 'listen_pose',
    thinking: 'think_pose',
    think: 'think_pose',
    think_pose: 'think_pose',
    talking: 'talk_explain',
    talk_explain: 'talk_explain',
    talk_excited: 'talk_excited',
    talk_smug: 'talk_smug',
    talk_angry: 'talk_angry',
    talk_sad: 'talk_sad',
    talk_surprised: 'talk_surprised',
    wave: 'wave',
    nod: 'nod',
    peace: 'peace',
    cheer: 'cheer',
    shrug: 'shrug',
    bow: 'bow',
    confident: 'confident',
    shy: 'shy',
    smug: 'smug_pose',
    smirk: 'smug_pose',
    smug_pose: 'smug_pose',
    refuse: 'refuse',
    hug: 'hug_attempt',
    welcome: 'hug_attempt',
    hug_attempt: 'hug_attempt',
    dance: 'dance_shikano',
    dance_shikano: 'dance_shikano',
    flip: 'backflip',
    backflip: 'backflip',
    walk: 'walk',
};

export function mapProtocolAnimationToPose(animName, emotion = 'neutral') {
    const clean = (animName || 'idle').toLowerCase();
    if (clean === 'talking') {
        const pool = EMOTION_SPEAKING_POSE_POOLS[emotion.toLowerCase()] || EMOTION_SPEAKING_POSE_POOLS.neutral;
        return pool[0];
    }
    return PROTOCOL_ANIMATION_MAP[clean] || clean;
}

export function isSpecialTrickPose(pose) {
    return ['backflip', 'dance_shikano', 'hug_attempt', 'walk'].includes(pose);
}

export function isIdleObjectOrWaitingPose(pose) {
    return IDLE_OBJECT_AND_WAITING_POSES.includes(pose);
}

export function extractMixamoFBXClip(fbxAsset, vrm, clipName, rigMetrics = { rSide: 1 }) {
    const sourceClip = fbxAsset.animations?.[0];
    if (!sourceClip || !vrm?.humanoid) return null;

    const tracks = [];
    const restRotationInverse = new THREE.Quaternion();
    const parentRestWorldRotation = new THREE.Quaternion();
    const _quat = new THREE.Quaternion();

    sourceClip.tracks.forEach((track) => {
        const trackSplits = track.name.split('.');
        const rawRigName = trackSplits[0].replace(/^.*:/, '');
        const vrmBoneName = MIXAMO_TO_VRM_MAP[rawRigName];
        const mixamoRigNode =
            fbxAsset.getObjectByName(trackSplits[0]) || fbxAsset.getObjectByName(rawRigName);

        if (vrmBoneName && mixamoRigNode && track instanceof THREE.QuaternionKeyframeTrack) {
            const propertyName = trackSplits[1];
            mixamoRigNode.getWorldQuaternion(restRotationInverse).invert();
            if (mixamoRigNode.parent) {
                mixamoRigNode.parent.getWorldQuaternion(parentRestWorldRotation);
            } else {
                parentRestWorldRotation.identity();
            }

            const newValues = new Float32Array(track.values.length);
            for (let i = 0; i < track.values.length; i += 4) {
                _quat.fromArray(track.values, i);
                _quat.premultiply(parentRestWorldRotation).multiply(restRotationInverse);
                if (rigMetrics.rSide > 0) {
                    _quat.x = -_quat.x;
                    _quat.z = -_quat.z;
                }
                _quat.toArray(newValues, i);
            }
            tracks.push(
                new THREE.QuaternionKeyframeTrack(
                    `${rawRigName}.${propertyName}`,
                    track.times,
                    newValues
                )
            );
        }
    });

    return tracks.length > 0 ? new THREE.AnimationClip(clipName, sourceClip.duration, tracks) : null;
}

export class AnimationManager {
    constructor(vrm, callbacks = {}) {
        this.vrm = vrm;
        this.mixer = new THREE.AnimationMixer(vrm.scene);
        this.actions = new Map();
        this.currentAction = null;
        this.currentName = 'idle';
        this.crossfadeDuration = 0.4;
        this.usingExternalFBX = false;
        this.onPoseChanged = callbacks.onPoseChanged || null;
        this.onBackflipTrigger = callbacks.onBackflipTrigger || null;
    }

    registerClip(name, animationClip) {
        const tracks = [];
        for (const track of animationClip.tracks) {
            const trackNameParts = track.name.split('.');
            const rawBoneName = trackNameParts[0].replace(/^.*:/, '');
            const property = trackNameParts[1];

            const vrmBoneName = MIXAMO_TO_VRM_MAP[rawBoneName];
            if (vrmBoneName) {
                const boneNode = this.vrm.humanoid.getNormalizedBoneNode(vrmBoneName);
                if (boneNode) {
                    tracks.push(
                        new track.constructor(`${boneNode.name}.${property}`, track.times, track.values)
                    );
                }
            }
        }

        const retargetedClip = new THREE.AnimationClip(name, animationClip.duration, tracks);
        const action = this.mixer.clipAction(retargetedClip);
        this.actions.set(name, action);
        return action;
    }

    play(name, crossfadeDuration = 0.4, loop = true) {
        const resolvedName =
            name === 'smug' ? 'smug_pose' : PROTOCOL_ANIMATION_MAP[name] || name || 'idle';
        this.crossfadeDuration = Math.max(0.15, crossfadeDuration);

        if (this.actions.has(resolvedName)) {
            const nextAction = this.actions.get(resolvedName);
            this.usingExternalFBX = true;
            nextAction.reset();
            nextAction.enabled = true;
            nextAction.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, loop ? Infinity : 1);
            nextAction.clampWhenFinished = !loop;

            if (this.currentAction && this.currentAction !== nextAction) {
                this.currentAction.crossFadeTo(nextAction, crossfadeDuration, true);
            } else {
                nextAction.play();
            }
            this.currentAction = nextAction;
        } else {
            if (this.currentAction) {
                this.currentAction.fadeOut(crossfadeDuration);
                this.currentAction = null;
            }
            this.usingExternalFBX = false;
            if (resolvedName === 'backflip' && this.onBackflipTrigger) {
                this.onBackflipTrigger();
            }
        }

        this.currentName = resolvedName;
        if (this.onPoseChanged) this.onPoseChanged(resolvedName);
        return resolvedName;
    }

    update(delta) {
        if (this.usingExternalFBX) {
            this.mixer.update(delta);
        }
    }
}

export class NavigationController {
    constructor(vrmScene, animManager, baseFacingYaw = Math.PI, callbacks = {}) {
        this.scene = vrmScene;
        this.animManager = animManager;
        this.baseFacingYaw = baseFacingYaw;
        this.targetPosition = null;
        this.stoppingDistance = 0.85;
        this.activeStopDist = 0.85;
        this.walkSpeed = 1.1;
        this.turnSpeed = 4.5;
        this.isNavigating = false;
        this.mode = 'idle';
        this.arrivalAnim = 'idle';
        this.circleTimer = 0;
        this.onHighlightNav = callbacks.onHighlightNav || null;
        this.onSetPose = callbacks.onSetPose || null;
        this.onStatus = callbacks.onStatus || null;
        this.controlsTarget = callbacks.controlsTarget || null;
    }

    setDestination(targetVector3, arrivalAnim = 'idle', stopDist = 0.85) {
        this.targetPosition = targetVector3.clone();
        this.targetPosition.y = 0;
        this.activeStopDist = stopDist;
        this.arrivalAnim = arrivalAnim || 'idle';
        this.isNavigating = true;
        this.animManager.play('walk', 0.35, true);
    }

    executeMovement(movementType, userCamera, arrivalAnim = 'idle') {
        const mode = (movementType || 'idle').toLowerCase();
        this.mode = mode;
        this.arrivalAnim = arrivalAnim || 'idle';
        if (this.onHighlightNav) this.onHighlightNav(mode === 'idle' ? 'stay' : mode);

        if (mode === 'idle' || mode === 'stay') {
            this.isNavigating = false;
            this.targetPosition = null;
            if (this.animManager.currentName === 'walk' && this.onSetPose) {
                this.onSetPose(this.arrivalAnim === 'walk' ? 'idle' : this.arrivalAnim);
            }
            return;
        }

        const camPos = new THREE.Vector3();
        userCamera.getWorldPosition(camPos);
        camPos.y = 0;

        if (mode === 'walk_to_user') {
            this.setDestination(camPos, arrivalAnim, this.stoppingDistance);
        } else if (mode === 'step_back') {
            const awayDir = new THREE.Vector3(
                this.scene.position.x - camPos.x,
                0,
                this.scene.position.z - camPos.z
            );
            if (awayDir.lengthSq() < 1e-4) awayDir.set(0, 0, -1);
            awayDir.normalize();
            const backTarget = new THREE.Vector3(
                this.scene.position.x + awayDir.x * 0.65,
                0,
                this.scene.position.z + awayDir.z * 0.65
            );
            this.setDestination(
                backTarget,
                arrivalAnim === 'idle' ? 'smug_pose' : arrivalAnim,
                0.04
            );
        } else if (mode === 'return_center') {
            this.setDestination(new THREE.Vector3(0, 0, 0), arrivalAnim, 0.04);
        } else if (mode === 'circle_user') {
            this.circleTimer = 2.4;
            this.isNavigating = true;
            this.targetPosition = camPos;
            this.animManager.play('walk', 0.35, true);
        }
    }

    update(delta, userCamera) {
        if (!this.isNavigating) return;

        const currentPos = this.scene.position;

        if (this.mode === 'circle_user' && userCamera) {
            this.circleTimer -= delta;
            const camPos = new THREE.Vector3();
            userCamera.getWorldPosition(camPos);
            const dx = currentPos.x - camPos.x;
            const dz = currentPos.z - camPos.z;
            const radius = THREE.MathUtils.clamp(Math.hypot(dx, dz), 0.95, 1.55);

            if (this.circleTimer > 0) {
                const curAngle = Math.atan2(dx, dz);
                const nextAngle = curAngle + (this.walkSpeed / radius) * delta;
                currentPos.x = camPos.x + Math.sin(nextAngle) * radius;
                currentPos.z = camPos.z + Math.cos(nextAngle) * radius;

                const faceAngle =
                    Math.atan2(camPos.x - currentPos.x, camPos.z - currentPos.z) +
                    this.baseFacingYaw;
                this.rotateTowardAngle(faceAngle, delta);
                if (this.controlsTarget) {
                    this.controlsTarget.x = THREE.MathUtils.lerp(
                        this.controlsTarget.x,
                        currentPos.x,
                        delta * 5.0
                    );
                    this.controlsTarget.z = THREE.MathUtils.lerp(
                        this.controlsTarget.z,
                        currentPos.z,
                        delta * 5.0
                    );
                }
                return;
            } else {
                this.finishNavigation(userCamera);
                return;
            }
        }

        if (!this.targetPosition) return;

        if (this.mode === 'walk_to_user' && userCamera) {
            userCamera.getWorldPosition(this.targetPosition);
            this.targetPosition.y = 0;
        }

        const direction = new THREE.Vector3(
            this.targetPosition.x - currentPos.x,
            0,
            this.targetPosition.z - currentPos.z
        );
        const distance = direction.length();

        if (distance <= this.activeStopDist) {
            this.finishNavigation(userCamera);
            return;
        }

        direction.normalize();

        const lookDir = this.mode === 'step_back' ? direction.clone().negate() : direction;
        const targetAngle = Math.atan2(lookDir.x, lookDir.z) + this.baseFacingYaw;
        this.rotateTowardAngle(targetAngle, delta);

        const step = Math.min(
            this.walkSpeed * delta,
            Math.max(0, distance - this.activeStopDist)
        );
        currentPos.x += direction.x * step;
        currentPos.z += direction.z * step;

        if (this.controlsTarget) {
            this.controlsTarget.x = THREE.MathUtils.lerp(
                this.controlsTarget.x,
                currentPos.x,
                delta * 5.0
            );
            this.controlsTarget.z = THREE.MathUtils.lerp(
                this.controlsTarget.z,
                currentPos.z,
                delta * 5.0
            );
        }
    }

    rotateTowardAngle(targetAngle, delta) {
        const currentRotation = this.scene.rotation.y;
        let diff = targetAngle - currentRotation;
        while (diff < -Math.PI) diff += Math.PI * 2;
        while (diff > Math.PI) diff -= Math.PI * 2;
        this.scene.rotation.y += Math.sign(diff) * Math.min(Math.abs(diff), this.turnSpeed * delta);
    }

    finishNavigation(userCamera) {
        this.isNavigating = false;
        this.mode = 'idle';
        if (this.onHighlightNav) this.onHighlightNav('stay');

        if (userCamera) {
            const camPos = new THREE.Vector3();
            userCamera.getWorldPosition(camPos);
            const faceAngle =
                Math.atan2(camPos.x - this.scene.position.x, camPos.z - this.scene.position.z) +
                this.baseFacingYaw;
            this.scene.rotation.y = faceAngle;
        }

        const nextAnim =
            this.arrivalAnim && this.arrivalAnim !== 'walk' ? this.arrivalAnim : 'idle';
        if (this.onSetPose) this.onSetPose(nextAnim, nextAnim !== 'idle' ? 4500 : 0);
        if (this.onStatus) this.onStatus(`Arrived! Pose: ${nextAnim}`);
    }
}
