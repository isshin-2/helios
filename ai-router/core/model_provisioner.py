import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

INITIALIZED_FILE = ".helios_initialized.json"

def is_initialized(base_dir: str = ".") -> bool:
    return os.path.exists(os.path.join(base_dir, INITIALIZED_FILE))

def read_initialized_manifest(base_dir: str = ".") -> Optional[Dict]:
    path = os.path.join(base_dir, INITIALIZED_FILE)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

async def run_first_start_provisioning(event_bus=None, base_dir: str = ".") -> Dict[str, Any]:
    from config import LLM_PROVIDER
    import config
    
    # Check if local models are enabled
    enable_local = getattr(config, "ENABLE_LOCAL_MODELS", True)
    if not enable_local or LLM_PROVIDER not in ["ollama", "localai", "pair"]:
        logger.info("Local model provisioning skipped (local models disabled or non-local provider selected).")
        return {"status": "skipped"}

    if is_initialized(base_dir):
        return {"status": "already_initialized"}
        
    logger.info("Starting HELIOS First-Start Provisioning with llmfit...")
    
    from providers.ollama import OllamaProvider
    from config import OLLAMA_HOST
    provider = OllamaProvider(host=OLLAMA_HOST)
    
    if event_bus:
        await event_bus.publish("provisioning_event", {"event": "HARDWARE_SCAN_START"})
    
    # Run llmfit recommend
    llmfit_path = os.path.join(base_dir, "llmfit_bin", "llmfit-v1.1.15-x86_64-pc-windows-msvc", "llmfit.exe")
    
    if not os.path.exists(llmfit_path):
        logger.error("llmfit not found. Cannot auto-provision.")
        return {"status": "error", "message": "llmfit missing"}
        
    try:
        process = await asyncio.create_subprocess_exec(
            llmfit_path, "recommend", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            return {"status": "error", "message": "llmfit failed"}
            
        data = json.loads(stdout.decode())
        recommendations = data.get("recommendations", [])
    except Exception as e:
        logger.error(f"llmfit execution error: {e}")
        return {"status": "error", "message": str(e)}

    # Find the best models to pull
    general_model = None
    embedding_model = None
    
    for rec in recommendations:
        ollama_name = rec.get("ollama_name")
        if not ollama_name:
            continue
            
        role = rec.get("category", "").lower()
        
        if role == "embedding" and not embedding_model:
            embedding_model = ollama_name
        elif not general_model:
            general_model = ollama_name
            
        if general_model and embedding_model:
            break
            
    # Fallbacks if llmfit didn't recommend an ollama model
    if not general_model:
        general_model = "llama3.2"
        
    models_to_pull = [general_model]
    if embedding_model:
        models_to_pull.append(embedding_model)
        
    provisioned = []
    
    for model in models_to_pull:
        if event_bus:
            await event_bus.publish("provisioning_event", {"event": "PULLING_MODEL", "model": model})
            
        logger.info(f"llmfit recommended pulling: {model}")
        success = await provider.pull_model(model)
        if success:
            provisioned.append(model)
            
    # Write initialized file
    manifest = {
        "status": "initialized",
        "models": provisioned,
        "provisioner": "llmfit"
    }
    
    with open(os.path.join(base_dir, INITIALIZED_FILE), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    if event_bus:
        await event_bus.publish("provisioning_event", {"event": "COMPLETED"})
        
    try:
        await provider.close()
    except:
        pass
        
    return {"status": "success", "provisioned_models": provisioned}

def load_checkpoint(*args, **kwargs):
    return None

def save_checkpoint(*args, **kwargs):
    pass
