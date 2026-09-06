import os
import asyncio
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from tools.base import BaseTool
from security.permissions import PermissionManager, HELIOS_DIR
import re

class RepoMapInput(BaseModel):
    directory: str = Field(description="The directory path to map.")
    extensions: Optional[List[str]] = Field(default=None, description="File extensions to include, e.g. ['.py', '.js']. Defaults to ['.py'].")

class RepoMapTool(BaseTool):
    name = "repo_map"
    description = "Generates a condensed structural map of a codebase showing only class names, function signatures, and imports. Use this to understand project structure before editing files."
    
    @property
    def input_schema(self):
        return RepoMapInput

    def __init__(self, permission_manager: PermissionManager):
        self.permission_manager = permission_manager
        
    async def execute(self, user_id: str, directory: str, extensions: Optional[List[str]] = None, **kwargs) -> Tuple[str, str]:
        if extensions is None:
            extensions = ['.py']
        return await asyncio.to_thread(self._sync_execute, directory, extensions)
        
    def _sync_execute(self, directory: str, extensions: List[str]) -> Tuple[str, str]:
        abs_dir = os.path.abspath(directory)
        if not abs_dir.startswith(os.path.abspath(HELIOS_DIR)):
            return "Error", f"Access denied: Path {directory} is outside HELIOS_DIR."
            
        if not os.path.isdir(abs_dir):
            return "Error", f"Directory {directory} not found."
            
        skip_dirs = {'__pycache__', '.git', 'node_modules', '.models', 'static'}
        result_lines = []
        
        class_re = re.compile(r'^(\s*)class\s+.*:')
        def_re = re.compile(r'^(\s*)(?:async\s+)?def\s+.*:')
        import_re = re.compile(r'^(\s*)(?:import\s+.*|from\s+.*import\s+.*)')
        
        for root, dirs, files in os.walk(abs_dir):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext not in extensions:
                    continue
                    
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, abs_dir)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        
                    file_map = []
                    for line in lines:
                        if class_re.match(line) or def_re.match(line) or import_re.match(line):
                            file_map.append(line.rstrip())
                            
                    if file_map:
                        result_lines.append(f"{rel_path}:")
                        for m_line in file_map:
                            result_lines.append(m_line)
                            
                except Exception as e:
                    result_lines.append(f"{rel_path}:")
                    result_lines.append(f"  # Error reading file: {e}")
                    
        output = "\n".join(result_lines)
        if len(output) > 4000:
            output = output[:4000] + "\n... [TRUNCATED due to length limit]"
            
        return "Success", output
