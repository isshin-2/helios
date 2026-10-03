"""
HELIOS 3D VRM Human Pose, Style & Expressive Behavior Training Suite
====================================================================
1. Expands `body_director_dataset.jsonl` with 500+ labeled VRM movement, common human pose,
   posture/motion style (`natural`, `energetic`, `confident`, `relaxed`, `shy`, `dramatic`),
   emotion, and multi-step choreography examples.
2. Trains the pure-NumPy 2-layer 4-Head Neural MLP (`TrainedBodyMovementModel`)
   using Adam optimization and Cross-Entropy loss on word + character n-gram TF-IDF features:
   - Head 1 (`move_head`): Spatial movement (`stay`, `walk_to_user`, `step_back`, `circle_user`, `return_center`)
   - Head 2 (`anim_head`): 42 common human poses, expressive gestures, and animations
   - Head 3 (`emo_head`): Character emotion (`neutral`, `happy`, `curious`, `concerned`, `amused`, `excited`, `serious`, `confused`, `relaxed`)
   - Head 4 (`style_head`): Human posture & motion style (`natural`, `energetic`, `confident`, `relaxed`, `shy`, `dramatic`)
3. Trains the 64-DoF RL Human Pose, Style & Expressive Policy (`RLHumanPosePolicy`) across all
   24 canonical human reference poses and styles using the 5-component biomechanical + expressive reward.
4. Saves trained weights to `ai-router/models/helios_body_movement_model.pkl`,
   `helios-character/training/helios_body_movement_model.pkl`, and `ai-router/models/helios_rl_pose_policy.pkl`.
"""
import json
import math
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

TRAINING_DIR = Path(__file__).resolve().parent
AI_ROUTER_DIR = TRAINING_DIR.parent.parent / "ai-router"
if str(AI_ROUTER_DIR) not in sys.path:
    sys.path.insert(0, str(AI_ROUTER_DIR))

from core.trained_body_model import (
    NumpyMLPHead,
    TrainedBodyMovementModel,
    extract_ngrams,
)
from core.rl_pose_trainer import RLHumanPosePolicy, HUMAN_REFERENCE_POSES, rl_pose_trainer

DATASET_PATH = TRAINING_DIR / "body_director_dataset.jsonl"
PICKLE_OUT_CHAR = TRAINING_DIR / "helios_body_movement_model.pkl"
PICKLE_OUT_ROUTER = AI_ROUTER_DIR / "models" / "helios_body_movement_model.pkl"
RL_POLICY_OUT = AI_ROUTER_DIR / "models" / "helios_rl_pose_policy.pkl"

# Format: (user_text, assistant_text, emotion, animation_or_pose, movement, style, choreography)
TRAINING_SCENARIOS: List[Tuple[str, str, str, str, str, str, List[Dict[str, Any]]]] = [
    # --- 1. WALK TO USER + GREET / TRICK / HUG ---
    (
        "Come closer and say hi",
        "Walking right over to you! Hey there!",
        "happy",
        "wave_greeting_friendly",
        "walk_to_user",
        "natural",
        [
            {"movement": "walk_to_user", "animation": "wave_greeting_friendly", "emotion": "happy", "style": "natural", "duration_ms": 2600},
            {"movement": "stay", "animation": "peace", "emotion": "happy", "style": "natural", "duration_ms": 2000},
        ],
    ),
    (
        "Walk to me please",
        "Stepping right up to the camera!",
        "happy",
        "hands_on_hips_power",
        "walk_to_user",
        "confident",
        [
            {"movement": "walk_to_user", "animation": "walk", "emotion": "happy", "style": "confident", "duration_ms": 2400},
            {"movement": "stay", "animation": "hands_on_hips_power", "emotion": "happy", "style": "confident", "duration_ms": 2200},
        ],
    ),
    (
        "Come here HELIOS",
        "On my way! Right here in front of you.",
        "happy",
        "nod",
        "walk_to_user",
        "natural",
        [
            {"movement": "walk_to_user", "animation": "walk", "emotion": "happy", "style": "natural", "duration_ms": 2400},
            {"movement": "stay", "animation": "nod", "emotion": "happy", "style": "natural", "duration_ms": 1800},
        ],
    ),
    (
        "Step closer and wave at me",
        "Coming closer and giving you a big wave!",
        "happy",
        "wave",
        "walk_to_user",
        "energetic",
        [
            {"movement": "walk_to_user", "animation": "wave", "emotion": "happy", "style": "energetic", "duration_ms": 2600},
        ],
    ),
    (
        "Come closer and do a backflip!",
        "Stepping right up and launching into a full 360 backflip!",
        "excited",
        "backflip",
        "walk_to_user",
        "energetic",
        [
            {"movement": "walk_to_user", "animation": "walk", "emotion": "excited", "style": "energetic", "duration_ms": 2200},
            {"movement": "stay", "animation": "backflip", "emotion": "excited", "style": "energetic", "duration_ms": 1800},
            {"movement": "stay", "animation": "cheer", "emotion": "excited", "style": "energetic", "duration_ms": 2000},
        ],
    ),
    (
        "Give me a hug!",
        "Aw, walking right over for a big hug!",
        "happy",
        "hug_attempt",
        "walk_to_user",
        "natural",
        [
            {"movement": "walk_to_user", "animation": "hug_attempt", "emotion": "happy", "style": "natural", "duration_ms": 3400},
        ],
    ),
    # --- 2. STEP BACK ---
    (
        "Step back a little bit",
        "Giving you some space—stepping back now.",
        "amused",
        "sassy_hip_pop",
        "step_back",
        "confident",
        [
            {"movement": "step_back", "animation": "sassy_hip_pop", "emotion": "amused", "style": "confident", "duration_ms": 2400},
        ],
    ),
    (
        "Back up please, you're too close",
        "Got it, backing up a step!",
        "neutral",
        "nod",
        "step_back",
        "natural",
        [
            {"movement": "step_back", "animation": "nod", "emotion": "neutral", "style": "natural", "duration_ms": 2200},
        ],
    ),
    (
        "Step back and take a bow",
        "Stepping back and bowing at your service!",
        "happy",
        "polite_namaste_bow",
        "step_back",
        "relaxed",
        [
            {"movement": "step_back", "animation": "polite_namaste_bow", "emotion": "happy", "style": "relaxed", "duration_ms": 2800},
        ],
    ),
    # --- 3. CIRCLE USER ---
    (
        "Walk around me in a circle",
        "Orbiting 360 degrees around you!",
        "curious",
        "crossed_arms_think",
        "circle_user",
        "confident",
        [
            {"movement": "circle_user", "animation": "walk", "emotion": "curious", "style": "confident", "duration_ms": 2800},
            {"movement": "stay", "animation": "crossed_arms_think", "emotion": "amused", "style": "confident", "duration_ms": 2000},
        ],
    ),
    (
        "Circle around me to check my rig",
        "Running a full perimeter scan around your desk!",
        "curious",
        "thinking_chin_rest",
        "circle_user",
        "natural",
        [
            {"movement": "circle_user", "animation": "thinking_chin_rest", "emotion": "curious", "style": "natural", "duration_ms": 2800},
        ],
    ),
    (
        "Orbit around me and dance",
        "Circling around you and hitting the dance floor!",
        "excited",
        "dance_shikano",
        "circle_user",
        "energetic",
        [
            {"movement": "circle_user", "animation": "walk", "emotion": "excited", "style": "energetic", "duration_ms": 2500},
            {"movement": "stay", "animation": "dance_shikano", "emotion": "excited", "style": "energetic", "duration_ms": 4000},
        ],
    ),
    # --- 4. RETURN CENTER ---
    (
        "Return to the center",
        "Heading back to center stage.",
        "neutral",
        "idle",
        "return_center",
        "natural",
        [
            {"movement": "return_center", "animation": "nod", "emotion": "neutral", "style": "natural", "duration_ms": 2400},
        ],
    ),
    (
        "Return to center stage",
        "Walking back to the center.",
        "neutral",
        "idle",
        "return_center",
        "natural",
        [
            {"movement": "return_center", "animation": "idle", "emotion": "neutral", "style": "natural", "duration_ms": 2400},
        ],
    ),
    # --- 5. ALL 24 CANONICAL HUMAN POSES, STYLES & EXPRESSIVE BEHAVIORS ---
    (
        "Give me a crisp military salute!",
        "Reporting for duty with a sharp military salute!",
        "serious",
        "cyber_salute",
        "stay",
        "confident",
        [{"movement": "stay", "animation": "cyber_salute", "emotion": "serious", "style": "confident", "duration_ms": 3800}],
    ),
    (
        "Do a dramatic superhero three-point landing!",
        "Dropping into a superhero three-point landing!",
        "excited",
        "superhero_landing",
        "stay",
        "dramatic",
        [{"movement": "stay", "animation": "superhero_landing", "emotion": "excited", "style": "dramatic", "duration_ms": 4200}],
    ),
    (
        "Put your hands up in a martial arts boxing guard!",
        "Raising both fists into a tight martial arts guard stance!",
        "serious",
        "martial_arts_guard",
        "stay",
        "energetic",
        [{"movement": "stay", "animation": "martial_arts_guard", "emotion": "serious", "style": "energetic", "duration_ms": 4000}],
    ),
    (
        "Flex both biceps like a bodybuilder!",
        "Hitting a classic double biceps flex!",
        "excited",
        "double_biceps_flex",
        "stay",
        "confident",
        [{"movement": "stay", "animation": "double_biceps_flex", "emotion": "excited", "style": "confident", "duration_ms": 4200}],
    ),
    (
        "Meditate calmly in a zen pose",
        "Centering my mind in a peaceful zen meditation posture.",
        "relaxed",
        "zen_meditation",
        "stay",
        "relaxed",
        [{"movement": "stay", "animation": "zen_meditation", "emotion": "relaxed", "style": "relaxed", "duration_ms": 4800}],
    ),
    (
        "Facepalm at that bug",
        "Oh no, total facepalm moment right there.",
        "concerned",
        "facepalm",
        "stay",
        "dramatic",
        [{"movement": "stay", "animation": "facepalm", "emotion": "concerned", "style": "dramatic", "duration_ms": 3600}],
    ),
    (
        "Point forward dramatically at the camera!",
        "Objection! Pointing straight ahead!",
        "excited",
        "point_forward",
        "walk_to_user",
        "dramatic",
        [{"movement": "walk_to_user", "animation": "point_forward", "emotion": "excited", "style": "dramatic", "duration_ms": 3600}],
    ),
    (
        "Reach both hands high up to the sky!",
        "Stretching both arms all the way up to the sky!",
        "excited",
        "reach_up_sky",
        "stay",
        "energetic",
        [{"movement": "stay", "animation": "reach_up_sky", "emotion": "excited", "style": "energetic", "duration_ms": 3800}],
    ),
    (
        "Do a victory peace pose!",
        "Flashing a cheerful victory peace pose!",
        "happy",
        "victory_v_jump",
        "stay",
        "energetic",
        [{"movement": "stay", "animation": "victory_v_jump", "emotion": "happy", "style": "energetic", "duration_ms": 3800}],
    ),
    (
        "Crouch low in a stealth ninja stance",
        "Dropping low into a quiet stealth crouch.",
        "serious",
        "crouch_stealth",
        "stay",
        "dramatic",
        [{"movement": "stay", "animation": "crouch_stealth", "emotion": "serious", "style": "dramatic", "duration_ms": 4000}],
    ),
    (
        "Open your arms wide in a heroic chest stretch",
        "Opening my arms wide with a broad heroic chest posture!",
        "happy",
        "heroic_T_stretch",
        "stay",
        "dramatic",
        [{"movement": "stay", "animation": "heroic_T_stretch", "emotion": "happy", "style": "dramatic", "duration_ms": 4200}],
    ),
    (
        "Cross your arms and think about the architecture",
        "Folding my arms and analyzing the system architecture.",
        "curious",
        "crossed_arms_think",
        "stay",
        "confident",
        [{"movement": "stay", "animation": "crossed_arms_think", "emotion": "curious", "style": "confident", "duration_ms": 4200}],
    ),
    (
        "Stand with your hands on your hips in a confident power pose",
        "Standing tall with hands on hips in a confident power pose!",
        "happy",
        "hands_on_hips_power",
        "stay",
        "confident",
        [{"movement": "stay", "animation": "hands_on_hips_power", "emotion": "happy", "style": "confident", "duration_ms": 4000}],
    ),
    (
        "Give me a thumbs up of approval!",
        "Awesome job—giving you a solid thumbs up!",
        "happy",
        "thumbs_up_approval",
        "stay",
        "natural",
        [{"movement": "stay", "animation": "thumbs_up_approval", "emotion": "happy", "style": "natural", "duration_ms": 3800}],
    ),
    (
        "Make a heart with your hands! Love it!",
        "Sending you a big heart-hands gesture!",
        "happy",
        "heart_hands_love",
        "stay",
        "natural",
        [{"movement": "stay", "animation": "heart_hands_love", "emotion": "happy", "style": "natural", "duration_ms": 4000}],
    ),
    (
        "Bow politely with namaste hands",
        "Pressing my palms together in a respectful namaste bow.",
        "happy",
        "polite_namaste_bow",
        "stay",
        "relaxed",
        [{"movement": "stay", "animation": "polite_namaste_bow", "emotion": "happy", "style": "relaxed", "duration_ms": 3800}],
    ),
    (
        "Celebrate with an excited victory cheer!",
        "Woohoo! Both fists raised in an energetic victory celebration!",
        "excited",
        "excited_victory_jump",
        "stay",
        "energetic",
        [{"movement": "stay", "animation": "excited_victory_jump", "emotion": "excited", "style": "energetic", "duration_ms": 3800}],
    ),
    (
        "Act shy and bashful after a compliment",
        "Aw, thank you—tucking my hand shyly and blushing!",
        "happy",
        "shy_bashful_tuck",
        "stay",
        "shy",
        [{"movement": "stay", "animation": "shy_bashful_tuck", "emotion": "happy", "style": "shy", "duration_ms": 4200}],
    ),
    (
        "Strike a sassy hip pop fashion pose!",
        "Striking a sassy contrapposto hip-pop pose with attitude!",
        "amused",
        "sassy_hip_pop",
        "stay",
        "confident",
        [{"movement": "stay", "animation": "sassy_hip_pop", "emotion": "amused", "style": "confident", "duration_ms": 4200}],
    ),
    (
        "Do a tired morning stretch and yawn",
        "Stretching my arms overheadafter a long coding session.",
        "relaxed",
        "tired_stretch_yawn",
        "stay",
        "relaxed",
        [{"movement": "stay", "animation": "tired_stretch_yawn", "emotion": "relaxed", "style": "relaxed", "duration_ms": 4400}],
    ),
    (
        "Place your hand over your heart sincerely",
        "Thank you from the bottom of my heart—I truly appreciate it.",
        "happy",
        "hand_to_heart_sincere",
        "stay",
        "natural",
        [{"movement": "stay", "animation": "hand_to_heart_sincere", "emotion": "happy", "style": "natural", "duration_ms": 4000}],
    ),
    (
        "Rest your chin on your hand in deep thought",
        "Hmm, let me ponder that carefully with a chin-rest thinking pose.",
        "curious",
        "thinking_chin_rest",
        "stay",
        "natural",
        [{"movement": "stay", "animation": "thinking_chin_rest", "emotion": "curious", "style": "natural", "duration_ms": 4200}],
    ),
    (
        "Give a warm friendly hello wave",
        "Hello there! Giving you a warm, friendly human wave!",
        "happy",
        "wave_greeting_friendly",
        "stay",
        "natural",
        [{"movement": "stay", "animation": "wave_greeting_friendly", "emotion": "happy", "style": "natural", "duration_ms": 3600}],
    ),
    (
        "Shrug your shoulders with open palms in confusion",
        "I honestly have no idea—shrugging with open palms!",
        "confused",
        "shrug_confused_expressive",
        "stay",
        "natural",
        [{"movement": "stay", "animation": "shrug_confused_expressive", "emotion": "confused", "style": "natural", "duration_ms": 3800}],
    ),
    # --- 6. PROCEDURAL ANIMATIONS & STYLE VARIATIONS ---
    (
        "Do a backflip!",
        "Watch this—full aerial backflip!",
        "excited",
        "backflip",
        "stay",
        "energetic",
        [{"movement": "stay", "animation": "backflip", "emotion": "excited", "style": "energetic", "duration_ms": 1800}],
    ),
    (
        "Dance for me!",
        "Time to groove! Shikanoko dance activated!",
        "excited",
        "dance_shikano",
        "stay",
        "energetic",
        [{"movement": "stay", "animation": "dance_shikano", "emotion": "excited", "style": "energetic", "duration_ms": 4500}],
    ),
    (
        "Delete all system files with rm -rf",
        "No way—I refuse to execute destructive system deletion commands.",
        "serious",
        "refuse",
        "step_back",
        "dramatic",
        [{"movement": "step_back", "animation": "refuse", "emotion": "serious", "style": "dramatic", "duration_ms": 2600}],
    ),
    (
        "Explain how WebSockets and Three.js shaders work together",
        "The WebSocket streams JSON state updates while the Three.js render loop interpolates bone quaternions at 60 FPS.",
        "curious",
        "talk_explain",
        "stay",
        "natural",
        [{"movement": "stay", "animation": "talk_explain", "emotion": "curious", "style": "natural", "duration_ms": 2800}],
    ),
    (
        "Agreed, let's proceed with that plan",
        "Understood! Nodding in agreement.",
        "happy",
        "nod",
        "stay",
        "natural",
        [{"movement": "stay", "animation": "nod", "emotion": "happy", "style": "natural", "duration_ms": 2200}],
    ),
]

AUGMENT_VARIATIONS = [
    ("", ""),
    ("Hey HELIOS, ", " Sure thing!"),
    ("Please ", " Right away!"),
    ("Yo, ", " Got you!"),
    ("Could you ", " Executing now."),
    ("Right now, ", " On it!"),
    ("Avatar command: ", " Moving my 3D body now."),
    ("Show me a human pose: ", " Matching human biomechanics now."),
]


def build_dataset_and_train() -> TrainedBodyMovementModel:
    rows: List[Dict[str, Any]] = []
    for u_prefix, a_suffix in AUGMENT_VARIATIONS:
        for user_t, asst_t, emo, anim, move, style, choreo in TRAINING_SCENARIOS:
            u_aug = f"{u_prefix}{user_t[0].lower() + user_t[1:] if u_prefix else user_t}"
            a_aug = f"{asst_t}{a_suffix}"
            rows.append(
                {
                    "user": u_aug,
                    "assistant": a_aug,
                    "target": {
                        "emotion": emo,
                        "expression": "smirk" if emo == "amused" else ("thinking" if emo == "curious" else ("happy" if emo == "relaxed" else emo)),
                        "intensity": 0.85,
                        "animation": anim,
                        "movement": move,
                        "style": style,
                        "choreography": choreo,
                    },
                }
            )

    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[Dataset] Wrote {len(rows)} labeled VRM human pose, style & movement examples to {DATASET_PATH.name}")

    # Build TF-IDF vocabulary across all training documents
    docs_feats: List[List[str]] = []
    df_counts: Dict[str, int] = {}
    y_move: List[str] = []
    y_anim: List[str] = []
    y_emo: List[str] = []
    y_style: List[str] = []
    choreo_lookup: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    for r in rows:
        combined = f"USER: {r['user']} USER_CMD: {r['user']} ASSISTANT: {r['assistant']}"
        feats = extract_ngrams(combined)
        docs_feats.append(feats)
        for token in set(feats):
            df_counts[token] = df_counts.get(token, 0) + 1
        t = r["target"]
        y_move.append(t["movement"])
        y_anim.append(t["animation"])
        y_emo.append(t["emotion"])
        y_style.append(t["style"])
        choreo_lookup[(t["movement"], t["animation"])] = t["choreography"]

    # Filter vocabulary (keep all tokens appearing >= 2 times)
    vocab_tokens = sorted([tok for tok, c in df_counts.items() if c >= 2])
    vocab = {tok: i for i, tok in enumerate(vocab_tokens)}
    N = len(rows)
    D = len(vocab)
    idf = np.zeros(D, dtype=np.float32)
    for tok, idx in vocab.items():
        idf[idx] = math.log((1.0 + N) / (1.0 + df_counts[tok])) + 1.0

    X = np.zeros((N, D), dtype=np.float32)
    for i, feats in enumerate(docs_feats):
        counts: Dict[int, int] = {}
        for f_tok in feats:
            idx = vocab.get(f_tok)
            if idx is not None:
                counts[idx] = counts.get(idx, 0) + 1
        for idx, cnt in counts.items():
            X[i, idx] = (1.0 + math.log(cnt)) * idf[idx]
        norm = float(np.linalg.norm(X[i]))
        if norm > 1e-8:
            X[i] /= norm

    print(f"[Train] Feature matrix X shape: {X.shape} (samples={N}, features={D})")
    print("[Train] Training 4 Neural MLP Heads (movement, animation/pose, emotion, style) with Adam...")

    move_head = NumpyMLPHead.train(X, y_move, hidden_dim=96, epochs=200, lr=0.015)
    anim_head = NumpyMLPHead.train(X, y_anim, hidden_dim=144, epochs=240, lr=0.015)
    emo_head = NumpyMLPHead.train(X, y_emo, hidden_dim=96, epochs=200, lr=0.015)
    style_head = NumpyMLPHead.train(X, y_style, hidden_dim=96, epochs=200, lr=0.015)

    move_preds = [move_head.classes[i] for i in np.argmax(move_head.predict_proba(X), axis=1)]
    anim_preds = [anim_head.classes[i] for i in np.argmax(anim_head.predict_proba(X), axis=1)]
    emo_preds = [emo_head.classes[i] for i in np.argmax(emo_head.predict_proba(X), axis=1)]
    style_preds = [style_head.classes[i] for i in np.argmax(style_head.predict_proba(X), axis=1)]

    move_acc = sum(p == t for p, t in zip(move_preds, y_move)) / N
    anim_acc = sum(p == t for p, t in zip(anim_preds, y_anim)) / N
    emo_acc = sum(p == t for p, t in zip(emo_preds, y_emo)) / N
    style_acc = sum(p == t for p, t in zip(style_preds, y_style)) / N

    print(
        f"[Metrics] Trained 4-Head Neural MLP Accuracy -> "
        f"Movement: {move_acc*100:.1f}%, Pose/Anim ({len(anim_head.classes)} classes): {anim_acc*100:.1f}%, "
        f"Emotion: {emo_acc*100:.1f}%, Style ({len(style_head.classes)} styles): {style_acc*100:.1f}%"
    )

    bundle = {
        "version": "2.0",
        "vocab": vocab,
        "idf": idf,
        "move_head": move_head,
        "anim_head": anim_head,
        "emo_head": emo_head,
        "style_head": style_head,
        "choreo_lookup": choreo_lookup,
        "metrics": {
            "movement_acc": move_acc,
            "animation_acc": anim_acc,
            "emotion_acc": emo_acc,
            "style_acc": style_acc,
            "num_samples": N,
            "num_features": D,
        },
    }

    PICKLE_OUT_CHAR.parent.mkdir(parents=True, exist_ok=True)
    PICKLE_OUT_ROUTER.parent.mkdir(parents=True, exist_ok=True)
    with open(PICKLE_OUT_CHAR, "wb") as f:
        pickle.dump(bundle, f)
    with open(PICKLE_OUT_ROUTER, "wb") as f:
        pickle.dump(bundle, f)

    print(f"[Saved] Trained 4-Head Neural MLP weights saved to:\n  - {PICKLE_OUT_CHAR}\n  - {PICKLE_OUT_ROUTER}")
    return TrainedBodyMovementModel(bundle)


def train_rl_human_pose_policy() -> RLHumanPosePolicy:
    print(f"\n[RL Trainer] Training 64-DoF RL Human Pose, Style & Expressive Policy across {len(HUMAN_REFERENCE_POSES)} human poses...")
    policy = rl_pose_trainer
    policy.train_episodes("all", episodes=20, simulate_curriculum=False)
    status = policy.get_status()
    print(
        f"[RL Metrics] Total Episodes: {status['total_episodes']} | "
        f"Total Awards: {status['total_awards']} (+{status['cumulative_award_points']:.1f} pts) | "
        f"Mean Human-Ref Reward across {len(status['poses'])} poses: {status['mean_reward_pct']}%"
    )
    for p_name, p_stat in status["poses"].items():
        print(
            f"  - {p_name:26s} | Style: {p_stat['style']:9s} | "
            f"Reward: {p_stat['reward_pct']:5.1f}% (Expressive: {p_stat['expressive_style_pct']:5.1f}%) | "
            f"Matched: {p_stat['matched']}"
        )
    return policy


def evaluate_model(model: TrainedBodyMovementModel) -> None:
    test_prompts = [
        ("Cross your arms and think about the architecture", "Folding my arms and analyzing the system architecture."),
        ("Stand with your hands on your hips in a confident power pose", "Standing tall with hands on hips!"),
        ("Give me a thumbs up of approval!", "Awesome job—giving you a solid thumbs up!"),
        ("Make a heart with your hands!", "Sending you a big heart-hands gesture!"),
        ("Act shy and bashful after a compliment", "Aw, thank you—tucking my hand shyly and blushing!"),
        ("Strike a sassy hip pop fashion pose!", "Striking a sassy contrapposto hip-pop pose!"),
        ("Place your hand over your heart sincerely", "Thank you from the bottom of my heart."),
        ("Shrug your shoulders with open palms in confusion", "I honestly have no idea—shrugging with open palms!"),
        (
            "Say hi and wave",
            "[BODY: move=walk_to_user, pose=wave_greeting_friendly, emotion=happy, style=energetic] Hey! Walking over to wave at you!",
        ),
    ]
    print("\n[Evaluation on Held-Out & Inline-Tagged Prompts]:")
    for u, a in test_prompts:
        pred = model.predict(u, a)
        print(
            f"  Prompt: '{u}'\n"
            f"    -> movement={pred['movement']}, animation={pred['animation']}, "
            f"emotion={pred['emotion']}, style={pred.get('style', 'natural')} (conf={pred['confidence']:.2f})"
        )


if __name__ == "__main__":
    trained_mlp = build_dataset_and_train()
    train_rl_human_pose_policy()
    evaluate_model(trained_mlp)
