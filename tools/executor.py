import os
import importlib
import inspect
from typing import Tuple, List
from skills.base import BaseSkill
from providers.base import BaseProvider
from health.monitor import SystemMonitor
from security.permissions import PermissionManager

class ToolExecutor:
    """
    Acts as a Skill Loader and executor.
    Dynamically loads all skills from the `skills/` directory.
    """
    def __init__(self, provider: BaseProvider, monitor: SystemMonitor,
                 permission_manager: PermissionManager):
        self.provider = provider
        self.monitor = monitor
        self.permission_manager = permission_manager
        self.skills: List[BaseSkill] = []
        self._load_skills()

    def _load_skills(self):
        """Dynamically load all Skill classes from the skills package."""
        skills_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
        if not os.path.exists(skills_dir):
            return
            
        # Skill classes that receive specific dependencies
        SYSTEM_SKILLS = {"SystemSkill"}
        FILESYSTEM_SKILLS = {
            "FileReaderSkill", "DirectoryListerSkill",
            "FileWriterSkill", "TerminalSkill"
        }
        
        for filename in os.listdir(skills_dir):
            if filename.endswith(".py") and not filename.startswith("__") and filename != "base.py":
                module_name = f"skills.{filename[:-3]}"
                try:
                    module = importlib.import_module(module_name)
                    # Find classes in the module that inherit from BaseSkill
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseSkill) and obj is not BaseSkill:
                            # Instantiate with appropriate dependencies
                            if name in SYSTEM_SKILLS:
                                self.skills.append(obj(self.provider, self.monitor))
                            elif name in FILESYSTEM_SKILLS:
                                self.skills.append(obj(self.permission_manager))
                            else:
                                self.skills.append(obj())
                except Exception as e:
                    print(f"Failed to load skill {module_name}: {e}")

    async def execute(self, prompt: str, force_skill: str = None,
                      user_id: int = None) -> Tuple[str, str]:
        """
        Executes skills based on prompt parsing or explicit routing.
        Returns (result_text, tool_name).
        user_id is forwarded to skills for permission checks.
        """
        kwargs = {}
        if user_id is not None:
            kwargs["user_id"] = user_id

        # If the router explicitly requested a specific skill class
        if force_skill:
            for skill in self.skills:
                if skill.__class__.__name__ == force_skill:
                    return await skill.execute(prompt, **kwargs)
                    
        # Otherwise, find the first skill that matches the prompt
        for skill in self.skills:
            if skill.match(prompt):
                return await skill.execute(prompt, **kwargs)
                
        return ("Tool matched but execution logic is not fully implemented yet for this command.", "unknown_tool")

