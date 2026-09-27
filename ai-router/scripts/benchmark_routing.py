import asyncio
import time
from typing import List, Dict
import json
from router.classifier import classify_request
from router.rules import get_routing_decision
from config import MODEL_CONFIG

test_cases = [
    {
        "name": "Simple Greeting",
        "messages": [{"role": "user", "content": "Hello, how are you?"}],
        "expected_role": "general"
    },
    {
        "name": "Code Request",
        "messages": [{"role": "user", "content": "Write a python script to parse JSON."}],
        "expected_role": "coding"
    },
    {
        "name": "Reasoning Puzzle",
        "messages": [{"role": "user", "content": "If I have 3 apples and you take 2 away from 5 oranges, how many apples do I have?"}],
        "expected_role": "reasoning"
    },
    {
        "name": "Tool Trigger (File list)",
        "messages": [{"role": "user", "content": "What files are in this directory?"}],
        "expected_role": "general"  # because tool execution uses general model now
    }
]

def run_benchmarks():
    print("Running Routing Benchmarks...")
    start_time = time.time()
    
    for case in test_cases:
        case_start = time.time()
        
        # 1. Classification
        classification = classify_request(case["messages"])
        
        # 2. Routing Decision
        route = get_routing_decision(classification)
        
        case_end = time.time()
        
        print(f"Case: {case['name']}")
        print(f"  Classification: {classification}")
        print(f"  Route: {route}")
        print(f"  Latency: {(case_end - case_start)*1000:.2f} ms")
        print("-" * 40)
        
    total_time = time.time() - start_time
    print(f"Total Benchmark Time: {total_time*1000:.2f} ms")

if __name__ == "__main__":
    run_benchmarks()
