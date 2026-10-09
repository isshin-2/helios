#!/usr/bin/env python3
"""
craft_male_ren_vrm.py

Synthesizes the authentic male Ren (Helios_Twin) VRM companion in full VRM 0.0 standard
matching Airi's exact architecture and three-vrm pipeline, equipped with:
  1. Base Rig: Yu1_1.vrm (100% rigged male humanoid mesh, 120 joints, 14 blendshapes, male hair/physics).
  2. Masculine Techwear Outfit:
     - High-collar male techwear jacket (vroid_extracted_22.png)
     - Tactical utility cargo trousers (vroid_extracted_21.png scaled to 1024x512)
     - Tactical combat runner shoes (vroid_extracted_20.png)
     - Male hair (Airi silver-cyan gradient)
     - Cybernetic piercing cyan irises (#00E5FF)
  3. DEDICATED HIGH-RES EMISSIVE MAPS (White circuit conduits & lines on black background):
     - Iris emissive map (Texture 25): Glowing iris conduits & pupil ring
     - Tops emissive map (Texture 26): Glowing zipper pulls, shoulder piping, and conduit lines
     - Bottoms emissive map (Texture 27): Glowing cargo buckle straps, side pocket piping, and seams
     - Shoes emissive map (Texture 28): Glowing soles and laces conduits
     - Hair emissive map (Texture 29): Cybernetic hair highlights
  4. MToon Shader properties:
     - _EmissionColor = [0.0, 0.898, 1.0, 1.0] (Helios cyan baseline)
     - _EmissionMap hooked to the dedicated emissive masks
     - Material names matching VRM 0.0 standard for three-vrm MToon loader

Outputs:
  - helios-character/viewer/models/Helios_Twin.vrm
  - helios-character/viewer/vrm/twin.vrm
  - C:/Users/krithik/Pictures/ren_helios.vrm
"""

import os
import io
import struct
import json
import numpy as np
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_VRM = os.path.join(SCRIPT_DIR, "viewer", "models", "Yu1_1.vrm")
OUT_VRM_MODELS = os.path.join(SCRIPT_DIR, "viewer", "models", "Helios_Twin.vrm")
OUT_VRM_VRM = os.path.join(SCRIPT_DIR, "viewer", "vrm", "twin.vrm")
OUT_PICTURES = r"C:\Users\krithik\Pictures\ren_helios.vrm"
MODELS_DIR = os.path.join(SCRIPT_DIR, "viewer", "models")


def recolor_hair_to_airi_silver_cyan(img_path):
    im = Image.open(img_path).convert('RGBA')
    arr = np.array(im, dtype=np.float32)
    alpha = arr[:, :, 3] / 255.0
    luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    vis = alpha > 0.05
    if np.any(vis):
        min_l = np.percentile(luma[vis], 5)
        max_l = np.percentile(luma[vis], 95)
        norm_luma = np.clip((luma - min_l) / max(1e-5, (max_l - min_l)), 0.0, 1.0)
    else:
        norm_luma = luma / 255.0
    r_new = 95.0 + norm_luma * (230.0 - 95.0)
    g_new = 120.0 + norm_luma * (245.0 - 120.0)
    b_new = 135.0 + norm_luma * (252.0 - 135.0)
    out = np.stack([
        np.clip(r_new, 0, 255),
        np.clip(g_new, 0, 255),
        np.clip(b_new, 0, 255),
        arr[:, :, 3]
    ], axis=-1).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


def recolor_brows_and_lashes(img_path):
    im = Image.open(img_path).convert('RGBA')
    arr = np.array(im, dtype=np.float32)
    luma = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]) / 255.0
    r_new = np.clip(luma * 115.0, 25, 135)
    g_new = np.clip(luma * 130.0, 35, 155)
    b_new = np.clip(luma * 150.0, 45, 180)
    out = np.stack([r_new, g_new, b_new, arr[:, :, 3]], axis=-1).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


def create_cybernetic_jacket(img_path):
    im = Image.open(img_path).convert('RGBA')
    arr = np.array(im, dtype=np.float32)
    alpha = arr[:, :, 3] > 30
    luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    accent_mask = alpha & (luma > 130)
    fabric_mask = alpha & (~accent_mask)

    arr[fabric_mask, 0] = np.clip(arr[fabric_mask, 0] * 0.40, 10, 32)
    arr[fabric_mask, 1] = np.clip(arr[fabric_mask, 1] * 0.45, 12, 38)
    arr[fabric_mask, 2] = np.clip(arr[fabric_mask, 2] * 0.52, 16, 48)

    norm_acc = np.clip((luma[accent_mask] - 130.0) / 125.0, 0.0, 1.0)
    arr[accent_mask, 0] = norm_acc * 80.0
    arr[accent_mask, 1] = 180.0 + norm_acc * 75.0
    arr[accent_mask, 2] = 220.0 + norm_acc * 35.0

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA')


def create_cybernetic_bottoms(vroid_bot_path, yu1_bot_path):
    im_v = Image.open(vroid_bot_path).convert('RGBA').resize((1024, 512), Image.Resampling.LANCZOS)
    arr = np.array(im_v, dtype=np.float32)
    alpha = arr[:, :, 3] > 30
    luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    accent_mask = alpha & (luma > 30.0)
    fabric_mask = alpha & (~accent_mask)

    arr[fabric_mask, 0] = np.clip(arr[fabric_mask, 0] * 0.65, 8, 22)
    arr[fabric_mask, 1] = np.clip(arr[fabric_mask, 1] * 0.70, 10, 28)
    arr[fabric_mask, 2] = np.clip(arr[fabric_mask, 2] * 0.80, 14, 38)

    norm_acc = np.clip(luma[accent_mask] / 60.0, 0.0, 1.0)
    arr[accent_mask, 0] = norm_acc * 60.0
    arr[accent_mask, 1] = 160.0 + norm_acc * 95.0
    arr[accent_mask, 2] = 200.0 + norm_acc * 55.0

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA')


def create_cybernetic_shoes(img_path):
    im = Image.open(img_path).convert('RGBA')
    arr = np.array(im, dtype=np.float32)
    alpha = arr[:, :, 3] > 30
    luma = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2])
    accent_mask = alpha & (luma > 55.0)
    sole_mask = alpha & (~accent_mask)

    arr[sole_mask, 0] = np.clip(arr[sole_mask, 0] * 0.40, 10, 30)
    arr[sole_mask, 1] = np.clip(arr[sole_mask, 1] * 0.45, 12, 35)
    arr[sole_mask, 2] = np.clip(arr[sole_mask, 2] * 0.50, 15, 45)

    arr[accent_mask, 0] = 0.0
    arr[accent_mask, 1] = 229.0
    arr[accent_mask, 2] = 255.0

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA')


def main():
    print(f"Loading Base Male Rig VRM from {BASE_VRM}...")
    with open(BASE_VRM, 'rb') as f:
        magic, version, total_len = struct.unpack('<4sII', f.read(12))
        assert magic == b'glTF', "Not a valid glTF/VRM file"
        
        json_len, json_type = struct.unpack('<II', f.read(8))
        gltf_bytes = f.read(json_len)
        gltf = json.loads(gltf_bytes.decode('utf-8'))
        
        bin_len, bin_type = struct.unpack('<II', f.read(8))
        bin_data = bytearray(f.read(bin_len))

    images = gltf.get('images', [])
    buffer_views = gltf.get('bufferViews', [])
    textures = gltf.get('textures', [])
    
    geom_byte_length = buffer_views[147]['byteOffset']
    print(f"Base geometry length: {geom_byte_length} bytes. Images: {len(images)}")
    
    # Textures replacements:
    replacements = {}
    
    # (A) Eyes: Airi piercing cyan iris
    airi_iris_path = os.path.join(MODELS_DIR, "airi_ref_3.png")
    replacements[3] = Image.open(airi_iris_path).convert('RGBA')
        
    # (B) Brows & Lashes
    replacements[8] = recolor_brows_and_lashes(os.path.join(MODELS_DIR, "yu1_img_8.png"))
    replacements[9] = recolor_brows_and_lashes(os.path.join(MODELS_DIR, "yu1_img_9.png"))
    replacements[10] = recolor_brows_and_lashes(os.path.join(MODELS_DIR, "yu1_img_10.png"))
    
    # (C) Hair
    replacements[14] = recolor_hair_to_airi_silver_cyan(os.path.join(MODELS_DIR, "yu1_img_14.png"))
    replacements[19] = recolor_hair_to_airi_silver_cyan(os.path.join(MODELS_DIR, "yu1_img_19.png"))

    # (D) Full Male Body / Skin: eliminate chest cutout/gap completely
    replacements[11] = Image.open(os.path.join(MODELS_DIR, "yu1_body_full_solid.png")).convert('RGBA')
    
    # (E) Male Techwear Clothing:
    # High-collar techwear hoodie top (Yu1 mesh 12 -> texture 17)
    replacements[17] = Image.open(os.path.join(MODELS_DIR, "recolored_yu1_hoodie.png")).convert('RGBA')
    
    # Cargo pleated tech bottoms (Yu1 mesh 13 -> texture 18)
    replacements[18] = Image.open(os.path.join(MODELS_DIR, "recolored_yu1_bottoms.png")).convert('RGBA')
    
    # High-top tactical buckle shoes (Yu1 mesh 9 -> texture 13)
    replacements[13] = Image.open(os.path.join(MODELS_DIR, "recolored_yu1_shoes.png")).convert('RGBA')
    
    # Blank out onepiece so no feminine dress elements render
    blank_onepiece = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    replacements[16] = blank_onepiece

    # (F) DEDICATED EMISSIVE MAPS (White circuit conduits on black background)
    # 25: Iris emissive map
    em_iris = Image.open(os.path.join(MODELS_DIR, "ren_emissive_iris.png")).convert('RGB')
    # 26: Tops emissive map
    em_top = Image.open(os.path.join(MODELS_DIR, "ren_emissive_yu1_hoodie.png")).convert('RGB')
    # 27: Bottoms emissive map
    em_bot = Image.open(os.path.join(MODELS_DIR, "ren_emissive_yu1_bottoms.png")).convert('RGB')
    # 28: Shoes emissive map
    em_shoe = Image.open(os.path.join(MODELS_DIR, "ren_emissive_yu1_shoes.png")).convert('RGB')
    # 29: Hair emissive map
    em_hair = Image.open(os.path.join(MODELS_DIR, "ren_emissive_hair.png")).convert('RGB')

    additional_emissive_images = [
        ("Ren_Iris_Emissive", em_iris),      # new image idx = 25
        ("Ren_Tops_Emissive", em_top),        # new image idx = 26
        ("Ren_Bottoms_Emissive", em_bot),    # new image idx = 27
        ("Ren_Shoes_Emissive", em_shoe),      # new image idx = 28
        ("Ren_Hair_Emissive", em_hair),      # new image idx = 29
    ]

    new_bin = bytearray(bin_data[:geom_byte_length])
    
    # Encode existing 25 images
    for i, img_desc in enumerate(images):
        bvi = img_desc['bufferView']
        old_bv = buffer_views[bvi]
        
        if i in replacements:
            buf = io.BytesIO()
            replacements[i].save(buf, format='PNG', optimize=True)
            enc_bytes = buf.getvalue()
        else:
            off = old_bv['byteOffset']
            length = old_bv['byteLength']
            enc_bytes = bin_data[off:off+length]
            
        pad = (4 - (len(new_bin) % 4)) % 4
        new_bin.extend(b'\x00' * pad)
        old_bv['byteOffset'] = len(new_bin)
        old_bv['byteLength'] = len(enc_bytes)
        new_bin.extend(enc_bytes)

    # Append the 5 new emissive maps
    new_tex_indices = {}
    for name, img_obj in additional_emissive_images:
        buf = io.BytesIO()
        img_obj.save(buf, format='PNG', optimize=True)
        enc_bytes = buf.getvalue()
        
        pad = (4 - (len(new_bin) % 4)) % 4
        new_bin.extend(b'\x00' * pad)
        
        new_bvi = len(buffer_views)
        buffer_views.append({
            'buffer': 0,
            'byteOffset': len(new_bin),
            'byteLength': len(enc_bytes)
        })
        new_bin.extend(enc_bytes)
        
        new_img_idx = len(images)
        images.append({
            'name': name,
            'mimeType': 'image/png',
            'bufferView': new_bvi
        })
        
        new_tex_idx = len(textures)
        textures.append({
            'sampler': 0,
            'source': new_img_idx
        })
        new_tex_indices[name] = new_tex_idx
        print(f"Added {name} -> Image {new_img_idx}, Texture {new_tex_idx}")

    # Hook up VRM 0.0 materialProperties and glTF materials
    mat_props = gltf['extensions']['VRM']['materialProperties']
    materials = gltf['materials']
    
    # Map texture hooks:
    # Mat 1: EyeIris -> emissiveMap = new_tex_indices["Ren_Iris_Emissive"]
    # Mat 9: Shoes -> emissiveMap = new_tex_indices["Ren_Shoes_Emissive"]
    # Mat 12: Tops -> emissiveMap = new_tex_indices["Ren_Tops_Emissive"]
    # Mat 13: Bottoms -> emissiveMap = new_tex_indices["Ren_Bottoms_Emissive"]
    # Mat 14: Hair -> emissiveMap = new_tex_indices["Ren_Hair_Emissive"]
    
    iris_tex = new_tex_indices["Ren_Iris_Emissive"]
    tops_tex = new_tex_indices["Ren_Tops_Emissive"]
    bot_tex = new_tex_indices["Ren_Bottoms_Emissive"]
    shoe_tex = new_tex_indices["Ren_Shoes_Emissive"]
    hair_tex = new_tex_indices["Ren_Hair_Emissive"]
    
    # 1. Update VRM 0.0 Material Properties
    for i, mp in enumerate(mat_props):
        name = mp.get('name', '')
        tp = mp.setdefault('textureProperties', {})
        vp = mp.setdefault('vectorProperties', {})
        
        if 'EyeIris' in name:
            tp['_EmissionMap'] = iris_tex
            vp['_Color'] = [1.0, 1.0, 1.0, 1.0]
            vp['_ShadeColor'] = [1.0, 1.0, 1.0, 1.0]
            vp['_EmissionColor'] = [0.0, 0.898, 1.0, 1.0]
        elif 'Tops' in name:
            tp['_EmissionMap'] = tops_tex
            vp['_Color'] = [1.0, 1.0, 1.0, 1.0]
            vp['_ShadeColor'] = [0.65, 0.70, 0.78, 1.0]
            vp['_EmissionColor'] = [0.0, 0.898, 1.0, 1.0]
        elif 'Bottoms' in name:
            tp['_EmissionMap'] = bot_tex
            vp['_Color'] = [1.0, 1.0, 1.0, 1.0]
            vp['_ShadeColor'] = [0.65, 0.70, 0.78, 1.0]
            vp['_EmissionColor'] = [0.0, 0.898, 1.0, 1.0]
        elif 'Shoes' in name:
            tp['_EmissionMap'] = shoe_tex
            vp['_Color'] = [1.0, 1.0, 1.0, 1.0]
            vp['_ShadeColor'] = [0.65, 0.70, 0.78, 1.0]
            vp['_EmissionColor'] = [0.0, 0.898, 1.0, 1.0]
        elif 'HAIR' in name:
            tp['_EmissionMap'] = hair_tex
            vp['_Color'] = [1.0, 1.0, 1.0, 1.0]
            vp['_ShadeColor'] = [0.72, 0.80, 0.88, 1.0]
            vp['_EmissionColor'] = [0.0, 0.35, 0.45, 1.0]

    # 2. Update standard glTF materials
    for i, m in enumerate(materials):
        name = m.get('name', '')
        if 'EyeIris' in name:
            m['emissiveTexture'] = {'index': iris_tex, 'texCoord': 0}
            m['emissiveFactor'] = [0.0, 0.898, 1.0]
        elif 'Tops' in name:
            m['emissiveTexture'] = {'index': tops_tex, 'texCoord': 0}
            m['emissiveFactor'] = [0.0, 0.898, 1.0]
        elif 'Bottoms' in name:
            m['emissiveTexture'] = {'index': bot_tex, 'texCoord': 0}
            m['emissiveFactor'] = [0.0, 0.898, 1.0]
        elif 'Shoes' in name:
            m['emissiveTexture'] = {'index': shoe_tex, 'texCoord': 0}
            m['emissiveFactor'] = [0.0, 0.898, 1.0]
        elif 'HAIR' in name:
            m['emissiveTexture'] = {'index': hair_tex, 'texCoord': 0}
            m['emissiveFactor'] = [0.0, 0.35, 0.45]

    # VRM Metadata
    vrm_meta = gltf['extensions']['VRM'].setdefault('meta', {})
    vrm_meta['title'] = "Helios_Twin (Ren) - Cybernetic Male Operative"
    vrm_meta['version'] = "2.3"
    vrm_meta['author'] = "HELIOS Character Studio"

    # Update glTF buffer 0 length
    gltf['buffers'][0]['byteLength'] = len(new_bin)
    
    # Serialize GLB / VRM
    new_json_bytes = json.dumps(gltf, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    json_pad = (4 - (len(new_json_bytes) % 4)) % 4
    new_json_bytes += b' ' * json_pad
    
    bin_pad = (4 - (len(new_bin) % 4)) % 4
    new_bin.extend(b'\x00' * bin_pad)
    
    header = struct.pack(
        '<4sII',
        b'glTF',
        2,
        12 + 8 + len(new_json_bytes) + 8 + len(new_bin)
    )
    chunk0_hdr = struct.pack('<II', len(new_json_bytes), 0x4E4F534A)
    chunk1_hdr = struct.pack('<II', len(new_bin), 0x004E4942)
    
    for path in [OUT_VRM_MODELS, OUT_VRM_VRM, OUT_PICTURES]:
        print(f"Writing output VRM to {path}...")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(header)
            f.write(chunk0_hdr)
            f.write(new_json_bytes)
            f.write(chunk1_hdr)
            f.write(new_bin)

    print("Success! Helios_Twin.vrm has been crafted with Airi's exact VRM 0.0 MToon emissive map architecture.")


if __name__ == "__main__":
    main()
