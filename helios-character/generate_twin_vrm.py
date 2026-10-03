"""
generate_twin_from_ashveil.py
==============================
Builds Helios_Twin.vrm from the Ashveil male VRM base.

Ashveil has:
  Tex 0  body_outfit  (2048x1024) - dark outfit, white coat, red/purple accents
  Tex 1  hair         (2048x2048) - dark blue-gray, white highlights
  Tex 2  face_skin    (1024x1024) - face, eyes, mouth baked together
  Tex 3  face_detail  (1024x1024) - face markings / detail layer
  Tex 4  eyebrow      (512x512)
  Tex 5  eyelash      (256x256)
  Tex 6  thumbnail    (608x570)

Twin target:
  Hair      -> silver-gray #A8AFBA (preserve highlight strands)
  Outfit    -> dark slate #0D0E12 / charcoal #2C3038, cyan neon trim replacing red/purple
  Eyes      -> cyan-blue #00E5FF
  Eyebrow   -> silver-gray to match hair
"""

import struct, json, io, os
import numpy as np
from PIL import Image

SRC = r"viewer\models\8040016181520828351.vrm"
DST = r"viewer\models\Helios_Twin.vrm"

# ── colour helpers ─────────────────────────────────────────────────────────
def hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16)/255.0 for i in (0, 2, 4))

def arr_from_bytes(png_bytes):
    img = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
    return img, np.array(img, dtype=np.float32) / 255.0

def arr_to_bytes(arr, orig_img):
    result = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
    out = Image.fromarray(result, 'RGBA')
    buf = io.BytesIO()
    out.save(buf, format='PNG', compress_level=6)
    return buf.getvalue()

# ── per-texture transforms ─────────────────────────────────────────────────

def recolor_hair(png_bytes):
    """Dark blue-gray hair -> silver-gray #A8AFBA, preserve shading & highlight strands."""
    img, arr = arr_from_bytes(png_bytes)
    r, g, b, a = arr[...,0], arr[...,1], arr[...,2], arr[...,3]

    # Luminance of source
    lum = 0.2126*r + 0.7152*g + 0.0722*b

    # Target silver-gray tint
    tr, tg, tb = hex_rgb('#A8AFBA')

    # Bright pixels (highlights) -> keep near-white/silver
    # Dark pixels -> silver-gray shadow
    new_r = np.clip(lum * tr / 0.35, 0, 1)
    new_g = np.clip(lum * tg / 0.35, 0, 1)
    new_b = np.clip(lum * tb / 0.35, 0, 1)

    # Clamp highlights to near-white silver
    new_r = np.clip(new_r, 0, 0.92)
    new_g = np.clip(new_g, 0, 0.92)
    new_b = np.clip(new_b, 0, 0.95)

    arr[...,0] = new_r
    arr[...,1] = new_g
    arr[...,2] = new_b
    return arr_to_bytes(arr, img)


def recolor_outfit(png_bytes):
    """
    Ashveil outfit: dark body (keep/darken), white coat (-> off-white #EBF0F5),
    red accents (-> cyan #00E5FF), purple accents (-> cyan/dark-slate).
    """
    img, arr = arr_from_bytes(png_bytes)
    r, g, b, a = arr[...,0].copy(), arr[...,1].copy(), arr[...,2].copy(), arr[...,3].copy()

    new_r = arr[...,0].copy()
    new_g = arr[...,1].copy()
    new_b = arr[...,2].copy()

    # Per-pixel colour classification
    # Red-dominant pixels (accents): r > g*1.4 and r > b*1.4 and r > 0.3
    is_red = (r > g * 1.35) & (r > b * 1.35) & (r > 0.25) & (a > 0.1)
    # Purple-dominant: b > r*0.8 and b > g*1.1 and r > 0.2
    is_purple = (b > 0.2) & (r > 0.15) & (b > g * 1.05) & (~is_red) & (a > 0.1)
    # White/near-white: all channels > 0.75 (the white coat)
    is_white = (r > 0.72) & (g > 0.72) & (b > 0.72) & (a > 0.5)
    # Very dark pixels (the dark body base): lum < 0.25
    lum = 0.2126*r + 0.7152*g + 0.0722*b
    is_dark = (lum < 0.30) & (a > 0.1)

    # 1. Red -> Cyan #00E5FF (neon trim)
    cyan_r, cyan_g, cyan_b = hex_rgb('#00E5FF')
    boost = np.clip(lum * 3.0, 0.5, 1.0)
    new_r = np.where(is_red, cyan_r * boost, new_r)
    new_g = np.where(is_red, cyan_g * boost, new_g)
    new_b = np.where(is_red, cyan_b * boost, new_b)

    # 2. Purple -> Dark slate #0D0E12 with faint cyan tint
    ds_r, ds_g, ds_b = hex_rgb('#0D0E12')
    new_r = np.where(is_purple & ~is_red, ds_r + 0.02, new_r)
    new_g = np.where(is_purple & ~is_red, ds_g + 0.03, new_g)
    new_b = np.where(is_purple & ~is_red, ds_b + 0.06, new_b)

    # 3. White coat -> charcoal #2C3038 (techwear hoodie base)
    ch_r, ch_g, ch_b = hex_rgb('#2C3038')
    # Preserve brightness variation within the coat
    brightness_scale = np.clip((r + g + b) / 3.0, 0.0, 1.0)
    new_r = np.where(is_white, np.clip(ch_r * (0.5 + brightness_scale * 0.8), 0, 1), new_r)
    new_g = np.where(is_white, np.clip(ch_g * (0.5 + brightness_scale * 0.8), 0, 1), new_g)
    new_b = np.where(is_white, np.clip(ch_b * (0.5 + brightness_scale * 0.8), 0, 1), new_b)

    # 4. Dark areas -> push further to dark slate, add slight cool blue tint
    ds2_r, ds2_g, ds2_b = hex_rgb('#0D0E12')
    new_r = np.where(is_dark & ~is_red & ~is_purple & ~is_white,
                     np.clip(ds2_r + lum * 0.15, 0, 1), new_r)
    new_g = np.where(is_dark & ~is_red & ~is_purple & ~is_white,
                     np.clip(ds2_g + lum * 0.15, 0, 1), new_g)
    new_b = np.where(is_dark & ~is_red & ~is_purple & ~is_white,
                     np.clip(ds2_b + lum * 0.20, 0, 1), new_b)

    arr[...,0] = np.clip(new_r, 0, 1)
    arr[...,1] = np.clip(new_g, 0, 1)
    arr[...,2] = np.clip(new_b, 0, 1)
    return arr_to_bytes(arr, img)


def recolor_face(png_bytes):
    """
    Face/skin: keep skin tone mostly intact.
    Recolor iris/pupil area toward cyan #00E5FF.
    """
    img, arr = arr_from_bytes(png_bytes)
    r, g, b, a = arr[...,0].copy(), arr[...,1].copy(), arr[...,2].copy(), arr[...,3].copy()

    new_r = r.copy()
    new_g = g.copy()
    new_b = b.copy()

    # Iris detection: coloured pixels that are not skin-tone and not near-white/black
    lum = 0.2126*r + 0.7152*g + 0.0722*b
    # Skin: warm mid-range, r > b typically
    is_skin = (r > 0.60) & (r > b * 1.05) & (lum > 0.45) & (lum < 0.92)
    # Dark iris/pupil region: mid-dark, not skin
    is_iris = (lum > 0.05) & (lum < 0.65) & (~is_skin) & (a > 0.3)

    # Recolor iris -> cyan
    cr, cg, cb = hex_rgb('#00CCDD')
    iris_boost = np.clip(lum * 2.0, 0.3, 1.0)
    new_r = np.where(is_iris, cr * iris_boost, new_r)
    new_g = np.where(is_iris, cg * iris_boost, new_g)
    new_b = np.where(is_iris, cb * iris_boost, new_b)

    arr[...,0] = np.clip(new_r, 0, 1)
    arr[...,1] = np.clip(new_g, 0, 1)
    arr[...,2] = np.clip(new_b, 0, 1)
    return arr_to_bytes(arr, img)


def recolor_eyebrow(png_bytes):
    """Eyebrow -> silver-gray to match hair."""
    img, arr = arr_from_bytes(png_bytes)
    r, g, b, a = arr[...,0], arr[...,1], arr[...,2], arr[...,3]
    lum = 0.2126*r + 0.7152*g + 0.0722*b
    tr, tg, tb = hex_rgb('#9BA3AD')
    mask = a > 0.1
    arr[...,0] = np.where(mask, np.clip(lum * tr / 0.30, 0, 0.85), arr[...,0])
    arr[...,1] = np.where(mask, np.clip(lum * tg / 0.30, 0, 0.85), arr[...,1])
    arr[...,2] = np.where(mask, np.clip(lum * tb / 0.30, 0, 0.88), arr[...,2])
    return arr_to_bytes(arr, img)


# ── read source VRM ───────────────────────────────────────────────────────
print('Reading ' + SRC + ' ...')
with open(SRC, 'rb') as f:
    raw = f.read()

magic   = raw[0:4]
version = struct.unpack_from('<I', raw, 4)[0]
assert magic == b'glTF', 'Not a glTF/VRM file!'

c0_len    = struct.unpack_from('<I', raw, 12)[0]
json_bytes = raw[20 : 20 + c0_len]

c1_start  = 20 + c0_len
c1_len    = struct.unpack_from('<I', raw, c1_start)[0]
bin_start  = c1_start + 8
bin_data   = bytearray(raw[bin_start : bin_start + c1_len])

gltf = json.loads(json_bytes.decode('utf-8'))

# ── patch VRM meta ────────────────────────────────────────────────────────
vrm_ext = gltf.get('extensions', {}).get('VRM', {})
if vrm_ext:
    meta = vrm_ext.setdefault('meta', {})
    meta['title']   = 'HELIOS Twin (Techwear)'
    meta['version'] = '1.0'
    meta['author']  = 'HELIOS Character Studio (Twin)'
    print('  VRM meta patched')

# ── texture recolor plan ──────────────────────────────────────────────────
# tex_idx -> transform_function
TEX_PLAN = {
    0: recolor_outfit,   # body_outfit
    1: recolor_hair,     # hair
    2: recolor_face,     # face_skin (contains eyes baked in)
    4: recolor_eyebrow,  # eyebrow
}

# ── build tex_idx -> bufferView mapping ───────────────────────────────────
images      = gltf.get('images', [])
textures    = gltf.get('textures', [])
bufferViews = gltf.get('bufferViews', [])

tex_to_bv = {}
for i, tex in enumerate(textures):
    src = tex.get('source')
    if src is not None:
        bv_idx = images[src].get('bufferView')
        if bv_idx is not None:
            tex_to_bv[i] = bv_idx

# ── recolor each texture ──────────────────────────────────────────────────
new_png_map = {}
for tex_idx, fn in TEX_PLAN.items():
    if tex_idx not in tex_to_bv:
        print('  WARNING: tex ' + str(tex_idx) + ' not found in mapping, skipping')
        continue
    bv_idx = tex_to_bv[tex_idx]
    bv = bufferViews[bv_idx]
    orig = bytes(bin_data[bv['byteOffset'] : bv['byteOffset'] + bv['byteLength']])
    print('  Recoloring tex ' + str(tex_idx) + ' (' + fn.__name__ + ') ' + str(bv['byteLength']) + 'B -> ', end='')
    try:
        new_bytes = fn(orig)
        print(str(len(new_bytes)) + 'B')
        new_png_map[bv_idx] = new_bytes
    except Exception as e:
        print('ERROR: ' + str(e) + ' (keeping original)')
        new_png_map[bv_idx] = orig

# ── rebuild BIN chunk with corrected offsets ──────────────────────────────
all_bv_sorted = sorted(enumerate(bufferViews), key=lambda x: x[1].get('byteOffset', 0))

new_bin = bytearray()
for bv_idx, bv in all_bv_sorted:
    orig_offset = bv.get('byteOffset', 0)
    orig_length = bv.get('byteLength', 0)

    chunk = new_png_map.get(bv_idx, bytes(bin_data[orig_offset : orig_offset + orig_length]))

    aligned_start = len(new_bin)
    new_bin += chunk
    pad = (4 - len(new_bin) % 4) % 4
    new_bin += b'\x00' * pad

    bufferViews[bv_idx]['byteOffset'] = aligned_start
    bufferViews[bv_idx]['byteLength'] = len(chunk)

if gltf.get('buffers'):
    gltf['buffers'][0]['byteLength'] = len(new_bin)

print('  BIN rebuilt: ' + str(len(bin_data)) + 'B -> ' + str(len(new_bin)) + 'B')

# ── reassemble VRM ────────────────────────────────────────────────────────
new_json = json.dumps(gltf, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
json_pad = (4 - len(new_json) % 4) % 4
new_json_padded = new_json + b' ' * json_pad

bin_pad = (4 - len(new_bin) % 4) % 4
new_bin_padded = bytes(new_bin) + b'\x00' * bin_pad

new_total = 12 + 8 + len(new_json_padded) + 8 + len(new_bin_padded)

out = bytearray()
out += magic
out += struct.pack('<I', version)
out += struct.pack('<I', new_total)
out += struct.pack('<I', len(new_json_padded))
out += b'JSON'
out += new_json_padded
out += struct.pack('<I', len(new_bin_padded))
out += b'BIN\x00'
out += new_bin_padded

os.makedirs(os.path.dirname(os.path.abspath(DST)), exist_ok=True)
with open(DST, 'wb') as f:
    f.write(out)

print()
print('Written: ' + DST)
print('Size: ' + str(len(out)) + 'B  (source was ' + str(len(raw)) + 'B)')
