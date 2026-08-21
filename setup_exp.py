import asyncio
import os
from skills.self_modification.workspace import ExperimentWorkspace
from security.permissions import PermissionManager
from skills.self_modification.models import RiskLevel

async def setup():
    pm = PermissionManager()
    ws = ExperimentWorkspace(pm)
    
    # 1. Create Experiment
    meta = ws.create_experiment("Clean up and reorganize the HELIOS system UI. Create a single System menu.", RiskLevel.LOW)
    print(f"EXPERIMENT_ID={meta.experiment_id}")
    
    # 2. Copy static/app.html
    success, msg = ws.copy_file_to_experiment(meta.experiment_id, "static/app.html")
    print(f"COPY_RESULT={success}, MSG={msg}")

if __name__ == "__main__":
    asyncio.run(setup())
