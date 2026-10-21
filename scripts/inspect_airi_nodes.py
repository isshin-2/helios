import struct, json, os

def inspect_meshes(p):
    with open(p, 'rb') as f:
        f.read(12)
        c0, _ = struct.unpack('<II', f.read(8))
        d = json.loads(f.read(c0).decode('utf-8'))
        materials = d.get('materials', [])
        meshes = d.get('meshes', [])
        nodes = d.get('nodes', [])
        for n_idx, node in enumerate(nodes):
            if 'mesh' in node:
                mesh_idx = node['mesh']
                mesh = meshes[mesh_idx]
                m_name = node.get('name', f'node_{n_idx}')
                print(f"Node: {m_name} (mesh {mesh_idx})")
                for p_idx, prim in enumerate(mesh.get('primitives', [])):
                    mat_idx = prim.get('material')
                    mat_name = materials[mat_idx]['name'] if mat_idx is not None else 'None'
                    print(f"   Prim {p_idx}: Material {mat_idx} ({mat_name})")

inspect_meshes(r'C:\projects\vrm\airi.vrm')
