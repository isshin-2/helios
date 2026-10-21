"""
HELIOS — Process & System Monitoring Tool
Inspects running processes, listening ports, CPU/RAM metrics, and terminates
hung or unwanted processes with permission checks.
"""

import os
import psutil
from typing import Tuple, List, Optional, Dict, Any
from pydantic import BaseModel, Field
from tools.base import BaseTool
from security.permissions import PermissionManager

class ProcessMonitorInput(BaseModel):
    action: str = Field(
        ...,
        description="Action to perform: 'list_ports', 'list_processes', 'system_stats', 'kill_process'."
    )
    port: Optional[int] = Field(
        default=None,
        description="Optional port number to inspect or filter by (e.g. 8000, 8080, 11434)."
    )
    process_name: Optional[str] = Field(
        default=None,
        description="Optional process name to filter (e.g. 'python.exe', 'ollama.exe')."
    )
    pid: Optional[int] = Field(
        default=None,
        description="Target Process ID for action='kill_process'."
    )

class ProcessMonitorTool(BaseTool):
    """
    Real-time process, port binding, and hardware utilization inspection.
    """
    def __init__(self, permission_manager: Optional[PermissionManager] = None):
        self.permission_manager = permission_manager

    @property
    def name(self) -> str:
        return "process_monitor"

    @property
    def aliases(self) -> List[str]:
        return ["ProcessMonitorTool", "ps_monitor"]

    @property
    def description(self) -> str:
        return (
            "Monitor running processes, open network ports, CPU/memory stats, "
            "and terminate tasks safely."
        )

    @property
    def input_schema(self) -> type[BaseModel]:
        return ProcessMonitorInput

    @property
    def requires_permission(self) -> bool:
        return True

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        action = kwargs.get("action", "").lower().strip()
        port = kwargs.get("port")
        name_filter = kwargs.get("process_name")
        pid = kwargs.get("pid")

        if action == "system_stats":
            cpu_percent = psutil.cpu_percent(interval=0.1)
            vmem = psutil.virtual_memory()
            disk = psutil.disk_usage(os.path.abspath(os.sep))
            report = (
                f"**System Resource Status:**\n"
                f"- CPU Usage: {cpu_percent}%\n"
                f"- RAM Usage: {vmem.percent}% ({vmem.used // (1024**2)}MB / {vmem.total // (1024**2)}MB)\n"
                f"- Available RAM: {vmem.available // (1024**2)}MB\n"
                f"- Disk Usage: {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)"
            )
            return (report, self.name)

        elif action == "list_ports":
            active_listeners = []
            try:
                for conn in psutil.net_connections(kind='inet'):
                    if conn.status == psutil.CONN_LISTEN:
                        lport = conn.laddr.port
                        if port and lport != port:
                            continue
                        proc_name = "unknown"
                        if conn.pid:
                            try:
                                proc = psutil.Process(conn.pid)
                                proc_name = proc.name()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                        active_listeners.append(
                            f"- Port {lport:5d} | PID: {conn.pid or -1:6d} | Process: {proc_name}"
                        )
            except Exception as e:
                return (f"Error querying network connections: {e}", self.name)

            if not active_listeners:
                return (f"No listening ports found matching criteria (port={port}).", self.name)

            # Sort and truncate
            active_listeners.sort()
            out = f"**Active Listening Ports ({len(active_listeners)}):**\n" + "\n".join(active_listeners[:50])
            return (out, self.name)

        elif action == "list_processes":
            procs = []
            name_lower = name_filter.lower() if name_filter else None
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                try:
                    pname = p.info['name'] or ""
                    if name_lower and name_lower not in pname.lower():
                        continue
                    mem_mb = (p.info['memory_info'].rss // (1024**2)) if p.info['memory_info'] else 0
                    procs.append((mem_mb, p.info['pid'], pname))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Sort by highest memory consumption
            procs.sort(key=lambda x: x[0], reverse=True)
            results = [f"- PID {pid:6d} | Memory: {mem:5d}MB | Name: {pname}" for mem, pid, pname in procs[:30]]
            out = f"**Top Processes by Memory (matching '{name_filter or '*'}'):**\n" + "\n".join(results)
            return (out, self.name)

        elif action == "kill_process":
            if not pid:
                return ("Error: 'pid' is required for action='kill_process'.", self.name)
            
            # Enforce zero-trust approval for terminating processes
            if self.permission_manager:
                perm = self.permission_manager.approval_manager.is_approved(user_id, "kill_process", str(pid))
                if not perm:
                    return (f"APPROVAL_REQUIRED::kill_process::{pid}", self.name)

            try:
                proc = psutil.Process(pid)
                pname = proc.name()
                proc.terminate()
                return (f"Successfully sent termination signal to process '{pname}' (PID: {pid}).", self.name)
            except psutil.NoSuchProcess:
                return (f"Error: Process with PID {pid} does not exist.", self.name)
            except Exception as e:
                return (f"Error killing process {pid}: {e}", self.name)

        return (f"Error: Unknown action '{action}'.", self.name)
