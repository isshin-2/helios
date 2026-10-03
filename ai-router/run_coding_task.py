"""
HELIOS Coding Swarm - Direct CLI Runner
Execute autonomous coding swarm tasks using the configured local models.
"""
import asyncio
import os
import sys
import argparse
import logging
from dotenv import load_dotenv

# Ensure ai-router directory is on python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from core.coding_swarm import CodingSwarmOrchestrator
from core.model_router import model_router
from core.task_contract import RiskLevel, TaskBudget
from providers.ollama import OllamaProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("helios.swarm_runner")


async def main():
    parser = argparse.ArgumentParser(description="Run HELIOS Coding Swarm on a task")
    parser.add_argument(
        "--objective",
        "-o",
        type=str,
        default="Add a math utility function fibonacci(n) and a unit test verifying it",
        help="Coding objective for the swarm",
    )
    parser.add_argument(
        "--repo",
        "-r",
        type=str,
        default=os.getcwd(),
        help="Repository root path (defaults to current working directory)",
    )
    parser.add_argument(
        "--test-cmd",
        "-t",
        type=str,
        default=None,
        help="Test command to verify changes (e.g. 'pytest tests/test_math.py')",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
        help="Ollama host URL",
    )
    args = parser.parse_args()

    print("=" * 70)
    print(" HELIOS AUTONOMOUS CODING SWARM")
    print("=" * 70)
    print(f"Ollama Endpoint: {args.host}")
    print(f"Repository Root: {args.repo}")
    print(f"Objective:       {args.objective}")
    if args.test_cmd:
        print(f"Test Command:    {args.test_cmd}")
    print("-" * 70)

    # Initialize Provider (Supports NVIDIA PAIR and Ollama)
    provider_type = os.getenv("LLM_PROVIDER", "pair").lower()
    if provider_type == "pair":
        from providers.pair import PairProvider
        pair_host = os.getenv("PAIR_HOST", args.host)
        provider = PairProvider(host=pair_host)
        print(f"Provider:        NVIDIA PAIR (Host: {pair_host})")
    else:
        provider = OllamaProvider(host=args.host)
        print(f"Provider:        Ollama (Host: {args.host})")

    # Check model resolutions
    print("Resolving agent models against host...")
    for agent in ["planner", "architect", "coder", "tester", "repair", "reviewer", "security_reviewer"]:
        m_name, _ = await model_router.prepare_model_for_agent(agent, provider)
        print(f"  [{agent.upper()}]: {m_name}")
    print("-" * 70)

    # Instantiate Swarm Orchestrator
    orchestrator = CodingSwarmOrchestrator(provider)

    print("\n[+] Starting Autonomous Pipeline...")
    summary = await orchestrator.run_task(
        objective=args.objective,
        repository_root=args.repo,
        budget=TaskBudget(
            max_iterations=12,
            max_agent_calls=30,
            max_tool_calls=60,
            max_retries=3,
        ),
        risk_level=RiskLevel.LOW,
        test_command=args.test_cmd,
    )

    print("\n" + "=" * 70)
    print(" EXECUTION SUMMARY")
    print("=" * 70)
    print(f"Status:          {summary.get('status')}")
    print(f"Task ID:         {summary.get('task_id')}")
    print(f"Iterations:      {summary.get('iterations')}")
    print(f"Tool Invocations:{summary.get('tool_calls')}")
    print(f"Changed Files:   {summary.get('changed_files', [])}")
    print(f"Duration:        {summary.get('duration_seconds', 0):.2f}s")
    if summary.get("diff"):
        print("\n--- GIT DIFF GENERATED IN WORKSPACE ---")
        print(summary["diff"][:1500])
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
