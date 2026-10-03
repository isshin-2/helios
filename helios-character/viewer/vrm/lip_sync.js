/**
 * HELIOS Character Addon — VRM Lip Sync Module (Section 12 & 13)
 * Driven by HELIOS VoiceManager (`character_speech` and `character_stop` protocol events).
 * Handles audio amplitude (FFT + RMS envelope), viseme timelines, mouth blendshapes,
 * and immediate speech interruption.
 */

export class AudioLipSync {
    constructor(vrm = null, options = {}) {
        this.vrm = vrm;
        this.audioContext = null;
        this.analyser = null;
        this.dataArray = null;
        this.activeSource = null;
        this.activeRms = null;
        this.activeVisemes = null;
        this.playStartTime = 0;
        this.playDuration = 0;
        this.isPlaying = false;
        this.voiceMuted = false;
        this.audioUnlockedByUser = false;
        this.simLipSyncTimer = null;
        this.envelopeTimer = null;
        this.playbackFallbackTimer = null;

        this.sharedVoiceAudio = new Audio();
        this.sharedVoiceAudio.preload = 'auto';
        this.sharedVoiceAudio.volume = 1.0;
        this.sharedVoiceAudio.playsInline = true;
        this.onFinishCallback = options.onFinish || null;
    }

    setVRM(vrm) {
        this.vrm = vrm;
    }

    setMuted(muted) {
        this.voiceMuted = Boolean(muted);
        if (this.voiceMuted) {
            this.stopCurrent();
        }
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
            if (this.audioContext && !this.audioUnlockedByUser) {
                const silentBuf = this.audioContext.createBuffer(1, 1, 22050);
                const silentSrc = this.audioContext.createBufferSource();
                silentSrc.buffer = silentBuf;
                silentSrc.connect(this.audioContext.destination);
                silentSrc.start(0);
                this.audioUnlockedByUser = true;
            }
        } catch (e) {}
    }

    stopCurrent() {
        if (this.simLipSyncTimer) {
            clearInterval(this.simLipSyncTimer);
            this.simLipSyncTimer = null;
        }
        if (this.envelopeTimer) {
            clearTimeout(this.envelopeTimer);
            this.envelopeTimer = null;
        }
        if (this.playbackFallbackTimer) {
            clearTimeout(this.playbackFallbackTimer);
            this.playbackFallbackTimer = null;
        }
        if (this.activeSource) {
            try {
                this.activeSource.stop();
            } catch (e) {}
            this.activeSource = null;
        }
        try {
            this.sharedVoiceAudio.pause();
            this.sharedVoiceAudio.onended = null;
            this.sharedVoiceAudio.onerror = null;
        } catch (e) {}
        if (window.speechSynthesis && window.speechSynthesis.speaking) {
            try {
                window.speechSynthesis.cancel();
            } catch (e) {}
        }
        this.isPlaying = false;
        this.activeRms = null;
        this.activeVisemes = null;
        this.clearVisemes();
    }

    startSimulatedLipSync(durationMs = 3500) {
        this.stopCurrent();
        let elapsed = 0;
        let step = 0;
        const vowels = ['aa', 'ih', 'ou', 'ee', 'oh'];
        this.playStartTime = performance.now() / 1000;
        this.playDuration = Math.max(0.4, durationMs / 1000);
        this.isPlaying = true;

        return new Promise((resolve) => {
            this.simLipSyncTimer = setInterval(() => {
                if (this.vrm && this.vrm.expressionManager) {
                    vowels.forEach((v) => {
                        try {
                            this.vrm.expressionManager.setValue(v, 0);
                        } catch (e) {}
                    });
                    const v = vowels[step % vowels.length];
                    const val = Math.sin(step * 0.85) * 0.38 + 0.45;
                    try {
                        this.vrm.expressionManager.setValue(v, val);
                    } catch (e) {}
                }
                step++;
                elapsed += 85;
                if (elapsed >= durationMs) {
                    clearInterval(this.simLipSyncTimer);
                    this.simLipSyncTimer = null;
                    this.isPlaying = false;
                    this.clearVisemes();
                    if (this.onFinishCallback) this.onFinishCallback();
                    resolve();
                }
            }, 85);
        });
    }

    /**
     * Play envelope-only lip sync when HELIOS VoiceManager is already playing audio
     * through the system speaker, avoiding duplicate speaker output while keeping
     * accurate mouth movement synchronized to the RMS/viseme stream.
     */
    playEnvelopeSync(rms = null, visemes = null, duration = 2.0) {
        this.stopCurrent();
        this.activeRms = Array.isArray(rms) ? rms : null;
        this.activeVisemes = Array.isArray(visemes) ? visemes : null;
        this.playStartTime = performance.now() / 1000;
        this.playDuration = Math.max(0.4, Number(duration) || 2.0);
        this.isPlaying = true;

        return new Promise((resolve) => {
            const waitMs = this.playDuration * 1000;
            this.envelopeTimer = setTimeout(() => {
                this.envelopeTimer = null;
                this.isPlaying = false;
                this.clearVisemes();
                if (this.onFinishCallback) this.onFinishCallback();
                resolve();
            }, waitMs);
        });
    }

    playStaticMp3Sync(mp3Url, fallbackText = '') {
        if (this.voiceMuted) {
            return this.startSimulatedLipSync(3500);
        }
        this.stopCurrent();
        this.ensureContext();
        this.playStartTime = performance.now() / 1000;
        this.playDuration = 3.8;
        this.isPlaying = true;

        return new Promise((resolve) => {
            let settled = false;
            const finish = () => {
                if (settled) return;
                settled = true;
                if (this.playbackFallbackTimer) {
                    clearTimeout(this.playbackFallbackTimer);
                    this.playbackFallbackTimer = null;
                }
                this.isPlaying = false;
                this.clearVisemes();
                if (this.onFinishCallback) this.onFinishCallback();
                resolve();
            };

            this.sharedVoiceAudio.src = mp3Url;
            this.sharedVoiceAudio.volume = 1.0;
            this.sharedVoiceAudio.currentTime = 0;
            this.sharedVoiceAudio.onended = finish;
            this.sharedVoiceAudio.onerror = finish;
            this.playbackFallbackTimer = setTimeout(finish, 6500);

            const playPromise = this.sharedVoiceAudio.play();
            if (playPromise && typeof playPromise.catch === 'function') {
                playPromise.catch(() => {
                    if (settled) return;
                    settled = true;
                    if (this.playbackFallbackTimer) {
                        clearTimeout(this.playbackFallbackTimer);
                        this.playbackFallbackTimer = null;
                    }
                    this.startSimulatedLipSync(2500).then(resolve);
                });
            }
        });
    }

    async playBase64Wav(
        b64Audio,
        fallbackText = '',
        rms = null,
        visemes = null,
        duration = 0,
        mimeType = 'audio/wav',
        playAudioElement = false
    ) {
        // When HELIOS VoiceManager is playing on the host speaker, default to envelope sync
        // unless playAudioElement is explicitly requested (e.g. remote browser viewer).
        if (!playAudioElement || this.voiceMuted || !b64Audio) {
            return this.playEnvelopeSync(rms, visemes, duration || 2.0);
        }

        this.stopCurrent();
        try {
            this.ensureContext();
            this.activeRms = Array.isArray(rms) ? rms : null;
            this.activeVisemes = Array.isArray(visemes) ? visemes : null;
            this.playStartTime = performance.now() / 1000;
            this.playDuration = Math.max(0.4, Number(duration) || 2.5);

            const binaryString = atob(b64Audio);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            const blob = new Blob([bytes], { type: mimeType || 'audio/wav' });
            const blobUrl = URL.createObjectURL(blob);

            return await new Promise((resolve) => {
                let settled = false;
                const cleanup = () => {
                    if (settled) return;
                    settled = true;
                    if (this.playbackFallbackTimer) {
                        clearTimeout(this.playbackFallbackTimer);
                        this.playbackFallbackTimer = null;
                    }
                    this.isPlaying = false;
                    this.clearVisemes();
                    URL.revokeObjectURL(blobUrl);
                    if (this.onFinishCallback) this.onFinishCallback();
                    resolve();
                };

                this.sharedVoiceAudio.onended = cleanup;
                this.sharedVoiceAudio.onerror = cleanup;
                this.sharedVoiceAudio.src = blobUrl;
                this.sharedVoiceAudio.volume = 1.0;
                this.isPlaying = true;
                this.playStartTime = performance.now() / 1000;
                this.playbackFallbackTimer = setTimeout(
                    cleanup,
                    Math.max(2500, (this.playDuration + 1.2) * 1000)
                );

                const p = this.sharedVoiceAudio.play();
                if (p && typeof p.catch === 'function') {
                    p.catch(() => {
                        if (settled) return;
                        settled = true;
                        if (this.playbackFallbackTimer) {
                            clearTimeout(this.playbackFallbackTimer);
                            this.playbackFallbackTimer = null;
                        }
                        URL.revokeObjectURL(blobUrl);
                        this.playEnvelopeSync(rms, visemes, duration || 2.0).then(resolve);
                    });
                }
            });
        } catch (err) {
            return this.playEnvelopeSync(rms, visemes, duration || 2.0);
        }
    }

    clearVisemes() {
        this.currentSpeechEnergy = 0;
        this.smoothVisemes = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
        if (!this.vrm || !this.vrm.expressionManager) return;
        ['aa', 'ih', 'ou', 'ee', 'oh'].forEach((v) => {
            try {
                this.vrm.expressionManager.setValue(v, 0);
            } catch (e) {}
        });
    }

    update() {
        if (!this.smoothVisemes) {
            this.smoothVisemes = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
        }
        if (!this.isPlaying || !this.vrm || !this.vrm.expressionManager) {
            this.currentSpeechEnergy = 0;
            return;
        }

        const wallElapsed = performance.now() / 1000 - this.playStartTime;
        if (
            this.playDuration > 0 &&
            wallElapsed >= this.playDuration + 0.35 &&
            (this.sharedVoiceAudio.paused || this.sharedVoiceAudio.ended) &&
            !this.simLipSyncTimer
        ) {
            this.stopCurrent();
            if (this.onFinishCallback) this.onFinishCallback();
            return;
        }

        let openness = 0;
        let ihWeight = 0;
        let ouWeight = 0;
        let eeWeight = 0;
        let ohWeight = 0;

        if (this.analyser && this.activeSource && this.dataArray) {
            this.analyser.getByteFrequencyData(this.dataArray);
            let lowEnergy = 0;
            let midEnergy = 0;
            let highMidEnergy = 0;
            let subEnergy = 0;

            for (let i = 2; i < 16; i++) lowEnergy += this.dataArray[i];
            for (let i = 16; i < 48; i++) midEnergy += this.dataArray[i];
            for (let i = 48; i < 96; i++) highMidEnergy += this.dataArray[i];
            for (let i = 1; i < 8; i++) subEnergy += this.dataArray[i];

            const lowNorm = lowEnergy / 14 / 255;
            const midNorm = midEnergy / 32 / 255;
            const highMidNorm = highMidEnergy / 48 / 255;
            const subNorm = subEnergy / 7 / 255;

            openness = Math.min(0.95, lowNorm * 1.85);
            ihWeight = midNorm > lowNorm * 0.5 ? Math.min(0.85, midNorm * 1.65) : 0;
            eeWeight = highMidNorm > 0.22 ? Math.min(0.7, highMidNorm * 1.45) : 0;
            ouWeight = subNorm > 0.35 ? Math.min(0.72, subNorm * 1.05) : 0;
            ohWeight = lowNorm > 0.32 && midNorm < 0.35 ? Math.min(0.68, lowNorm * 1.2) : 0;
        }

        const elapsed =
            !this.sharedVoiceAudio.paused && this.sharedVoiceAudio.currentTime > 0
                ? this.sharedVoiceAudio.currentTime
                : performance.now() / 1000 - this.playStartTime;

        if (openness < 0.05 && this.activeRms && this.activeRms.length > 0) {
            const frameIdx = Math.min(
                this.activeRms.length - 1,
                Math.max(0, Math.floor(elapsed * 30))
            );
            openness = Math.min(0.95, (this.activeRms[frameIdx] || 0) * 1.25);
            ihWeight = Math.min(0.62, openness * 0.46 * (0.5 + 0.5 * Math.sin(elapsed * 17.5)));
            ouWeight = Math.min(0.52, openness * 0.36 * (0.5 + 0.5 * Math.cos(elapsed * 13.5)));
            eeWeight = Math.min(0.45, openness * 0.32 * Math.max(0, Math.sin(elapsed * 21.0)));
            ohWeight = Math.min(0.50, openness * 0.40 * Math.max(0, Math.cos(elapsed * 10.5)));
        } else if (openness < 0.05) {
            const syll = Math.max(
                0,
                Math.sin(elapsed * 14.8) * 0.52 + Math.sin(elapsed * 6.9) * 0.34 + 0.22
            );
            openness = Math.min(0.88, syll);
            ihWeight = Math.max(0, Math.sin(elapsed * 11.2) * 0.42);
            ouWeight = Math.max(0, Math.cos(elapsed * 9.3) * 0.32);
            eeWeight = Math.max(0, Math.sin(elapsed * 17.4 + 1.1) * 0.30);
            ohWeight = Math.max(0, Math.cos(elapsed * 7.8 + 0.6) * 0.34);
        }

        // Human jaw co-articulation: faster attack (0.48) when opening, softer release (0.24) when closing
        const targets = { aa: openness, ih: ihWeight, ou: ouWeight, ee: eeWeight, oh: ohWeight };
        ['aa', 'ih', 'ou', 'ee', 'oh'].forEach((v) => {
            const cur = this.smoothVisemes[v] || 0;
            const tgt = targets[v] || 0;
            const alpha = tgt > cur ? 0.48 : 0.24;
            const next = cur + (tgt - cur) * alpha;
            this.smoothVisemes[v] = next;
            try {
                this.vrm.expressionManager.setValue(v, next);
            } catch (e) {}
        });

        this.currentSpeechEnergy = Math.min(
            1.0,
            this.smoothVisemes.aa * 0.75 + this.smoothVisemes.oh * 0.45 + this.smoothVisemes.ee * 0.25
        );
    }
}
