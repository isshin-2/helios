import re
from typing import Dict, Any, List

def check_vision_required(messages: List[Dict[str, Any]]) -> bool:
    """Check if any message contains an image."""
    for msg in messages:
        if "images" in msg and msg["images"]:
            return True
    return False

def check_tools_required(prompt: str) -> bool:
    """Check if the prompt matches any known deterministic tool patterns."""
    prompt = prompt.lower().strip()
    tool_patterns = [
        r"^start ollama",
        r"^stop ollama",
        r"^check ollama status",
        r"^list models",
        r"^check ram",
        r"^check memory",
        r"^check disk",
        r"^restart ollama",
        r"^pull model ",
        r"^unload model"
    ]
    for pattern in tool_patterns:
        if re.search(pattern, prompt):
            return True
    return False

def check_filesystem_required(prompt: str) -> Dict[str, Any]:
    """
    Detect if the prompt requires filesystem access (file read, directory list,
    file write, or terminal execution).
    
    Returns a dict with:
        requires_filesystem (bool)
        filesystem_skill (str or None): one of FileReaderSkill, DirectoryListerSkill,
                                         FileWriterSkill, TerminalSkill
    """
    prompt_lower = prompt.lower().strip()

    # File read patterns
    file_read_patterns = [
        r"read\s+[\w./\\]+\.\w+",
        r"show\s+(?:me\s+)?(?:the\s+)?(?:code|contents?|file)\s+(?:in|of|from)\s+",
        r"open\s+[\w./\\]+\.\w+",
        r"cat\s+[\w./\\]+",
        r"(?:what\s+does|what's\s+in)\s+[\w./\\]+\.\w+",
        r"look\s+at\s+[\w./\\]+\.\w+",
        r"show\s+(?:me\s+)?[\w./\\]+\.\w+",
        r"read\s+(?:the\s+)?file",
    ]
    for pattern in file_read_patterns:
        if re.search(pattern, prompt_lower):
            return {"requires_filesystem": True, "filesystem_skill": "FileReaderSkill"}

    # Directory listing patterns
    dir_list_patterns = [
        r"list\s+(?:the\s+)?(?:files|directory|folder|dir)",
        r"show\s+(?:me\s+)?(?:the\s+)?files\s+in",
        r"what(?:'s|\s+is)\s+inside",
        r"show\s+(?:me\s+)?(?:my\s+)?\w+\s+project",
        r"show\s+directory",
        r"^ls\s+",
        r"^dir\s+",
        r"what\s+files\s+(?:are|do)\s+",
        r"explore\s+(?:the\s+)?(?:folder|directory|project)",
    ]
    for pattern in dir_list_patterns:
        if re.search(pattern, prompt_lower):
            return {"requires_filesystem": True, "filesystem_skill": "DirectoryListerSkill"}

    # File write patterns
    file_write_patterns = [
        r"write\s+to\s+",
        r"save\s+to\s+",
        r"create\s+(?:a\s+)?file",
        r"modify\s+(?:the\s+)?file",
        r"update\s+(?:the\s+)?file",
        r"edit\s+(?:the\s+)?file",
        r"fix\s+(?:the\s+)?file",
    ]
    for pattern in file_write_patterns:
        if re.search(pattern, prompt_lower):
            return {"requires_filesystem": True, "filesystem_skill": "FileWriterSkill"}

    # Terminal execution patterns
    terminal_patterns = [
        r"^!run\s+",
        r"run\s+(?:the\s+)?tests?",
        r"run\s+(?:the\s+)?script",
        r"execute\s+",
        r"run\s+python\s+",
        r"run\s+node\s+",
        r"run\s+git\s+",
        r"run\s+npm\s+",
        r"run\s+pip\s+",
        r"run\s+command",
    ]
    for pattern in terminal_patterns:
        if re.search(pattern, prompt_lower):
            return {"requires_filesystem": True, "filesystem_skill": "TerminalSkill"}

    return {"requires_filesystem": False, "filesystem_skill": None}

def classify_category(prompt: str, messages: List[Dict[str, Any]]) -> str:
    """Determine the primary intent category of the request."""
    prompt_lower = prompt.lower()
    
    # Check vision first
    for msg in messages:
        if "images" in msg and msg["images"]:
            return "vision"
            
    # System / Tool use
    tool_patterns = [
        r"^start ollama", r"^stop ollama", r"^check ollama status",
        r"^list models", r"^check ram", r"^check memory", r"^check disk",
        r"^restart ollama", r"^pull model ", r"^unload model",
        r"^!run\s+", r"run\s+python\s+", r"run\s+node\s+", r"run\s+git\s+", r"execute\s+"
    ]
    for pattern in tool_patterns:
        if re.search(pattern, prompt_lower):
            return "system"

    # Research / Sub-Agent
    research_keywords = [
        "plan a refactor", "build a whole app", "autonomous",
        "step-by-step plan", "execute a complex", "multi-step",
        "research", "deep dive", "sub-agent"
    ]
    if any(kw in prompt_lower for kw in research_keywords):
        return "research"

    # Coding
    code_keywords = [
        "python", "javascript", "node.js", "react", "bash", "powershell",
        "script", "debug", "error", "exception", "compile", "segmentation fault",
        "ui component", "tailwind", "frontend", "css", "html"
    ]
    code_patterns = [r"```", r"fix this.*code", r"write a.*script"]
    for pattern in code_patterns:
        if re.search(pattern, prompt_lower):
            return "coding"
    if any(kw in prompt_lower for kw in code_keywords):
        return "coding"
        
    # Reasoning
    reasoning_keywords = [
        "architecture", "relay", "power-system", "control-system", 
        "pid controller", "oscillating", "compare", "design", "plan", 
        "trade-offs", "strategy", "why does", "how does", "analyze", "explain why"
    ]
    if any(kw in prompt_lower for kw in reasoning_keywords):
        return "reasoning"
        
    # Tool Use (General File/Internet requests)
    tool_use_keywords = [
        "read", "show files", "list files", "write to", "save to", "search the web",
        "look up", "latest news", "weather today"
    ]
    if any(kw in prompt_lower for kw in tool_use_keywords):
        return "tool_use"
        
    # Conversation (Very short, conversational)
    conversation_keywords = ["hello", "hi", "hey", "thanks", "thank you", "goodbye", "bye", "ok", "okay"]
    if prompt_lower.strip() in conversation_keywords or (len(prompt_lower) < 20 and "?" not in prompt_lower):
        return "conversation"

    # Default
    return "general"

def detect_detail_level(prompt: str) -> str:
    """Detect if user explicitly wants simple, normal, or detailed output."""
    prompt_lower = prompt.lower()
    
    detailed_keywords = ["in depth", "detailed", "step by step", "comprehensive", "exactly", "thoroughly", "explain every step", "from basics"]
    simple_keywords = ["just curious", "briefly", "what is", "summary", "tl;dr", "tldr", "in short", "simple", "short answer", "concise"]
    
    if any(kw in prompt_lower for kw in detailed_keywords):
        return "detailed"
    elif any(kw in prompt_lower for kw in simple_keywords):
        return "simple"
    
    return "normal"

def check_requires_tools(prompt: str) -> bool:
    prompt_lower = prompt.lower()
    keywords = ["read", "file", "list", "directory", "run", "execute", "search", "write", "save"]
    return any(kw in prompt_lower for kw in keywords)

def classify_request(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Main entry point for request classification.
    Returns a strictly structured JSON representation of intent.
    """
    if not messages:
        return {
            "intent": "general",
            "detail": "normal",
            "requires_tools": False,
            "requires_reasoning": False,
            "requires_vision": False,
            "requires_research": False
        }
        
    last_user_msg = next((m for m in reversed(messages) if m["role"] == "user"), None)
    prompt = last_user_msg["content"] if last_user_msg else ""
    
    intent = classify_category(prompt, messages)
    detail = detect_detail_level(prompt)
    
    requires_vision = intent == "vision"
    requires_tools = intent in ("tool_use", "system") or check_requires_tools(prompt)
    requires_reasoning = intent == "reasoning" or detail == "detailed"
    requires_research = intent == "research"
    
    return {
        "intent": intent,
        "detail": detail,
        "requires_tools": requires_tools,
        "requires_reasoning": requires_reasoning,
        "requires_vision": requires_vision,
        "requires_research": requires_research
    }

