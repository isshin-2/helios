from typing import Dict, Any, Optional
from config import MODEL_CONFIG, CONTEXT_SIZES

def _get_model_by_role(role: str, default: str) -> str:
    """Helper to get highest priority model matching a role."""
    candidates = []
    for name, cfg in MODEL_CONFIG.items():
        if role in cfg.get("roles", []) and cfg.get("priority", 0) > 0:
            candidates.append((cfg.get("priority", 1), name))
    
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    return default

def get_routing_decision(classification: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply routing rules based on the intent classification.
    Returns a dict with model, route, context size, and reasoning.
    """
    intent = classification.get("intent", "general")
    detail = classification.get("detail", "normal")
    requires_vision = classification.get("requires_vision", False)
    
    base_response = {
        "intent": intent,
        "detail": detail,
        "confidence": 0.9
    }
    
    # 1. Vision
    if requires_vision:
        model = _get_model_by_role("vision", "llava:latest")
        base_response.update({
            "route": "vision",
            "model": model,
            "context_size": CONTEXT_SIZES.get("medium", 4096),
            "reason": "Request contains image data."
        })
        return base_response
        
    # 2. Coding
    if intent == "coding":
        model = _get_model_by_role("coding", "qwen2.5-coder:7b")
        base_response.update({
            "route": "coding",
            "model": model,
            "context_size": CONTEXT_SIZES.get("complex", 8192),
            "reason": "Coding request."
        })
        return base_response
        
    # 3. Reasoning / Research
    if intent in ("reasoning", "research"):
        model = _get_model_by_role("reasoning", "deepseek-r1:7b")
        base_response.update({
            "route": "reasoning",
            "model": model,
            "context_size": CONTEXT_SIZES.get("complex", 8192),
            "reason": f"Intent '{intent}' requires deep reasoning."
        })
        return base_response
        
    # 4. System / Tool Use
    if intent in ("system", "tool_use"):
        model = _get_model_by_role("tool_use", "qwen3:8b")
        base_response.update({
            "route": "general",
            "model": model,
            "context_size": CONTEXT_SIZES.get("complex", 8192),
            "reason": "System/Tool request needs capable tool model."
        })
        return base_response

    # 5. Conversation
    if intent == "conversation":
        model = _get_model_by_role("fast", "qwen3:4b")
        base_response.update({
            "route": "general",
            "model": model,
            "context_size": CONTEXT_SIZES.get("simple", 2048),
            "reason": "Short conversational request."
        })
        return base_response
        
    # Default: General
    model = _get_model_by_role("general", "qwen3:8b")
    context_size = CONTEXT_SIZES.get("medium", 4096)
    reason = "Standard general request."
    
    # Detail overrides
    if detail == "detailed":
        model = _get_model_by_role("reasoning", "deepseek-r1:7b")
        context_size = CONTEXT_SIZES.get("complex", 8192)
        reason += " (Upgraded to reasoning model for high detail)"
    elif detail == "simple":
        model = _get_model_by_role("fast", "qwen3:4b")
        context_size = CONTEXT_SIZES.get("simple", 2048)
        reason += " (Downgraded to fast model for simple answer)"
        
    base_response.update({
        "route": "general",
        "model": model,
        "context_size": context_size,
        "reason": reason
    })
    return base_response

