"""
HELIOS Trained 3D Body Movement & Choreography Neural Model
===========================================================
Provides:
1. A pure-NumPy 2-layer Neural MLP + Sublinear TF-IDF N-gram Classifier trained on
   250+ labeled VRM avatar movement examples (`body_director_dataset.jsonl`) to predict:
   - `movement`: 3D spatial navigation (`stay`, `walk_to_user`, `step_back`, `circle_user`, `return_center`)
   - `animation`: Full-body 2-bone IK pose / trick (`wave`, `nod`, `peace`, `cheer`, `shrug`, `bow`,
     `confident`, `shy`, `smug_pose`, `refuse`, `hug_attempt`, `dance_shikano`, `backflip`,
     `think_pose`, `talk_explain`, `talk_excited`, `talk_smug`, `idle`)
   - `emotion`: Character emotion (`neutral`, `happy`, `amused`, `curious`, `excited`, `concerned`, `serious`, `confused`)
   - `choreography`: Multi-step sequential body keyframes (`[{"movement": ..., "animation": ..., "emotion": ..., "duration_ms": ...}]`)
2. Inline `[BODY: move=..., pose=..., emotion=...]` tag parser for the trained conversational LLM
   (`helios-avatar:latest` / `llama3.2:3b`).
"""
import json
import math
import pickle
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .character_state import (
    DEFAULT_EMOTION_EXPRESSION,
    VALID_ANIMATIONS,
    VALID_EMOTIONS,
    VALID_MOVEMENTS,
    VALID_STYLES,
)

INLINE_BODY_TAG_RE = re.compile(
    r"`*\[BODY\s*:\s*([^\]\n]+?)(?:\]|>>+|>+\s*,|\n)`*[,;\s]*",
    re.IGNORECASE,
)


def parse_and_strip_inline_body_tags(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Extract inline `[BODY: move=walk_to_user, pose=wave, emotion=happy, style=energetic]` directives
    (including 3B model variations like `[BODY: move<stay, pose<cheer, emotion<happy>>`)
    and return `(clean_text, extracted_directives)`.
    """
    if not text:
        return "", []

    directives: List[Dict[str, str]] = []
    for match in INLINE_BODY_TAG_RE.finditer(text):
        kv_str = match.group(1)
        parsed: Dict[str, str] = {}
        for part in kv_str.split(","):
            kv = re.split(r"[=:<]", part, maxsplit=1)
            if len(kv) == 2:
                k, v = kv[0], kv[1]
                k = k.strip().lower().strip("`'\"<>[]")
                v = v.strip().lower().strip("`'\"<>[]")
                if k in ("move", "movement") and v in VALID_MOVEMENTS:
                    parsed["movement"] = v
                elif k in ("pose", "anim", "animation"):
                    parsed["animation"] = v
                elif k == "emotion" and v in VALID_EMOTIONS:
                    parsed["emotion"] = v
                elif k == "style" and v in VALID_STYLES:
                    parsed["style"] = v
        if parsed:
            directives.append(parsed)

    clean_text = INLINE_BODY_TAG_RE.sub("", text)
    clean_text = re.sub(r"`*\[BODY\s*:[^\]\n]*$", "", clean_text, flags=re.IGNORECASE).strip()
    if clean_text.startswith("`") and clean_text.endswith("`") and "```" not in clean_text:
        clean_text = clean_text.strip("`").strip()
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)
    return clean_text, directives


def extract_ngrams(text: str) -> List[str]:
    """Extract word (1..3) and character (3..5) n-grams for VRM movement classification."""
    clean = re.sub(r"[^a-z0-9_\s']", " ", (text or "").lower())
    words = [w for w in clean.split() if w]
    feats: List[str] = []
    # Word 1..3-grams
    for n in (1, 2, 3):
        for i in range(len(words) - n + 1):
            feats.append("w:" + "_".join(words[i : i + n]))
    # Character 3..5-grams within words
    for w in words:
        padded = f"<{w}>"
        for n in (3, 4, 5):
            for i in range(len(padded) - n + 1):
                feats.append("c:" + padded[i : i + n])
    return feats


class NumpyMLPHead:
    """
    2-Layer Neural MLP (`Input -> Hidden (ReLU) -> Output (Softmax)`)
    trained with Mini-Batch Adam and Cross-Entropy Loss in pure NumPy.
    """

    def __init__(self, classes: List[str], W1: np.ndarray, b1: np.ndarray, W2: np.ndarray, b2: np.ndarray):
        self.classes = classes
        self.W1 = W1
        self.b1 = b1
        self.W2 = W2
        self.b2 = b2

    @classmethod
    def train(
        cls,
        X: np.ndarray,
        y_labels: List[str],
        hidden_dim: int = 96,
        epochs: int = 220,
        lr: float = 0.012,
        l2_reg: float = 1e-4,
        seed: int = 42,
    ) -> "NumpyMLPHead":
        rng = np.random.default_rng(seed)
        classes = sorted(set(y_labels))
        class_to_idx = {c: i for i, c in enumerate(classes)}
        N, D = X.shape
        K = len(classes)
        Y = np.zeros((N, K), dtype=np.float32)
        for i, lbl in enumerate(y_labels):
            Y[i, class_to_idx[lbl]] = 1.0

        W1 = rng.normal(0.0, math.sqrt(2.0 / D), size=(D, hidden_dim)).astype(np.float32)
        b1 = np.zeros((1, hidden_dim), dtype=np.float32)
        W2 = rng.normal(0.0, math.sqrt(2.0 / hidden_dim), size=(hidden_dim, K)).astype(np.float32)
        b2 = np.zeros((1, K), dtype=np.float32)

        # Adam state
        mW1, vW1 = np.zeros_like(W1), np.zeros_like(W1)
        mb1, vb1 = np.zeros_like(b1), np.zeros_like(b1)
        mW2, vW2 = np.zeros_like(W2), np.zeros_like(W2)
        mb2, vb2 = np.zeros_like(b2), np.zeros_like(b2)
        beta1, beta2, eps = 0.9, 0.999, 1e-8

        for t in range(1, epochs + 1):
            # Forward pass
            Z1 = X @ W1 + b1
            H1 = np.maximum(0.0, Z1)
            logits = H1 @ W2 + b2
            logits -= np.max(logits, axis=1, keepdims=True)
            exp_scores = np.exp(logits)
            probs = exp_scores / np.sum(exp_scores, axis=1, keepdims=True)

            # Backward pass
            dlogits = (probs - Y) / N
            dW2 = H1.T @ dlogits + l2_reg * W2
            db2 = np.sum(dlogits, axis=0, keepdims=True)

            dH1 = dlogits @ W2.T
            dZ1 = dH1 * (Z1 > 0)
            dW1 = X.T @ dZ1 + l2_reg * W1
            db1 = np.sum(dZ1, axis=0, keepdims=True)

            # Adam updates
            for param, grad, m, v in (
                (W1, dW1, mW1, vW1),
                (b1, db1, mb1, vb1),
                (W2, dW2, mW2, vW2),
                (b2, db2, mb2, vb2),
            ):
                m[:] = beta1 * m + (1.0 - beta1) * grad
                v[:] = beta2 * v + (1.0 - beta2) * (grad * grad)
                m_hat = m / (1.0 - beta1**t)
                v_hat = v / (1.0 - beta2**t)
                param -= lr * m_hat / (np.sqrt(v_hat) + eps)

        return cls(classes=classes, W1=W1, b1=b1, W2=W2, b2=b2)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        H1 = np.maximum(0.0, X @ self.W1 + self.b1)
        logits = H1 @ self.W2 + self.b2
        logits -= np.max(logits, axis=1, keepdims=True)
        exp_scores = np.exp(logits)
        return exp_scores / np.sum(exp_scores, axis=1, keepdims=True)

    def predict_one(self, x_vec: np.ndarray) -> Tuple[str, float]:
        probs = self.predict_proba(x_vec.reshape(1, -1))[0]
        idx = int(np.argmax(probs))
        return self.classes[idx], float(probs[idx])


class TrainedBodyMovementModel:
    """
    4-Head Neural Body Movement, Human Style & Expressive Behavior Predictor.
    Loads trained weights from `models/helios_body_movement_model.pkl`
    and predicts `{emotion, expression, intensity, animation, movement, style, choreography}` in <1ms.
    """

    def __init__(self, bundle: Dict[str, Any]):
        self.trained: bool = True
        self.vocab: Dict[str, int] = bundle["vocab"]
        self.idf: np.ndarray = bundle["idf"]
        self.move_head: NumpyMLPHead = bundle["move_head"]
        self.anim_head: NumpyMLPHead = bundle["anim_head"]
        self.emo_head: NumpyMLPHead = bundle["emo_head"]
        self.style_head: Optional[NumpyMLPHead] = bundle.get("style_head")
        self.choreo_lookup: Dict[Tuple[str, str], List[Dict[str, Any]]] = bundle.get("choreo_lookup", {})
        self.metrics: Dict[str, Any] = bundle.get("metrics", {})

    def _build_choreography(
        self,
        movement: str,
        animation: str,
        emotion: str = "happy",
        style: str = "natural",
    ) -> List[Dict[str, Any]]:
        steps = self.choreo_lookup.get((movement, animation))
        if steps:
            return list(steps)
        if movement and movement not in ("stay", "idle") and animation != "walk":
            return [
                {"movement": movement, "animation": "walk", "emotion": emotion, "style": style, "duration": 1.4},
                {"movement": "stay", "animation": animation, "emotion": emotion, "style": style, "duration": 1.8},
            ]
        return [{"movement": movement or "stay", "animation": animation or "idle", "emotion": emotion, "style": style, "duration": 1.8}]

    @classmethod
    def load_default(cls) -> Optional["TrainedBodyMovementModel"]:
        candidates = [
            Path(__file__).resolve().parent.parent / "models" / "helios_body_movement_model.pkl",
            Path(__file__).resolve().parent.parent.parent
            / "helios-character"
            / "training"
            / "helios_body_movement_model.pkl",
        ]
        for path in candidates:
            if path.exists():
                try:
                    with open(path, "rb") as f:
                        bundle = pickle.load(f)
                    return cls(bundle)
                except Exception:
                    pass
        return None

    def vectorize_one(self, user_text: str, assistant_text: str = "") -> np.ndarray:
        combined = f"USER: {user_text} USER_CMD: {user_text} ASSISTANT: {assistant_text}"
        feats = extract_ngrams(combined)
        vec = np.zeros(len(self.vocab), dtype=np.float32)
        counts: Dict[int, int] = {}
        for f in feats:
            idx = self.vocab.get(f)
            if idx is not None:
                counts[idx] = counts.get(idx, 0) + 1
        for idx, cnt in counts.items():
            vec[idx] = (1.0 + math.log(cnt)) * self.idf[idx]
        norm = float(np.linalg.norm(vec))
        if norm > 1e-8:
            vec /= norm
        return vec

    def predict(
        self,
        user_text: str,
        assistant_text: str = "",
    ) -> Dict[str, Any]:
        """
        Predict `{emotion, expression, intensity, animation, movement, style, confidence, choreography}`
        using the trained 4-head Neural MLP + inline `[BODY: ...]` tags if present.
        """
        clean_asst, inline_tags = parse_and_strip_inline_body_tags(assistant_text)
        x = self.vectorize_one(user_text, clean_asst)

        pred_move, conf_move = self.move_head.predict_one(x)
        pred_anim, conf_anim = self.anim_head.predict_one(x)
        pred_emo, conf_emo = self.emo_head.predict_one(x)
        if self.style_head is not None:
            pred_style, conf_style = self.style_head.predict_one(x)
        else:
            pred_style, conf_style = "natural", 0.90

        # If the trained conversational LLM emitted explicit [BODY: ...] tags, merge them
        if inline_tags:
            first_tag = inline_tags[0]
            if "movement" in first_tag:
                pred_move = first_tag["movement"]
                conf_move = 0.99
            if "animation" in first_tag:
                pred_anim = first_tag["animation"]
                conf_anim = 0.99
            if "emotion" in first_tag:
                pred_emo = first_tag["emotion"]
                conf_emo = 0.99
            if "style" in first_tag:
                pred_style = first_tag["style"]
                conf_style = 0.99

        avg_conf = (conf_move + conf_anim + conf_emo + conf_style) / 4.0
        intensity = round(max(0.55, min(0.95, 0.5 + 0.45 * avg_conf)), 3)
        expression = DEFAULT_EMOTION_EXPRESSION.get(pred_emo, "neutral")

        # Build multi-step choreography sequence
        if len(inline_tags) > 1:
            choreo = [
                {
                    "movement": t.get("movement", "stay"),
                    "animation": t.get("animation", pred_anim),
                    "emotion": t.get("emotion", pred_emo),
                    "style": t.get("style", pred_style),
                    "duration_ms": 2200,
                }
                for t in inline_tags
            ]
        else:
            choreo = list(
                self.choreo_lookup.get(
                    (pred_move, pred_anim),
                    [
                        {
                            "movement": pred_move,
                            "animation": pred_anim,
                            "emotion": pred_emo,
                            "style": pred_style,
                            "duration_ms": 2500,
                        }
                    ],
                )
            )

        return {
            "emotion": pred_emo,
            "expression": expression,
            "intensity": intensity,
            "animation": pred_anim,
            "movement": pred_move,
            "style": pred_style,
            "confidence": round(avg_conf, 3),
            "choreography": choreo,
            "clean_assistant_text": clean_asst,
        }
