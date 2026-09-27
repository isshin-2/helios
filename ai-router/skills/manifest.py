"""
HELIOS — Dynamic Skill Manifest
Allows skills to declare their metadata, capabilities, and arguments explicitly.
Replaces the old regex-based matching with structured capabilities.
"""

import os
import importlib
import inspect
from typing import Dict, Any, List, Type
import logging

from skills.base import BaseSkill

logger = logging.getLogger("helios.skills.manifest")

class SkillManifest:
    """
    Scans and manages the dynamic loading of skills, building a manifest
    of their capabilities.
    """
    def __init__(self):
        self.skills: Dict[str, BaseSkill] = {}
        self.manifest: List[Dict[str, Any]] = []
        self._load_skills()

    def _load_skills(self):
        """Dynamically load all Skill classes from the skills package."""
        skills_dir = os.path.dirname(__file__)
        if not os.path.exists(skills_dir):
            return
            
        quarantine_dir = os.path.join(os.path.dirname(skills_dir), "quarantine")
        if not os.path.exists(quarantine_dir):
            try:
                os.makedirs(quarantine_dir, exist_ok=True)
            except Exception as e:
                logger.warning(f"Could not create quarantine directory: {e}")
            
        from skills.validator import validate_skill, log_validation_result
        import config
            
        for filename in os.listdir(skills_dir):
            if filename.endswith(".py") and not filename.startswith("__") and filename not in ("base.py", "validator.py", "manifest.py"):
                filepath = os.path.join(skills_dir, filename)
                
                # --- SECURITY GATE: Validate before import ---
                validation = validate_skill(filepath)
                
                load_decision = "QUARANTINE"
                
                if validation.status == "SCANNER_UNAVAILABLE":
                    # Fail-open for scanner unavailable, but disable dynamic loading?
                    # "Skillspector unavailable -> Disable dynamic skill loading -> Continue HELIOS core boot"
                    # We will log it and skip loading ANY further skills to simulate disabling dynamic loading.
                    log_validation_result(validation, "DISABLED_DYNAMIC_LOADING")
                    logger.warning("Skillspector unavailable. Disabling dynamic skill loading.")
                    break
                    
                elif validation.status == "SKIPPED":
                    load_decision = "LOAD"
                    
                elif validation.status == "SUCCESS":
                    rec = validation.risk_recommendation
                    if rec == "SAFE":
                        load_decision = "LOAD"
                    elif rec == "CAUTION":
                        if getattr(config, "SKILLS_REJECT_CAUTION", True):
                            load_decision = "QUARANTINE"
                        else:
                            load_decision = "LOAD"
                    elif rec == "DO_NOT_INSTALL":
                        load_decision = "QUARANTINE"
                    else:
                        load_decision = "QUARANTINE"
                else:
                    # SCAN_ERROR, SCAN_TIMEOUT -> Fail closed
                    load_decision = "QUARANTINE"
                    
                log_validation_result(validation, load_decision)
                
                if load_decision == "QUARANTINE":
                    skill_path = filepath
                    # Write quarantine metadata record
                    if getattr(config, "SKILLS_QUARANTINE_ENABLED", True):
                        q_file = os.path.join(quarantine_dir, f"{os.path.basename(skill_path)}.quarantine.json")
                        import json
                        with open(q_file, "w") as f:
                            json.dump({
                                "skill_file": filename,
                                "validation_status": validation.status,
                                "recommendation": validation.risk_recommendation,
                                "reason": validation.reason
                            }, f, indent=2)
                    continue
                
                # --- SAFE TO LOAD ---
                module_name = f"skills.{filename[:-3]}"
                try:
                    module = importlib.import_module(module_name)
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseSkill) and obj is not BaseSkill:
                            # Instantiate the skill
                            try:
                                skill_instance = obj()
                            except TypeError:
                                continue
                                
                            skill_name = getattr(skill_instance, "name", name)
                            self.skills[skill_name] = skill_instance
                            
                            # Add to manifest
                            capabilities = getattr(skill_instance, "required_capabilities", [])
                            self.manifest.append({
                                "name": skill_name,
                                "description": getattr(skill_instance, "description", ""),
                                "capabilities": [cap.name for cap in capabilities] if capabilities else []
                            })
                except Exception as e:
                    logger.error(f"Failed to load skill module {module_name}: {e}")

    def get_manifest(self) -> List[Dict[str, Any]]:
        """Returns the full manifest of loaded skills."""
        return self.manifest
        
    def get_skill(self, name: str) -> BaseSkill:
        """Retrieves a skill by name."""
        return self.skills.get(name)

manifest_manager = SkillManifest()
