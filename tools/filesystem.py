import os
import re
from pathlib import Path
from typing import Tuple, Optional
from pydantic import BaseModel, Field

from tools.base import BaseTool
from security.permissions import (
    PermissionManager, 
    HELIOS_DIR, 
    MAX_FILE_SIZE_BYTES,
    MAX_DIR_DEPTH,
    MAX_DIR_ENTRIES,
    is_binary_file
)

class FileReaderInput(BaseModel):
    file_path: str = Field(description="The absolute or relative path to the file to read.")

class FileReaderTool(BaseTool):
    def __init__(self, permission_manager: PermissionManager):
        self.permission_manager = permission_manager

    @property
    def name(self) -> str:
        return "FileReaderTool"

    @property
    def description(self) -> str:
        return "Reads the contents of a specified file. Fails if the file is binary or too large."

    @property
    def input_schema(self) -> type[BaseModel]:
        return FileReaderInput

    @property
    def requires_permission(self) -> bool:
        return True

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        working_directory = kwargs.get("working_directory", HELIOS_DIR)
        file_path = kwargs.get("file_path")
        
        if not file_path and "prompt" in kwargs:
            file_path = self._extract_path(kwargs["prompt"])
            
        if not file_path:
            return ("Error: No file_path provided.", self.name)
        
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(working_directory) / path
        resolved_str = str(path.resolve())

        perm = self.permission_manager.can_read_file(user_id, resolved_str)
        if not perm.allowed:
            return (f"**Permission denied**: {perm.reason}", self.name)

        safe_path: Path = perm.resolved_path or Path(resolved_str)

        if not safe_path.exists():
            self.permission_manager.log_operation(
                user_id, self.name, "read_file", str(safe_path),
                "APPROVED", error="File not found",
            )
            return (f"File not found: `{safe_path}`", self.name)

        if not safe_path.is_file():
            return (f"`{safe_path}` is not a regular file.", self.name)

        if is_binary_file(safe_path):
            size = safe_path.stat().st_size
            self.permission_manager.log_operation(
                user_id, self.name, "read_file", str(safe_path),
                "APPROVED", exec_result="binary_detected",
            )
            return (f"`{safe_path.name}` appears to be a binary file. I can't display its contents as text.", self.name)

        file_size = safe_path.stat().st_size

        if file_size > MAX_FILE_SIZE_BYTES:
            return self._read_large_file(safe_path, file_size, user_id)

        try:
            content = safe_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = safe_path.read_text(encoding="latin-1")

        self.permission_manager.log_operation(
            user_id, self.name, "read_file", str(safe_path),
            "APPROVED", exec_result=f"read {len(content)} chars",
        )

        ext = safe_path.suffix.lstrip(".")
        return (f"**{safe_path.name}**:\n```{ext}\n{content}\n```", self.name)

    def _read_large_file(self, filepath: Path, file_size: int, user_id: int) -> Tuple[str, str]:
        lines: list[str] = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i >= 500:
                        break
                    lines.append(line)
        except OSError as exc:
            return (f"Error reading `{filepath.name}`: {exc}", self.name)
            
        self.permission_manager.log_operation(
            user_id, self.name, "read_file", str(filepath),
            "APPROVED", exec_result=f"large_file_preview ({file_size} bytes)",
        )
        
        ext = filepath.suffix.lstrip(".")
        preview = "".join(lines)
        return (
            f"**File too large** `{filepath.name}` is over the limit.\n\n"
            f"Here are the first {len(lines)} lines:\n"
            f"```{ext}\n{preview}```",
            self.name
        )


    def _extract_path(self, prompt: str) -> Optional[str]:
        cleaned = re.sub(r"^(read|open|cat|show|look at|display|view)\s+", "", prompt.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"^(me\s+)?(the\s+)?(code|contents?|file)\s+(in|of|from)\s+", "", cleaned, flags=re.IGNORECASE)
        match = re.search(r"['\"]?([a-zA-Z0-9_./\\-]+)['\"]?", cleaned)
        if match:
            return match.group(1)
        return None

class FileWriterInput(BaseModel):
    file_path: str = Field(description="The absolute or relative path to the file to write.")
    content: str = Field(description="The text content to write to the file.")

class FileWriterTool(BaseTool):
    def __init__(self, permission_manager: PermissionManager):
        self.permission_manager = permission_manager

    @property
    def name(self) -> str:
        return "FileWriterTool"

    @property
    def description(self) -> str:
        return "Writes content to a specified file. Requires user approval."

    @property
    def input_schema(self) -> type[BaseModel]:
        return FileWriterInput

    @property
    def requires_permission(self) -> bool:
        return True

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        working_directory = kwargs.get("working_directory", HELIOS_DIR)
        file_path = kwargs.get("file_path")
        content = kwargs.get("content", "")
        
        if not file_path and "prompt" in kwargs:
            # Basic fallback for legacy prompt
            match = re.search(r"(?:write to|save to|create file|modify file)\s+(['\"]?)([^\s'\"]+)\1", kwargs["prompt"], re.IGNORECASE)
            if match:
                file_path = match.group(2)
                
        if not file_path:
            return ("Error: No file_path provided.", self.name)
        
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(working_directory) / path
        resolved_str = str(path.resolve())

        perm = self.permission_manager.can_write_file(user_id, resolved_str)
        if not perm.allowed:
            return (f"**Permission denied**: {perm.reason}", self.name)

        # FileWriter halts and asks for approval.
        self._pending_content = content
        
        return (f"APPROVAL_REQUIRED::file_write::{resolved_str}", self.name)

    async def perform_write(self, path: str, content: str, user_id: int) -> Tuple[str, str]:
        """Actually write the file after approval has been granted."""
        result = self.permission_manager.can_write_file(user_id, path)
        if not result.allowed:
            return (result.reason, self.name)
            
        try:
            resolved = result.resolved_path
            resolved.parent.mkdir(parents=True, exist_ok=True)
            write_content = getattr(self, '_pending_content', content)
            with open(resolved, 'w', encoding='utf-8') as f:
                f.write(write_content)
            self.permission_manager.log_operation(
                user_id, self.name, 'write_file',
                str(resolved), 'APPROVED', 'SUCCESS'
            )
            self._pending_content = ""
            return (f"Successfully wrote to {resolved}", self.name)
        except Exception as e:
            self.permission_manager.log_operation(
                user_id, self.name, 'write_file',
                str(path), 'APPROVED', 'FAILED', str(e)
            )
            return (f"Failed to write file: {e}", self.name)


class DirectoryListerInput(BaseModel):
    directory_path: str = Field(description="The path to the directory to list.")

class DirectoryListerTool(BaseTool):
    def __init__(self, permission_manager: PermissionManager):
        self.permission_manager = permission_manager

    @property
    def name(self) -> str:
        return "DirectoryListerTool"

    @property
    def description(self) -> str:
        return "Recursively lists contents of a directory."

    @property
    def input_schema(self) -> type[BaseModel]:
        return DirectoryListerInput

    @property
    def requires_permission(self) -> bool:
        return True

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        working_directory = kwargs.get("working_directory", HELIOS_DIR)
        directory_path = kwargs.get("directory_path")
        
        if not directory_path and "prompt" in kwargs:
            match = re.search(r"(?:list files|show files in|ls|dir)\s+(['\"]?)([^\s'\"]+)\1", kwargs["prompt"], re.IGNORECASE)
            if match:
                directory_path = match.group(2)
            else:
                directory_path = "."
                
        if not directory_path:
            return ("Error: No directory_path provided.", self.name)
        
        path = Path(directory_path)
        if not path.is_absolute():
            path = Path(working_directory) / path
        resolved_str = str(path.resolve())

        perm = self.permission_manager.can_list_directory(user_id, resolved_str)
        if not perm.allowed:
            return (f"**Permission denied**: {perm.reason}", self.name)
            
        safe_path: Path = perm.resolved_path or Path(resolved_str)
        
        if not safe_path.exists():
            return (f"Directory not found: `{safe_path}`", self.name)
            
        if not safe_path.is_dir():
            return (f"`{safe_path}` is not a directory.", self.name)
            
        tree = self._build_tree(safe_path, depth=0)
        self.permission_manager.log_operation(
            user_id, self.name, "list_directory", str(safe_path),
            "APPROVED", "SUCCESS"
        )
        return (f"Directory listing for **{safe_path.name}**:\n```\n{tree}\n```", self.name)
        
    def _build_tree(self, path: Path, depth: int, max_depth: int = MAX_DIR_DEPTH) -> str:
        if depth > max_depth:
            return "  " * depth + "└── [Max Depth Reached]\n"
            
        out = ""
        try:
            entries = list(path.iterdir())
            entries = [e for e in entries if not e.name.startswith('.') and e.name not in ('__pycache__', 'node_modules')]
            entries.sort(key=lambda x: (not x.is_dir(), x.name))
            
            for i, entry in enumerate(entries[:MAX_DIR_ENTRIES]):
                prefix = "└── " if i == len(entries) - 1 else "├── "
                indent = "  " * depth
                if entry.is_dir():
                    out += f"{indent}{prefix}📁 {entry.name}\n"
                    out += self._build_tree(entry, depth + 1, max_depth)
                else:
                    out += f"{indent}{prefix}📄 {entry.name}\n"
                    
            if len(entries) > MAX_DIR_ENTRIES:
                out += f"{'  ' * depth}└── ... ({len(entries) - MAX_DIR_ENTRIES} more entries)\n"
                
        except PermissionError:
            out += f"{'  ' * depth}└── [Permission Denied]\n"
            
        return out
