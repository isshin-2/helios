import os
from sandbox.manager import SandboxManager

# Ensure package structure
if not os.path.exists(os.path.join(os.path.dirname(__file__), "__init__.py")):
    with open(os.path.join(os.path.dirname(__file__), "__init__.py"), "w") as f:
        f.write("# Sandbox package\n")
