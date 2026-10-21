import struct, json, io, os
from PIL import Image

def analyze_airi_parts(p):
    with open(p, 'rb') as f:
        f.read(12)
        c0, _ = struct.unpack('<II', f.read(8))
        d = json.loads(f.read(c0).decode('utf-8'))
        c1, _ = struct.unpack('<II', f.read(8))
        bin_offset = f.tell()
        
        print("=== Materials in", p, "===")
        for idx, m in enumerate(d.get('materials', [])):
            b = m.get('pbrMetallicRoughness', {}).get('baseColorTexture', {}).get('index')
            print(f"Mat {idx:02d}: {m.get('name')} -> baseTex: {b}")
            
        print("\n=== Checking Bottoms / Body / Shoes textures ===")
        # Bottoms is Mat 9 (N00_001_03_Bottoms_01_CLOTH), baseTex 13 -> Image 13
        # Body is Mat 8 (N00_000_00_Body_00_SKIN), baseTex 11 -> Image 11
        # Shoes is Mat 10 (N00_004_01_Shoes_01_CLOTH), baseTex 14 -> Image 14
        out_dir = r"C:\projects\vrm\inspect_airi_pant"
        os.makedirs(out_dir, exist_ok=True)
        
        for img_idx in [11, 13, 14]:
            img_desc = d['images'][img_idx]
            bv = d['bufferViews'][img_desc['bufferView']]
            f.seek(bin_offset + bv.get('byteOffset', 0))
            raw = f.read(bv['byteLength'])
            im = Image.open(io.BytesIO(raw))
            im_path = os.path.join(out_dir, f"airi_img_{img_idx}_{img_desc.get('name','unnamed')}_{im.size[0]}x{im.size[1]}.png")
            im.save(im_path)
            print(f"Saved Image {img_idx} ({img_desc.get('name')}): {im.size}, mode={im.mode} to {im_path}")

analyze_airi_parts(r'C:\projects\vrm\airi.vrm')
analyze_airi_parts(r'C:\projects\vrm\airi.vrm.bak')
