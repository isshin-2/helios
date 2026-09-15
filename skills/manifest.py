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
            
        for filename in os.listdir(skills_dir):
            if filename.endswith(".py") and not filename.startswith("__") and filename != "base.py":
                module_name = f"skills.{filename[:-3]}"
                try:
                    module = importlib.import_module(module_name)
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseSkill) and obj is not BaseSkill:
                            # Instantiate the skill (we pass empty kwargs, in reality they might need dependencies)
                            try:
                                skill_instance = obj()
                            except TypeError:
                                # Skip skills that require dependencies for now during manifest building
                                # A full DI container would inject dependencies here
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
