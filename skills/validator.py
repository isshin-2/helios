import os
import sys
import json
import subprocess
import shutil
import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import uuid

import config

logger = logging.getLogger("helios.skills.validator")

@dataclass
class ValidationResult:
    status: str
    risk_recommendation: str
    reason: str
    skill_path: str
    scanner_available: bool
    raw_result: Optional[dict] = None

def get_skillspector_cmd():
    if shutil.which("skillspector"):
        return ["skillspector"]
    elif os.path.exists(os.path.join(sys.prefix, "Scripts", "skillspector.exe")):
        return [os.path.join(sys.prefix, "Scripts", "skillspector.exe")]
    elif os.path.exists(os.path.join(sys.prefix, "bin", "skillspector")):
        return [os.path.join(sys.prefix, "bin", "skillspector")]
    else:
        return [sys.executable, "-m", "skillspector"]

def validate_skill(path: str) -> ValidationResult:
    if not getattr(config, "SKILLS_VALIDATION_ENABLED", True):
        return ValidationResult("SKIPPED", "SAFE", "Validation disabled", path, False)
        
    timeout = getattr(config, "SKILLS_VALIDATION_TIMEOUT", 15)
    
    cmd = get_skillspector_cmd()
    
    # Try running it to check if it's installed
    try:
        subprocess.run(cmd + ["--help"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ValidationResult("SCANNER_UNAVAILABLE", "ERROR", "Skillspector not installed", path, False)

    # Build the CLI command
    use_llm = getattr(config, "SKILLSPECTOR_LLM_ANALYSIS", False)
    scan_cmd = cmd + ["scan", path, "-f", "json"]
    if not use_llm:
        scan_cmd.append("--no-llm")

    try:
        process = subprocess.run(
            scan_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        # In JSON mode, skillspector prints logging to stderr and the JSON output to stdout.
        # So we can just parse process.stdout
        try:
            # Find the first '{' in case there's any stray output before JSON
            start_idx = process.stdout.find('{')
            if start_idx == -1:
                json_str = "{}"
            else:
                json_str = process.stdout[start_idx:]
            
            data = json.loads(json_str)
            if "risk_assessment" not in data or "recommendation" not in data["risk_assessment"]:
                return ValidationResult("SCAN_ERROR", "ERROR", f"Missing recommendation in output. Stderr: {process.stderr}", path, True)
                
            rec = data["risk_assessment"]["recommendation"].upper()
            return ValidationResult("SUCCESS", rec, data.get("summary", "No summary"), path, True, raw_result=data)
            
        except json.JSONDecodeError:
            return ValidationResult("SCAN_ERROR", "ERROR", f"Invalid JSON output. Stdout: {process.stdout} Stderr: {process.stderr}", path, True)
            
    except subprocess.TimeoutExpired:
        return ValidationResult("SCAN_TIMEOUT", "ERROR", f"Scan timed out after {timeout}s", path, True)
    except Exception as e:
        return ValidationResult("SCAN_ERROR", "ERROR", f"Failed to execute scanner: {str(e)}", path, True)

def log_validation_result(result: ValidationResult, action: str):
    log_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": str(uuid.uuid4()), # Ideally from a global session
        "skill_path": result.skill_path,
        "scanner_available": result.scanner_available,
        "status": result.status,
        "risk_recommendation": result.risk_recommendation,
        "reason": result.reason,
        "action": action
    }
    # Log as structured JSON
    logger.warning(f"SKILL VALIDATION EVENT: {json.dumps(log_data)}")
