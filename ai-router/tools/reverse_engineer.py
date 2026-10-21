"""
HELIOS — Reverse Engineer Anything (REA) Tool
Inspired by awesome-reverse-engineer-anything (https://github.com/AIshihzong/awesome-reverse-engineer-anything)
and the Morluto REA agent framework.

Enables agents to:
1. Extract static metadata and architecture info from binaries (PE, ELF, Mach-O, ZIP/JAR/APK).
2. Extract readable strings (ASCII / Unicode) filtered by entropy and min length.
3. Inspect exported symbols, sections, headers, and dependencies.
4. Query curated REA methodologies, cases, and decompilation techniques (Ghidra, IDA, JADX, radare2).
"""

import os
import re
import struct
import zipfile
from typing import Tuple, List, Optional, Dict, Any
from pydantic import BaseModel, Field
from tools.base import BaseTool
from security.permissions import PermissionManager, HELIOS_DIR

# Curated intelligence database from awesome-reverse-engineer-anything & modern REA patterns
REA_KNOWLEDGE_BASE = {
    "ghidra": (
        "**Ghidra Decompilation Workflow:**\n"
        "- Headless analysis: `analyzeHeadless <project_dir> <proj_name> -import <target_file> -postScript <script.py>`\n"
        "- Best suited for: C/C++ native binaries (x86, x64, ARM, MIPS), firmware blobs, and complex architectures.\n"
        "- Key tips: Identify string references -> xref back to functions -> rename variables and parameter types."
    ),
    "jadx": (
        "**JADX APK/DEX/JVM Decompilation Workflow:**\n"
        "- CLI: `jadx -d <output_dir> <target.apk|target.jar>`\n"
        "- Best suited for: Android applications, Java/Kotlin JARs, and Dalvik bytecode.\n"
        "- Key tips: Check `AndroidManifest.xml` for exported components, search for API endpoints and crypto keys in assets/."
    ),
    "ilspy": (
        "**ILSpy / dnSpy (.NET / C# / Unity) Decompilation:**\n"
        "- CLI: `ilspycmd -p -o <output_dir> <assembly.dll>`\n"
        "- Best suited for: Unity games (`Assembly-CSharp.dll`), .NET Core / Framework executables.\n"
        "- Key tips: Near-complete source reconstruction is possible because metadata and symbol names are preserved in CIL."
    ),
    "electron": (
        "**Electron / Desktop JS App Unpacking:**\n"
        "- CLI: `npx asar extract resources/app.asar <output_dir>`\n"
        "- Best suited for: VS Code, Slack, Discord, and hybrid desktop apps.\n"
        "- Key tips: Look for main process entry point (`package.json` -> `main`), IPC handlers (`ipcMain.handle`), and embedded web assets."
    ),
    "radare2": (
        "**Radare2 / Rizin Quick Triage:**\n"
        "- Commands: `r2 -A <binary>`, then `iI` (binary info), `iE` (exports), `izz` (strings in data sections), `afl` (list functions).\n"
        "- Best suited for: Fast CLI inspection without heavy GUI overhead."
    )
}

class ReverseEngineerInput(BaseModel):
    action: str = Field(
        ...,
        description="Action to perform: 'inspect_binary', 'extract_strings', 'inspect_sections', 'rea_knowledge'."
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Path to target binary, DLL, APK, JAR, or executable to inspect."
    )
    min_string_length: Optional[int] = Field(
        default=5,
        description="Minimum character length when action='extract_strings' (default: 5)."
    )
    topic: Optional[str] = Field(
        default=None,
        description="Topic query for action='rea_knowledge' (e.g. 'ghidra', 'jadx', 'electron', 'ilspy', 'radare2')."
    )

class ReverseEngineerTool(BaseTool):
    """
    Reverse Engineer Anything (REA) orchestration and static binary analysis tool.
    """
    def __init__(self, permission_manager: Optional[PermissionManager] = None):
        self.permission_manager = permission_manager

    @property
    def name(self) -> str:
        return "reverse_engineer"

    @property
    def aliases(self) -> List[str]:
        return ["ReverseEngineerTool", "rea_inspector", "rea"]

    @property
    def description(self) -> str:
        return (
            "Reverse Engineer Anything (REA) tool: inspect binary headers (PE/ELF/Mach-O/ZIP), "
            "extract ASCII/Unicode strings, audit sections, and retrieve curated reverse engineering knowledge."
        )

    @property
    def input_schema(self) -> type[BaseModel]:
        return ReverseEngineerInput

    @property
    def requires_permission(self) -> bool:
        return True

    def _detect_file_format(self, data: bytes) -> str:
        if data.startswith(b"MZ"):
            return "Windows PE (Portable Executable / DLL / EXE)"
        elif data.startswith(b"\x7fELF"):
            return "Linux ELF (Executable and Linkable Format)"
        elif data.startswith((b"\xca\xfe\xba\xbe", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe")):
            return "Apple Mach-O Binary or Java Class"
        elif data.startswith(b"PK\x03\x04"):
            return "ZIP Archive (possible JAR, APK, or Office document)"
        elif data.startswith(b"dex\n"):
            return "Android DEX (Dalvik Executable)"
        return "Unknown Binary Format"

    def _extract_ascii_and_unicode_strings(self, data: bytes, min_len: int = 5, limit: int = 60) -> List[str]:
        # ASCII strings regex
        ascii_matches = re.findall(rb"[\x20-\x7e]{" + str(min_len).encode() + rb",}", data)
        # UTF-16LE strings (common in Windows binaries)
        utf16_matches = re.findall(rb"(?:[\x20-\x7e]\x00){" + str(min_len).encode() + rb",}", data)

        results = []
        for m in ascii_matches[:limit]:
            try:
                results.append(m.decode("ascii"))
            except Exception:
                pass
        for m in utf16_matches[:limit // 2]:
            try:
                results.append(m.decode("utf-16le"))
            except Exception:
                pass
        return list(dict.fromkeys(results))[:limit]

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        action = kwargs.get("action", "").lower().strip()
        file_path = kwargs.get("file_path")
        min_len = int(kwargs.get("min_string_length") or 5)
        topic = (kwargs.get("topic") or "").lower().strip()

        if action == "rea_knowledge":
            if topic and topic in REA_KNOWLEDGE_BASE:
                return (REA_KNOWLEDGE_BASE[topic], self.name)
            
            # List available knowledge topics
            topics = "\n".join([f"- **{k}**: {REA_KNOWLEDGE_BASE[k].splitlines()[0]}" for k in sorted(REA_KNOWLEDGE_BASE.keys())])
            return (
                f"**Awesome REA (Reverse Engineer Anything) Knowledge Guide:**\n\n"
                f"REA lets coding agents inspect native binaries, Electron apps, .NET assemblies, "
                f"APKs, and firmware without source code.\n\n"
                f"Available Topic Guides:\n{topics}\n\n"
                f"*(Specify topic='ghidra' or 'jadx' etc. for complete instructions)*",
                self.name
            )

        if not file_path:
            return ("Error: 'file_path' is required for binary inspection actions.", self.name)

        if not os.path.exists(file_path):
            # Check relative to HELIOS_DIR
            alt_path = os.path.join(HELIOS_DIR, file_path)
            if os.path.exists(alt_path):
                file_path = alt_path
            else:
                return (f"Error: File '{file_path}' not found.", self.name)

        file_size = os.path.getsize(file_path)

        if action == "inspect_binary":
            with open(file_path, "rb") as fp:
                head = fp.read(4096)

            fmt = self._detect_file_format(head)
            report = [
                f"**REA Binary Inspection for `{os.path.basename(file_path)}`:**",
                f"- Full Path: `{file_path}`",
                f"- File Size: {file_size:,} bytes ({file_size // 1024} KB)",
                f"- Format Detected: **{fmt}**"
            ]

            # PE specific inspection
            if "PE" in fmt and len(head) >= 0x40:
                e_lfanew = struct.unpack_from("<I", head, 0x3C)[0]
                if e_lfanew < len(head) - 24:
                    pe_sig = head[e_lfanew:e_lfanew+4]
                    if pe_sig == b"PE\x00\x00":
                        machine = struct.unpack_from("<H", head, e_lfanew + 4)[0]
                        num_sections = struct.unpack_from("<H", head, e_lfanew + 6)[0]
                        arch_map = {0x014c: "i386 (32-bit)", 0x8664: "AMD64 (64-bit)", 0xaa64: "ARM64"}
                        arch_str = arch_map.get(machine, f"Machine: 0x{machine:04x}")
                        report.append(f"- Architecture: {arch_str}")
                        report.append(f"- Number of Sections: {num_sections}")

            # ZIP / APK / JAR specific inspection
            elif "ZIP" in fmt:
                try:
                    with zipfile.ZipFile(file_path, 'r') as z:
                        namelist = z.namelist()
                        report.append(f"- Archive Entries: {len(namelist)} files")
                        sample = [f"  - `{n}`" for n in namelist[:15]]
                        report.append("- Sample Contents:\n" + "\n".join(sample))
                        if len(namelist) > 15:
                            report.append(f"  ... and {len(namelist) - 15} more entries.")
                except Exception as e:
                    report.append(f"- Warning reading archive entries: {e}")

            return ("\n".join(report), self.name)

        elif action == "extract_strings":
            # Read up to first 2MB for string extraction to maintain responsiveness
            read_size = min(file_size, 2 * 1024 * 1024)
            with open(file_path, "rb") as fp:
                data = fp.read(read_size)

            found_strings = self._extract_ascii_and_unicode_strings(data, min_len=min_len, limit=50)
            if not found_strings:
                return (f"No strings >= {min_len} characters found in {os.path.basename(file_path)}.", self.name)

            out = [
                f"**Extracted Strings ({len(found_strings)}) from `{os.path.basename(file_path)}`:**",
                "```text"
            ] + found_strings + ["```"]
            return ("\n".join(out), self.name)

        elif action == "inspect_sections":
            with open(file_path, "rb") as fp:
                head = fp.read(8192)

            fmt = self._detect_file_format(head)
            if "PE" not in fmt:
                return (f"Section header parsing currently supports PE binaries. Detected: {fmt}", self.name)

            e_lfanew = struct.unpack_from("<I", head, 0x3C)[0]
            num_sections = struct.unpack_from("<H", head, e_lfanew + 6)[0]
            opt_hdr_size = struct.unpack_from("<H", head, e_lfanew + 20)[0]
            sec_start = e_lfanew + 24 + opt_hdr_size

            sections = []
            for i in range(min(num_sections, 16)):
                offset = sec_start + (i * 40)
                if offset + 40 <= len(head):
                    sec_name = head[offset:offset+8].rstrip(b"\x00").decode("ascii", errors="ignore")
                    v_size = struct.unpack_from("<I", head, offset + 8)[0]
                    v_addr = struct.unpack_from("<I", head, offset + 12)[0]
                    raw_size = struct.unpack_from("<I", head, offset + 16)[0]
                    sections.append(f"- Section `{sec_name:8s}` | VirtSize: 0x{v_size:08x} | VirtAddr: 0x{v_addr:08x} | RawSize: {raw_size:,}B")

            if not sections:
                return (f"Could not locate PE section headers in buffer for {os.path.basename(file_path)}.", self.name)

            return (
                f"**PE Sections for `{os.path.basename(file_path)}` ({len(sections)} sections):**\n" +
                "\n".join(sections),
                self.name
            )

        return (f"Error: Unknown action '{action}'.", self.name)
