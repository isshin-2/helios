"""
HELIOS Client — Interactive Terminal & Swarm Console
Rich Claude-Code and Codex-style terminal for interacting with remote HELIOS Core.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import subprocess
import sys
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from .config import (
        check_server_health,
        get_server_url,
        get_ws_url,
        set_server_url,
        wake_server_wol,
        load_client_config,
    )
    from .api_client import HeliosAPIClient
except ImportError:
    from config import (
        check_server_health,
        get_server_url,
        get_ws_url,
        set_server_url,
        wake_server_wol,
        load_client_config,
    )
    from api_client import HeliosAPIClient

# Try importing rich for enhanced terminal aesthetics
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich.markdown import Markdown
    from rich.text import Text
    from rich.align import Align
    HAS_RICH = True
    console = Console(force_terminal=True, legacy_windows=False)
except ImportError:
    HAS_RICH = False
    console = None


class HeliosClientCLI:
    """Terminal client connecting to remote HELIOS server."""

    def __init__(self, server_url: Optional[str] = None):
        self.server_url = (server_url or get_server_url()).rstrip("/")
        self.api = HeliosAPIClient(self.server_url)
        self.workspace_dir = os.path.abspath(os.getcwd())
        self.session_id: Optional[str] = None

    def get_git_branch(self) -> str:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass
        return "main"

    def print_banner(self, health_info: Dict[str, Any]):
        online = health_info.get("online", False)
        lat = health_info.get("latency_ms", 0.0)
        status_badge = f"[bold green]● ONLINE ({lat}ms)[/bold green]" if online else "[bold red]○ OFFLINE[/bold red]"
        branch = self.get_git_branch()
        node_name = platform.node()

        if HAS_RICH:
            banner_table = Table.grid(expand=True)
            banner_table.add_column(justify="left", ratio=3)
            banner_table.add_column(justify="right", ratio=2)

            title_markup = "[bold cyan]✦ HELIOS CLIENT[/bold cyan] [dim]v2.1.0 · REMOTE PROTOCOL[/dim]"
            banner_table.add_row(
                title_markup,
                f"Status: {status_badge}"
            )
            banner_table.add_row(
                f"[dim]Server:[/dim] [cyan]{self.server_url}[/cyan]",
                f"[dim]Client Node:[/dim] [bright_magenta]{node_name}[/bright_magenta]"
            )
            banner_table.add_row(
                f"[dim]Local Workspace:[/dim] [yellow]{self.workspace_dir}[/yellow]",
                f"[dim]Branch:[/dim] [cyan]{branch}[/cyan]"
            )

            panel = Panel(
                banner_table,
                border_style="cyan",
                padding=(0, 1),
                subtitle="[dim]Type [bold white]/help[/bold white] for commands · natural language for coding swarm[/dim]"
            )
            console.print(panel)
        else:
            print("=" * 70)
            print("  HELIOS CLIENT (Remote Console)")
            print(f"  Server: {self.server_url} | Online: {online} ({lat}ms)")
            print(f"  Client Node: {node_name} | Branch: {branch}")
            print(f"  Workspace: {self.workspace_dir}")
            print("=" * 70)

    async def execute_remote_hikari(self, cmd_text: str):
        """Stream coding task or slash command through server's /ws/hikari endpoint."""
        ws_url = get_ws_url("/ws/hikari", base_url=self.server_url)
        import websockets

        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                # Receive welcome banner from server
                try:
                    welcome_raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                except Exception:
                    pass

                # Send command payload
                await ws.send(json.dumps({"command": cmd_text, "text": cmd_text}))

                # Stream server responses
                while True:
                    msg_raw = await ws.recv()
                    data = json.loads(msg_raw)
                    msg_type = data.get("type")

                    if msg_type == "step":
                        state = data.get("state", "RUN")
                        text = data.get("message", "")
                        if HAS_RICH:
                            color = {
                                "ANALYZE": "cyan",
                                "PLAN": "yellow",
                                "ARCHITECT": "magenta",
                                "EXECUTE": "green",
                                "TEST": "blue",
                                "VERIFY": "bright_green",
                            }.get(state, "white")
                            console.print(f"  [{color}]◆ {state:10s}[/{color}] {text}")
                        else:
                            print(f"  [{state}] {text}")

                    elif msg_type == "output":
                        text = data.get("text", "")
                        if HAS_RICH:
                            if data.get("isDiff"):
                                console.print(Panel(text, title="Workspace Diff", border_style="cyan"))
                            else:
                                console.print(text)
                        else:
                            print(text)

                    elif msg_type == "done":
                        break
                    elif msg_type == "clear":
                        if HAS_RICH:
                            console.clear()
                        else:
                            os.system("cls" if os.name == "nt" else "clear")

        except Exception as e:
            if HAS_RICH:
                console.print(f"[bold red]WebSocket Error:[/bold red] {e}")
                console.print("[dim]Falling back to REST chat endpoint...[/dim]")
            else:
                print(f"WebSocket Error: {e}. Falling back to REST chat...")

            # REST Fallback
            resp = await self.api.send_headless_chat(cmd_text)
            reply = resp.get("response", "[No response from server]")
            if HAS_RICH:
                console.print(Panel(Markdown(reply), title="HELIOS Core", border_style="green"))
            else:
                print(f"\nHELIOS:\n{reply}\n")

    def show_help(self):
        if HAS_RICH:
            tbl = Table(title="HELIOS Client Commands", border_style="cyan")
            tbl.add_column("Command", style="bold yellow")
            tbl.add_column("Description", style="white")
            tbl.add_row("/help", "Display available commands")
            tbl.add_row("/status", "Query server health, GPU node, and client latency")
            tbl.add_row("/models", "List active models and VRAM allocations on server")
            tbl.add_row("/diff", "View git diff of local client workspace")
            tbl.add_row("/test [cmd]", "Run local verification test (e.g. /test pytest)")
            tbl.add_row("/server [url]", "View or switch HELIOS server endpoint")
            tbl.add_row("/wake", "Send Wake-on-LAN packet to wake sleeping AI PC")
            tbl.add_row("/clear", "Clear terminal screen")
            tbl.add_row("/exit, /quit", "Exit client terminal")
            tbl.add_row("<prompt>", "Submit natural language prompt to autonomous coding swarm")
            console.print(tbl)
        else:
            print("\nAvailable Commands:")
            print("  /help          Show this help message")
            print("  /status        Query server health & latency")
            print("  /models        List active models on server")
            print("  /diff          View local workspace git diff")
            print("  /test [cmd]    Run test in local client workspace")
            print("  /server [url]  Switch server endpoint")
            print("  /wake          Send Wake-on-LAN packet to server")
            print("  /clear         Clear terminal screen")
            print("  /exit          Quit client\n")

    async def run_loop(self):
        health = self.api.check_health()
        self.print_banner(health)

        if not health.get("online"):
            if HAS_RICH:
                console.print(f"[bold red]Warning:[/bold red] Cannot connect to HELIOS Server at {self.server_url}.")
                console.print("[yellow]Type [bold white]/wake[/bold white] to send Wake-on-LAN, or [bold white]/server <url>[/bold white] to change address.[/yellow]\n")
            else:
                print(f"Warning: Cannot connect to {self.server_url}. Type /wake or /server <url>.")

        while True:
            try:
                if HAS_RICH:
                    prompt_label = "[bold cyan]helios-client>[/bold cyan] "
                    user_input = console.input(prompt_label).strip()
                else:
                    user_input = input("helios-client> ").strip()

                if not user_input:
                    continue

                lower = user_input.lower()

                if lower in ("/exit", "/quit", "exit", "quit"):
                    break
                elif lower in ("/help", "help"):
                    self.show_help()
                elif lower in ("/clear", "clear"):
                    if HAS_RICH:
                        console.clear()
                    else:
                        os.system("cls" if os.name == "nt" else "clear")
                    self.print_banner(self.api.check_health())
                elif lower.startswith("/server"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) > 1:
                        new_url = parts[1].strip()
                        set_server_url(new_url)
                        self.server_url = get_server_url()
                        self.api = HeliosAPIClient(self.server_url)
                        h = self.api.check_health()
                        if HAS_RICH:
                            console.print(f"[green]Switched server to:[/green] {self.server_url} (Online: {h.get('online')})")
                        else:
                            print(f"Switched server to: {self.server_url} (Online: {h.get('online')})")
                    else:
                        h = self.api.check_health()
                        if HAS_RICH:
                            console.print(f"[cyan]Current Server URL:[/cyan] {self.server_url} (Online: {h.get('online')}, {h.get('latency_ms')}ms)")
                        else:
                            print(f"Current Server: {self.server_url} (Online: {h.get('online')})")
                elif lower in ("/wake", "wake"):
                    if HAS_RICH:
                        console.print("[yellow][*] Sending Wake-on-LAN magic packet to AI PC...[/yellow]")
                    else:
                        print("[*] Sending Wake-on-LAN packet...")
                    ok = wake_server_wol()
                    await self.api.wake_cluster(wait=False)
                    if HAS_RICH:
                        console.print(f"[green][✓] WoL packet transmitted ({ok}). Checking reachability...[/green]")
                    else:
                        print(f"[✓] WoL packet sent ({ok}). Checking reachability...")
                    await asyncio.sleep(2.0)
                    h = self.api.check_health()
                    status_text = "[bold green]ONLINE[/bold green]" if h.get("online") else "[bold red]STILL OFFLINE (booting up)[/bold red]"
                    if HAS_RICH:
                        console.print(f"Server Status: {status_text} ({h.get('latency_ms')}ms)")
                    else:
                        print(f"Server Status: {h.get('online')} ({h.get('latency_ms')}ms)")
                elif lower.startswith("/test"):
                    test_cmd = user_input[5:].strip() or "pytest"
                    if HAS_RICH:
                        console.print(f"[cyan]Running local test on client:[/cyan] {test_cmd}")
                    else:
                        print(f"Running local test: {test_cmd}")
                    res = subprocess.run(test_cmd, shell=True, cwd=self.workspace_dir, capture_output=True, text=True)
                    out = (res.stdout + "\n" + res.stderr).strip()
                    if HAS_RICH:
                        border = "green" if res.returncode == 0 else "red"
                        console.print(Panel(out or "Execution finished with exit code 0", title=f"Local Test: {test_cmd}", border_style=border))
                    else:
                        print(out)
                elif lower in ("/diff", "diff"):
                    res = subprocess.run(["git", "diff", "--stat"], cwd=self.workspace_dir, capture_output=True, text=True)
                    diff_out = res.stdout.strip() or "No uncommitted diffs found in local workspace."
                    if HAS_RICH:
                        console.print(Panel(diff_out, title="Local Git Diff", border_style="cyan"))
                    else:
                        print(diff_out)
                else:
                    # Forward to remote HELIOS server
                    await self.execute_remote_hikari(user_input)

            except (KeyboardInterrupt, EOFError):
                break
            except Exception as e:
                if HAS_RICH:
                    console.print(f"[bold red]Error:[/bold red] {e}")
                else:
                    print(f"Error: {e}")

        if HAS_RICH:
            console.print("[dim]HELIOS Client closed.[/dim]")
        else:
            print("HELIOS Client closed.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="HELIOS Client Terminal CLI")
    parser.add_argument("--server", type=str, help="HELIOS server URL (e.g. http://192.168.100.254:8000)")
    args = parser.parse_args()

    cli = HeliosClientCLI(server_url=args.server)
    try:
        asyncio.run(cli.run_loop())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
