/**
 * HELIOS Character Addon — VRM Expressions Module (Section 12)
 * Maps renderer-independent HELIOS emotions & expressions
 * (neutral, happy, amused, curious, excited, concerned, serious, confused, smirk)
 * onto VRM 0.x / 1.0 BlendShapes with intensity scaling.
 */
import * as THREE from 'three';

export const EXPRESSION_ALIASES = {
    surprised: ['surprised', 'Surprised'],
    confused: ['surprised', 'Surprised'],
    curious: ['relaxed', 'fun', 'Fun', 'surprised'],
    happy: ['happy', 'joy', 'Joy'],
    excited: ['happy', 'joy', 'Joy'],
    joy: ['happy', 'joy', 'Joy'],
    amused: ['relaxed', 'fun', 'Fun', 'happy'],
    smirk: ['relaxed', 'fun', 'Fun'],
    smug: ['relaxed', 'fun', 'Fun'],
    relaxed: ['relaxed', 'fun', 'Fun'],
    fun: ['relaxed', 'fun', 'Fun'],
    concerned: ['sad', 'sorrow', 'Sorrow'],
    sad: ['sad', 'sorrow', 'Sorrow'],
    sorrow: ['sad', 'sorrow', 'Sorrow'],
    serious: ['angry', 'Angry', 'neutral', 'Neutral'],
    angry: ['angry', 'Angry'],
    thinking: ['relaxed', 'neutral', 'Neutral'],
    neutral: ['neutral', 'Neutral'],
};

export class ExpressionController {
    constructor(vrm = null, onPresetHighlight = null) {
        this.vrm = vrm;
        this.availableExpressions = [];
        this.currentEmotion = 'neutral';
        this.onPresetHighlight = onPresetHighlight;
        if (vrm) this.setVRM(vrm);
    }

    setVRM(vrm) {
        this.vrm = vrm;
        this.availableExpressions = [];
        if (vrm && vrm.expressionManager) {
            const expressions = vrm.expressionManager.expressions || [];
            expressions.forEach((expr) => {
                const name = expr.expressionName;
                if (!['lookUp', 'lookDown', 'lookLeft', 'lookRight'].includes(name)) {
                    this.availableExpressions.push(name);
                }
            });
        }
        return this.availableExpressions;
    }

    resolveExpressionName(requested) {
        if (!this.vrm || !this.vrm.expressionManager) return requested;
        const candidates = EXPRESSION_ALIASES[(requested || '').toLowerCase()] || [requested];
        for (const c of candidates) {
            const match = this.availableExpressions.find(
                (e) => e === c || e.toLowerCase() === c.toLowerCase()
            );
            if (match) return match;
        }
        return requested;
    }

    setExpressionSmart(name, weight = 1.0) {
        if (!this.vrm || !this.vrm.expressionManager) return;
        const actualName = this.resolveExpressionName(name);
        try {
            this.vrm.expressionManager.setValue(actualName, THREE.MathUtils.clamp(weight, 0, 1));
        } catch (e) {}
    }

    resetExpressions(keepBlinkAndMouth = false) {
        if (!this.vrm || !this.vrm.expressionManager) return;
        const exp = this.vrm.expressionManager;
        this.availableExpressions.forEach((name) => {
            if (keepBlinkAndMouth && ['blink', 'aa', 'ih', 'ou', 'ee', 'oh'].includes(name)) return;
            try {
                exp.setValue(name, 0);
            } catch (e) {}
        });
        if (this.onPresetHighlight) this.onPresetHighlight(null);
    }

    applyExpressionState(expressionOrEmotion, weight = 0.75, blendshapeWeights = null) {
        this.resetExpressions(true);
        const key = (expressionOrEmotion || 'neutral').toLowerCase();
        this.currentEmotion = key;
        const clamped = THREE.MathUtils.clamp(Number(weight) || 0.75, 0.0, 1.0);

        if (
            blendshapeWeights &&
            typeof blendshapeWeights === 'object' &&
            Object.keys(blendshapeWeights).length > 0
        ) {
            Object.entries(blendshapeWeights).forEach(([k, v]) => {
                this.setExpressionSmart(k, Number(v) || 0);
            });
            if (this.onPresetHighlight) {
                this.onPresetHighlight(this.resolveExpressionName(Object.keys(blendshapeWeights)[0]));
            }
            return;
        }

        if (key === 'smirk' || key === 'amused' || key === 'smug') {
            this.setExpressionSmart('relaxed', 0.65 * clamped);
            this.setExpressionSmart('happy', 0.25 * clamped);
            this.setExpressionSmart('blinkLeft', 0.22 * clamped);
            if (this.onPresetHighlight) this.onPresetHighlight(this.resolveExpressionName('relaxed'));
        } else if (key === 'serious') {
            this.setExpressionSmart('angry', 0.45 * clamped);
            this.setExpressionSmart('neutral', 0.8);
            if (this.onPresetHighlight) this.onPresetHighlight(this.resolveExpressionName('angry'));
        } else if (key === 'concerned') {
            this.setExpressionSmart('sad', 0.65 * clamped);
            if (this.onPresetHighlight) this.onPresetHighlight(this.resolveExpressionName('sad'));
        } else if (key === 'curious' || key === 'thinking') {
            this.setExpressionSmart('relaxed', 0.55 * clamped);
            this.setExpressionSmart('oh', 0.15 * clamped);
            if (this.onPresetHighlight) this.onPresetHighlight(this.resolveExpressionName('relaxed'));
        } else if (key === 'confused') {
            this.setExpressionSmart('surprised', 0.6 * clamped);
            if (this.onPresetHighlight) this.onPresetHighlight(this.resolveExpressionName('surprised'));
        } else if (key === 'excited') {
            this.setExpressionSmart('happy', Math.min(1.0, clamped * 1.1));
            if (this.onPresetHighlight) this.onPresetHighlight(this.resolveExpressionName('happy'));
        } else if (key !== 'neutral') {
            this.setExpressionSmart(key, clamped);
            if (this.onPresetHighlight) this.onPresetHighlight(this.resolveExpressionName(key));
        }
    }
}
