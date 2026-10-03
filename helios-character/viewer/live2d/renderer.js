/**
 * HELIOS Character Addon — Live2D Renderer Adapter (Phase 12)
 * Implements the same Character Protocol consumer interface as the VRM renderer
 * (`applyCharacterState`, `applyCharacterActivity`, `applyCharacterSpeech`, `stopSpeech`)
 * so Live2D models (.model3.json) can be selected via `CHARACTER_RENDERER=live2d`
 * without any changes to HELIOS Core.
 */

export class Live2DRendererAdapter {
    constructor(containerEl, statusCallback = null) {
        this.container = containerEl;
        this.onStatus = statusCallback;
        this.currentMode = 'idle';
        this.currentEmotion = 'neutral';
        this.currentExpression = 'neutral';
        this.currentAnimation = 'idle';
        this.speaking = false;
        this.mouthOpen = 0.0;
    }

    async loadModel(manifestOrUrl) {
        if (this.onStatus) {
            this.onStatus(`Live2D Adapter Ready (${manifestOrUrl?.id || manifestOrUrl})`);
        }
        return true;
    }

    applyCharacterState(stateMsg) {
        if (!stateMsg) return;
        this.currentMode = stateMsg.mode || 'idle';
        this.currentEmotion = stateMsg.emotion || 'neutral';
        this.currentExpression = stateMsg.expression || 'neutral';
        this.currentAnimation = stateMsg.animation || 'idle';
        this.speaking = Boolean(stateMsg.speaking);
        if (this.onStatus) {
            this.onStatus(
                `[Live2D] Mode: ${this.currentMode} | Emotion: ${this.currentEmotion} | Expr: ${this.currentExpression}`
            );
        }
    }

    applyCharacterActivity(activityMsg) {
        if (this.onStatus && activityMsg?.activity) {
            this.onStatus(`[Live2D Activity] ${activityMsg.activity}`);
        }
    }

    applyCharacterSpeech(speechMsg) {
        this.speaking = Boolean(speechMsg?.speaking);
        if (!this.speaking) {
            this.mouthOpen = 0.0;
        }
    }

    stopSpeech() {
        this.speaking = false;
        this.mouthOpen = 0.0;
        this.currentMode = 'idle';
    }
}
