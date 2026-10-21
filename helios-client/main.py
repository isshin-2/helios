"""
HELIOS Client — Main Entry Point
CLI dispatcher supporting Desktop GUI, Terminal CLI, and Sidecar Agent.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

try:
    from .config import (
        check_server_health,
        get_server_url,
        set_server_url,
        wake_server_wol,
        load_client_config,
    )
except ImportError:
    from config import (
        check_server_health,
        get_server_url,
        set_server_url,
        wake_server_wol,
        load_client_config,
    )


def print_status(server_url: str):
    print("=" * 65)
    print("  HELIOS CLIENT — SERVER REACHABILITY CHECK")
    print(f"  Target Server: {server_url}")
    print("=" * 65)
    health = check_server_health(server_url, timeout=3.0)
    online = health.get("online", False)
    lat = health.get("latency_ms", 0.0)
    status_str = f"ONLINE ({lat}ms)" if online else "OFFLINE"
    print(f"  Status       : {status_str}")
    if online:
        info = health.get("info", {})
        if isinstance(info, dict):
            for k, v in info.items():
                print(f"  - {k}: {v}")
    else:
        print(f"  Error Detail : {health.get('error')}")
        print("\n  Tip: Run 'python -m helios-client --wake' to send a Wake-on-LAN packet.")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(
        prog="helios-client",
        description="HELIOS Client — Client-sided interface and sidecar for remote HELIOS Core server"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--gui", action="store_true", help="Launch native Cyberpunk Desktop GUI application")
    group.add_argument("--cli", action="store_true", help="Launch interactive Claude Code / Codex terminal console")
    group.add_argument("--sidecar", action="store_true", help="Run local device sidecar daemon (OS & desktop agent)")
    group.add_argument("--status", action="store_true", help="Check server connectivity and latency")
    group.add_argument("--wake", action="store_true", help="Transmit native UDP Wake-on-LAN packet to AI PC")

    parser.add_argument("--server", type=str, help="HELIOS server URL (e.g. http://192.168.100.254:8000)")
    parser.add_argument("--set-server", type=str, help="Permanently update default server URL in client_config.json")

    args = parser.parse_args()

    # Handle permanent server update
    if args.set_server:
        set_server_url(args.set_server)
        print(f"[✓] Saved new default HELIOS server: {args.set_server}")
        return

    # Override session server URL if provided
    server_url = args.server or get_server_url()

    if args.wake:
        print(f"[*] Sending Wake-on-LAN magic packet to dedicated AI PC...")
        ok = wake_server_wol()
        print(f"[✓] WoL Packet sent ({ok}). Checking reachability in 2s...")
        import time
        time.sleep(2.0)
        print_status(server_url)
        return

    if args.status:
        print_status(server_url)
        return

    if args.sidecar:
        try:
            from .sidecar import start_sidecar_standalone
        except ImportError:
            from sidecar import start_sidecar_standalone
        start_sidecar_standalone(server_url)
        return

    if args.cli:
        try:
            from .cli import HeliosClientCLI
        except ImportError:
            from cli import HeliosClientCLI
        cli = HeliosClientCLI(server_url=server_url)
        try:
            asyncio.run(cli.run_loop())
        except KeyboardInterrupt:
            pass
        return

    # Default to GUI if available or requested
    if args.gui or not any([args.gui, args.cli, args.sidecar, args.status, args.wake]):
        try:
            from .desktop import launch_desktop
        except ImportError:
            from desktop import launch_desktop
        launch_desktop(server_url)


if __name__ == "__main__":
    main()
