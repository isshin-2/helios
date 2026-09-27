import os
import asyncio
import difflib
from typing import Tuple, Optional
from pydantic import BaseModel, Field
from tools.base import BaseTool
from security.permissions import PermissionManager, HELIOS_DIR

class FilePatchInput(BaseModel):
    file_path: str = Field(description="Path to the file to patch.")
    search_block: str = Field(description="The exact text block to find in the file. Must match exactly.")
    replace_block: str = Field(description="The replacement text to substitute.")

class FilePatchTool(BaseTool):
    name = "file_patch"
    description = "Surgically edits a file by finding an exact text block and replacing it. Much safer than rewriting entire files. Use SEARCH/REPLACE blocks."
    
    @property
    def input_schema(self):
        return FilePatchInput
        
    @property
    def requires_permission(self) -> bool:
        return True

    def __init__(self, permission_manager: PermissionManager):
        self.permission_manager = permission_manager
        
    async def execute(self, user_id: str, file_path: str, search_block: str, replace_block: str, **kwargs) -> Tuple[str, str]:
        return await asyncio.to_thread(self._sync_execute, user_id, file_path, search_block, replace_block)
        
    def _sync_execute(self, user_id: str, file_path: str, search_block: str, replace_block: str) -> Tuple[str, str]:
        abs_path = os.path.abspath(file_path)
        if not abs_path.startswith(os.path.abspath(HELIOS_DIR)):
            return "Error", f"Access denied: Path {file_path} is outside HELIOS_DIR."
            
        if not os.path.exists(abs_path):
            return "Error", f"File {file_path} not found."
            
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            def normalize_block(text: str) -> str:
                return '\n'.join([line.rstrip() for line in text.split('\n')])
                
            norm_content = normalize_block(content)
            norm_search = normalize_block(search_block)
            
            count = norm_content.count(norm_search)
            
            if count == 0:
                return "Error", "Search block not found. Try providing more context lines or ensure exact match."
            elif count > 1:
                return "Error", "Search block found multiple times. Provide more context lines to make it unique."
                
            new_norm_content = norm_content.replace(norm_search, replace_block)
            
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(new_norm_content)
                
            old_lines = content.splitlines(keepends=True)
            new_lines = new_norm_content.splitlines(keepends=True)
            diff = "".join(difflib.unified_diff(
                old_lines, new_lines,
                fromfile=f"a/{os.path.basename(abs_path)}",
                tofile=f"b/{os.path.basename(abs_path)}"
            ))
            
            # self.permission_manager.log_action("file_patch", user_id, file_path=file_path)
            
            return "Success", diff
            
        except Exception as e:
            return "Error", str(e)
