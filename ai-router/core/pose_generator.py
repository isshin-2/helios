"""
HELIOS Autonomous 3D VRM Pose Synthesizer & Kinematic Controller
================================================================
Built on open-source VRM AI avatar conventions from:
- `@pixiv/three-vrm` (VRM 0.x / 1.0 Normalized Humanoid Bone Specification)
- `pixiv/ChatVRM` & `tegnike/aituber-kit` (JSON EmoteController & Expression Blending)
- `semperai/amica` & `Open-LLM-VTuber` (LLM-driven Procedural Avatar Action Protocol)
- `Kalidokit` (Anatomical Joint Angle Clamping & 2-Bone IK Keypoint Mapping)

Allows HELIOS Core's AI to:
1. Control every normalized VRM humanoid bone (`hips`, `spine`, `chest`, `neck`, `head`,
   `leftShoulder`, `leftUpperArm`, `leftLowerArm`, `leftHand`, `rightShoulder`,
   `rightUpperArm`, `rightLowerArm`, `rightHand`, `leftUpperLeg`, `leftLowerLeg`,
   `leftFoot`, `rightUpperLeg`, `rightLowerLeg`, `rightFoot`),
2. Control 2-Bone IK hand targets (`leftWrist`, `rightWrist` relative to body anchors:
   `head`, `chest`, `hips`, `shoulder`) and finger/hand shapes (`open`, `fist`, `peace`,
   `point`, `cupped`, `clasped`, `antler`, `thumbs_up`, `rock_on`, `salute`, `relaxed`),
3. Synthesize brand-new custom poses and multi-keyframe animations on its own from natural
   language or LLM JSON output, and register them into the runtime Pose Library.
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

# Anatomical joint limits in degrees [min_x, max_x, min_y, max_y, min_z, max_z]
# following Kalidokit & @pixiv/three-vrm normalized T-pose conventions.
VRM_BONE_LIMITS_DEG: Dict[str, Tuple[float, float, float, float, float, float]] = {
    "hips": (-45.0, 45.0, -60.0, 60.0, -35.0, 35.0),
    "spine": (-45.0, 45.0, -45.0, 45.0, -35.0, 35.0),
    "chest": (-40.0, 40.0, -40.0, 40.0, -30.0, 30.0),
    "upperChest": (-30.0, 30.0, -30.0, 30.0, -25.0, 25.0),
    "neck": (-35.0, 35.0, -50.0, 50.0, -30.0, 30.0),
    "head": (-45.0, 45.0, -65.0, 65.0, -35.0, 35.0),
    "leftShoulder": (-25.0, 25.0, -25.0, 25.0, -35.0, 35.0),
    "rightShoulder": (-25.0, 25.0, -25.0, 25.0, -35.0, 35.0),
    "leftUpperArm": (-120.0, 120.0, -110.0, 110.0, -95.0, 95.0),
    "rightUpperArm": (-120.0, 120.0, -110.0, 110.0, -95.0, 95.0),
    "leftLowerArm": (-145.0, 145.0, -145.0, 145.0, -145.0, 145.0),
    "rightLowerArm": (-145.0, 145.0, -145.0, 145.0, -145.0, 145.0),
    "leftHand": (-70.0, 70.0, -70.0, 70.0, -70.0, 70.0),
    "rightHand": (-70.0, 70.0, -70.0, 70.0, -70.0, 70.0),
    "leftUpperLeg": (-125.0, 90.0, -60.0, 60.0, -60.0, 60.0),
    "rightUpperLeg": (-125.0, 90.0, -60.0, 60.0, -60.0, 60.0),
    "leftLowerLeg": (-150.0, 150.0, -35.0, 35.0, -25.0, 25.0),
    "rightLowerLeg": (-150.0, 150.0, -35.0, 35.0, -25.0, 25.0),
    "leftFoot": (-55.0, 55.0, -35.0, 35.0, -30.0, 30.0),
    "rightFoot": (-55.0, 55.0, -35.0, 35.0, -30.0, 30.0),
}

VALID_HAND_SHAPES = {
    "relaxed",
    "open",
    "fist",
    "peace",
    "point",
    "cupped",
    "clasped",
    "antler",
    "thumbs_up",
    "rock_on",
    "salute",
}


def clamp_bone_degrees(bone_name: str, xyz_deg: List[float]) -> List[float]:
    """Clamp Euler angles (in degrees) to safe anatomical VRM humanoid joint limits."""
    limits = VRM_BONE_LIMITS_DEG.get(bone_name)
    if not limits or len(xyz_deg) < 3:
        return [float(xyz_deg[0]), float(xyz_deg[1]), float(xyz_deg[2])] if len(xyz_deg) >= 3 else [0.0, 0.0, 0.0]
    x = max(limits[0], min(limits[1], float(xyz_deg[0])))
    y = max(limits[2], min(limits[3], float(xyz_deg[1])))
    z = max(limits[4], min(limits[5], float(xyz_deg[2])))
    return [round(x, 2), round(y, 2), round(z, 2)]


def sanitize_custom_pose(raw_pose: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize a custom VRM pose descriptor (either synthesized by HELIOS LLM
    or composed by the kinematic engine) into the normalized Character Protocol `custom_pose` format.
    """
    name = re.sub(r"[^a-z0-9_]", "_", str(raw_pose.get("name") or "helios_custom_pose").lower()).strip("_")
    if not name:
        name = "helios_custom_pose"

    description = str(raw_pose.get("description") or f"HELIOS synthesized pose: {name}")
    emotion = str(raw_pose.get("emotion") or "happy").lower()
    movement = str(raw_pose.get("movement") or "stay").lower()
    hips_offset_y = max(-0.42, min(0.55, float(raw_pose.get("hipsOffsetY", 0.0))))
    duration_ms = max(800, min(12000, int(raw_pose.get("duration_ms", 3800))))

    # Normalize & clamp direct humanoid bone rotations (in degrees)
    clean_bones: Dict[str, List[float]] = {}
    raw_bones = raw_pose.get("bones") or {}
    if isinstance(raw_bones, dict):
        for bone_name, rot in raw_bones.items():
            if bone_name in VRM_BONE_LIMITS_DEG and isinstance(rot, (list, tuple)) and len(rot) >= 3:
                clean_bones[bone_name] = clamp_bone_degrees(bone_name, list(rot[:3]))

    # Normalize 2-Bone IK targets (relative to body anchors: head, chest, hips, shoulder)
    clean_ik: Dict[str, Any] = {}
    raw_ik = raw_pose.get("ik") or {}
    if isinstance(raw_ik, dict):
        for hand_key in ("rightWrist", "leftWrist"):
            if hand_key in raw_ik and isinstance(raw_ik[hand_key], dict):
                t = raw_ik[hand_key]
                anchor = str(t.get("anchor") or "chest").lower()
                if anchor not in ("head", "chest", "hips", "shoulder"):
                    anchor = "chest"
                offset = t.get("offset") or [0.0, 0.0, 0.15]
                if isinstance(offset, (list, tuple)) and len(offset) >= 3:
                    hand_entry: Dict[str, Any] = {
                        "anchor": anchor,
                        "offset": [
                            max(-0.55, min(0.55, float(offset[0]))),
                            max(-0.55, min(0.55, float(offset[1]))),
                            max(-0.35, min(0.55, float(offset[2]))),
                        ],
                    }
                    for vec_key in ("pole", "fingerDir", "palmNormal"):
                        vec_val = t.get(vec_key)
                        if isinstance(vec_val, (list, tuple)) and len(vec_val) >= 3:
                            hand_entry[vec_key] = [
                                round(float(vec_val[0]), 3),
                                round(float(vec_val[1]), 3),
                                round(float(vec_val[2]), 3),
                            ]
                    clean_ik[hand_key] = hand_entry
        for shape_key in ("rightHandShape", "leftHandShape"):
            sh = str(raw_ik.get(shape_key) or raw_pose.get(shape_key) or "").lower()
            if sh in VALID_HAND_SHAPES:
                clean_ik[shape_key] = sh

    # Optional multi-keyframe animation sequence
    clean_keyframes: List[Dict[str, Any]] = []
    raw_keyframes = raw_pose.get("keyframes") or []
    if isinstance(raw_keyframes, list):
        for kf in raw_keyframes[:8]:
            if not isinstance(kf, dict):
                continue
            kf_bones: Dict[str, List[float]] = {}
            for b_name, rot in (kf.get("bones") or {}).items():
                if b_name in VRM_BONE_LIMITS_DEG and isinstance(rot, (list, tuple)) and len(rot) >= 3:
                    kf_bones[b_name] = clamp_bone_degrees(b_name, list(rot[:3]))
            kf_ik: Dict[str, Any] = {}
            if isinstance(kf.get("ik"), dict):
                for hk in ("rightWrist", "leftWrist"):
                    if hk in kf["ik"] and isinstance(kf["ik"][hk], dict):
                        t = kf["ik"][hk]
                        off = t.get("offset") or [0.0, 0.0, 0.15]
                        if isinstance(off, (list, tuple)) and len(off) >= 3:
                            hk_entry: Dict[str, Any] = {
                                "anchor": str(t.get("anchor") or "chest").lower(),
                                "offset": [float(off[0]), float(off[1]), float(off[2])],
                            }
                            for vec_key in ("pole", "fingerDir", "palmNormal"):
                                vec_val = t.get(vec_key)
                                if isinstance(vec_val, (list, tuple)) and len(vec_val) >= 3:
                                    hk_entry[vec_key] = [
                                        round(float(vec_val[0]), 3),
                                        round(float(vec_val[1]), 3),
                                        round(float(vec_val[2]), 3),
                                    ]
                            kf_ik[hk] = hk_entry
                for sk in ("rightHandShape", "leftHandShape"):
                    if sk in kf["ik"] and str(kf["ik"][sk]).lower() in VALID_HAND_SHAPES:
                        kf_ik[sk] = str(kf["ik"][sk]).lower()
            clean_keyframes.append(
                {
                    "duration_ms": max(250, min(5000, int(kf.get("duration_ms", 900)))),
                    "hipsOffsetY": max(-0.42, min(0.55, float(kf.get("hipsOffsetY", hips_offset_y)))),
                    "bones": kf_bones,
                    "ik": kf_ik,
                    "rightHandShape": kf_ik.get("rightHandShape", clean_ik.get("rightHandShape", "relaxed")),
                    "leftHandShape": kf_ik.get("leftHandShape", clean_ik.get("leftHandShape", "relaxed")),
                }
            )

    style = str(raw_pose.get("style") or "natural").lower()
    if style not in ("natural", "energetic", "confident", "relaxed", "shy", "dramatic"):
        style = "natural"

    result: Dict[str, Any] = {
        "name": name,
        "description": description,
        "emotion": emotion,
        "movement": movement,
        "style": style,
        "hipsOffsetY": round(hips_offset_y, 3),
        "duration_ms": duration_ms,
        "loop": bool(raw_pose.get("loop", False)),
        "rightHandShape": clean_ik.get("rightHandShape", "relaxed"),
        "leftHandShape": clean_ik.get("leftHandShape", "relaxed"),
        "bones": clean_bones,
        "ik": clean_ik,
        "keyframes": clean_keyframes,
    }
    for rl_key in ("rl_reward", "rl_reward_pct", "rl_matched", "rl_award_points", "rl_evaluation"):
        if rl_key in raw_pose:
            result[rl_key] = raw_pose[rl_key]
    return result


# ============================================================================
# Open-Source VRM Procedural Pose Templates (ChatVRM / Amica / Kalidokit style)
# Calibrated against human anatomical references (forearm-aligned wrists,
# physiological elbow poles, and balanced center-of-mass).
# ============================================================================
PROCEDURAL_POSE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "cyber_salute": {
        "name": "cyber_salute",
        "description": "Crisp tactical salute with right fingertips at right brow and left hand resting on hip",
        "emotion": "serious",
        "movement": "stay",
        "style": "confident",
        "hipsOffsetY": 0.0,
        "duration_ms": 4000,
        "bones": {
            "hips": [0, 3, 0],
            "spine": [-4, 0, 0],
            "chest": [-3, 2, 0],
            "head": [-2, -3, 2],
            "rightShoulder": [0, 0, 10],
        },
        "ik": {
            "rightWrist": {
                "anchor": "head",
                "offset": [0.155, -0.02, 0.115],
                "pole": [0.90, -0.10, 0.42],
                "fingerDir": [-0.74, 0.64, -0.20],
                "palmNormal": [-0.15, -0.45, 0.88],
            },
            "leftWrist": {
                "anchor": "hips",
                "offset": [0.135, 0.08, 0.045],
                "pole": [1.0, 0.08, -0.25],
                "fingerDir": [-0.35, -0.82, 0.45],
                "palmNormal": [-0.85, -0.25, -0.45],
            },
            "rightHandShape": "salute",
            "leftHandShape": "cupped",
        },
    },
    "superhero_landing": {
        "name": "superhero_landing",
        "description": "Deep three-point superhero landing crouch with right fist reaching to the ground and head glaring up at the camera",
        "emotion": "serious",
        "movement": "stay",
        "style": "dramatic",
        "hipsOffsetY": -0.32,
        "duration_ms": 4500,
        "loop": False,
        "bones": {
            "hips": [12, -12, 0],
            "spine": [20, 8, 0],
            "chest": [12, 6, 0],
            "neck": [-8, -4, 0],
            "head": [-12, -8, 3],
            "leftUpperLeg": [-68, 12, -6],
            "leftLowerLeg": [92, 0, 0],
            "leftFoot": [25, 0, 0],
            "rightUpperLeg": [-44, -10, 6],
            "rightLowerLeg": [88, 0, 0],
            "rightFoot": [22, 0, 0],
        },
        "ik": {
            "rightWrist": {
                "anchor": "shoulder",
                "offset": [-0.03, -0.36, 0.14],
                "pole": [0.35, -0.20, 0.85],
                "fingerDir": [-0.04, -0.96, 0.28],
                "palmNormal": [-0.85, 0.0, -0.52],
            },
            "leftWrist": {
                "anchor": "hips",
                "offset": [0.24, 0.06, -0.16],
                "pole": [0.85, 0.20, -0.45],
                "fingerDir": [0.45, -0.78, -0.42],
                "palmNormal": [-0.75, -0.25, -0.60],
            },
            "rightHandShape": "fist",
            "leftHandShape": "open",
        },
        "keyframes": [
            {
                "duration_ms": 360,
                "hipsOffsetY": 0.26,
                "bones": {
                    "spine": [-8, 0, 0],
                    "neck": [-6, 0, 0],
                    "head": [-8, 0, 0],
                    "leftUpperLeg": [-35, 0, -5],
                    "rightUpperLeg": [-35, 0, 5],
                    "leftLowerLeg": [55, 0, 0],
                    "rightLowerLeg": [55, 0, 0],
                },
                "ik": {
                    "rightWrist": {
                        "anchor": "head",
                        "offset": [0.18, 0.12, 0.08],
                        "pole": [0.85, -0.20, 0.38],
                        "fingerDir": [-0.10, 0.96, 0.20],
                        "palmNormal": [-0.30, 0.10, 0.94],
                    },
                    "leftWrist": {
                        "anchor": "head",
                        "offset": [0.18, 0.12, 0.08],
                        "pole": [0.85, -0.20, 0.38],
                        "fingerDir": [-0.10, 0.96, 0.20],
                        "palmNormal": [-0.30, 0.10, 0.94],
                    },
                    "rightHandShape": "fist",
                    "leftHandShape": "fist",
                },
            },
            {
                "duration_ms": 4000,
                "hipsOffsetY": -0.32,
                "bones": {
                    "hips": [12, -12, 0],
                    "spine": [20, 8, 0],
                    "chest": [12, 6, 0],
                    "neck": [-8, -4, 0],
                    "head": [-12, -8, 3],
                    "leftUpperLeg": [-68, 12, -6],
                    "leftLowerLeg": [92, 0, 0],
                    "leftFoot": [25, 0, 0],
                    "rightUpperLeg": [-44, -10, 6],
                    "rightLowerLeg": [88, 0, 0],
                    "rightFoot": [22, 0, 0],
                },
                "ik": {
                    "rightWrist": {
                        "anchor": "shoulder",
                        "offset": [-0.03, -0.36, 0.14],
                        "pole": [0.35, -0.20, 0.85],
                        "fingerDir": [-0.04, -0.96, 0.28],
                        "palmNormal": [-0.85, 0.0, -0.52],
                    },
                    "leftWrist": {
                        "anchor": "hips",
                        "offset": [0.24, 0.06, -0.16],
                        "pole": [0.85, 0.20, -0.45],
                        "fingerDir": [0.45, -0.78, -0.42],
                        "palmNormal": [-0.75, -0.25, -0.60],
                    },
                    "rightHandShape": "fist",
                    "leftHandShape": "open",
                },
            },
        ],
    },
    "martial_arts_guard": {
        "name": "martial_arts_guard",
        "description": "Orthodox martial arts combat stance with staggered lead left fist out front and rear right fist guarding the chin",
        "emotion": "serious",
        "movement": "stay",
        "style": "confident",
        "hipsOffsetY": -0.08,
        "duration_ms": 4200,
        "bones": {
            "hips": [6, -26, 0],
            "spine": [8, 16, 0],
            "chest": [6, 12, 0],
            "neck": [-4, -6, 0],
            "head": [4, -14, -4],
            "leftUpperLeg": [-26, 14, -8],
            "leftLowerLeg": [40, 0, 0],
            "leftFoot": [14, 0, 0],
            "rightUpperLeg": [-22, -16, 8],
            "rightLowerLeg": [36, 0, 0],
            "rightFoot": [12, 0, 0],
        },
        "ik": {
            "rightWrist": {
                "anchor": "head",
                "offset": [0.085, -0.115, 0.13],
                "pole": [0.42, -0.88, 0.28],
                "fingerDir": [-0.08, 0.96, 0.24],
                "palmNormal": [-0.86, 0.0, -0.51],
            },
            "leftWrist": {
                "anchor": "head",
                "offset": [0.08, -0.025, 0.28],
                "pole": [0.45, -0.85, 0.38],
                "fingerDir": [-0.06, 0.93, 0.35],
                "palmNormal": [-0.82, 0.0, -0.57],
            },
            "rightHandShape": "fist",
            "leftHandShape": "fist",
        },
    },
    "double_biceps_flex": {
        "name": "double_biceps_flex",
        "description": "Classic front double-biceps flex with elbows at shoulder height and fists curled inward toward the head",
        "emotion": "amused",
        "movement": "stay",
        "style": "energetic",
        "hipsOffsetY": -0.03,
        "duration_ms": 4000,
        "bones": {
            "hips": [-3, 0, 0],
            "spine": [-7, 0, 0],
            "chest": [-6, 0, 0],
            "head": [-5, 0, 3],
            "leftShoulder": [0, 0, -10],
            "rightShoulder": [0, 0, 10],
            "leftUpperLeg": [-8, 0, -5],
            "rightUpperLeg": [-8, 0, 5],
            "leftLowerLeg": [12, 0, 0],
            "rightLowerLeg": [12, 0, 0],
        },
        "ik": {
            "rightWrist": {
                "anchor": "head",
                "offset": [0.24, 0.06, 0.04],
                "pole": [0.95, -0.08, 0.28],
                "fingerDir": [-0.68, 0.72, 0.12],
                "palmNormal": [-0.86, -0.32, 0.40],
            },
            "leftWrist": {
                "anchor": "head",
                "offset": [0.24, 0.06, 0.04],
                "pole": [0.95, -0.08, 0.28],
                "fingerDir": [-0.68, 0.72, 0.12],
                "palmNormal": [-0.86, -0.32, 0.40],
            },
            "rightHandShape": "fist",
            "leftHandShape": "fist",
        },
    },
    "facepalm": {
        "name": "facepalm",
        "description": "Exasperated facepalm with right palm covering face/forehead and head bowed",
        "emotion": "concerned",
        "movement": "stay",
        "style": "dramatic",
        "hipsOffsetY": 0.0,
        "duration_ms": 3800,
        "bones": {
            "spine": [10, 0, -3],
            "chest": [6, 0, 0],
            "head": [18, 5, -6],
        },
        "ik": {
            "rightWrist": {
                "anchor": "head",
                "offset": [0.025, -0.055, 0.125],
                "pole": [0.55, -0.65, 0.52],
                "fingerDir": [-0.28, 0.92, -0.25],
                "palmNormal": [-0.15, -0.25, -0.95],
            },
            "leftWrist": {
                "anchor": "hips",
                "offset": [0.135, 0.08, 0.045],
                "pole": [1.0, 0.08, -0.25],
                "fingerDir": [-0.35, -0.82, 0.45],
                "palmNormal": [-0.85, -0.25, -0.45],
            },
            "rightHandShape": "cupped",
            "leftHandShape": "cupped",
        },
    },
    "zen_meditation": {
        "name": "zen_meditation",
        "description": "Calm hovering cyber-zen lotus posture with hands in prayer mudra at chest",
        "emotion": "relaxed",
        "movement": "stay",
        "style": "relaxed",
        "hipsOffsetY": 0.08,
        "duration_ms": 4500,
        "bones": {
            "spine": [-3, 0, 0],
            "chest": [-2, 0, 0],
            "head": [5, 0, 0],
            "leftUpperLeg": [-46, 20, -16],
            "leftLowerLeg": [85, 0, 0],
            "rightUpperLeg": [-46, -20, 16],
            "rightLowerLeg": [85, 0, 0],
        },
        "ik": {
            "rightWrist": {
                "anchor": "chest",
                "offset": [0.038, 0.04, 0.155],
                "pole": [0.70, -0.65, 0.30],
                "fingerDir": [-0.03, 0.98, 0.18],
                "palmNormal": [-0.98, 0.02, 0.18],
            },
            "leftWrist": {
                "anchor": "chest",
                "offset": [0.038, 0.04, 0.155],
                "pole": [0.70, -0.65, 0.30],
                "fingerDir": [-0.03, 0.98, 0.18],
                "palmNormal": [-0.98, 0.02, 0.18],
            },
            "rightHandShape": "open",
            "leftHandShape": "open",
        },
    },
    "point_forward": {
        "name": "point_forward",
        "description": "Dramatic forward point directly at the viewer with left hand on hip",
        "emotion": "amused",
        "movement": "stay",
        "style": "dramatic",
        "hipsOffsetY": 0.0,
        "duration_ms": 3800,
        "bones": {
            "hips": [0, -10, 0],
            "spine": [4, 10, 0],
            "chest": [4, 8, 0],
            "head": [-3, -8, 4],
        },
        "ik": {
            "rightWrist": {
                "anchor": "shoulder",
                "offset": [-0.02, -0.01, 0.35],
                "pole": [0.55, -0.75, 0.35],
                "fingerDir": [-0.05, 0.15, 0.98],
                "palmNormal": [-0.35, -0.92, 0.15],
            },
            "leftWrist": {
                "anchor": "hips",
                "offset": [0.135, 0.08, 0.045],
                "pole": [1.0, 0.08, -0.25],
                "fingerDir": [-0.35, -0.82, 0.45],
                "palmNormal": [-0.85, -0.25, -0.45],
            },
            "rightHandShape": "point",
            "leftHandShape": "cupped",
        },
    },
    "hands_up_surrender": {
        "name": "hands_up_surrender",
        "description": "Playful 'hands up / caught red-handed' pose with both open palms raised facing forward",
        "emotion": "amused",
        "movement": "step_back",
        "style": "dramatic",
        "hipsOffsetY": 0.0,
        "duration_ms": 3800,
        "bones": {
            "spine": [-5, 0, 0],
            "head": [-3, 0, 5],
        },
        "ik": {
            "rightWrist": {
                "anchor": "head",
                "offset": [0.20, 0.03, 0.10],
                "pole": [0.85, -0.35, 0.35],
                "fingerDir": [0.08, 0.98, 0.12],
                "palmNormal": [-0.15, 0.08, 0.98],
            },
            "leftWrist": {
                "anchor": "head",
                "offset": [0.20, 0.03, 0.10],
                "pole": [0.85, -0.35, 0.35],
                "fingerDir": [0.08, 0.98, 0.12],
                "palmNormal": [-0.15, 0.08, 0.98],
            },
            "rightHandShape": "open",
            "leftHandShape": "open",
        },
    },
    "cyber_dab": {
        "name": "cyber_dab",
        "description": "Sharp angled cyber-dab with head tucked into left elbow and right arm extended high",
        "emotion": "excited",
        "movement": "stay",
        "style": "energetic",
        "hipsOffsetY": -0.03,
        "duration_ms": 3600,
        "bones": {
            "hips": [4, 10, -4],
            "spine": [10, -10, -6],
            "chest": [6, -6, -4],
            "head": [22, 26, -12],
        },
        "ik": {
            "leftWrist": {
                "anchor": "head",
                "offset": [-0.05, 0.01, 0.15],
                "pole": [0.95, -0.10, 0.35],
                "fingerDir": [-0.88, 0.42, -0.20],
                "palmNormal": [0.0, -0.35, -0.93],
            },
            "rightWrist": {
                "anchor": "shoulder",
                "offset": [0.31, 0.17, -0.04],
                "pole": [0.70, -0.50, -0.35],
                "fingerDir": [0.82, 0.55, -0.12],
                "palmNormal": [0.0, -0.50, 0.86],
            },
            "leftHandShape": "open",
            "rightHandShape": "open",
        },
    },
    "rock_on_pose": {
        "name": "rock_on_pose",
        "description": "Cyberpunk rockstar stance throwing up rock horns",
        "emotion": "excited",
        "movement": "stay",
        "style": "energetic",
        "hipsOffsetY": -0.04,
        "duration_ms": 4000,
        "bones": {
            "hips": [-4, -10, 4],
            "spine": [-7, 8, 5],
            "head": [-8, -6, 8],
            "leftUpperLeg": [-12, 0, -6],
            "rightUpperLeg": [-12, 0, 6],
            "leftLowerLeg": [18, 0, 0],
            "rightLowerLeg": [18, 0, 0],
        },
        "ik": {
            "rightWrist": {
                "anchor": "head",
                "offset": [0.18, 0.10, 0.13],
                "pole": [0.85, -0.15, 0.40],
                "fingerDir": [0.10, 0.98, 0.15],
                "palmNormal": [-0.20, 0.08, 0.97],
            },
            "leftWrist": {
                "anchor": "hips",
                "offset": [0.135, 0.08, 0.045],
                "pole": [1.0, 0.08, -0.25],
                "fingerDir": [-0.35, -0.82, 0.45],
                "palmNormal": [-0.85, -0.25, -0.45],
            },
            "rightHandShape": "rock_on",
            "leftHandShape": "cupped",
        },
    },
    "crossed_arms_think": {
        "name": "crossed_arms_think",
        "description": "Classic human crossed-arms posture across chest with weight shifted onto one hip and analytical head tilt",
        "emotion": "curious",
        "movement": "stay",
        "style": "confident",
        "hipsOffsetY": 0.0,
        "duration_ms": 4000,
        "bones": {
            "hips": [0, 6, 4],
            "spine": [-3, -4, -3],
            "chest": [-2, -2, 0],
            "neck": [2, 3, -4],
            "head": [4, 5, -7],
            "leftUpperLeg": [-5, 0, -3],
            "rightUpperLeg": [0, 0, 2],
            "leftLowerLeg": [9, 0, 0],
        },
        "ik": {
            "rightWrist": {
                "anchor": "chest",
                "offset": [-0.11, -0.02, 0.16],
                "pole": [0.78, -0.58, 0.35],
                "fingerDir": [-0.88, 0.25, -0.38],
                "palmNormal": [-0.25, -0.35, -0.90],
            },
            "leftWrist": {
                "anchor": "chest",
                "offset": [-0.11, -0.045, 0.145],
                "pole": [0.78, -0.58, 0.35],
                "fingerDir": [-0.88, 0.22, -0.40],
                "palmNormal": [-0.25, -0.35, -0.90],
            },
            "rightHandShape": "cupped",
            "leftHandShape": "cupped",
        },
    },
    "hands_on_hips_power": {
        "name": "hands_on_hips_power",
        "description": "Heroic human akimbo power stance with both hands resting on hips, elbows flared out, and proud lifted chest",
        "emotion": "happy",
        "movement": "stay",
        "style": "confident",
        "hipsOffsetY": 0.0,
        "duration_ms": 4000,
        "bones": {
            "hips": [-2, 0, 2],
            "spine": [-5, 0, 0],
            "chest": [-5, 0, 0],
            "neck": [-2, 0, 0],
            "head": [-4, -4, 3],
            "leftUpperLeg": [-4, 0, -5],
            "rightUpperLeg": [-4, 0, 5],
            "leftLowerLeg": [7, 0, 0],
            "rightLowerLeg": [7, 0, 0],
        },
        "ik": {
            "rightWrist": {
                "anchor": "hips",
                "offset": [0.135, 0.085, 0.045],
                "pole": [1.0, 0.10, -0.22],
                "fingerDir": [-0.35, -0.82, 0.45],
                "palmNormal": [-0.85, -0.25, -0.45],
            },
            "leftWrist": {
                "anchor": "hips",
                "offset": [0.135, 0.085, 0.045],
                "pole": [1.0, 0.10, -0.22],
                "fingerDir": [-0.35, -0.82, 0.45],
                "palmNormal": [-0.85, -0.25, -0.45],
            },
            "rightHandShape": "cupped",
            "leftHandShape": "cupped",
        },
    },
    "thumbs_up_approval": {
        "name": "thumbs_up_approval",
        "description": "Encouraging human thumbs-up approval gesture at chest-shoulder height with warm smile and nod",
        "emotion": "happy",
        "movement": "stay",
        "style": "energetic",
        "hipsOffsetY": 0.0,
        "duration_ms": 3800,
        "bones": {
            "hips": [0, -6, 2],
            "spine": [-3, 5, 2],
            "chest": [-2, 4, 0],
            "head": [-3, -5, 6],
        },
        "ik": {
            "rightWrist": {
                "anchor": "chest",
                "offset": [0.16, 0.08, 0.24],
                "pole": [0.65, -0.68, 0.32],
                "fingerDir": [-0.15, 0.45, 0.88],
                "palmNormal": [-0.96, 0.08, -0.24],
            },
            "leftWrist": {
                "anchor": "hips",
                "offset": [0.135, 0.08, 0.045],
                "pole": [1.0, 0.08, -0.25],
                "fingerDir": [-0.35, -0.82, 0.45],
                "palmNormal": [-0.85, -0.25, -0.45],
            },
            "rightHandShape": "thumbs_up",
            "leftHandShape": "cupped",
        },
    },
    "heart_hands_love": {
        "name": "heart_hands_love",
        "description": "Affectionate human heart-hands gesture held at upper chest with warm head tilt and smile",
        "emotion": "happy",
        "movement": "stay",
        "style": "energetic",
        "hipsOffsetY": 0.0,
        "duration_ms": 4000,
        "bones": {
            "hips": [0, 0, 3],
            "spine": [-2, 0, -2],
            "chest": [-2, 0, 0],
            "head": [-3, 0, 9],
            "leftShoulder": [0, 0, -6],
            "rightShoulder": [0, 0, 6],
        },
        "ik": {
            "rightWrist": {
                "anchor": "chest",
                "offset": [0.052, 0.095, 0.175],
                "pole": [0.75, -0.58, 0.35],
                "fingerDir": [-0.38, 0.88, 0.26],
                "palmNormal": [-0.72, -0.15, 0.68],
            },
            "leftWrist": {
                "anchor": "chest",
                "offset": [0.052, 0.095, 0.175],
                "pole": [0.75, -0.58, 0.35],
                "fingerDir": [-0.38, 0.88, 0.26],
                "palmNormal": [-0.72, -0.15, 0.68],
            },
            "rightHandShape": "cupped",
            "leftHandShape": "cupped",
        },
    },
    "polite_namaste_bow": {
        "name": "polite_namaste_bow",
        "description": "Respectful human bow with palms pressed together in front of chest and warm forward inclination",
        "emotion": "happy",
        "movement": "stay",
        "style": "natural",
        "hipsOffsetY": -0.02,
        "duration_ms": 3800,
        "bones": {
            "hips": [8, 0, 0],
            "spine": [14, 0, 0],
            "chest": [8, 0, 0],
            "neck": [6, 0, 0],
            "head": [8, 0, 0],
        },
        "ik": {
            "rightWrist": {
                "anchor": "chest",
                "offset": [0.036, 0.035, 0.16],
                "pole": [0.68, -0.65, 0.32],
                "fingerDir": [-0.03, 0.98, 0.18],
                "palmNormal": [-0.98, 0.02, 0.18],
            },
            "leftWrist": {
                "anchor": "chest",
                "offset": [0.036, 0.035, 0.16],
                "pole": [0.68, -0.65, 0.32],
                "fingerDir": [-0.03, 0.98, 0.18],
                "palmNormal": [-0.98, 0.02, 0.18],
            },
            "rightHandShape": "open",
            "leftHandShape": "open",
        },
    },
    "excited_victory_jump": {
        "name": "excited_victory_jump",
        "description": "Celebratory human victory fist-pump into the air with left fist pulled to chest and joyful bounce",
        "emotion": "excited",
        "movement": "stay",
        "style": "energetic",
        "hipsOffsetY": 0.07,
        "duration_ms": 3800,
        "bones": {
            "hips": [-4, -8, 3],
            "spine": [-6, 6, 4],
            "chest": [-5, 4, 0],
            "head": [-6, -4, 5],
            "rightShoulder": [0, 0, 14],
            "leftUpperLeg": [-18, 0, -5],
            "leftLowerLeg": [32, 0, 0],
            "rightUpperLeg": [-10, 0, 5],
            "rightLowerLeg": [18, 0, 0],
        },
        "ik": {
            "rightWrist": {
                "anchor": "head",
                "offset": [0.19, 0.15, 0.10],
                "pole": [0.85, -0.15, 0.38],
                "fingerDir": [-0.04, 0.98, 0.18],
                "palmNormal": [-0.82, 0.0, -0.56],
            },
            "leftWrist": {
                "anchor": "chest",
                "offset": [0.14, 0.02, 0.15],
                "pole": [0.68, -0.68, 0.28],
                "fingerDir": [-0.25, 0.88, 0.40],
                "palmNormal": [-0.85, -0.15, -0.50],
            },
            "rightHandShape": "fist",
            "leftHandShape": "fist",
        },
    },
    "shy_bashful_tuck": {
        "name": "shy_bashful_tuck",
        "description": "Bashful human posture with inward-rolled shoulders, hands clasped gently at lower chest, and shy tilted head",
        "emotion": "happy",
        "movement": "stay",
        "style": "shy",
        "hipsOffsetY": -0.01,
        "duration_ms": 4000,
        "bones": {
            "hips": [2, 5, -3],
            "spine": [5, -3, 2],
            "chest": [4, 0, 0],
            "neck": [6, 4, -5],
            "head": [10, 8, -9],
            "leftShoulder": [0, 6, 4],
            "rightShoulder": [0, -6, -4],
            "leftUpperLeg": [-4, -6, 3],
            "rightUpperLeg": [-4, 6, -3],
        },
        "ik": {
            "rightWrist": {
                "anchor": "chest",
                "offset": [0.042, -0.06, 0.145],
                "pole": [0.52, -0.78, 0.32],
                "fingerDir": [-0.42, 0.72, 0.55],
                "palmNormal": [-0.78, -0.25, -0.56],
            },
            "leftWrist": {
                "anchor": "chest",
                "offset": [0.042, -0.06, 0.145],
                "pole": [0.52, -0.78, 0.32],
                "fingerDir": [-0.42, 0.72, 0.55],
                "palmNormal": [-0.78, -0.25, -0.56],
            },
            "rightHandShape": "clasped",
            "leftHandShape": "clasped",
        },
    },
    "sassy_hip_pop": {
        "name": "sassy_hip_pop",
        "description": "Expressive human contrapposto hip-pop with left hand on hip, right hand gesturing near shoulder, and playful smirk",
        "emotion": "amused",
        "movement": "stay",
        "style": "dramatic",
        "hipsOffsetY": -0.01,
        "duration_ms": 4000,
        "bones": {
            "hips": [-2, -10, -7],
            "spine": [-4, 8, 6],
            "chest": [-3, 5, 4],
            "neck": [-2, -4, 4],
            "head": [-4, -6, 8],
            "leftUpperLeg": [-8, 0, 4],
            "leftLowerLeg": [14, 0, 0],
            "rightUpperLeg": [0, 0, -4],
        },
        "ik": {
            "rightWrist": {
                "anchor": "head",
                "offset": [0.16, -0.08, 0.14],
                "pole": [0.80, -0.52, 0.35],
                "fingerDir": [-0.20, 0.86, 0.46],
                "palmNormal": [-0.35, 0.45, 0.82],
            },
            "leftWrist": {
                "anchor": "hips",
                "offset": [0.14, 0.09, 0.045],
                "pole": [1.0, 0.12, -0.22],
                "fingerDir": [-0.35, -0.82, 0.45],
                "palmNormal": [-0.85, -0.25, -0.45],
            },
            "rightHandShape": "open",
            "leftHandShape": "cupped",
        },
    },
    "tired_stretch_yawn": {
        "name": "tired_stretch_yawn",
        "description": "Full-body human overhead stretch with both arms raised high and thoracic extension",
        "emotion": "relaxed",
        "movement": "stay",
        "style": "relaxed",
        "hipsOffsetY": 0.01,
        "duration_ms": 4200,
        "bones": {
            "hips": [-4, 0, 0],
            "spine": [-9, 0, 0],
            "chest": [-8, 0, 0],
            "neck": [-5, 0, 3],
            "head": [-8, 0, 6],
            "leftShoulder": [0, 0, -14],
            "rightShoulder": [0, 0, 14],
        },
        "ik": {
            "rightWrist": {
                "anchor": "head",
                "offset": [0.16, 0.17, 0.05],
                "pole": [0.90, -0.10, 0.35],
                "fingerDir": [0.12, 0.98, 0.14],
                "palmNormal": [-0.25, 0.10, 0.96],
            },
            "leftWrist": {
                "anchor": "head",
                "offset": [0.16, 0.17, 0.05],
                "pole": [0.90, -0.10, 0.35],
                "fingerDir": [0.12, 0.98, 0.14],
                "palmNormal": [-0.25, 0.10, 0.96],
            },
            "rightHandShape": "open",
            "leftHandShape": "open",
        },
    },
    "hand_to_heart_sincere": {
        "name": "hand_to_heart_sincere",
        "description": "Sincere human gratitude gesture with right palm resting gently over chest/heart and warm forward lean",
        "emotion": "happy",
        "movement": "stay",
        "style": "natural",
        "hipsOffsetY": 0.0,
        "duration_ms": 3800,
        "bones": {
            "spine": [4, 0, 0],
            "chest": [3, 0, 0],
            "neck": [2, 0, 3],
            "head": [3, 0, 6],
        },
        "ik": {
            "rightWrist": {
                "anchor": "chest",
                "offset": [-0.02, 0.05, 0.14],
                "pole": [0.75, -0.58, 0.35],
                "fingerDir": [-0.78, 0.58, 0.22],
                "palmNormal": [-0.20, -0.25, -0.95],
            },
            "leftWrist": {
                "anchor": "hips",
                "offset": [0.135, 0.08, 0.045],
                "pole": [1.0, 0.08, -0.25],
                "fingerDir": [-0.35, -0.82, 0.45],
                "palmNormal": [-0.85, -0.25, -0.45],
            },
            "rightHandShape": "cupped",
            "leftHandShape": "relaxed",
        },
    },
    "thinking_chin_rest": {
        "name": "thinking_chin_rest",
        "description": "Deep human contemplation with left forearm folded across torso supporting right elbow and right hand resting on chin",
        "emotion": "curious",
        "movement": "stay",
        "style": "natural",
        "hipsOffsetY": 0.0,
        "duration_ms": 4000,
        "bones": {
            "hips": [0, 4, 2],
            "spine": [3, -3, 0],
            "chest": [2, 0, 0],
            "neck": [4, -3, -3],
            "head": [6, -5, -6],
        },
        "ik": {
            "rightWrist": {
                "anchor": "head",
                "offset": [0.035, -0.105, 0.125],
                "pole": [0.45, -0.82, 0.35],
                "fingerDir": [-0.22, 0.94, 0.25],
                "palmNormal": [-0.75, -0.18, -0.63],
            },
            "leftWrist": {
                "anchor": "chest",
                "offset": [-0.09, -0.05, 0.15],
                "pole": [0.75, -0.60, 0.32],
                "fingerDir": [-0.88, 0.20, -0.42],
                "palmNormal": [-0.20, 0.65, -0.73],
            },
            "rightHandShape": "chinTouch",
            "leftHandShape": "cupped",
        },
    },
    "wave_greeting_friendly": {
        "name": "wave_greeting_friendly",
        "description": "Warm human open-palm greeting wave at shoulder/head height with friendly body lean",
        "emotion": "happy",
        "movement": "stay",
        "style": "energetic",
        "hipsOffsetY": 0.0,
        "duration_ms": 3800,
        "bones": {
            "hips": [0, -4, 3],
            "spine": [-2, 4, 3],
            "chest": [-2, 3, 2],
            "head": [-3, -3, 6],
            "rightShoulder": [0, 0, 8],
        },
        "ik": {
            "rightWrist": {
                "anchor": "head",
                "offset": [0.19, -0.02, 0.14],
                "pole": [0.85, -0.32, 0.40],
                "fingerDir": [0.12, 0.97, 0.20],
                "palmNormal": [-0.18, 0.12, 0.97],
            },
            "leftWrist": {
                "anchor": "hips",
                "offset": [0.135, 0.08, 0.045],
                "pole": [1.0, 0.08, -0.25],
                "fingerDir": [-0.35, -0.82, 0.45],
                "palmNormal": [-0.85, -0.25, -0.45],
            },
            "rightHandShape": "open",
            "leftHandShape": "cupped",
        },
    },
    "shrug_confused_expressive": {
        "name": "shrug_confused_expressive",
        "description": "Expressive human 'who knows?' shrug with raised shoulders, tucked elbows, and supinated open palms out to the sides",
        "emotion": "confused",
        "movement": "stay",
        "style": "dramatic",
        "hipsOffsetY": 0.0,
        "duration_ms": 3800,
        "bones": {
            "spine": [-2, 0, 0],
            "chest": [-2, 0, 0],
            "neck": [2, 0, 4],
            "head": [3, -4, 10],
            "leftShoulder": [0, 0, -11],
            "rightShoulder": [0, 0, 11],
        },
        "ik": {
            "rightWrist": {
                "anchor": "chest",
                "offset": [0.24, 0.03, 0.15],
                "pole": [0.48, -0.82, -0.25],
                "fingerDir": [0.68, 0.52, 0.51],
                "palmNormal": [-0.15, 0.78, 0.60],
            },
            "leftWrist": {
                "anchor": "chest",
                "offset": [0.24, 0.03, 0.15],
                "pole": [0.48, -0.82, -0.25],
                "fingerDir": [0.68, 0.52, 0.51],
                "palmNormal": [-0.15, 0.78, 0.60],
            },
            "rightHandShape": "open",
            "leftHandShape": "open",
        },
    },
}


INLINE_POSE_TAG_RE = re.compile(r"\[POSE_JSON:\s*(\{.*?\})\s*\]", re.IGNORECASE | re.DOTALL)


class HELIOSPoseGenerator:
    """
    Synthesizes custom 3D VRM poses & multi-keyframe animations from:
    1. Explicit `[POSE_JSON: {...}]` blocks emitted by HELIOS Core's LLM,
    2. Semantic natural-language kinematic composition (combining arbitrary arm, leg,
       torso, head, and hand instructions into a unified `custom_pose`), or
    3. On-demand LLM pose synthesis via Ollama (`llama3.2:3b` / `helios-avatar:latest`).
    """

    def __init__(self) -> None:
        self.custom_pose_registry: Dict[str, Dict[str, Any]] = {
            k: sanitize_custom_pose(v) for k, v in PROCEDURAL_POSE_TEMPLATES.items()
        }

    def list_template_names(self) -> List[str]:
        """Return the list of all registered template & custom pose names."""
        return list(self.custom_pose_registry.keys())

    def get_library(self) -> List[Dict[str, Any]]:
        """Return all registered procedural & AI-synthesized custom poses."""
        return list(self.custom_pose_registry.values())

    def extract_inline_pose_json(self, text: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Extract and strip `[POSE_JSON: {...}]` emitted directly by HELIOS."""
        if not text:
            return "", None
        m = INLINE_POSE_TAG_RE.search(text)
        if not m:
            return text, None
        raw_json = m.group(1)
        clean_text = INLINE_POSE_TAG_RE.sub("", text).strip()
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                pose = sanitize_custom_pose(parsed)
                self.custom_pose_registry[pose["name"]] = pose
                return clean_text, pose
        except Exception:
            pass
        return clean_text, None

    def _attach_rl_evaluation(self, pose: Dict[str, Any], prompt_hint: str = "") -> Dict[str, Any]:
        """Evaluate and refine a synthesized pose against HUMAN_REFERENCE_POSES via the RL policy."""
        try:
            from .rl_pose_trainer import rl_pose_trainer

            refined = rl_pose_trainer.evaluate_and_refine_pose(
                pose, prompt_hint=prompt_hint or pose.get("name", ""), auto_train_if_low=True
            )
            self.custom_pose_registry[refined["name"]] = refined
            return refined
        except Exception:
            self.custom_pose_registry[pose["name"]] = pose
            return pose

    def match_or_compose_pose(
        self,
        user_text: str = "",
        assistant_text: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Check if the user or HELIOS is requesting or describing a custom/novel pose
        (either a template like salute/superhero landing/karate/flex/facepalm/meditate/dab/point/surrender,
        or a compositional kinematic instruction like 'raise your left hand and look right').
        """
        combined = f"{user_text or ''} {assistant_text or ''}".lower().strip()
        if not combined:
            return None

        # 1. Check inline [POSE_JSON: {...}] first
        _, inline_pose = self.extract_inline_pose_json(assistant_text or "")
        if inline_pose:
            return self._attach_rl_evaluation(inline_pose, combined)

        # 1b. Direct template key lookup (e.g. "cyber_salute" or "superhero_landing")
        clean_key = re.sub(r"[^a-z0-9_]", "_", combined).strip("_")
        if clean_key in PROCEDURAL_POSE_TEMPLATES:
            pose = sanitize_custom_pose(PROCEDURAL_POSE_TEMPLATES[clean_key])
            return self._attach_rl_evaluation(pose, clean_key)
        for t_key, t_spec in PROCEDURAL_POSE_TEMPLATES.items():
            if t_key in combined or t_key.replace("_", " ") in combined:
                pose = sanitize_custom_pose(t_spec)
                return self._attach_rl_evaluation(pose, t_key)

        # 2. Check high-precision procedural pose templates
        norm_user = (user_text or "").replace("_", " ")
        norm_asst = (assistant_text or "").replace("_", " ")
        template_triggers: List[Tuple[re.Pattern, str]] = [
            (re.compile(r"\b(salute|at\s+attention|reporting\s+for\s+duty|aye\s+aye)\b", re.I), "cyber_salute"),
            (re.compile(r"\b(superhero\s+landing|hero\s+landing|three\s+point\s+landing|iron\s+man\s+landing)\b", re.I), "superhero_landing"),
            (re.compile(r"\b(karate|martial\s+arts|martial\s+guard|fighting\s+stance|combat\s+stance|kung\s+fu|boxer|boxing\s+guard)\b", re.I), "martial_arts_guard"),
            (re.compile(r"\b(flex|biceps|muscle|bodybuilder|strong\s+pose|show\s+your\s+strength)\b", re.I), "double_biceps_flex"),
            (re.compile(r"\b(facepalm|palm\s+to\s+face|oh\s+god\s+why|smh)\b", re.I), "facepalm"),
            (re.compile(r"\b(meditat\w*|zen\s+pose|zen\s+lotus|lotus\s+pose|inner\s+peace)\b", re.I), "zen_meditation"),
            (re.compile(r"\b(point\s+at\s+me|point\s+forward|objection|you\s+there)\b", re.I), "point_forward"),
            (re.compile(r"\b(hands\s+up|surrender|don't\s+shoot|i\s+give\s+up|freeze)\b", re.I), "hands_up_surrender"),
            (re.compile(r"\b(dab|hit\s+the\s+dab|dabbing)\b", re.I), "cyber_dab"),
            (re.compile(r"\b(rock\s+on|metal\s+horns|rockstar|devil\s+horns)\b", re.I), "rock_on_pose"),
            (re.compile(r"\b(cross\s+(your\s+)?arms|crossed\s+arms|fold\s+(your\s+)?arms|arms\s+folded)\b", re.I), "crossed_arms_think"),
            (re.compile(r"\b(hands\s+on\s+(your\s+)?hips|power\s+pose|power\s+stance|akimbo|wonder\s+woman\s+pose)\b", re.I), "hands_on_hips_power"),
            (re.compile(r"\b(thumbs\s+up|good\s+job|nice\s+work|approve|approval)\b", re.I), "thumbs_up_approval"),
            (re.compile(r"\b(heart\s+hands|finger\s+heart|make\s+a\s+heart|love\s+you|send\s+love)\b", re.I), "heart_hands_love"),
            (re.compile(r"\b(namaste|polite\s+bow|respectful\s+bow|prayer\s+bow)\b", re.I), "polite_namaste_bow"),
            (re.compile(r"\b(victory\s+jump|fist\s+pump|we\s+won|victory\s+pose)\b", re.I), "excited_victory_jump"),
            (re.compile(r"\b(bashful|shy\s+pose|acting\s+shy|flustered|blushing)\b", re.I), "shy_bashful_tuck"),
            (re.compile(r"\b(sassy|hip\s+pop|contrapposto|diva\s+pose|attitude\s+pose)\b", re.I), "sassy_hip_pop"),
            (re.compile(r"\b(stretch|stretching|morning\s+stretch|tired\s+stretch|yawn)\b", re.I), "tired_stretch_yawn"),
            (re.compile(r"\b(hand\s+(to|on|over)\s+heart|sincere|my\s+heart|thank\s+you\s+so\s+much|honored)\b", re.I), "hand_to_heart_sincere"),
            (re.compile(r"\b(chin\s+rest|rodin|the\s+thinker|deep\s+in\s+thought|pondering)\b", re.I), "thinking_chin_rest"),
            (re.compile(r"\b(friendly\s+wave|warm\s+wave|wave\s+hello\s+to\s+me)\b", re.I), "wave_greeting_friendly"),
            (re.compile(r"\b(expressive\s+shrug|big\s+shrug|i\s+have\s+no\s+idea)\b", re.I), "shrug_confused_expressive"),
        ]
        for pattern, key in template_triggers:
            if pattern.search(norm_user) or pattern.search(norm_asst):
                pose = sanitize_custom_pose(PROCEDURAL_POSE_TEMPLATES[key])
                return self._attach_rl_evaluation(pose, key)

        # 3. Compositional Kinematic Pose Builder for arbitrary body part instructions!
        # e.g., "raise your left arm, put right hand on hip, crouch down, and look left"
        if re.search(
            r"\b(make\s+a\s+pose|create\s+a\s+pose|strike\s+a\s+pose|custom\s+pose|new\s+pose|"
            r"raise\s+(your\s+)?(left|right|both)\s+(arm|hand)|"
            r"put\s+(your\s+)?(left|right|both)\s+hand|"
            r"crouch|squat|kneel|lean\s+(forward|back|left|right)|"
            r"tilt\s+(your\s+)?head|look\s+(left|right|up|down)|"
            r"thumbs\s+up|pose\s+on\s+your\s+own)\b",
            combined,
            re.I,
        ):
            return self.compose_kinematic_pose_from_text(user_text or assistant_text)

        return None

    def compose_kinematic_pose_from_text(self, text: str) -> Dict[str, Any]:
        """
        Synthesize a normalized VRM humanoid bone + 2-Bone IK pose directly from
        natural-language anatomical instructions with human-referenced wrist & pole vectors.
        """
        t = (text or "").lower()
        bones: Dict[str, List[float]] = {
            "hips": [0.0, 0.0, 0.0],
            "spine": [0.0, 0.0, 0.0],
            "chest": [0.0, 0.0, 0.0],
            "neck": [0.0, 0.0, 0.0],
            "head": [0.0, 0.0, 0.0],
            "leftUpperLeg": [0.0, 0.0, -2.0],
            "rightUpperLeg": [0.0, 0.0, 2.0],
            "leftLowerLeg": [0.0, 0.0, 0.0],
            "rightLowerLeg": [0.0, 0.0, 0.0],
            "leftFoot": [0.0, 0.0, 0.0],
            "rightFoot": [0.0, 0.0, 0.0],
        }
        ik: Dict[str, Any] = {
            "rightWrist": {
                "anchor": "chest",
                "offset": [0.13, 0.05, 0.17],
                "pole": [0.68, -0.65, 0.35],
                "fingerDir": [-0.25, 0.65, 0.72],
                "palmNormal": [-0.50, 0.45, 0.74],
            },
            "leftWrist": {
                "anchor": "hips",
                "offset": [0.135, 0.08, 0.045],
                "pole": [1.0, 0.08, -0.25],
                "fingerDir": [-0.35, -0.82, 0.45],
                "palmNormal": [-0.85, -0.25, -0.45],
            },
            "rightHandShape": "open",
            "leftHandShape": "cupped",
        }
        hips_y = 0.0
        emotion = "amused"

        # Crouch / squat / jump
        if re.search(r"\b(crouch|squat|kneel|low)\b", t):
            hips_y = -0.22
            bones["spine"] = [14.0, 0.0, 0.0]
            bones["chest"] = [8.0, 0.0, 0.0]
            bones["neck"] = [-12.0, 0.0, 0.0]
            bones["head"] = [-12.0, 0.0, 0.0]
            bones["leftUpperLeg"] = [-52.0, 10.0, -6.0]
            bones["rightUpperLeg"] = [-52.0, -10.0, 6.0]
            bones["leftLowerLeg"] = [78.0, 0.0, 0.0]
            bones["rightLowerLeg"] = [78.0, 0.0, 0.0]
            bones["leftFoot"] = [22.0, 0.0, 0.0]
            bones["rightFoot"] = [22.0, 0.0, 0.0]
        elif re.search(r"\b(jump|leap|hop|air)\b", t):
            hips_y = 0.24
            emotion = "excited"
            bones["leftUpperLeg"] = [-25.0, 0.0, -6.0]
            bones["rightUpperLeg"] = [-25.0, 0.0, 6.0]
            bones["leftLowerLeg"] = [45.0, 0.0, 0.0]
            bones["rightLowerLeg"] = [45.0, 0.0, 0.0]

        # Torso lean
        if "lean forward" in t:
            bones["spine"][0] += 14.0
        elif "lean back" in t:
            bones["spine"][0] -= 10.0
        if "lean left" in t:
            bones["spine"][2] -= 10.0
        elif "lean right" in t:
            bones["spine"][2] += 10.0

        # Head gaze / tilt
        if "look left" in t:
            bones["head"][1] = 24.0
        elif "look right" in t:
            bones["head"][1] = -24.0
        if "look up" in t:
            bones["head"][0] -= 20.0
        elif "look down" in t:
            bones["head"][0] += 20.0
        if "tilt" in t:
            bones["head"][2] = -12.0 if "left" in t else 12.0

        is_fist_pose = bool(re.search(r"\b(fist|punch)\b", t))

        # Left / Right Arm & Hand IK placement with anatomical pole & wrist vectors
        if re.search(r"\b(both\s+(arms|hands)\s+(up|high|raised)|raise\s+both)\b", t):
            ik["rightWrist"] = {
                "anchor": "head",
                "offset": [0.19, 0.14, 0.09],
                "pole": [0.85, -0.20, 0.38],
                "fingerDir": [-0.06, 0.98, 0.14],
                "palmNormal": [-0.82, 0.0, -0.56] if is_fist_pose else [-0.20, 0.08, 0.97],
            }
            ik["leftWrist"] = {
                "anchor": "head",
                "offset": [0.19, 0.14, 0.09],
                "pole": [0.85, -0.20, 0.38],
                "fingerDir": [-0.06, 0.98, 0.14],
                "palmNormal": [-0.82, 0.0, -0.56] if is_fist_pose else [-0.20, 0.08, 0.97],
            }
            ik["rightHandShape"] = "fist" if is_fist_pose else "open"
            ik["leftHandShape"] = "fist" if is_fist_pose else "open"
            emotion = "amused"
        else:
            if re.search(r"\b(raise\s+(your\s+)?right|right\s+(hand|arm)\s+(up|high|raised|in\s+a\s+fist))\b", t):
                ik["rightWrist"] = {
                    "anchor": "head",
                    "offset": [0.19, 0.14, 0.10],
                    "pole": [0.85, -0.20, 0.38],
                    "fingerDir": [-0.05, 0.98, 0.16],
                    "palmNormal": [-0.82, 0.0, -0.56] if is_fist_pose else [-0.25, 0.08, 0.96],
                }
            elif re.search(r"\b(right\s+hand\s+on\s+(hip|waist))\b", t):
                ik["rightWrist"] = {
                    "anchor": "hips",
                    "offset": [0.135, 0.08, 0.045],
                    "pole": [1.0, 0.08, -0.25],
                    "fingerDir": [-0.35, -0.82, 0.45],
                    "palmNormal": [-0.85, -0.25, -0.45],
                }
            elif re.search(r"\b(right\s+hand\s+over\s+heart|right\s+hand\s+on\s+chest)\b", t):
                ik["rightWrist"] = {
                    "anchor": "chest",
                    "offset": [0.03, 0.05, 0.15],
                    "pole": [0.65, -0.70, 0.30],
                    "fingerDir": [-0.75, 0.60, 0.20],
                    "palmNormal": [-0.40, 0.0, -0.90],
                }

            if re.search(r"\b(raise\s+(your\s+)?left|left\s+(hand|arm)\s+(up|high|raised|in\s+a\s+fist))\b", t):
                ik["leftWrist"] = {
                    "anchor": "head",
                    "offset": [0.19, 0.14, 0.10],
                    "pole": [0.85, -0.20, 0.38],
                    "fingerDir": [-0.05, 0.98, 0.16],
                    "palmNormal": [-0.82, 0.0, -0.56] if is_fist_pose else [-0.25, 0.08, 0.96],
                }
            elif re.search(r"\b(left\s+hand\s+on\s+(hip|waist))\b", t):
                ik["leftWrist"] = {
                    "anchor": "hips",
                    "offset": [0.135, 0.08, 0.045],
                    "pole": [1.0, 0.08, -0.25],
                    "fingerDir": [-0.35, -0.82, 0.45],
                    "palmNormal": [-0.85, -0.25, -0.45],
                }
            elif re.search(r"\b(left\s+hand\s+over\s+heart|left\s+hand\s+on\s+chest)\b", t):
                ik["leftWrist"] = {
                    "anchor": "chest",
                    "offset": [0.03, 0.05, 0.15],
                    "pole": [0.65, -0.70, 0.30],
                    "fingerDir": [-0.75, 0.60, 0.20],
                    "palmNormal": [-0.40, 0.0, -0.90],
                }

        # Hand shapes
        if "thumbs up" in t:
            ik["rightHandShape"] = "thumbs_up"
        elif "fist" in t or "punch" in t:
            ik["rightHandShape"] = "fist"
        elif "point" in t:
            ik["rightHandShape"] = "point"
        elif "peace" in t:
            ik["rightHandShape"] = "peace"
        elif "rock" in t:
            ik["rightHandShape"] = "rock_on"

        slug_words = [w for w in re.sub(r"[^a-z0-9\s]", "", t).split() if w not in {"make", "a", "pose", "the", "your", "and", "to", "on", "own"}][:3]
        pose_name = "ai_" + ("_".join(slug_words) if slug_words else "custom_pose")

        pose = sanitize_custom_pose(
            {
                "name": pose_name,
                "description": f"AI-synthesized pose from: {(text or '')[:80]}",
                "emotion": emotion,
                "movement": "stay",
                "hipsOffsetY": hips_y,
                "duration_ms": 4200,
                "bones": bones,
                "ik": ik,
            }
        )
        return self._attach_rl_evaluation(pose, text)

    async def synthesize_pose_with_llm(self, prompt: str, ollama_host: str = "http://127.0.0.1:11434") -> Dict[str, Any]:
        """
        Synthesize a 3D VRM pose with normalized humanoid bone angles and 2-bone IK wrist targets.
        Returns high-precision procedural templates or compositional kinematic poses immediately (<1ms),
        and queries HELIOS's local LLM (`llama3.2:3b` / `helios-avatar:latest`) for open-ended creative prompts.
        """
        matched = self.match_or_compose_pose(user_text=prompt)
        if matched:
            return matched

        try:
            import httpx

            sys_prompt = (
                "You are HELIOS's 3D VRM Kinematic Pose Designer (using @pixiv/three-vrm normalized humanoid bones).\n"
                "Given a pose request, design an expressive 3D pose in JSON with:\n"
                '- "name": short snake_case name\n'
                '- "description": brief description\n'
                '- "emotion": one of ["neutral","happy","amused","curious","excited","concerned","serious","confused"]\n'
                '- "movement": one of ["stay","walk_to_user","step_back","circle_user","return_center"]\n'
                '- "hipsOffsetY": float between -0.35 (crouch) and +0.30 (jump)\n'
                '- "bones": Euler [x,y,z] degrees for "hips", "spine", "chest", "head", "leftUpperLeg", "rightUpperLeg", "leftLowerLeg", "rightLowerLeg"\n'
                '- "ik": {\n'
                '    "rightWrist": {"anchor": "head"|"chest"|"hips", "offset": [x, y, z]},\n'
                '    "leftWrist": {"anchor": "head"|"chest"|"hips", "offset": [x, y, z]},\n'
                '    "rightHandShape": "open"|"fist"|"peace"|"point"|"thumbs_up"|"rock_on"|"salute"|"cupped",\n'
                '    "leftHandShape": "open"|"fist"|"peace"|"point"|"thumbs_up"|"rock_on"|"salute"|"cupped"\n'
                "  }\n"
                f"User Pose Request: {prompt}\n"
                "Output ONLY valid JSON."
            )
            async with httpx.AsyncClient(timeout=2.5) as client:
                resp = await client.post(
                    f"{ollama_host.rstrip('/')}/api/generate",
                    json={
                        "model": "llama3.2:3b",
                        "prompt": sys_prompt,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.35, "num_predict": 220},
                    },
                )
                if resp.status_code == 200:
                    raw = resp.json().get("response", "{}")
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(parsed, dict) and ("bones" in parsed or "ik" in parsed):
                        pose = sanitize_custom_pose(parsed)
                        return self._attach_rl_evaluation(pose, prompt)
        except Exception:
            pass

        return self.compose_kinematic_pose_from_text(prompt)


# Singleton Pose Generator owned by HELIOS Core
pose_generator = HELIOSPoseGenerator()


def get_pose_generator() -> HELIOSPoseGenerator:
    """Return the singleton HELIOSPoseGenerator owned by HELIOS Core."""
    return pose_generator

