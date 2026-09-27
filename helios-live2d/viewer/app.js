import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

// Status & Thought HUD elements
const statusBadge = document.getElementById('status-badge');
const thoughtBanner = document.getElementById('thought-banner');
const thoughtText = document.getElementById('thought-text');

function updateStatus(msg) {
    if (statusBadge) statusBadge.innerText = msg;
}

function updateThoughtBanner(thought) {
    if (!thoughtBanner || !thoughtText) return;
    if (thought && thought.trim().length > 0) {
        thoughtText.innerText = thought;
        thoughtBanner.style.display = 'block';
    } else {
        thoughtBanner.style.display = 'none';
    }
}

// ----------------------------------------------------
// THREE.JS SCENE SETUP (Base from backup_vrm)
// ----------------------------------------------------
const container = document.getElementById('canvas-container');
const scene = new THREE.Scene();

const camera = new THREE.PerspectiveCamera(30, window.innerWidth / window.innerHeight, 0.1, 25.0);
camera.position.set(0.0, 1.35, 1.65);

const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
container.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.screenSpacePanning = true;
controls.target.set(0.0, 1.15, 0.0);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.update();

// Lights
const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
dirLight.position.set(1.0, 2.0, 1.0).normalize();
scene.add(dirLight);

const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
scene.add(ambientLight);

// Subtle spatial floor grid so Riko's 3D navigation ("Come to Me") is visually grounded
const gridHelper = new THREE.PolarGridHelper(2.5, 16, 6, 64, 0x38bdf8, 0x1e293b);
gridHelper.position.y = 0.002;
gridHelper.material.transparent = true;
gridHelper.material.opacity = 0.22;
scene.add(gridHelper);

// ----------------------------------------------------
// PHASE 2: PROCEDURAL HUMANIZATION ENGINE (Humanizer)
// ----------------------------------------------------
export class Humanizer {
    constructor(vrm) {
        this.vrm = vrm;
        this.blinkTimer = 0;
        this.nextBlinkInterval = 3.2;
        this.blinkProgress = 0;
        this.isBlinking = false;

        this.saccadeTimer = 0;
        this.nextSaccade = 0.4;
        this.saccadeOffset = new THREE.Vector2(0, 0);
        this.smoothSaccade = new THREE.Vector2(0, 0);
    }

    update(delta) {
        if (!this.vrm || !this.vrm.humanoid) return;
        this.applyNaturalBlink(delta);
        this.applyGazeAndSaccades(delta);
    }

    getBreathingOffset(elapsed) {
        // Calm dual-harmonic breathing
        const primaryBreath = Math.sin(elapsed * 1.5) * 0.012;
        const secondaryBreath = Math.sin(elapsed * 0.75) * 0.004;
        return (primaryBreath + secondaryBreath) * rigMetrics.forwardX;
    }

    applyNaturalBlink(delta) {
        if (!this.vrm.expressionManager || currentState === 'thinking') return;

        this.blinkTimer += delta;
        if (this.blinkTimer >= this.nextBlinkInterval) {
            this.isBlinking = true;
            this.blinkTimer = 0;
            this.blinkProgress = 0;
        }

        if (this.isBlinking) {
            this.blinkProgress += delta * 14.0;
            const blinkValue = Math.sin(this.blinkProgress);

            if (blinkValue < 0 || this.blinkProgress >= Math.PI) {
                this.isBlinking = false;
                this.vrm.expressionManager.setValue('blink', 0);
                // 20% probability of an immediate double blink
                this.nextBlinkInterval = Math.random() < 0.2 ? 0.25 : 2.5 + Math.random() * 4.0;
            } else {
                this.vrm.expressionManager.setValue('blink', Math.min(1.0, blinkValue));
            }
        }
    }

    applyGazeAndSaccades(delta) {
        this.saccadeTimer += delta;
        if (this.saccadeTimer >= this.nextSaccade) {
            this.saccadeTimer = 0;
            this.nextSaccade = 0.35 + Math.random() * 0.8;
            this.saccadeOffset.set(
                (Math.random() - 0.5) * 0.025,
                (Math.random() - 0.5) * 0.018
            );
        }

        this.smoothSaccade.lerp(this.saccadeOffset, Math.min(1.0, delta * 10.0));

        const lEye = this.vrm.humanoid.getNormalizedBoneNode('leftEye');
        const rEye = this.vrm.humanoid.getNormalizedBoneNode('rightEye');
        if (lEye && rEye) {
            lEye.rotation.y = this.smoothSaccade.x;
            lEye.rotation.x = this.smoothSaccade.y;
            rEye.rotation.y = this.smoothSaccade.x;
            rEye.rotation.x = this.smoothSaccade.y;
        }
    }
}

// ----------------------------------------------------
// PHASE 3: MIXAMO FBX INTEGRATION & ANIMATION BLENDING (AnimationManager)
// ----------------------------------------------------
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
    mixamorigRightToeBase: 'rightToes'
};

export class AnimationManager {
    constructor(vrm) {
        this.vrm = vrm;
        this.mixer = new THREE.AnimationMixer(vrm.scene);
        this.actions = new Map();
        this.currentAction = null;
        this.currentName = 'idle';
        this.crossfadeDuration = 0.4;
        this.usingExternalFBX = false;
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
                    tracks.push(new track.constructor(`${boneNode.name}.${property}`, track.times, track.values));
                }
            }
        }

        const retargetedClip = new THREE.AnimationClip(name, animationClip.duration, tracks);
        const action = this.mixer.clipAction(retargetedClip);
        this.actions.set(name, action);
        return action;
    }

    play(name, crossfadeDuration = 0.4, loop = true) {
        const resolvedName = name === 'smug' ? 'smug_pose' : (name || 'idle');
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
            if (resolvedName === 'backflip' && currentPose !== 'backflip') {
                backflipStartTime = clock.getElapsedTime();
            }
        }

        this.currentName = resolvedName;
        currentPose = resolvedName;
        highlightPoseButton(resolvedName);
    }

    update(delta) {
        if (this.usingExternalFBX) {
            this.mixer.update(delta);
        }
    }
}

// ----------------------------------------------------
// PHASE 4: SPATIAL NAVIGATION ("COME TO ME") (NavigationController)
// ----------------------------------------------------
export class NavigationController {
    constructor(vrmScene, animManager, baseFacingYaw = Math.PI) {
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
        highlightNavButton(mode === 'idle' ? 'stay' : mode);

        if (mode === 'idle' || mode === 'stay') {
            this.isNavigating = false;
            this.targetPosition = null;
            if (currentPose === 'walk') {
                setPose(this.arrivalAnim === 'walk' ? 'idle' : this.arrivalAnim);
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
            this.setDestination(backTarget, arrivalAnim === 'idle' ? 'smug_pose' : arrivalAnim, 0.04);
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

                const faceAngle = Math.atan2(camPos.x - currentPos.x, camPos.z - currentPos.z) + this.baseFacingYaw;
                this.rotateTowardAngle(faceAngle, delta);
                controls.target.x = THREE.MathUtils.lerp(controls.target.x, currentPos.x, delta * 5.0);
                controls.target.z = THREE.MathUtils.lerp(controls.target.z, currentPos.z, delta * 5.0);
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

        const step = Math.min(this.walkSpeed * delta, Math.max(0, distance - this.activeStopDist));
        currentPos.x += direction.x * step;
        currentPos.z += direction.z * step;

        controls.target.x = THREE.MathUtils.lerp(controls.target.x, currentPos.x, delta * 5.0);
        controls.target.z = THREE.MathUtils.lerp(controls.target.z, currentPos.z, delta * 5.0);
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
        highlightNavButton('stay');

        if (userCamera) {
            const camPos = new THREE.Vector3();
            userCamera.getWorldPosition(camPos);
            const faceAngle = Math.atan2(
                camPos.x - this.scene.position.x,
                camPos.z - this.scene.position.z
            ) + this.baseFacingYaw;
            this.scene.rotation.y = faceAngle;
        }

        const nextAnim = (this.arrivalAnim && this.arrivalAnim !== 'walk') ? this.arrivalAnim : 'idle';
        setPose(nextAnim, nextAnim !== 'idle' ? 4500 : 0);
        updateStatus(`Arrived! Pose: ${nextAnim}`);
    }
}

// ----------------------------------------------------
// PHASE 5: AUDIO-DRIVEN LIP SYNC & NEURAL VOICE ENGINE
// ----------------------------------------------------
let voiceMuted = false;
let selectedVoiceId = 'af_heart';

// Pre-warm a single persistent HTMLAudioElement in the DOM so browsers never block async playback
const sharedVoiceAudio = new Audio();
sharedVoiceAudio.preload = 'auto';
sharedVoiceAudio.volume = 1.0;
sharedVoiceAudio.playsInline = true;
let audioUnlockedByUser = false;

export class AudioLipSync {
    constructor(vrm) {
        this.vrm = vrm;
        this.audioContext = null;
        this.analyser = null;
        this.dataArray = null;
        this.activeSource = null;
        this.activeAudioEl = sharedVoiceAudio;
        this.activeRms = null;
        this.activeVisemes = null;
        this.playStartTime = 0;
        this.playDuration = 0;
        this.isPlaying = false;
    }

    ensureContext() {
        try {
            if (!this.audioContext) {
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                if (AudioCtx) {
                    this.audioContext = new AudioCtx();
                    this.analyser = this.audioContext.createAnalyser();
                    this.analyser.fftSize = 512;
                    this.analyser.smoothingTimeConstant = 0.62;
                    this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
                    this.analyser.connect(this.audioContext.destination);
                }
            }
            if (this.audioContext && this.audioContext.state === 'suspended') {
                this.audioContext.resume().catch(() => {});
            }
            if (this.audioContext && !audioUnlockedByUser) {
                const silentBuf = this.audioContext.createBuffer(1, 1, 22050);
                const silentSrc = this.audioContext.createBufferSource();
                silentSrc.buffer = silentBuf;
                silentSrc.connect(this.audioContext.destination);
                silentSrc.start(0);
                audioUnlockedByUser = true;
            }
        } catch (e) {}
    }

    stopCurrent() {
        if (this.activeSource) {
            try { this.activeSource.stop(); } catch (e) {}
            this.activeSource = null;
        }
        try {
            sharedVoiceAudio.pause();
            sharedVoiceAudio.onended = null;
            sharedVoiceAudio.onerror = null;
        } catch (e) {}
        if (window.speechSynthesis && window.speechSynthesis.speaking) {
            try { window.speechSynthesis.cancel(); } catch (e) {}
        }
        this.isPlaying = false;
        this.activeRms = null;
        this.activeVisemes = null;
        this.clearVisemes();
    }

    /**
     * Synchronously starts playing a pre-baked static MP3 inside the click event handler (0ms latency, never blocked by browser autoplay).
     */
    playStaticMp3Sync(mp3Url, fallbackText = '') {
        if (voiceMuted) {
            startSimulatedLipSync(3500);
            return Promise.resolve();
        }

        this.stopCurrent();
        this.ensureContext();

        this.activeRms = null;
        this.activeVisemes = null;
        this.playStartTime = performance.now() / 1000;
        this.playDuration = 3.8;
        this.isPlaying = true;

        return new Promise((resolve) => {
            sharedVoiceAudio.src = mp3Url;
            sharedVoiceAudio.volume = 1.0;
            sharedVoiceAudio.currentTime = 0;

            const finish = () => {
                this.isPlaying = false;
                this.clearVisemes();
                resolve();
            };

            sharedVoiceAudio.onended = finish;
            sharedVoiceAudio.onerror = () => {
                this.isPlaying = false;
                this.playBrowserSpeechFallback(fallbackText, 3.2).then(resolve);
            };

            const playPromise = sharedVoiceAudio.play();
            if (playPromise && typeof playPromise.catch === 'function') {
                playPromise.catch((err) => {
                    console.warn('Static MP3 play fallback to SpeechSynthesis:', err);
                    this.isPlaying = false;
                    this.playBrowserSpeechFallback(fallbackText, 3.2).then(resolve);
                });
            }
        });
    }

    async playBase64Wav(b64Audio, fallbackText = '', rms = null, visemes = null, duration = 0, mimeType = 'audio/mpeg') {
        if (voiceMuted) {
            const waitMs = Math.max(800, (duration || 2.0) * 1000);
            startSimulatedLipSync(waitMs);
            return new Promise(r => setTimeout(r, waitMs));
        }

        this.stopCurrent();

        if (!b64Audio) {
            return this.playBrowserSpeechFallback(fallbackText, duration);
        }

        try {
            this.ensureContext();
            this.activeRms = Array.isArray(rms) ? rms : null;
            this.activeVisemes = Array.isArray(visemes) ? visemes : null;
            this.playStartTime = performance.now() / 1000;
            this.playDuration = duration || 2.5;

            const binaryString = atob(b64Audio);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            // Primary path: Play directly via native HTML5 Audio Element (guaranteed OS sound output)
            const blob = new Blob([bytes], { type: mimeType || 'audio/mpeg' });
            const blobUrl = URL.createObjectURL(blob);

            return await new Promise((resolve) => {
                const cleanup = () => {
                    this.isPlaying = false;
                    this.clearVisemes();
                    URL.revokeObjectURL(blobUrl);
                    resolve();
                };

                sharedVoiceAudio.onended = cleanup;
                sharedVoiceAudio.onerror = () => {
                    URL.revokeObjectURL(blobUrl);
                    this.isPlaying = false;
                    this.playBrowserSpeechFallback(fallbackText, duration).then(resolve);
                };

                sharedVoiceAudio.src = blobUrl;
                sharedVoiceAudio.volume = 1.0;
                this.isPlaying = true;
                this.playStartTime = performance.now() / 1000;

                const p = sharedVoiceAudio.play();
                if (p && typeof p.catch === 'function') {
                    p.catch(async (err) => {
                        console.warn('HTML5 Audio fallback to WebAudio BufferSource:', err);
                        URL.revokeObjectURL(blobUrl);
                        try {
                            if (this.audioContext) {
                                const audioBuffer = await this.audioContext.decodeAudioData(bytes.buffer.slice(0));
                                const source = this.audioContext.createBufferSource();
                                source.buffer = audioBuffer;
                                source.connect(this.analyser);
                                this.activeSource = source;
                                this.isPlaying = true;
                                this.playStartTime = performance.now() / 1000;
                                source.onended = () => {
                                    this.isPlaying = false;
                                    this.activeSource = null;
                                    this.clearVisemes();
                                    resolve();
                                };
                                source.start(0);
                                return;
                            }
                        } catch (e2) {}
                        this.isPlaying = false;
                        await this.playBrowserSpeechFallback(fallbackText, duration);
                        resolve();
                    });
                }
            });
        } catch (err) {
            console.warn('Audio playback fallback to Browser SpeechSynthesis:', err);
            this.isPlaying = false;
            return this.playBrowserSpeechFallback(fallbackText, duration);
        }
    }

    playBrowserSpeechFallback(text, duration = 2.0) {
        const clean = (text || '').trim();
        if (!clean || !window.speechSynthesis) {
            const ms = Math.max(900, (duration || 2.0) * 1000);
            startSimulatedLipSync(ms);
            return new Promise(r => setTimeout(r, ms));
        }

        return new Promise((resolve) => {
            try {
                window.speechSynthesis.cancel();
                const utter = new SpeechSynthesisUtterance(clean);
                const voices = window.speechSynthesis.getVoices();
                const preferred = voices.find(v => /Aria|Ana|Zira|Jenny|Samantha|Hazel|Google US English|Female/i.test(v.name))
                    || voices.find(v => v.lang && v.lang.startsWith('en'))
                    || voices[0];
                if (preferred) utter.voice = preferred;
                utter.pitch = 1.2;
                utter.rate = 1.06;
                utter.volume = 1.0;

                const estMs = Math.max(1200, clean.length * 62);
                startSimulatedLipSync(estMs);

                utter.onend = () => {
                    this.clearVisemes();
                    resolve();
                };
                utter.onerror = () => {
                    this.clearVisemes();
                    resolve();
                };
                window.speechSynthesis.speak(utter);
            } catch (e) {
                resolve();
            }
        });
    }

    clearVisemes() {
        if (!this.vrm || !this.vrm.expressionManager) return;
        ['aa', 'ih', 'ou', 'ee', 'oh'].forEach((v) => {
            try { this.vrm.expressionManager.setValue(v, 0); } catch (e) {}
        });
    }

    update() {
        if (!this.isPlaying || !this.vrm || !this.vrm.expressionManager) return;

        let openness = 0;
        let ihWeight = 0;
        let ouWeight = 0;

        if (this.analyser && this.activeSource && this.dataArray) {
            this.analyser.getByteFrequencyData(this.dataArray);

            let lowEnergy = 0;
            let midEnergy = 0;
            let subEnergy = 0;

            for (let i = 2; i < 16; i++) lowEnergy += this.dataArray[i];
            for (let i = 16; i < 64; i++) midEnergy += this.dataArray[i];
            for (let i = 1; i < 8; i++) subEnergy += this.dataArray[i];

            const lowNorm = lowEnergy / 14 / 255;
            const midNorm = midEnergy / 48 / 255;
            const subNorm = subEnergy / 7 / 255;

            openness = Math.min(1.0, lowNorm * 1.9);
            ihWeight = midNorm > lowNorm * 0.55 ? Math.min(1.0, midNorm * 1.9) : 0;
            ouWeight = subNorm > 0.35 ? Math.min(0.75, subNorm * 1.1) : 0;
        }

        const elapsed = (!sharedVoiceAudio.paused && sharedVoiceAudio.currentTime > 0)
            ? sharedVoiceAudio.currentTime
            : (performance.now() / 1000 - this.playStartTime);

        if (openness < 0.05 && this.activeRms && this.activeRms.length > 0) {
            const frameIdx = Math.min(this.activeRms.length - 1, Math.max(0, Math.floor(elapsed * 30)));
            openness = Math.min(1.0, (this.activeRms[frameIdx] || 0) * 1.25);
            ihWeight = Math.min(0.65, openness * 0.48 * (0.5 + 0.5 * Math.sin(elapsed * 18)));
            ouWeight = Math.min(0.55, openness * 0.38 * (0.5 + 0.5 * Math.cos(elapsed * 14)));
        } else if (openness < 0.05) {
            // Smooth procedural syllable cadence while static MP3 plays
            const syll = Math.max(0, Math.sin(elapsed * 15.5) * 0.55 + Math.sin(elapsed * 7.2) * 0.35 + 0.25);
            openness = Math.min(0.92, syll);
            ihWeight = Math.max(0, Math.sin(elapsed * 11.0) * 0.45);
            ouWeight = Math.max(0, Math.cos(elapsed * 9.5) * 0.35);
        }

        this.vrm.expressionManager.setValue('aa', openness);
        this.vrm.expressionManager.setValue('ih', ihWeight);
        this.vrm.expressionManager.setValue('ou', ouWeight);
    }
}

// ----------------------------------------------------
// VRM MODEL LOADER & EXACT SKELETON CALIBRATION
// ----------------------------------------------------
let currentVrm = null;
let humanizer = null;
let animManager = null;
let navController = null;
let audioLipSync = null;
let availableExpressions = [];
let baseFacingYaw = Math.PI;
let backflipStartTime = -1;

const rigMetrics = {
    rSide: 1,
    lSide: -1,
    camZ: -1,
    forwardX: -1,
    leftFingerCurlZ: 1,
    rightFingerCurlZ: -1,
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

const loader = new GLTFLoader();
loader.register((parser) => new VRMLoaderPlugin(parser));
const fbxLoader = new FBXLoader();

const DEFAULT_VRM_URL = 'models/Yu1_1.vrm';

function loadVRM(url, isBlob = false) {
    updateStatus('Loading VRM model... 0%');

    loader.load(
        url,
        (gltf) => {
            const vrm = gltf.userData.vrm;

            if (currentVrm) {
                scene.remove(currentVrm.scene);
                VRMUtils.deepDispose(currentVrm.scene);
            }

            currentVrm = vrm;
            scene.add(vrm.scene);

            VRMUtils.rotateVRM0(vrm);
            baseFacingYaw = vrm.scene.rotation.y;

            calibrateSkeletonAndRestPose(vrm);

            humanizer = new Humanizer(vrm);
            animManager = new AnimationManager(vrm);
            navController = new NavigationController(vrm.scene, animManager, baseFacingYaw);
            audioLipSync = new AudioLipSync(vrm);

            applyProceduralPose(0, 1.0);
            vrm.humanoid.update();
            vrm.scene.updateMatrixWorld(true);

            readAndRenderPresets(vrm);
            focusOnModel(vrm);

            updateStatus(`Riko Ready! (${availableExpressions.length} BlendShapes | Listening & Multi-Emotion Speaking Poses)`);
            console.log('Riko VRM initialized:', vrm);

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
            console.error('Failed to load VRM:', error);
            updateStatus('Error loading VRM: ' + error.message);
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

    const upperPalmHint = new THREE.Vector3(0, -0.5, -rigMetrics.camZ * 0.85)
        .lerp(palmNormal, 0.25)
        .normalize();
    const lowerPalmHint = new THREE.Vector3()
        .copy(upperPalmHint)
        .lerp(palmNormal, 0.72)
        .normalize();

    buildArmSegmentQuaternion(uDir, upperPalmHint, sideSign, _qUpper);
    buildArmSegmentQuaternion(lDir, lowerPalmHint, sideSign, _qLower);
    buildArmSegmentQuaternion(fingerDir, palmNormal, sideSign, _qHand);

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
    relaxed:   { curls: [0.25, 0.22, 0.28, 0.34, 0.40], spread: 0.04 },
    open:      { curls: [0.08, 0.03, 0.03, 0.05, 0.07], spread: 0.16 },
    fist:      { curls: [0.65, 0.88, 0.92, 0.95, 0.98], spread: 0.0  },
    peace:     { curls: [0.75, 0.02, 0.02, 0.92, 0.95], spread: 0.22 },
    point:     { curls: [0.65, 0.02, 0.88, 0.92, 0.95], spread: 0.0  },
    chinTouch: { curls: [0.32, 0.04, 0.82, 0.88, 0.92], spread: 0.04 },
    cupped:    { curls: [0.35, 0.42, 0.46, 0.50, 0.54], spread: 0.02 },
    clasped:   { curls: [0.45, 0.55, 0.60, 0.65, 0.70], spread: 0.0  },
    antler:    { curls: [0.05, 0.04, 0.05, 0.08, 0.12], spread: 0.24 }
};

function lerpBoneEuler(bone, tx, ty, tz, speed) {
    if (!bone) return;
    bone.rotation.x = THREE.MathUtils.lerp(bone.rotation.x, tx, speed);
    bone.rotation.y = THREE.MathUtils.lerp(bone.rotation.y, ty, speed);
    bone.rotation.z = THREE.MathUtils.lerp(bone.rotation.z, tz, speed);
}

function applyHandShape(humanoid, side, shapeName, speed) {
    const shape = HAND_SHAPES[shapeName] || HAND_SHAPES.relaxed;
    const curlSign = side === 'left' ? rigMetrics.leftFingerCurlZ : rigMetrics.rightFingerCurlZ;
    const fwdYSign = side === 'left' ? rigMetrics.leftElbowFwdY : rigMetrics.rightElbowFwdY;

    FINGER_NAMES.forEach((finger, fIdx) => {
        const baseCurl = shape.curls[fIdx];
        let spreadAngle = 0;
        if (fIdx >= 1) {
            if (shapeName === 'peace' && (fIdx === 1 || fIdx === 2)) {
                spreadAngle = (fIdx === 1 ? -1 : 1) * shape.spread * curlSign;
            } else {
                spreadAngle = (fIdx - 2.2) * shape.spread * curlSign;
            }
        }

        FINGER_SEGMENTS.forEach((seg, sIdx) => {
            const bone = humanoid.getNormalizedBoneNode(`${side}${finger}${seg}`);
            if (!bone) return;

            if (finger === 'Thumb') {
                const tx = 0;
                const ty = fwdYSign * baseCurl * (sIdx === 0 ? 0.55 : 0.45);
                const tz = curlSign * baseCurl * (sIdx === 0 ? 0.35 : 0.45);
                lerpBoneEuler(bone, tx, ty, tz, speed);
            } else {
                const jointWeight = sIdx === 0 ? 0.95 : (sIdx === 1 ? 1.05 : 0.80);
                const tx = 0;
                const ty = (sIdx === 0) ? spreadAngle : 0;
                const tz = curlSign * baseCurl * jointWeight;
                lerpBoneEuler(bone, tx, ty, tz, speed);
            }
        });
    });
}

// ----------------------------------------------------
// REAL-TIME SMOOTH 3D POSE ENGINE (2-BONE IK + LISTENING & SPEAKING POSES)
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

    const breath = humanizer ? humanizer.getBreathingOffset(time) : Math.sin(time * 1.5) * 0.012 * fwd;

    let scenePosY = 0;
    let hipsRot = [0, 0, 0];
    let spineRot = [breath * 0.5, 0, 0];
    let chestRot = [breath, 0, 0];
    let neckRot = [0, 0, 0];
    let headRot = [
        Math.sin(time * 1.1) * 0.01,
        Math.cos(time * 0.7) * 0.012,
        0
    ];
    let lShoulderRot = [0, 0, 0];
    let rShoulderRot = [0, 0, 0];

    let lUpperLegRot = [0, 0, lSide * 0.015];
    let rUpperLegRot = [0, 0, rSide * 0.015];
    let lLowerLegRot = [0, 0, 0];
    let rLowerLegRot = [0, 0, 0];
    let lFootRot = [0, 0, 0];
    let rFootRot = [0, 0, 0];

    let leftHandShape = 'relaxed';
    let rightHandShape = 'relaxed';

    // Default Idle Right & Left Arm IK Targets
    let rWrist = new THREE.Vector3(S_R.x + rSide * 0.058, S_R.y - reach * 0.93, S_R.z + camZ * 0.04);
    let rPole  = new THREE.Vector3(rSide * 0.6, -0.2, -camZ * 0.8);
    let rFDir  = new THREE.Vector3(rSide * 0.12, -0.98, camZ * 0.12);
    let rPalm  = new THREE.Vector3(-rSide * 0.95, -0.15, camZ * 0.25);

    let lWrist = new THREE.Vector3(S_L.x + lSide * 0.058, S_L.y - reach * 0.93, S_L.z + camZ * 0.04);
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
        rShoulderRot = [0, 0, rSide * 0.18];
        headRot = [fwd * -0.04, -rSide * 0.06, rSide * 0.08];
        spineRot = [0, 0, rSide * 0.04];

        rWrist.set(
            S_R.x + rSide * (0.13 + Math.sin(time * 8.5) * 0.045),
            headP.y + 0.08,
            headP.z + camZ * 0.10
        );
        rPole.set(rSide * 0.9, 0.25, camZ * 0.15);
        rFDir.set(rSide * waveAngle, 1.0, camZ * 0.05).normalize();
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
        lShoulderRot = [0, 0, lSide * 0.22];
        rShoulderRot = [0, 0, rSide * 0.22];
        headRot = [fwd * -0.08, 0, Math.sin(time * 6.0) * 0.05];
        spineRot = [fwd * -0.05, 0, 0];

        const pumpY = Math.sin(time * 6.0) * 0.03;
        rWrist.set(headP.x + rSide * 0.17, headP.y + 0.19 + pumpY, headP.z + camZ * 0.07);
        rPole.set(rSide * 0.9, 0.3, camZ * 0.2);
        rFDir.set(-rSide * 0.1, 0.99, 0).normalize();
        rPalm.set(-rSide * 0.25, 0, camZ * 0.96).normalize();

        lWrist.set(headP.x + lSide * 0.17, headP.y + 0.19 + pumpY, headP.z + camZ * 0.07);
        lPole.set(lSide * 0.9, 0.3, camZ * 0.2);
        lFDir.set(-lSide * 0.1, 0.99, 0).normalize();
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
        spineRot = [fwd * 0.40, 0, 0];
        chestRot = [fwd * 0.25, 0, 0];
        headRot = [fwd * 0.18, 0, 0];

        rWrist.set(rSide * 0.035, chestP.y - 0.04, chestP.z + camZ * 0.14);
        rPole.set(rSide * 0.8, -0.5, 0);
        rFDir.set(-rSide * 0.85, -0.45, camZ * 0.2).normalize();
        rPalm.set(0, 0.3, -camZ * 0.95).normalize();

        lWrist.set(lSide * 0.035, chestP.y - 0.04, chestP.z + camZ * 0.14);
        lPole.set(lSide * 0.8, -0.5, 0);
        lFDir.set(-lSide * 0.85, -0.45, camZ * 0.2).normalize();
        lPalm.set(0, 0.3, -camZ * 0.95).normalize();

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
    }

    // Add natural conversational head rhythm while speaking
    if (currentState === 'speaking') {
        headRot[0] += Math.sin(time * 5.5) * 0.028;
        headRot[1] += Math.cos(time * 2.5) * 0.022;
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

    // Apply Torso, Neck, Head & Shoulders
    lerpBoneEuler(h.getNormalizedBoneNode('spine'), ...spineRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('chest'), ...chestRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('neck'), ...neckRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('head'), ...headRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('leftShoulder'), ...lShoulderRot, speed);
    lerpBoneEuler(h.getNormalizedBoneNode('rightShoulder'), ...rShoulderRot, speed);

    // Solve & apply 2-Bone Analytic IK + Shortest-Path Quaternion Slerp for both arms
    solveAndApplyArmIK(h, rootNode, 'right', rWrist, rPole, rFDir, rPalm, speed);
    solveAndApplyArmIK(h, rootNode, 'left', lWrist, lPole, lFDir, lPalm, speed);

    // Apply 30-bone finger shapes
    applyHandShape(h, 'left', leftHandShape, speed);
    applyHandShape(h, 'right', rightHandShape, speed);
}

// External Mixamo FBX file retargeting helper for user-uploaded .fbx files
function extractMixamoFBXClip(fbxAsset, vrm, clipName) {
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
        const mixamoRigNode = fbxAsset.getObjectByName(trackSplits[0]) || fbxAsset.getObjectByName(rawRigName);

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
            tracks.push(new THREE.QuaternionKeyframeTrack(`${rawRigName}.${propertyName}`, track.times, newValues));
        }
    });

    return tracks.length > 0 ? new THREE.AnimationClip(clipName, sourceClip.duration, tracks) : null;
}

// ----------------------------------------------------
// MULTI-POSE EMOTION-DRIVEN SPEAKING SYSTEM & UI HELPERS
// ----------------------------------------------------
let currentState = 'idle';
let currentEmotion = 'neutral';
let currentPose = 'idle';
let poseResetTimeout = null;
let simLipSyncTimer = null;

// Pools of multiple speaking poses mapped to each emotion
const EMOTION_SPEAKING_POSE_POOLS = {
    happy:     ['talk_excited', 'peace', 'cheer', 'wave', 'nod'],
    joy:       ['talk_excited', 'peace', 'cheer', 'wave', 'nod'],
    relaxed:   ['talk_smug', 'smug_pose', 'confident', 'talk_explain', 'shrug'],
    fun:       ['talk_smug', 'smug_pose', 'confident', 'talk_explain', 'shrug'],
    smug:      ['talk_smug', 'smug_pose', 'confident', 'shrug'],
    angry:     ['talk_angry', 'refuse', 'confident', 'smug_pose'],
    sad:       ['talk_sad', 'shy', 'bow'],
    sorrow:    ['talk_sad', 'shy', 'bow'],
    surprised: ['talk_surprised', 'shrug', 'talk_explain'],
    neutral:   ['talk_explain', 'nod', 'talk_smug', 'confident', 'shrug']
};

let speakingPoseIndex = 0;
let speakingPoseCycleTimer = 0;
const SPEAKING_POSE_INTERVAL = 1.65; // Switch speaking pose every 1.65s

function getNextSpeakingPoseForEmotion(emotion) {
    const key = (emotion || currentEmotion || 'neutral').toLowerCase();
    const pool = EMOTION_SPEAKING_POSE_POOLS[key] || EMOTION_SPEAKING_POSE_POOLS.neutral;
    const pose = pool[speakingPoseIndex % pool.length];
    speakingPoseIndex = (speakingPoseIndex + 1) % pool.length;
    return pose;
}

function isSpecialTrickPose(pose) {
    return ['backflip', 'dance_shikano', 'hug_attempt', 'walk'].includes(pose);
}

const EXPRESSION_ALIASES = {
    surprised: ['surprised', 'Surprised'],
    happy: ['happy', 'joy', 'Joy'],
    joy: ['happy', 'joy', 'Joy'],
    relaxed: ['relaxed', 'fun', 'Fun'],
    fun: ['relaxed', 'fun', 'Fun'],
    sad: ['sad', 'sorrow', 'Sorrow'],
    sorrow: ['sad', 'sorrow', 'Sorrow'],
    angry: ['angry', 'Angry'],
    neutral: ['neutral', 'Neutral']
};

function resolveExpressionName(requested) {
    if (!currentVrm || !currentVrm.expressionManager) return requested;
    const candidates = EXPRESSION_ALIASES[(requested || '').toLowerCase()] || [requested];
    for (const c of candidates) {
        const match = availableExpressions.find(e => e === c || e.toLowerCase() === c.toLowerCase());
        if (match) return match;
    }
    return requested;
}

function setExpressionSmart(name, weight = 1.0) {
    if (!currentVrm || !currentVrm.expressionManager) return;
    const actualName = resolveExpressionName(name);
    try {
        currentVrm.expressionManager.setValue(actualName, THREE.MathUtils.clamp(weight, 0, 1));
    } catch (e) {}
}

function resetExpressions(keepBlinkAndMouth = false) {
    if (!currentVrm || !currentVrm.expressionManager) return;
    const exp = currentVrm.expressionManager;
    availableExpressions.forEach(name => {
        if (keepBlinkAndMouth && ['blink', 'aa', 'ih', 'ou', 'ee', 'oh'].includes(name)) return;
        try { exp.setValue(name, 0); } catch (e) {}
    });
    highlightPresetButton(null);
}

function applyExpressionState(expressionName, weight = 0.75, blendshapeWeights = null) {
    resetExpressions(true);
    currentEmotion = (expressionName || 'neutral').toLowerCase();

    if (blendshapeWeights && typeof blendshapeWeights === 'object' && Object.keys(blendshapeWeights).length > 0) {
        Object.entries(blendshapeWeights).forEach(([k, v]) => {
            setExpressionSmart(k, Number(v) || 0);
        });
        highlightPresetButton(resolveExpressionName(Object.keys(blendshapeWeights)[0]));
    } else if (currentEmotion === 'smug') {
        setExpressionSmart('relaxed', 0.65);
        setExpressionSmart('happy', 0.25);
        setExpressionSmart('blinkLeft', 0.25);
        highlightPresetButton(resolveExpressionName('relaxed'));
    } else if (currentEmotion !== 'neutral') {
        setExpressionSmart(currentEmotion, weight);
        highlightPresetButton(resolveExpressionName(currentEmotion));
    }
}

function readAndRenderPresets(vrm) {
    const presetContainer = document.getElementById('preset-controls');
    const presetButtons = document.getElementById('preset-buttons');
    if (!presetContainer || !presetButtons) return;

    presetButtons.innerHTML = '';
    availableExpressions = [];

    if (!vrm.expressionManager) {
        presetContainer.style.display = 'none';
        return;
    }

    const expressions = vrm.expressionManager.expressions || [];
    expressions.forEach((expr) => {
        const name = expr.expressionName;
        if (['lookUp', 'lookDown', 'lookLeft', 'lookRight'].includes(name)) return;
        availableExpressions.push(name);

        const btn = document.createElement('button');
        btn.innerText = name;
        btn.onclick = () => {
            resetExpressions();
            setExpressionSmart(name, 1.0);
            highlightPresetButton(name);
            // If an emotion expression was clicked, update currentEmotion and preview its speaking pose if speaking
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

    presetContainer.style.display = availableExpressions.length > 0 ? 'flex' : 'none';
}

function highlightPresetButton(activeName) {
    document.querySelectorAll('#preset-buttons button').forEach(b => {
        b.classList.toggle('active', b.innerText.toLowerCase() === (activeName || '').toLowerCase());
    });
}

function highlightPoseButton(poseName) {
    document.querySelectorAll('#pose-buttons button').forEach(b => {
        b.classList.toggle('active', b.getAttribute('data-pose') === poseName);
    });
}

function highlightNavButton(navName) {
    document.querySelectorAll('#nav-buttons button').forEach(b => {
        b.classList.toggle('active', b.getAttribute('data-nav') === navName);
    });
}

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
        controls.target.set(headPos.x, headPos.y - 0.16, headPos.z);
        camera.position.set(headPos.x, headPos.y - 0.05, headPos.z + 1.45);
        controls.update();
    }
}

function setPose(poseName, autoReturnMs = 0) {
    const cleanPose = poseName || 'idle';
    if (animManager) {
        animManager.play(cleanPose, 0.4, cleanPose !== 'backflip');
    } else {
        currentPose = cleanPose;
        highlightPoseButton(cleanPose);
    }

    if (cleanPose === 'backflip') {
        backflipStartTime = clock.getElapsedTime();
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

function startSimulatedLipSync(durationMs = 6500) {
    if (simLipSyncTimer) clearInterval(simLipSyncTimer);
    let elapsed = 0;
    let step = 0;
    const vowels = ['aa', 'ih', 'ou', 'ee', 'oh'];
    simLipSyncTimer = setInterval(() => {
        if (!currentVrm || !currentVrm.expressionManager || (audioLipSync && audioLipSync.isPlaying)) return;
        vowels.forEach(v => setExpressionSmart(v, 0));
        const v = vowels[step % vowels.length];
        const val = Math.sin(step * 0.85) * 0.38 + 0.45;
        setExpressionSmart(v, val);
        step++;
        elapsed += 85;
        if (elapsed >= durationMs) {
            clearInterval(simLipSyncTimer);
            simLipSyncTimer = null;
            vowels.forEach(vw => setExpressionSmart(vw, 0));
            if (currentState === 'speaking') {
                setTestState('idle', 'idle');
            }
        }
    }, 85);
}

const RIKO_EMOTION_VOICE_LINES = {
    happy: [
        "Hehe! Look at me go! If you want an encore, that'll be fifty thousand Zeni!",
        "Yay! See how awesome I am? You're lucky to have me around!"
    ],
    joy: [
        "Hehe! Look at me go! If you want an encore, that'll be fifty thousand Zeni!"
    ],
    relaxed: [
        "Hmph, obviously I'm the smartest companion here. Try to keep up with me!",
        "Everything is under control. Well, for a small fee of twenty thousand Zeni, of course."
    ],
    fun: [
        "Hmph, obviously I'm the smartest companion here. Try to keep up with me!"
    ],
    smug: [
        "Oh? You want my help again? That'll cost you one hundred thousand Zeni up front!",
        "Hehe, you really can't do anything without me, can you?"
    ],
    angry: [
        "Hey! Watch where you're clicking! Do you have any idea how expensive my time is?!",
        "Excuse me?! Don't test my patience unless you brought a mountain of Zeni!"
    ],
    sad: [
        "Ugh... nobody appreciates how hard I work around here... maybe a little snack would cheer me up.",
        "Sigh... my Zeni wallet is feeling so light today..."
    ],
    sorrow: [
        "Ugh... nobody appreciates how hard I work around here..."
    ],
    surprised: [
        "W-wait, seriously?! You actually expect me to do that right now without paying first?!",
        "Whoa! Don't sneak up on me like that, you startled me!"
    ],
    neutral: [
        "Alright, listen closely! I'm only going to explain this once, so pay attention!",
        "Here's the deal: you ask nicely, pay the Zeni, and maybe I'll help you out."
    ]
};

let voiceLineCounter = 0;

function getVoiceLineForEmotion(emotion) {
    const key = (emotion || currentEmotion || 'neutral').toLowerCase();
    const lines = RIKO_EMOTION_VOICE_LINES[key] || RIKO_EMOTION_VOICE_LINES.neutral;
    const line = lines[voiceLineCounter % lines.length];
    voiceLineCounter++;
    return line;
}

// Unlock AudioContext on first user interaction anywhere in the document
['pointerdown', 'touchstart', 'click', 'keydown'].forEach((evt) => {
    window.addEventListener(evt, () => {
        if (audioLipSync) audioLipSync.ensureContext();
    }, { passive: true });
});

const STATIC_EMOTION_MP3_MAP = {
    happy: 'models/voices/happy.mp3',
    joy: 'models/voices/happy.mp3',
    relaxed: 'models/voices/relaxed.mp3',
    fun: 'models/voices/relaxed.mp3',
    smug: 'models/voices/smug.mp3',
    angry: 'models/voices/angry.mp3',
    sad: 'models/voices/sad.mp3',
    sorrow: 'models/voices/sad.mp3',
    surprised: 'models/voices/surprised.mp3',
    neutral: 'models/voices/neutral.mp3'
};

async function speakRikoVoiceLine(customText = null, emotion = null, initialPose = null) {
    const targetEmotion = (emotion || currentEmotion || 'relaxed').toLowerCase();
    currentEmotion = targetEmotion;
    currentState = 'speaking';
    speakingPoseCycleTimer = 0;

    const firstPose = initialPose || getNextSpeakingPoseForEmotion(targetEmotion);
    setPose(firstPose);
    applyExpressionState(targetEmotion, 0.85);

    const text = customText || getVoiceLineForEmotion(targetEmotion);
    updateStatus(`🔊 Riko Speaking [${targetEmotion} | ${selectedVoiceId}]: "${text}"`);

    if (!audioLipSync) return;
    audioLipSync.ensureContext();

    // Instant 0ms synchronous playback for default Riko voice using pre-baked MP3s
    const staticMp3 = STATIC_EMOTION_MP3_MAP[targetEmotion] || STATIC_EMOTION_MP3_MAP.neutral;
    if (!customText && selectedVoiceId === 'af_heart' && staticMp3) {
        await audioLipSync.playStaticMp3Sync(staticMp3, text);
        if (currentState === 'speaking' && (!audioLipSync || !audioLipSync.isPlaying)) {
            currentState = 'idle';
            setPose('idle');
            updateStatus(`State: Idle | Pose: idle`);
        }
        return;
    }

    try {
        const resp = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text,
                voice: selectedVoiceId,
                emotion: targetEmotion
            })
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        await audioLipSync.playBase64Wav(
            data.audio_b64,
            text,
            data.rms,
            data.visemes,
            data.duration,
            data.mime_type || 'audio/mpeg'
        );
    } catch (err) {
        console.warn('TTS API fallback to static MP3 / browser voice:', err);
        await audioLipSync.playStaticMp3Sync(staticMp3, text);
    }

    if (currentState === 'speaking' && (!audioLipSync || !audioLipSync.isPlaying)) {
        currentState = 'idle';
        setPose('idle');
        updateStatus(`State: Idle | Pose: idle`);
    }
}
window.speakRikoVoiceLine = speakRikoVoiceLine;

function setTestState(state, customPose = null, triggerVoice = false) {
    currentState = state;
    if (simLipSyncTimer && state !== 'speaking') {
        clearInterval(simLipSyncTimer);
        simLipSyncTimer = null;
    }
    if (state !== 'speaking' && audioLipSync) {
        audioLipSync.stopCurrent();
    }

    if (state === 'idle') {
        setPose(customPose || 'idle');
        applyExpressionState(currentEmotion, 0.45);
        updateStatus(`State: Idle | Pose: ${currentPose}`);
    } else if (state === 'listening') {
        // Dedicated Listening Pose (hand cupped near ear, leaning in attentively)
        applyExpressionState('surprised', 0.55);
        setPose(customPose || 'listen_pose');
        updateStatus(`State: Listening... | Pose: ${currentPose}`);
    } else if (state === 'thinking') {
        // Dedicated Thinking Pose (finger on chin, left hand cupping elbow)
        applyExpressionState('relaxed', 0.75, { relaxed: 0.75, oh: 0.2 });
        setPose(customPose || 'think_pose');
        updateStatus(`State: Riko is Thinking... | Pose: ${currentPose}`);
    } else if (state === 'speaking') {
        // Multi-pose emotion-driven speaking state with real voice!
        speakingPoseCycleTimer = 0;
        const firstSpeakPose = customPose || getNextSpeakingPoseForEmotion(currentEmotion);
        setPose(firstSpeakPose);
        applyExpressionState(currentEmotion, 0.8);
        if (triggerVoice) {
            speakRikoVoiceLine(null, currentEmotion, firstSpeakPose);
        } else if (!audioLipSync || !audioLipSync.isPlaying) {
            startSimulatedLipSync(6600);
        }
        updateStatus(`State: Speaking [${currentEmotion}] | Cycling Pose: ${currentPose}`);
    }
}
window.setTestState = setTestState;

// ----------------------------------------------------
// FILE IMPORT & UI BUTTON LISTENERS
// ----------------------------------------------------
const fileInput = document.getElementById('vrm-file-input');
if (fileInput) {
    fileInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (!file) return;
        updateStatus(`Reading ${file.name}...`);
        loadVRM(URL.createObjectURL(file), true);
    });
}

const fbxInput = document.getElementById('fbx-file-input');
if (fbxInput) {
    fbxInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (!file || !currentVrm || !animManager) return;
        updateStatus(`Retargeting Mixamo FBX: ${file.name}...`);
        const blobUrl = URL.createObjectURL(file);
        fbxLoader.load(
            blobUrl,
            (fbxAsset) => {
                const clipName = file.name.replace(/\.fbx$/i, '');
                const clip = extractMixamoFBXClip(fbxAsset, currentVrm, clipName);
                if (clip) {
                    animManager.registerClip(clipName, clip);
                    animManager.play(clipName, 0.4, true);
                    updateStatus(`Playing Retargeted Mixamo FBX: ${clipName}`);
                } else {
                    updateStatus(`Could not find Mixamo tracks in ${file.name}`);
                }
                URL.revokeObjectURL(blobUrl);
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
        speakRikoVoiceLine(null, currentEmotion);
    });
}

const btnTestVoice = document.getElementById('btn-test-voice');
if (btnTestVoice) {
    btnTestVoice.onclick = () => {
        speakingPoseIndex = 0;
        speakRikoVoiceLine(null, currentEmotion);
    };
}

const btnMuteVoice = document.getElementById('btn-mute-voice');
if (btnMuteVoice) {
    btnMuteVoice.onclick = () => {
        voiceMuted = !voiceMuted;
        btnMuteVoice.classList.toggle('active', !voiceMuted);
        btnMuteVoice.innerText = voiceMuted ? '🔇 Voice: OFF' : '🔊 Voice: ON';
        if (voiceMuted && audioLipSync) {
            audioLipSync.stopCurrent();
        }
    };
}

// HELIOS Add-On Bridge Controls
const heliosStatusPill = document.getElementById('helios-status-pill');
const brainModeSelect = document.getElementById('brain-mode-select');
const btnMirrorHelios = document.getElementById('btn-mirror-helios');
let selectedBrainMode = 'auto';
let mirrorHeliosEvents = true;

function applyHeliosAddonStatus(status) {
    if (!status) return;
    if (status.mode) {
        selectedBrainMode = status.mode;
        if (brainModeSelect) brainModeSelect.value = status.mode;
    }
    if (typeof status.mirror_events === 'boolean') {
        mirrorHeliosEvents = status.mirror_events;
        if (btnMirrorHelios) {
            btnMirrorHelios.classList.toggle('active', mirrorHeliosEvents);
            btnMirrorHelios.innerText = mirrorHeliosEvents ? '🔄 Mirror: ON' : '⏸️ Mirror: OFF';
        }
    }
    if (heliosStatusPill) {
        if (status.connected) {
            heliosStatusPill.className = 'addon-pill online';
            heliosStatusPill.innerText = status.mode === 'standalone'
                ? '🟢 HELIOS Online (Standalone Mode)'
                : '🟢 HELIOS Core (:8000) Connected';
        } else {
            heliosStatusPill.className = 'addon-pill offline';
            heliosStatusPill.innerText = '🟡 Standalone (:8000 Offline)';
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
        selectedBrainMode = brainModeSelect.value || 'auto';
        syncHeliosConfig({ mode: selectedBrainMode });
    });
}

if (btnMirrorHelios) {
    btnMirrorHelios.onclick = () => {
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

document.querySelectorAll('#pose-buttons button').forEach(btn => {
    btn.onclick = () => {
        const p = btn.getAttribute('data-pose');
        setPose(p);
        if (p === 'talk_explain') {
            speakRikoVoiceLine(null, 'neutral', 'talk_explain');
        } else if (p === 'talk_excited') {
            speakRikoVoiceLine(null, 'happy', 'talk_excited');
        } else if (p === 'talk_smug') {
            speakRikoVoiceLine(null, 'smug', 'talk_smug');
        } else if (p === 'talk_angry') {
            speakRikoVoiceLine(null, 'angry', 'talk_angry');
        } else if (p === 'talk_sad') {
            speakRikoVoiceLine(null, 'sad', 'talk_sad');
        } else if (p === 'talk_surprised') {
            speakRikoVoiceLine(null, 'surprised', 'talk_surprised');
        } else if (p === 'smug_pose') {
            applyExpressionState('smug');
            updateStatus(`Pose: ${p} | State: ${currentState}`);
        } else {
            updateStatus(`Pose: ${p} | State: ${currentState}`);
        }
    };
});

// ----------------------------------------------------
// MAIN RENDER LOOP (Phases 2, 3, 4, 5 + Multi-Pose Speaking Cycle)
// ----------------------------------------------------
const clock = new THREE.Clock();

function animate() {
    requestAnimationFrame(animate);

    const delta = Math.min(clock.getDelta(), 0.1);
    const elapsed = clock.getElapsedTime();

    if (currentVrm && currentVrm.humanoid) {
        const speed = Math.min(1.0, delta * 7.5);

        // Multi-pose emotion-driven cycling during Speaking state
        if (currentState === 'speaking' && (!navController || !navController.isNavigating) && !isSpecialTrickPose(currentPose)) {
            speakingPoseCycleTimer += delta;
            if (speakingPoseCycleTimer >= SPEAKING_POSE_INTERVAL) {
                speakingPoseCycleTimer = 0;
                const nextSpeakPose = getNextSpeakingPoseForEmotion(currentEmotion);
                setPose(nextSpeakPose);
                updateStatus(`State: Speaking [${currentEmotion}] | Pose: ${nextSpeakPose}`);
            }
        }

        // Phase 4: Spatial Navigation ("Come to Me")
        if (navController) {
            navController.update(delta, camera);
        }

        // Phase 3: Smooth 2-Bone IK Pose Engine (or external FBX mixer if active)
        if (animManager && animManager.usingExternalFBX) {
            animManager.update(delta);
        } else {
            applyProceduralPose(elapsed, speed);
        }

        // Phase 2: Procedural Humanization (Blinking & subtle eye saccades)
        if (humanizer) {
            humanizer.update(delta);
        }

        // Phase 5: Web Audio API FFT + RMS Lip-Sync
        if (audioLipSync) {
            audioLipSync.update();
        }

        // Update VRM internal SpringBone physics & expressions
        currentVrm.update(delta);
    }

    controls.update();
    renderer.render(scene, camera);
}

window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

// ----------------------------------------------------
// WEBSOCKET (/ws/chat) STREAMING SEQUENCE & VOICE INPUT
// ----------------------------------------------------
const chatLog = document.getElementById('chat-log');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const chatMic = document.getElementById('chat-mic');
let ws = null;
let currentChatBubble = null;
let ttsPlaybackQueue = Promise.resolve();

function appendToChat(text, isUser = false, metaTag = '') {
    if (!chatLog) return;
    chatLog.style.display = 'block';
    if (isUser || !currentChatBubble) {
        currentChatBubble = document.createElement('div');
        currentChatBubble.style.marginBottom = '8px';
        const badge = metaTag ? ` <small style="color:#38bdf8;font-weight:600;">[${metaTag}]</small>` : '';
        currentChatBubble.innerHTML = `<strong>${isUser ? 'You' : 'Riko'}${badge}:</strong> <span class="msg-text"></span>`;
        currentChatBubble.style.color = isUser ? '#38bdf8' : '#e2e8f0';
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
    const wsHost = window.location.host || 'localhost:8080';
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    ws = new WebSocket(protocol + wsHost + '/ws/chat');

    ws.onopen = () => {
        console.log('Connected to Riko WebSocket (/ws/chat)');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'helios_status') {
            applyHeliosAddonStatus(data);
            return;
        }

        if (data.type === 'helios_thought') {
            if (data.thought) updateThoughtBanner(data.thought);
            return;
        }

        if (data.type === 'agent_sequence') {
            if (data.thought) {
                updateThoughtBanner(data.thought);
            }
            const seq = Array.isArray(data.sequence) ? data.sequence : [];
            const navStep = seq.find(s => s.action_type === 'navigate' || (s.movement && s.movement !== 'idle'));
            const speakStep = seq.find(s => s.action_type === 'speak' || s.dialogue) || seq[0] || {};

            const moveCmd = navStep ? (navStep.movement || navStep.action || 'idle') : 'idle';
            const targetExpr = speakStep.expression || speakStep.emotion || 'neutral';
            const targetWeight = speakStep.expression_weight ?? 0.75;
            speakingPoseIndex = 0;

            let targetAnim = speakStep.animation || 'idle';
            if (targetAnim === 'idle' || targetAnim === 'smug_pose') {
                targetAnim = getNextSpeakingPoseForEmotion(targetExpr);
            }

            applyExpressionState(targetExpr, targetWeight, speakStep.blendshape_weights);

            if (moveCmd && moveCmd !== 'idle' && moveCmd !== 'stay' && navController) {
                navController.executeMovement(moveCmd, camera, targetAnim);
            } else {
                setPose(targetAnim);
            }

            const tagParts = [targetExpr, targetAnim];
            if (moveCmd && moveCmd !== 'idle' && moveCmd !== 'stay') {
                tagParts.unshift(moveCmd);
            }
            if (data.source === 'helios') {
                tagParts.unshift('HELIOS');
            }
            currentChatBubble = null;
            appendToChat('', false, tagParts.join(' | '));
            updateStatus(`Riko -> ${tagParts.join(' | ')}`);

        } else if (data.type === 'tts_chunk') {
            ttsPlaybackQueue = ttsPlaybackQueue.then(async () => {
                currentState = 'speaking';
                speakingPoseCycleTimer = 0;
                const expr = data.expression || data.emotion || 'neutral';
                const weight = data.expression_weight ?? 0.75;
                applyExpressionState(expr, weight, data.blendshape_weights);

                // Pick a varied emotion-based pose for each clause unless performing a special trick
                const requestedAnim = data.animation || 'idle';
                const clausePose = isSpecialTrickPose(requestedAnim)
                    ? requestedAnim
                    : (data.clause_index === 0 && !['idle', 'smug_pose'].includes(requestedAnim)
                        ? requestedAnim
                        : getNextSpeakingPoseForEmotion(expr));

                if (navController && navController.isNavigating) {
                    navController.arrivalAnim = clausePose;
                } else {
                    setPose(clausePose);
                }

                if (data.text && !data.is_voice_preview) {
                    appendToChat((data.clause_index > 0 ? ' ' : '') + data.text, false);
                }

                if (audioLipSync) {
                    await audioLipSync.playBase64Wav(
                        data.audio_b64,
                        data.text || data.dialogue || '',
                        data.rms,
                        data.visemes,
                        data.duration,
                        data.mime_type || 'audio/mpeg'
                    );
                }
            });

        } else if (data.type === 'state_change') {
            setTestState(data.state, data.pose || null);

        } else if (data.type === 'chat_done') {
            ttsPlaybackQueue = ttsPlaybackQueue.then(() => {
                currentChatBubble = null;
                currentState = 'idle';
                if (audioLipSync) audioLipSync.clearVisemes();
                if ((!navController || !navController.isNavigating) && currentPose !== 'idle') {
                    setPose(currentPose, 3200);
                }
            });
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
    appendToChat(text, true);
    ws.send(JSON.stringify({
        type: 'chat_message',
        text,
        voice: selectedVoiceId,
        brain_mode: selectedBrainMode
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

// Initialize default model, render loop & AI connection
loadVRM(DEFAULT_VRM_URL);
animate();
connectAI();
