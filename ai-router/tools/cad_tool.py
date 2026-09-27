import os
import subprocess

def generate_openscad_model(scad_code: str, output_stl_path: str) -> str:
    """
    Generates a 3D STL file from OpenSCAD code.
    Requires OpenSCAD to be installed and available in the system PATH.
    """
    temp_scad_path = "temp_model.scad"
    with open(temp_scad_path, "w") as f:
        f.write(scad_code)
        
    try:
        # Run OpenSCAD in headless mode to render the STL
        result = subprocess.run(
            ["openscad", "-o", output_stl_path, temp_scad_path],
            capture_output=True,
            text=True,
            check=True
        )
        return f"Successfully generated CAD model at {output_stl_path}"
    except FileNotFoundError:
        return "Error: OpenSCAD is not installed or not in system PATH."
    except subprocess.CalledProcessError as e:
        return f"CAD Generation Error:\n{e.stderr}"
    finally:
        if os.path.exists(temp_scad_path):
            os.remove(temp_scad_path)

def build_cad_tool_schema():
    return {
        "name": "generate_cad_model",
        "description": "Generates a 3D STL CAD model from OpenSCAD code.",
        "parameters": {
            "type": "object",
            "properties": {
                "scad_code": {
                    "type": "string",
                    "description": "The OpenSCAD code to render."
                },
                "output_stl_path": {
                    "type": "string",
                    "description": "The file path to save the generated .stl file."
                }
            },
            "required": ["scad_code", "output_stl_path"]
        }
    }
