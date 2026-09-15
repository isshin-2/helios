import re

with open('config.py', 'r') as f:
    config_content = f.read()

# Replace the entire MODEL_CONFIG dict
new_model_config = '''MODEL_CONFIG = {
    # Fast / Background (Low Latency)
    "phi4:mini": {"type": "fast", "max_tokens": 2048, "cloud_fallback": "groq/openai/gpt-oss-20b"},
    "llama3.2:3b": {"type": "fast", "max_tokens": 2048, "cloud_fallback": "groq/openai/gpt-oss-20b"},
    
    # Base / General (Core Workhorses)
    "qwen3.5:4b": {"type": "general", "max_tokens": 4096, "cloud_fallback": "groq/openai/gpt-oss-20b"},
    "qwen3.5:9b": {"type": "general", "max_tokens": 4096, "cloud_fallback": "groq/openai/gpt-oss-20b"},
    "ministral3:8b": {"type": "general", "max_tokens": 4096, "cloud_fallback": "groq/openai/gpt-oss-20b"},
    
    # Tool Use / System
    "hermes3:8b": {"type": "tool_use", "max_tokens": 8192, "cloud_fallback": "google/gemini-3.6-flash"},
    
    # Reasoning
    "qwen3.6-thinking:9b": {"type": "reasoning", "max_tokens": 8192, "cloud_fallback": "google/gemini-3.1-pro-preview"},
    
    # Coding / Agentic
    "ornith:9b": {"type": "coding", "max_tokens": 8192, "cloud_fallback": "google/gemini-3.1-pro-preview"},
    "gemma4:12b": {"type": "coding", "max_tokens": 16000, "cloud_fallback": "google/gemini-3.1-pro-preview"},
    
    # Vision
    "qwen3-vl:8b": {"type": "vision", "max_tokens": 4096, "cloud_fallback": "google/gemini-3.6-flash"},
    
    # Cloud models (Fallbacks)
    "google/gemini-3.6-flash": {"type": "agent", "max_tokens": 8192, "cloud_fallback": "google/gemini-3.1-pro-preview"},
    "google/gemini-1.5-pro": {"type": "agent", "max_tokens": 32000, "cloud_fallback": "google/gemini-3.1-pro-preview"},
    "google/gemini-3.1-pro-preview": {"type": "agent", "max_tokens": 64000, "cloud_fallback": "groq/openai/gpt-oss-20b"},
}'''

# Use regex to replace the MODEL_CONFIG dictionary
config_content = re.sub(r'MODEL_CONFIG = \{.*?\n\}', new_model_config, config_content, flags=re.DOTALL)

with open('config.py', 'w') as f:
    f.write(config_content)
    
with open('router/rules.py', 'r') as f:
    rules_content = f.read()

# Fix the roles to look at "type" instead of "roles" so _get_model_by_role works natively with the config dict
rules_content = rules_content.replace('role in cfg.get("roles", [])', 'role == cfg.get("type", "")')

# Update the default models
rules_content = rules_content.replace('"llava:latest"', '"qwen3-vl:8b"')
rules_content = rules_content.replace('"qwen2.5-coder:7b"', '"ornith:9b"')
rules_content = rules_content.replace('"deepseek-r1:7b"', '"qwen3.6-thinking:9b"')
rules_content = rules_content.replace('"qwen3:8b"', '"hermes3:8b"')
rules_content = rules_content.replace('"qwen3:4b"', '"phi4:mini"')

# The second qwen3:8b is for default general
rules_content = re.sub(r'_get_model_by_role\("general", ".*?"\)', '_get_model_by_role("general", "ministral3:8b")', rules_content)

with open('router/rules.py', 'w') as f:
    f.write(rules_content)

