"""
craft_older_brother_vrm.py
==========================
Generates Helios_Twin.vrm as the mature older male sibling to Airi:
- Taller, broader masculine athletic frame (broadened shoulders, deeper chest, longer limbs)
- Shared sibling genetic aesthetic: piercing cybernetic cyan eyes, silver-slate hair with cyan undertones
- Tactical operative attire: heavy slate/charcoal combat techwear with glowing cyan conduits
"""

import struct
import json
import io
import os
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

SRC = r"viewer\models\Helios_Airi.vrm"
DST_MODELS = r"viewer\models\Helios_Twin.vrm"
DST_VRM_DIR = r"viewer\vrm\twin.vrm"

def hex_to_rgb_norm(h: str):
    h = h.lstrip('#')
    return np.array([int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4)], dtype=np.float32)

def recolor_hair_mature(png_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
    arr = np.array(img, dtype=np.float32) / 255.0
    r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]

    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    # Mature silver-slate target (#7A828E)
    target_silver = hex_to_rgb_norm('#7A828E')
    cyan_accent = hex_to_rgb_norm('#00E5FF')

    # Detect bright cyan highlight tips from Airi and shift to deeper, disciplined cyan
    is_cyan = (b > r * 1.25) & (g > r * 1.15) & (lum > 0.35)

    new_rgb = np.zeros_like(arr[..., :3])
    for c in range(3):
        # Mature silver-slate with realistic contrast
        base_c = np.clip(lum * (target_silver[c] / 0.40), 0.0, 0.90)
        # Sibling cyan accent reserved for tips/highlights
        accent_c = cyan_accent[c] * np.clip(lum * 1.8, 0.3, 1.0)
        new_rgb[..., c] = np.where(is_cyan, accent_c, base_c)

    arr[..., :3] = np.clip(new_rgb, 0.0, 1.0)
    out_img = Image.fromarray((arr * 255).astype(np.uint8), 'RGBA')
    buf = io.BytesIO()
    out_img.save(buf, format='PNG', compress_level=6)
    return buf.getvalue()

def recolor_eyebrow_mature(png_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
    arr = np.array(img, dtype=np.float32) / 255.0
    r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    # Darker, bolder masculine silver-charcoal brow (#585E68)
    brow_col = hex_to_rgb_norm('#585E68')
    mask = a > 0.08
    for c in range(3):
        arr[..., c] = np.where(mask, np.clip(lum * (brow_col[c] / 0.35), 0.0, 0.85), arr[..., c])
    out_img = Image.fromarray((np.clip(arr, 0.0, 1.0) * 255).astype(np.uint8), 'RGBA')
    buf = io.BytesIO()
    out_img.save(buf, format='PNG', compress_level=6)
    return buf.getvalue()

def recolor_eyes_mature(png_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
    arr = np.array(img, dtype=np.float32) / 255.0
    r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b

    # Sibling cyan: identical iris base to Airi (#00E5FF) with darker limbal ring
    cyan_col = hex_to_rgb_norm('#00E5FF')
    deep_blue = hex_to_rgb_norm('#005577')

    is_colored = (a > 0.2) & ((b > r * 1.1) | (g > r * 1.1) | (lum < 0.6))
    for c in range(3):
        blended = np.where(lum > 0.35, cyan_col[c] * np.clip(lum * 1.6, 0.4, 1.0), deep_blue[c] * 1.2)
        arr[..., c] = np.where(is_colored, np.clip(blended, 0.0, 1.0), arr[..., c])

    out_img = Image.fromarray((np.clip(arr, 0.0, 1.0) * 255).astype(np.uint8), 'RGBA')
    buf = io.BytesIO()
    out_img.save(buf, format='PNG', compress_level=6)
    return buf.getvalue()

def recolor_tactical_outfit(png_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
    arr = np.array(img, dtype=np.float32) / 255.0
    r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b

    # Dark tactical slate (#0B0D11) & charcoal armor panels (#1B1E26)
    slate_dark = hex_to_rgb_norm('#0B0D11')
    charcoal = hex_to_rgb_norm('#1B1E26')
    cyan_neon = hex_to_rgb_norm('#00E5FF')

    is_cyan_neon = (b > r * 1.3) & (g > r * 1.2) & (lum > 0.4)
    is_light = (lum > 0.55) & (~is_cyan_neon)
    is_dark = (lum <= 0.55) & (~is_cyan_neon)

    for c in range(3):
        # Push light patches to reinforced charcoal
        arr[..., c] = np.where(is_light, np.clip(charcoal[c] * (0.6 + lum * 0.7), 0.0, 0.85), arr[..., c])
        # Dark areas to tactical stealth slate
        arr[..., c] = np.where(is_dark, np.clip(slate_dark[c] + lum * 0.12, 0.0, 0.7), arr[..., c])
        # Glowing cyan power channels
        arr[..., c] = np.where(is_cyan_neon, cyan_neon[c] * np.clip(lum * 1.8, 0.5, 1.0), arr[..., c])

    out_img = Image.fromarray((np.clip(arr, 0.0, 1.0) * 255).astype(np.uint8), 'RGBA')
    buf = io.BytesIO()
    out_img.save(buf, format='PNG', compress_level=6)
    return buf.getvalue()

def recolor_bottoms_to_combat_trousers(png_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
    arr = np.array(img, dtype=np.float32) / 255.0
    r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b

    # Transform bottoms into dark tactical operative cargo weave
    trousers_dark = hex_to_rgb_norm('#10131A')
    cyan_trim = hex_to_rgb_norm('#00E5FF')

    is_accent = (b > r * 1.3) & (lum > 0.35)
    for c in range(3):
        base = np.clip(trousers_dark[c] + lum * 0.14, 0.0, 0.7)
        accent = cyan_trim[c] * np.clip(lum * 1.6, 0.4, 1.0)
        arr[..., c] = np.where(is_accent, accent, base)

    out_img = Image.fromarray((np.clip(arr, 0.0, 1.0) * 255).astype(np.uint8), 'RGBA')
    buf = io.BytesIO()
    out_img.save(buf, format='PNG', compress_level=6)
    return buf.getvalue()

def process_vrm():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(script_dir, SRC)
    dst_models_path = os.path.join(script_dir, DST_MODELS)
    dst_vrm_path = os.path.join(script_dir, DST_VRM_DIR)

    print(f"[*] Reading Airi base VRM: {src_path} ...")
    with open(src_path, "rb") as f:
        raw = f.read()

    magic = raw[0:4]
    version = struct.unpack_from("<I", raw, 4)[0]
    c0_len = struct.unpack_from("<I", raw, 12)[0]
    json_bytes = raw[20 : 20 + c0_len]
    c1_start = 20 + c0_len
    c1_len = struct.unpack_from("<I", raw, c1_start)[0]
    bin_start = c1_start + 8
    bin_data = bytearray(raw[bin_start : bin_start + c1_len])

    gltf = json.loads(json_bytes.decode("utf-8"))

    # 1. Update VRM Metadata for Older Brother
    vrm_meta = gltf.get("extensions", {}).get("VRM", {}).get("meta", {})
    vrm_meta["title"] = "HELIOS Twin (Older Brother - Ren)"
    vrm_meta["version"] = "2.0"
    vrm_meta["author"] = "HELIOS Character Studio (Brother to Airi)"
    vrm_meta["contactInformation"] = "HELIOS Cybernetic Operatives"
    vrm_meta["reference"] = "Airi Sibling Pair"
    print("  [+] Patched VRM metadata for older brother Ren")

    # 2. Modify Bone Skeleton for Mature Older Male Physique
    human_bones = gltf.get("extensions", {}).get("VRM", {}).get("humanoid", {}).get("humanBones", [])
    nodes = gltf.get("nodes", [])

    bone_node_map = {hb["bone"]: hb["node"] for hb in human_bones}

    # Shoulder broadening (mature male athletic stance)
    if "leftShoulder" in bone_node_map:
        ln = nodes[bone_node_map["leftShoulder"]]
        ln["scale"] = [1.16, 1.04, 1.12]
        if "translation" in ln:
            ln["translation"][0] -= 0.015  # Expand laterally
    if "rightShoulder" in bone_node_map:
        rn = nodes[bone_node_map["rightShoulder"]]
        rn["scale"] = [1.16, 1.04, 1.12]
        if "translation" in rn:
            rn["translation"][0] += 0.015  # Expand laterally

    # Chest & Upper Torso Broadening
    if "chest" in bone_node_map:
        nodes[bone_node_map["chest"]]["scale"] = [1.12, 1.05, 1.10]
    if "upperChest" in bone_node_map:
        nodes[bone_node_map["upperChest"]]["scale"] = [1.14, 1.06, 1.12]

    # Spine & Hips: Taller height, athletic masculine taper
    if "spine" in bone_node_map:
        nodes[bone_node_map["spine"]]["scale"] = [1.06, 1.06, 1.06]
    if "hips" in bone_node_map:
        hn = nodes[bone_node_map["hips"]]
        hn["scale"] = [0.96, 1.04, 0.96]  # Narrower hips relative to shoulders

    # Elongate legs for taller height (~1.82m vs 1.68m)
    for leg_bone in ["leftUpperLeg", "rightUpperLeg", "leftLowerLeg", "rightLowerLeg"]:
        if leg_bone in bone_node_map:
            nodes[bone_node_map[leg_bone]]["scale"] = [1.02, 1.06, 1.02]

    # Arms elongation
    for arm_bone in ["leftUpperArm", "rightUpperArm", "leftLowerArm", "rightLowerArm"]:
        if arm_bone in bone_node_map:
            nodes[bone_node_map[arm_bone]]["scale"] = [1.05, 1.05, 1.05]

    # Mature head proportion (slightly smaller head-to-body ratio)
    if "head" in bone_node_map:
        nodes[bone_node_map["head"]]["scale"] = [0.95, 0.95, 0.95]

    print("  [+] Scaled bone skeleton to mature athletic male proportions (1.82m)")

    # 3. Recolor Textures (Image Index Map)
    # Image 3: Eye Iris
    # Image 8: Eyebrow
    # Image 14: HairBack
    # Image 16: Onepiece
    # Image 17: Tops (Hoodie)
    # Image 18: Bottoms
    # Image 19: Hair
    # Image 20: Hair details
    IMAGE_TRANSFORMS = {
        3: recolor_eyes_mature,
        8: recolor_eyebrow_mature,
        14: recolor_hair_mature,
        16: recolor_tactical_outfit,
        17: recolor_tactical_outfit,
        18: recolor_bottoms_to_combat_trousers,
        19: recolor_hair_mature,
        20: recolor_hair_mature,
    }

    images = gltf.get("images", [])
    bufferViews = gltf.get("bufferViews", [])

    new_png_map = {}
    for img_idx, transform_fn in IMAGE_TRANSFORMS.items():
        if img_idx >= len(images):
            continue
        bv_idx = images[img_idx]["bufferView"]
        bv = bufferViews[bv_idx]
        offset = bv["byteOffset"]
        length = bv["byteLength"]
        orig_bytes = bytes(bin_data[offset : offset + length])
        try:
            new_bytes = transform_fn(orig_bytes)
            print(f"  [+] Transformed image {img_idx} ({transform_fn.__name__}): {length}B -> {len(new_bytes)}B")
            new_png_map[bv_idx] = new_bytes
        except Exception as err:
            print(f"  [!] Failed image {img_idx}: {err}")

    # Rebuild BIN Buffer
    all_bv_sorted = sorted(enumerate(bufferViews), key=lambda x: x[1].get("byteOffset", 0))
    new_bin = bytearray()
    for bv_idx, bv in all_bv_sorted:
        orig_offset = bv.get("byteOffset", 0)
        orig_length = bv.get("byteLength", 0)
        chunk = new_png_map.get(bv_idx, bytes(bin_data[orig_offset : orig_offset + orig_length]))

        aligned_start = len(new_bin)
        new_bin += chunk
        pad = (4 - len(new_bin) % 4) % 4
        new_bin += b"\x00" * pad

        bufferViews[bv_idx]["byteOffset"] = aligned_start
        bufferViews[bv_idx]["byteLength"] = len(chunk)

    if gltf.get("buffers"):
        gltf["buffers"][0]["byteLength"] = len(new_bin)

    # Reassemble VRM GLB container
    new_json = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - len(new_json) % 4) % 4
    new_json_padded = new_json + b" " * json_pad

    bin_pad = (4 - len(new_bin) % 4) % 4
    new_bin_padded = bytes(new_bin) + b"\x00" * bin_pad

    new_total = 12 + 8 + len(new_json_padded) + 8 + len(new_bin_padded)

    out = bytearray()
    out += magic
    out += struct.pack("<I", version)
    out += struct.pack("<I", new_total)
    out += struct.pack("<I", len(new_json_padded))
    out += b"JSON"
    out += new_json_padded
    out += struct.pack("<I", len(new_bin_padded))
    out += b"BIN\x00"
    out += new_bin_padded

    for target in [dst_models_path, dst_vrm_path]:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(out)
        print(f"[+] Saved updated older brother VRM to {target} ({len(out)} bytes)")

if __name__ == "__main__":
    process_vrm()
