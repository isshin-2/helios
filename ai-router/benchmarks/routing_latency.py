"""
HELIOS Routing Latency Benchmark
==================================
Exercises the production routing classifier with representative prompts.

TRUST MODEL:
    This script does NOT report performance metrics.
    It simply executes the classifier so that BenchmarkRunner
    can measure process latency externally.

    The benchmark must:
      - Run inside sandbox.py (no writes, no network, no subprocess)
      - Exercise real production classification logic
      - Exit 0 on success, non-zero on failure
"""

import sys
import os

# Ensure the HELIOS root is importable
sys.path.insert(0, os.getcwd())

from router.classifier import classify_request

# Representative prompt set covering all major categories
BENCHMARK_PROMPTS = [
    # General
    {"role": "user", "content": "What is the capital of France?"},
    {"role": "user", "content": "Tell me a joke about programming."},
    {"role": "user", "content": "Summarize the history of the internet."},
    # Coding
    {"role": "user", "content": "Write a Python script to sort a list of numbers."},
    {"role": "user", "content": "Fix this javascript error: Uncaught TypeError"},
    {"role": "user", "content": "Debug this React component that won't render."},
    # Tool use
    {"role": "user", "content": "Read the file main.py"},
    {"role": "user", "content": "List files in the project directory"},
    {"role": "user", "content": "!run python tests/test_helios.py"},
    # Reasoning
    {"role": "user", "content": "Analyze the trade-offs between microservices and monoliths."},
    {"role": "user", "content": "Explain why PID controllers oscillate with high gain."},
    {"role": "user", "content": "Compare REST vs GraphQL architecture."},
    # Conversation
    {"role": "user", "content": "Hello"},
    {"role": "user", "content": "Thanks"},
    # Research
    {"role": "user", "content": "Plan a refactor of the authentication module."},
]


def run_benchmark():
    """Execute classification on all representative prompts."""
    results = {}
    for prompt_msg in BENCHMARK_PROMPTS:
        messages = [prompt_msg]
        try:
            result = classify_request(messages)
            # Validate the result structure
            assert "intent" in result, "Missing 'intent' in classification result"
            assert "detail" in result, "Missing 'detail' in classification result"
            results[prompt_msg["content"][:40]] = result["intent"]
        except Exception as e:
            print(f"Classification failed for: {prompt_msg['content'][:40]}", file=sys.stderr)
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # All classifications succeeded
    print(f"Benchmark completed: {len(results)} prompts classified successfully.")


if __name__ == "__main__":
    run_benchmark()
