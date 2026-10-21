import struct, json, os
import numpy as np

def check_prim_positions(p):
    with open(p, 'rb') as f:
        f.read(12)
        c0, _ = struct.unpack('<II', f.read(8))
        d = json.loads(f.read(c0).decode('utf-8'))
        c1, _ = struct.unpack('<II', f.read(8))
        bin_offset = f.tell()
        
        mesh = d['meshes'][1]
        materials = d['materials']
        print(f"Mesh 1 ({mesh.get('name', 'Body')}) primitives:")
        for prim_idx, prim in enumerate(mesh['primitives']):
            mat_idx = prim['material']
            mat_name = materials[mat_idx]['name']
            pos_acc_idx = prim['attributes']['POSITION']
            acc = d['accessors'][pos_acc_idx]
            bv = d['bufferViews'][acc['bufferView']]
            
            f.seek(bin_offset + bv.get('byteOffset', 0) + acc.get('byteOffset', 0))
            raw = f.read(acc['count'] * 12)
            verts = np.frombuffer(raw, dtype=np.float32).reshape(-1, 3)
            print(f"Prim {prim_idx} (Mat {mat_idx}: {mat_name}): {len(verts)} verts")
            print(f"   X: [{verts[:,0].min():.3f}, {verts[:,0].max():.3f}]")
            print(f"   Y (height): [{verts[:,1].min():.3f}, {verts[:,1].max():.3f}]")
            print(f"   Z: [{verts[:,2].min():.3f}, {verts[:,2].max():.3f}]")

check_prim_positions(r'C:\projects\vrm\airi.vrm')
