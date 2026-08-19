import os
import sys

# Add HELIOS_DIR to path if needed (subprocess sets PYTHONPATH, but this handles imports robustly)
sys.path.insert(0, os.getcwd())

from router.classifier import classify_request

def run_benchmark():
    messages = [
        {"role": "user", "content": "Hello, can you help me?"},
        {"role": "assistant", "content": "I am HELIOS. How can I assist you today?"},
        {"role": "user", "content": "Please read main.py and tell me what the routing latency is in ms. Then start ollama and pull llama3."}
    ]
    
    # Run classification a few times to simulate workload
    for _ in range(10):
        result = classify_request(messages)

if __name__ == "__main__":
    run_benchmark()
