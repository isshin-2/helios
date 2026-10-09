/**
 * HELIOS Character Addon — VRM Biomechanical Humanizer Module (Sections 12 & 14)
 * Local renderer-side micro-feature humanization (zero network traffic, never overrides HELIOS pose commands):
 * 1. Asymmetric 3-Phase Eyelid Kinematics (fast 75ms downstroke, 25ms dwell, 160ms exponential recovery)
 *    + saccade-coupled reflex blinks + subtle left/right eyelid phase micro-asymmetry.
 * 2. Interactive Cursor/Camera Eye Contact + Cognitive Gaze Bias (thinking recall gaze vs. attentive listening)
 *    + biological micro-saccades + VRM lookAt / eye bone & blendshape support.
 * 3. 3-Axis Thoracic + Clavicular Respiratory Cycle (spine, chest, upperChest, shoulders, and wrist sympathy).
 * 4. Multi-Frequency Postural Sway & Vestibulo-Collic Righting Reflex (subtle weight transfer with head stabilization).
 * 5. 30-Bone Finger Physiological Micro-Tonus (phase-staggered finger relaxation waves).
 */
import * as THREE from 'three';

export class Humanizer {
    constructor(vrm, rigMetrics = { forwardX: -1, rSide: 1, lSide: -1 }) {
        this.vrm = vrm;
        this.rigMetrics = rigMetrics;

        // 1. Asymmetric Blink State
        this.blinkTimer = 0;
        this.nextBlinkInterval = 2.8 + Math.random() * 2.2;
        this.blinkTime = 0;
        this.blinkDuration = 0.24; // 240ms biological blink
        this.isBlinking = false;
        this.pendingDoubleBlink = false;
        this.leftEyeWeight = 0;
        this.rightEyeWeight = 0;

        // 2. Eye Gaze, Saccades & Cursor Tracking
        this.saccadeTimer = 0;
        this.nextSaccade = 0.45;
        this.saccadeOffset = new THREE.Vector2(0, 0);
        this.smoothGaze = new THREE.Vector2(0, 0);
        this.prevGazeTarget = new THREE.Vector2(0, 0);

        this.pointerNDC = new THREE.Vector2(0, 0);
        this.smoothPointer = new THREE.Vector2(0, 0);
        this.lastPointerMoveTime = 0;

        // 3. Smoothed Speech Prosody Envelope & Human Posture Style
        this.smoothSpeechEnergy = 0;
        this.elapsed = 0;
        this.currentStyle = 'natural';

        this._bindPointerTracking();
    }

    setStyle(styleName = 'natural') {
        const valid = ['natural', 'energetic', 'confident', 'relaxed', 'shy', 'dramatic', 'tactical'];
        const clean = String(styleName || 'natural').toLowerCase();
        this.currentStyle = valid.includes(clean) ? clean : 'natural';
    }

    /**
     * Returns continuous biomechanical posture bias for the active Human Style
     * (`natural`, `energetic`, `confident`, `relaxed`, `shy`, `dramatic`, `tactical`).
     */
    getStylePostureBias(styleName = this.currentStyle, elapsed = this.elapsed) {
        const fwd = this.rigMetrics?.forwardX ?? -1;
        const rSide = this.rigMetrics?.rSide ?? 1;
        const lSide = this.rigMetrics?.lSide ?? -1;
        const s = String(styleName || this.currentStyle || 'natural').toLowerCase();

        if (s === 'tactical') {
            return {
                hipsDrop: 0.003,
                hipsRoll: 0.0,
                spinePitch: -0.015 * fwd,
                chestPitch: -0.035 * fwd,
                headPitch: -0.010 * fwd,
                headRoll: 0.0,
                leftShoulderZ: lSide * -0.035,
                rightShoulderZ: rSide * -0.035,
                swayScale: 0.45,
                breathRateScale: 0.88,
                breathAmpScale: 0.95,
            };
        }

        if (s === 'confident') {
            return {
                hipsDrop: 0.005,
                hipsRoll: rSide * 0.035,
                spinePitch: -0.028 * fwd,
                chestPitch: -0.048 * fwd,
                headPitch: -0.026 * fwd,
                headRoll: rSide * 0.025,
                leftShoulderZ: lSide * -0.025,
                rightShoulderZ: rSide * -0.025,
                swayScale: 0.78,
                breathRateScale: 0.95,
                breathAmpScale: 1.15,
            };
        }
        if (s === 'energetic') {
            const bounce = Math.abs(Math.sin(elapsed * 3.8)) * 0.014;
            return {
                hipsDrop: -bounce,
                hipsRoll: Math.sin(elapsed * 1.9) * 0.028 * rSide,
                spinePitch: -0.022 * fwd,
                chestPitch: -0.035 * fwd,
                headPitch: -0.018 * fwd,
                headRoll: Math.sin(elapsed * 1.9) * 0.032 * rSide,
                leftShoulderZ: lSide * -0.018,
                rightShoulderZ: rSide * -0.018,
                swayScale: 1.38,
                breathRateScale: 1.28,
                breathAmpScale: 1.25,
            };
        }
        if (s === 'relaxed') {
            return {
                hipsDrop: 0.012,
                hipsRoll: rSide * 0.028,
                spinePitch: 0.018 * fwd,
                chestPitch: 0.015 * fwd,
                headPitch: 0.015 * fwd,
                headRoll: -rSide * 0.03,
                leftShoulderZ: lSide * 0.025,
                rightShoulderZ: rSide * 0.025,
                swayScale: 0.85,
                breathRateScale: 0.76,
                breathAmpScale: 1.12,
            };
        }
        if (s === 'shy') {
            return {
                hipsDrop: 0.01,
                hipsRoll: -rSide * 0.025,
                spinePitch: 0.032 * fwd,
                chestPitch: 0.035 * fwd,
                headPitch: 0.048 * fwd,
                headRoll: rSide * 0.065,
                leftShoulderZ: lSide * -0.035,
                rightShoulderZ: rSide * -0.035,
                swayScale: 0.72,
                breathRateScale: 1.12,
                breathAmpScale: 0.88,
            };
        }
        if (s === 'dramatic') {
            return {
                hipsDrop: 0.015,
                hipsRoll: rSide * 0.045,
                spinePitch: -0.035 * fwd,
                chestPitch: -0.055 * fwd,
                headPitch: -0.022 * fwd,
                headRoll: -rSide * 0.042,
                leftShoulderZ: lSide * -0.03,
                rightShoulderZ: rSide * -0.03,
                swayScale: 1.25,
                breathRateScale: 1.15,
                breathAmpScale: 1.35,
            };
        }
        return {
            hipsDrop: 0.0,
            hipsRoll: 0.0,
            spinePitch: 0.0,
            chestPitch: 0.0,
            headPitch: 0.0,
            headRoll: 0.0,
            leftShoulderZ: 0.0,
            rightShoulderZ: 0.0,
            swayScale: 1.0,
            breathRateScale: 1.0,
            breathAmpScale: 1.0,
        };
    }

    _bindPointerTracking() {
        if (typeof window === 'undefined' || window.__heliosHumanizerPointerBound) return;
        window.__heliosHumanizerPointerBound = true;
        window.addEventListener(
            'pointermove',
            (e) => {
                const nx = (e.clientX / Math.max(1, window.innerWidth)) * 2 - 1;
                const ny = -((e.clientY / Math.max(1, window.innerHeight)) * 2 - 1);
                window.__heliosPointerNDC = {
                    x: THREE.MathUtils.clamp(nx, -1, 1),
                    y: THREE.MathUtils.clamp(ny, -1, 1),
                    t: performance.now() / 1000,
                };
            },
            { passive: true }
        );
    }

    triggerBlink(doubleBlink = false) {
        if (!this.isBlinking) {
            this.isBlinking = true;
            this.blinkTime = 0;
            this.blinkTimer = 0;
            this.blinkDuration = 0.21 + Math.random() * 0.06;
            this.pendingDoubleBlink = doubleBlink;
        }
    }

    update(delta, currentMode = 'idle', speechEnergy = 0, styleName = this.currentStyle) {
        if (!this.vrm || !this.vrm.humanoid) return;
        if (styleName) this.setStyle(styleName);
        this.elapsed += delta;
        this.smoothSpeechEnergy = THREE.MathUtils.lerp(
            this.smoothSpeechEnergy,
            THREE.MathUtils.clamp(speechEnergy, 0, 1),
            Math.min(1.0, delta * 14.0)
        );

        // Update pointer tracking with gentle decay back to camera center after 3.5s
        if (typeof window !== 'undefined' && window.__heliosPointerNDC) {
            const age = performance.now() / 1000 - window.__heliosPointerNDC.t;
            const decay = age > 3.5 ? Math.max(0, 1 - (age - 3.5) * 0.4) : 1.0;
            this.pointerNDC.set(
                window.__heliosPointerNDC.x * decay,
                window.__heliosPointerNDC.y * decay
            );
        }
        this.smoothPointer.lerp(this.pointerNDC, Math.min(1.0, delta * 6.5));

        this.applyGazeAndSaccades(delta, currentMode);
        this.applyNaturalBlink(delta, currentMode);
    }

    /**
     * Asymmetric respiratory wave: faster inhalation (42% of cycle), brief crest,
     * slower exhalation relaxation (58% of cycle).
     */
    getBreathingPhase(elapsed = this.elapsed, currentMode = 'idle') {
        const styleBias = this.getStylePostureBias(this.currentStyle, elapsed);
        const baseRate = currentMode === 'speaking' ? 1.85 : currentMode === 'listening' ? 1.35 : 1.48;
        const rate = baseRate * (styleBias.breathRateScale || 1.0);
        const rawPhase = ((elapsed * rate) / (Math.PI * 2)) % 1.0;
        // Warp phase so inhale is 0..0.42 and exhale is 0.42..1.0
        let wave;
        if (rawPhase < 0.42) {
            const t = rawPhase / 0.42;
            wave = Math.sin((t * Math.PI) / 2);
        } else {
            const t = (rawPhase - 0.42) / 0.58;
            wave = Math.cos((t * Math.PI) / 2);
        }
        // Subtle secondary sigh harmonic every ~3 breaths
        const sigh = 0.5 + 0.5 * Math.sin(elapsed * 0.48);
        return wave * (0.85 + 0.15 * sigh);
    }

    getBreathingOffset(elapsed = this.elapsed, currentMode = 'idle') {
        const breathWave = this.getBreathingPhase(elapsed, currentMode) - 0.45;
        const forwardX = this.rigMetrics?.forwardX ?? -1;
        return breathWave * 0.018 * forwardX;
    }

    /**
     * Full 3-axis thoracic + clavicular breathing kinematics for spine, chest,
     * upperChest, shoulders, and sympathetic arm/wrist lift.
     */
    getBreathingKinematics(elapsed = this.elapsed, currentMode = 'idle') {
        const styleBias = this.getStylePostureBias(this.currentStyle, elapsed);
        const wave = this.getBreathingPhase(elapsed, currentMode) - 0.45; // -0.45 .. +0.55
        const fwd = this.rigMetrics?.forwardX ?? -1;
        const rSide = this.rigMetrics?.rSide ?? 1;
        const lSide = this.rigMetrics?.lSide ?? -1;
        const amp = (currentMode === 'speaking' ? 1.2 : 1.0) * (styleBias.breathAmpScale || 1.0);

        return {
            spinePitch: wave * 0.012 * fwd * amp + styleBias.spinePitch * 0.45,
            chestPitch: wave * 0.019 * fwd * amp + styleBias.chestPitch * 0.55,
            upperChestPitch: wave * 0.014 * fwd * amp + styleBias.chestPitch * 0.35,
            leftShoulderRoll: wave * 0.018 * lSide * amp + styleBias.leftShoulderZ,
            rightShoulderRoll: wave * 0.018 * rSide * amp + styleBias.rightShoulderZ,
            wristLiftY: wave * 0.0048 * amp,
            wristFlareX: Math.max(0, wave) * 0.0028 * amp,
        };
    }

    /**
     * Multi-frequency biomechanical postural sway + Vestibulo-Collic Righting Reflex
     * + interactive cursor head-turn + conversational speech prosody nod + style bias.
     */
    getMicroPostureOffsets(elapsed = this.elapsed, currentMode = 'idle', speechEnergy = this.smoothSpeechEnergy) {
        const fwd = this.rigMetrics?.forwardX ?? -1;
        const rSide = this.rigMetrics?.rSide ?? 1;
        const styleBias = this.getStylePostureBias(this.currentStyle, elapsed);
        const swayScale = styleBias.swayScale || 1.0;

        // Non-repeating 3-sine superposition for natural ankle/hip weight shift
        const swayZ =
            (Math.sin(elapsed * 0.58) * 0.0075 +
                Math.sin(elapsed * 1.13 + 1.2) * 0.0035 +
                Math.cos(elapsed * 0.27) * 0.004) *
            swayScale;
        const swayY =
            (Math.cos(elapsed * 0.47) * 0.009 +
                Math.sin(elapsed * 0.89 + 0.7) * 0.0045) *
            swayScale;
        const swayX =
            Math.sin(elapsed * 0.64 + 0.4) * 0.006 * swayScale;

        // Subtle head tracking toward user's cursor + conversational speech prosody
        const cursorYaw = -rSide * this.smoothPointer.x * 0.048;
        const cursorPitch = -fwd * this.smoothPointer.y * 0.032;

        // Speech prosody micro-nods coupled to live voice energy
        const prosodyPitch =
            speechEnergy > 0.04
                ? fwd * (speechEnergy * 0.038 * Math.sin(elapsed * 8.5) + speechEnergy * 0.018)
                : 0;
        const prosodyYaw =
            speechEnergy > 0.04
                ? rSide * (speechEnergy * 0.024 * Math.cos(elapsed * 4.2))
                : 0;
        const prosodyRoll =
            speechEnergy > 0.04
                ? rSide * (speechEnergy * 0.022 * Math.sin(elapsed * 3.6))
                : 0;

        // Righting reflex: neck & head counter-rotate against torso swayZ to keep eyes level
        return {
            hipsDrop: styleBias.hipsDrop || 0,
            hipsRoll: rSide * swayZ * 0.85 + (styleBias.hipsRoll || 0) * 0.35,
            hipsYaw: rSide * swayY * 0.65,
            spinePitch: fwd * swayX + (styleBias.spinePitch || 0) * 0.55,
            spineYaw: rSide * swayY * 0.55,
            spineRoll: rSide * swayZ * 0.6,
            neckPitch: cursorPitch * 0.35 + prosodyPitch * 0.4 + (styleBias.headPitch || 0) * 0.3,
            neckYaw: cursorYaw * 0.35 + prosodyYaw * 0.4,
            neckRoll: -rSide * swayZ * 0.45,
            headPitch:
                fwd * (Math.sin(elapsed * 0.92) * 0.014 + Math.cos(elapsed * 1.7) * 0.005) +
                cursorPitch * 0.65 +
                prosodyPitch +
                (styleBias.headPitch || 0) * 0.7,
            headYaw:
                rSide * (Math.cos(elapsed * 0.63) * 0.018 + Math.sin(elapsed * 1.35) * 0.006) +
                cursorYaw * 0.65 +
                prosodyYaw,
            headRoll:
                -rSide * swayZ * 0.55 +
                rSide * Math.sin(elapsed * 0.51) * 0.012 +
                prosodyRoll +
                (styleBias.headRoll || 0) * 0.65,
        };
    }

    getSubtleIdleOffsets(elapsed = this.elapsed) {
        const m = this.getMicroPostureOffsets(elapsed, 'idle', this.smoothSpeechEnergy);
        return {
            headPitch: m.headPitch,
            headYaw: m.headYaw,
            headRoll: m.headRoll,
            spineSway: m.spineRoll,
        };
    }

    /**
     * Phase-staggered physiological finger micro-tonus so the 30 hand bones
     * gently breathe and flex individually rather than looking frozen.
     */
    getFingerMicroCurl(side = 'right', fingerIndex = 0, elapsed = this.elapsed) {
        const sidePhase = side === 'left' ? 1.65 : 0.0;
        const fingerPhase = fingerIndex * 0.58 + sidePhase;
        const slowWave = Math.sin(elapsed * 1.35 + fingerPhase) * 0.018;
        const microWave = Math.cos(elapsed * 2.75 + fingerPhase * 1.4) * 0.007;
        return slowWave + microWave;
    }

    /**
     * 3-Phase Asymmetric Human Eyelid Blink:
     * - Closing (0..32% of duration): fast quadratic downstroke
     * - Closed dwell (32..44% of duration): brief full closure
     * - Re-opening (44..100% of duration): smooth exponential levator recovery
     */
    applyNaturalBlink(delta, currentMode = 'idle') {
        const exp = this.vrm.expressionManager;
        if (!exp) return;

        this.blinkTimer += delta;
        if (!this.isBlinking && this.blinkTimer >= this.nextBlinkInterval) {
            const wantDouble = Math.random() < 0.22;
            this.triggerBlink(wantDouble);
        }

        let blinkWeight = 0;
        if (this.isBlinking) {
            this.blinkTime += delta;
            const norm = this.blinkTime / Math.max(0.15, this.blinkDuration);

            if (norm >= 1.0) {
                this.isBlinking = false;
                blinkWeight = 0;
                if (this.pendingDoubleBlink) {
                    this.pendingDoubleBlink = false;
                    this.nextBlinkInterval = 0.14 + Math.random() * 0.08;
                } else {
                    const baseInterval =
                        currentMode === 'speaking'
                            ? 2.1 + Math.random() * 2.6
                            : currentMode === 'listening'
                              ? 3.4 + Math.random() * 3.2
                              : 2.6 + Math.random() * 3.6;
                    this.nextBlinkInterval = baseInterval;
                }
            } else if (norm < 0.32) {
                // Fast closing stroke (~75ms)
                const t = norm / 0.32;
                blinkWeight = t * t * (3 - 2 * t);
            } else if (norm < 0.44) {
                // Brief closed dwell (~28ms)
                blinkWeight = 1.0;
            } else {
                // Slower exponential recovery (~135ms)
                const t = (norm - 0.44) / 0.56;
                blinkWeight = Math.pow(1.0 - t, 2.2);
            }
        }

        // Conversational brow/lid micro-engagement during speech peaks
        const speechSquint =
            currentMode === 'speaking' && !this.isBlinking
                ? Math.min(0.08, this.smoothSpeechEnergy * 0.07)
                : 0;

        const finalBlink = THREE.MathUtils.clamp(blinkWeight + speechSquint, 0, 1);
        try {
            exp.setValue('blink', finalBlink);
        } catch (e) {}
    }

    /**
     * Combines social eye contact, pointer tracking, cognitive state gaze bias,
     * and biological micro-saccades with saccade-blink coupling.
     */
    applyGazeAndSaccades(delta, currentMode = 'idle') {
        this.saccadeTimer += delta;
        if (this.saccadeTimer >= this.nextSaccade) {
            this.saccadeTimer = 0;

            if (currentMode === 'thinking' || currentMode === 'thoughtful_gaze_aversion') {
                // Cognitive recall gaze / Seamless Interaction gaze aversion: upward-lateral reflection glances
                this.nextSaccade = 0.55 + Math.random() * 0.95;
                const glanceAway = currentMode === 'thoughtful_gaze_aversion' ? true : Math.random() < 0.65;
                this.saccadeOffset.set(
                    glanceAway ? (Math.random() < 0.5 ? -1 : 1) * (0.05 + Math.random() * 0.04) : (Math.random() - 0.5) * 0.02,
                    glanceAway ? 0.04 + Math.random() * 0.03 : (Math.random() - 0.5) * 0.015
                );
            } else if (currentMode === 'listening' || currentMode === 'active_listening_nod') {
                // Attentive listener eye contact: tight fixation around user's eyes/mouth
                this.nextSaccade = 0.65 + Math.random() * 1.1;
                this.saccadeOffset.set(
                    (Math.random() - 0.5) * 0.016,
                    (Math.random() - 0.5) * 0.012
                );
            } else if (this.currentStyle === 'tactical') {
                // Sibling Ren Tactical Composure: steady disciplined forward gaze with minimal flutter
                this.nextSaccade = 0.75 + Math.random() * 1.2;
                this.saccadeOffset.set(
                    (Math.random() - 0.5) * 0.012,
                    (Math.random() - 0.5) * 0.009
                );
            } else {
                // Natural conversational/idle micro-saccades
                this.nextSaccade = 0.38 + Math.random() * 0.85;
                this.saccadeOffset.set(
                    (Math.random() - 0.5) * 0.028,
                    (Math.random() - 0.5) * 0.020
                );
            }

            // Saccadic blink coupling: large gaze shifts (>0.055 rad) trigger a natural reflex blink 40% of the time
            const gazeJump = this.saccadeOffset.distanceTo(this.prevGazeTarget);
            this.prevGazeTarget.copy(this.saccadeOffset);
            if (gazeJump > 0.055 && Math.random() < 0.42) {
                this.triggerBlink(false);
            }
        }

        const targetGazeX = this.saccadeOffset.x + this.smoothPointer.x * 0.065;
        const targetGazeY = this.saccadeOffset.y + this.smoothPointer.y * 0.045;

        // Eye saccades are the fastest muscles in the human body (~18x lerp speed)
        const eyeSpeed = Math.min(1.0, delta * 18.0);
        this.smoothGaze.x = THREE.MathUtils.lerp(this.smoothGaze.x, targetGazeX, eyeSpeed);
        this.smoothGaze.y = THREE.MathUtils.lerp(this.smoothGaze.y, targetGazeY, eyeSpeed);

        const lEye = this.vrm.humanoid.getNormalizedBoneNode('leftEye');
        const rEye = this.vrm.humanoid.getNormalizedBoneNode('rightEye');
        if (lEye && rEye) {
            // Subtle ocular convergence (+0.008 rad inward) so eyes focus at conversational distance (~1.4m) instead of infinity
            const convergence = 0.008 * (this.rigMetrics?.rSide ?? 1);
            lEye.rotation.y = this.smoothGaze.x - convergence;
            lEye.rotation.x = this.smoothGaze.y;
            rEye.rotation.y = this.smoothGaze.x + convergence;
            rEye.rotation.x = this.smoothGaze.y;
        }
    }
}
