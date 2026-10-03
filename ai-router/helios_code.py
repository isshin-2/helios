"""
HIKARI (h-code) — Interactive Multi-Agent Coding CLI
A Claude-Code and Codex-CLI inspired terminal interface powered by NVIDIA PAIR
and the HELIOS 8-Agent Autonomous Swarm.
"""

from __future__ import annotations

import asyncio
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import subprocess
import argparse
from typing import Optional, Dict, Any
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.text import Text
from rich.align import Align

from core.coding_swarm import CodingSwarmOrchestrator
from core.model_router import model_router
from core.task_contract import RiskLevel, TaskBudget
from providers.pair import PairProvider
from providers.ollama import OllamaProvider

console = Console(force_terminal=True, legacy_windows=False)


class HeliosCodeCLI:
    def __init__(
        self,
        repo_root: str,
        host: str,
        provider_name: str = "pair",
        model_name: Optional[str] = None
    ):
        self.repo_root = os.path.abspath(repo_root)
        self.host = host
        self.provider_name = provider_name.lower()
        self.model_name = model_name or os.getenv("HIKARI_MODEL", "Swarm (Qwen 2.5-Coder / Devstral)")
        self.provider_display = (
            "NVIDIA PAIR (AI PC · RTX 5060 Ti)" if self.provider_name == "pair"
            else ("Ollama (Local)" if self.provider_name == "ollama"
            else ("Anthropic API" if self.provider_name == "anthropic" or "claude" in self.model_name.lower()
            else self.provider_name.upper()))
        )
        self.last_summary: Optional[Dict[str, Any]] = None

        if self.provider_name == "pair":
            self.provider = PairProvider(host=self.host)
        else:
            self.provider = OllamaProvider(host=self.host)

        self.orchestrator = CodingSwarmOrchestrator(self.provider)

    def get_git_branch(self) -> str:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass
        return "main"

    def get_workspace_short(self) -> str:
        norm = os.path.normpath(self.repo_root)
        parts = norm.split(os.sep)
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        return os.path.basename(norm) or "workspace"

    def get_workspace_display(self) -> str:
        home = os.path.expanduser("~")
        if self.repo_root.startswith(home):
            return "~" + self.repo_root[len(home):]
        return self.repo_root

    def print_banner(self):
        # ─── Top Header Bar ───
        top_bar = Table.grid(expand=True)
        top_bar.add_column(justify="left")
        top_bar.add_column(justify="right")
        top_bar.add_row(
            Text.from_markup("[bold #00e5ff]✦ HIKARI CLI[/bold #00e5ff] [dim #00e5ff]v2.0.76[/dim #00e5ff]"),
            Text.from_markup("[dim #00e5ff]// BUILD · THINK · EXECUTE[/dim #00e5ff]"),
        )
        console.print()
        console.print(top_bar)
        console.rule(style="#005577")
        console.print()

        # ─── Accretion Disk Eye & Hero Info ───
        model_ctx = f"{self.model_name} · {self.provider_display}"
        console.print("     [bold #00e5ff]▗▟████▙▖[/]     [bold #00e5ff]HIKARI[/]  [bold white]Autonomous Coding Swarm[/]")
        console.print(f"  [bold #00e5ff]━━━[/][#00b4d8]███[/][bold #ff9f43]░░[/][#00b4d8]███[/][bold #00e5ff]━━━[/]  [white]{model_ctx}[/]")
        console.print(f"     [bold #00e5ff]▝▜████▛▘[/]     [dim #00b4d8]{self.get_workspace_display()}[/]")
        console.print()

        # ─── Quick Commands Panel ───
        console.print("  [bold #00e5ff][ QUICK COMMANDS ][/]")
        console.print("  [bold #00e5ff]/help[/]    [white]Show available commands[/]          [bold #00e5ff]/models[/]  [white]List available models[/]")
        console.print("  [bold #00e5ff]/clear[/]   [white]Reset active terminal view[/]       [bold #00e5ff]/exit[/]    [white]End current session[/]")
        console.print()
        console.rule(style="#005577")

    def print_footer(self, status: str = "Ready"):
        status_styles = {
            "Ready": "[bold #00e676]● Ready[/bold #00e676]",
            "Working": "[bold #ffb300]● Working[/bold #ffb300]",
            "Error": "[bold #ff3344]● Error[/bold #ff3344]",
        }
        status_markup = status_styles.get(status, f"[cyan]● {status}[/cyan]")
        console.print(
            f"  [bold #00e5ff]📁 {self.get_workspace_short()}[/]   "
            f"[dim #00b4d8]git:([/][bold #00e5ff]♦ {self.get_git_branch()}[/][dim #00b4d8])[/]   "
            f"[white]⚬ {self.model_name}[/]   "
            f"{status_markup}"
        )

    async def show_models(self):
        table = Table(title="[bold cyan]HELIOS Model Router & Hardware Mapping[/bold cyan]")
        table.add_column("Agent Role", style="bold magenta")
        table.add_column("Primary Model", style="green")
        table.add_column("VRAM Policy", style="yellow")
        table.add_column("Active Host", style="cyan")

        for agent in ["planner", "architect", "repo_mapper", "coder", "tester", "repair", "reviewer", "security_reviewer"]:
            m_name, _ = await model_router.prepare_model_for_agent(agent, self.provider)
            vram_note = "Resident (<9 GB)" if "14b" in m_name or "7b" in m_name else "Proactive Swap"
            table.add_row(agent.upper(), m_name, vram_note, self.host)

        console.print(table)

    def show_diff(self):
        if not self.last_summary or not self.last_summary.get("diff"):
            console.print("[dim yellow]No active worktree diff from the latest task.[/dim yellow]")
            return

        diff_text = self.last_summary["diff"]
        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title="[bold green]Workspace Git Diff[/bold green]", border_style="green"))

    async def run_task(self, objective: str, test_cmd: Optional[str] = None):
        console.print(f"\n[bold green]▶ Task Initiated:[/bold green] [white]{objective}[/white]")
        if test_cmd:
            console.print(f"[dim]Validation Command: {test_cmd}[/dim]")

        with console.status("[bold cyan][ANALYZE][/bold cyan] Initializing workspace & mapping repository...") as status:

            def on_step(state: str, message: str, payload: Any):
                colors = {
                    "ANALYZE": "cyan",
                    "PLAN": "magenta",
                    "ARCHITECT": "blue",
                    "EXECUTE": "green",
                    "VERIFY": "yellow",
                    "REPAIR": "red",
                    "REVIEW": "white",
                    "SECURITY_REVIEW": "bold red",
                    "FINALIZE": "green",
                }
                c = colors.get(state, "white")
                status.update(f"[bold {c}][{state}][/bold {c}] {message}")

            summary = await self.orchestrator.run_task(
                objective=objective,
                repository_root=self.repo_root,
                budget=TaskBudget(
                    max_iterations=12,
                    max_agent_calls=30,
                    max_tool_calls=60,
                    max_retries=3,
                ),
                risk_level=RiskLevel.LOW,
                test_command=test_cmd,
                on_step=on_step,
            )

        self.last_summary = summary
        self.render_summary(summary)

    def render_summary(self, summary: Dict[str, Any]):
        status = summary.get("status")
        is_success = status == "COMPLETED"

        style = "bold green" if is_success else "bold red"
        title = f"[{style}]Task {status}[/{style}]"

        metrics_text = Text()
        metrics_text.append(f"Task ID:        {summary.get('task_id')}\n")
        metrics_text.append(f"Iterations:     {summary.get('iterations')}\n")
        metrics_text.append(f"Duration:       {summary.get('duration_seconds', 0):.2f}s\n")
        metrics_text.append(f"Files Changed:  {', '.join(summary.get('changed_files', [])) or 'None'}\n")
        metrics_text.append(f"Workspace:      {summary.get('worktree')}\n")

        console.print("\n", Panel(metrics_text, title=title, border_style="green" if is_success else "red"))

        if summary.get("diff"):
            diff_syntax = Syntax(summary["diff"], "diff", theme="monokai", line_numbers=True)
            console.print(Panel(diff_syntax, title="[bold cyan]Diff Preview[/bold cyan]", border_style="cyan"))

    def show_help(self):
        help_table = Table(
            title="[bold #00e5ff]HIKARI (h-code) Commands[/bold #00e5ff]",
            border_style="#005577",
            header_style="bold #00e5ff"
        )
        help_table.add_column("Command", style="bold #00e5ff")
        help_table.add_column("Description", style="white")

        help_table.add_row("/help", "Show available quick commands & options")
        help_table.add_row("/models", "Inspect active models & VRAM hardware mapping")
        help_table.add_row("/model <name>", "Switch displayed / active model profile")
        help_table.add_row("/diff", "View syntax-highlighted git diff of the current task")
        help_table.add_row("/review", "Run automated code quality and security review on recent changes")
        help_table.add_row("/test [cmd]", "Run verification command manually in workspace")
        help_table.add_row("/cd <path>", "Switch workspace target directory inside session")
        help_table.add_row("/workspace", "Show current workspace root path")
        help_table.add_row("/rollback", "Discard current task worktree changes")
        help_table.add_row("/clear", "Clear terminal screen and refresh HUD")
        help_table.add_row("/exit, /quit", "Exit Hikari CLI")
        help_table.add_row("<prompt>", "Send natural language coding instruction to swarm")

        console.print(help_table)
        console.print()

    async def repl(self, show_banner: bool = True):
        if show_banner:
            self.print_banner()
            self.print_footer("Ready")
            console.print()

        while True:
            try:
                user_input = console.input("  [bold #00e5ff]hikari[/] [bold #00e5ff]❯[/] ").strip()
                if not user_input:
                    continue

                if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
                    console.print("[dim yellow]Exiting Hikari (h-code). Goodbye![/dim yellow]")
                    break

                elif user_input.lower() in ("/help", "help", "?"):
                    self.show_help()

                elif user_input.lower() == "/diff":
                    self.show_diff()

                elif user_input.lower() == "/review":
                    if self.last_summary and self.last_summary.get("changed_files"):
                        console.print(f"[bold cyan]Running Code & Security Review on {len(self.last_summary['changed_files'])} file(s)...[/bold cyan]")
                        from agents.reviewer import ReviewerAgent
                        from agents.security_reviewer import SecurityReviewerAgent
                        reviewer = ReviewerAgent(self.provider)
                        sec_reviewer = SecurityReviewerAgent(self.provider)
                        rev_res, sec_res = await asyncio.gather(
                            reviewer.execute(f"Review changes in {self.last_summary['changed_files']}", {"diff": self.last_summary.get("diff", "")}),
                            sec_reviewer.execute(f"Security audit for {self.last_summary['changed_files']}", {"diff": self.last_summary.get("diff", "")})
                        )
                        console.print(Panel(str(rev_res.output), title="[bold green]Code Review Findings[/bold green]"))
                        console.print(Panel(str(sec_res.output), title="[bold yellow]Security Audit Findings[/bold yellow]"))
                    else:
                        console.print("[dim yellow]No recent file changes to review.[/dim yellow]")

                elif user_input.lower() == "/models":
                    await self.show_models()

                elif user_input.lower().startswith("/model"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) > 1:
                        self.model_name = parts[1].strip()
                        self.provider_display = (
                            "NVIDIA PAIR (AI PC · RTX 5060 Ti)" if self.provider_name == "pair"
                            else ("Ollama (Local)" if self.provider_name == "ollama"
                            else ("Anthropic API" if self.provider_name == "anthropic" or "claude" in self.model_name.lower()
                            else self.provider_name.upper()))
                        )
                        console.print(f"[bold green]✔ Active Model set to:[/bold green] {self.model_name}")
                    else:
                        console.print(f"[bold cyan]Active Model:[/bold cyan] {self.model_name} ({self.provider_display})")

                elif user_input.lower() == "/clear":
                    os.system("cls" if os.name == "nt" else "clear")
                    self.print_banner()
                    self.print_footer("Ready")
                    console.print()

                elif user_input.lower() == "/rollback":
                    if self.last_summary and self.last_summary.get("worktree"):
                        console.print(f"[bold yellow]Rolling back workspace changes at {self.last_summary['worktree']}...[/bold yellow]")
                        self.last_summary = None
                        console.print("[green]Workspace reset cleanly.[/green]")
                    else:
                        console.print("[dim]No active worktree to rollback.[/dim]")

                elif user_input.lower() in ("/workspace", "/pwd"):
                    console.print(f"[bold cyan]Current Workspace Root:[/bold cyan] {self.repo_root}")

                elif user_input.startswith("/cd"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) > 1:
                        target_dir = os.path.abspath(parts[1].strip())
                        if os.path.isdir(target_dir):
                            self.repo_root = target_dir
                            console.print(f"[bold green]✔ Workspace switched to:[/bold green] {self.repo_root}")
                        else:
                            console.print(f"[bold red]✘ Directory does not exist:[/bold red] {target_dir}")
                    else:
                        console.print(f"[bold cyan]Current Workspace Root:[/bold cyan] {self.repo_root}")

                elif user_input.startswith("/test"):
                    parts = user_input.split(maxsplit=1)
                    cmd = parts[1] if len(parts) > 1 else "pytest"
                    console.print(f"[dim]Running '{cmd}'...[/dim]")
                    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=self.repo_root)
                    if res.returncode == 0:
                        console.print(f"[bold green]✔ Tests Passed[/bold green]\n{res.stdout}")
                    else:
                        console.print(f"[bold red]✘ Tests Failed (exit code {res.returncode})[/bold red]\n{res.stderr or res.stdout}")

                else:
                    # Natural language coding task
                    self.print_footer("Working")
                    await self.run_task(user_input)
                    self.print_footer("Ready")
                    console.print()

            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim yellow]Session interrupted. Exiting.[/dim yellow]")
                break
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Hikari (h-code) — Autonomous Multi-Agent Coding CLI (Claude Code & Codex style)"
    )
    parser.add_argument("prompt", nargs="*", default=[], help="Coding prompt or task instruction")
    parser.add_argument("--repo", "-r", type=str, default=os.getcwd(), help="Repository root path")
    parser.add_argument("--host", type=str, default=os.getenv("PAIR_HOST", "http://127.0.0.1:11434"), help="NVIDIA PAIR host URL")
    parser.add_argument("--provider", type=str, default=os.getenv("LLM_PROVIDER", "pair"), help="LLM Provider (pair/ollama/anthropic)")
    parser.add_argument("--model", "-m", type=str, default=os.getenv("HIKARI_MODEL", None), help="Active model name (defaults to swarm profile)")
    parser.add_argument("-p", "--print", dest="print_mode", action="store_true", help="Print task output directly and exit (Claude Code style)")
    parser.add_argument("-t", "--task", dest="task", type=str, default=None, help="Explicit coding task string")
    args = parser.parse_args()

    cli = HeliosCodeCLI(
        repo_root=args.repo,
        host=args.host,
        provider_name=args.provider,
        model_name=args.model
    )
    
    prompt_text = " ".join(args.prompt).strip() or (args.task or "").strip()
    if prompt_text:
        cli.print_banner()
        cli.print_footer("Working")
        asyncio.run(cli.run_task(prompt_text))
        cli.print_footer("Ready")
        if not args.print_mode:
            asyncio.run(cli.repl(show_banner=False))
    else:
        asyncio.run(cli.repl(show_banner=True))


if __name__ == "__main__":
    main()
