import logging
import httpx
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class RoutingEngine:
    """
    Intelligent routing engine to dispatch queries to Fast Path, Semantic Cache, Local, or Cloud (Gemini).
    """
    
    def __init__(self, semantic_cache_db, ollama_url: str = "http://127.0.0.1:11434"):
        self.cache = semantic_cache_db
        self.ollama_url = ollama_url
        # Fallback chain for local models
        self.local_chain = ["qwen2.5:7b", "phi3:mini"]

    async def check_ollama_memory(self) -> Dict[str, Any]:
        """
        Queries Ollama's /api/ps to check loaded models and RAM usage.
        """
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                res = await client.get(f"{self.ollama_url}/api/ps")
                return res.json()
            except Exception as e:
                logger.warning(f"Failed to reach Ollama memory telemetry: {e}")
                return {"models": []}

    async def force_evict_local_models(self):
        """
        Forces Ollama to drop models from RAM to free memory for Cloud tasks or specific heavy jobs.
        Sends keep_alive=0 to loaded models.
        """
        loaded = await self.check_ollama_memory()
        async with httpx.AsyncClient(timeout=10.0) as client:
            for model_info in loaded.get("models", []):
                model_name = model_info["name"]
                logger.info(f"Evicting {model_name} from RAM...")
                await client.post(f"{self.ollama_url}/api/generate", json={
                    "model": model_name,
                    "keep_alive": 0
                })

    async def route_request(self, query: str, agent_mode: bool = False) -> Tuple[str, Any]:
        """
        Determines the execution path for a given query.
        
        Returns:
            Tuple[str, Any]: Route type ("cache", "fast_path", "local", "cloud") and metadata.
            
        Concurrency:
            Uses non-blocking DB/HTTP lookups.
        """
        # Extract text from multimodal arrays (vision support)
        text_query = query
        if isinstance(query, list):
            text_query = next((item.get("text", "") for item in query if item.get("type") == "text"), str(query))

        # 1. Fast Path (Commands)
        query_lower = text_query.lower().strip()
        if query_lower in ["stop", "clear memory", "mute"]:
            return "fast_path", {"command": query_lower}
            
        # 2. Semantic Cache
        if self.cache:
            try:
                cached_response = await self.cache.search_exact_or_semantic(text_query)
                if cached_response and cached_response.get("confidence", 0) > 0.95:
                    return "cache", {"response": cached_response["text"]}
            except Exception as e:
                logger.warning(f"Cache lookup failed: {e}")
        import config
        import os
        from router.classifier import classify_request
        from router.rules import get_routing_decision
        
        # Check for explicit user tags or deployment mode
        deployment_mode = os.environ.get("DEPLOYMENT_MODE", "hybrid").lower()
        force_local = "@local" in query_lower or deployment_mode == "local"
        force_cloud = "@cloud" in query_lower
        
        use_cloud = (bool(config.GEMINI_API_KEY) or bool(config.GROQ_API_KEY) or bool(config.NVIDIA_API_KEY)) and not force_local

        if force_cloud:
            use_cloud = True
            
        cloud_text_model = "google/gemini-3.6-flash" if use_cloud else "gemini-3.6-flash"
        cloud_vision_model = "google/gemini-3.6-flash" if use_cloud else "gemini-3.6-flash"

        # Route multimodal data directly to Cloud unless forced local
        if isinstance(query, list):
            if not force_local and use_cloud:
                await self.force_evict_local_models()
                return "cloud", {"model": cloud_vision_model}
            
        # Classify intent to pick the best local model if we stay local
        classification = await classify_request([{"role": "user", "content": text_query}])
        local_decision = get_routing_decision(classification)
        best_local_model = local_decision.get("model", "ministral3:8b")
            
        # Simple heuristic: technical terms, long prompts, or coding requests go to Cloud
        coding_keywords = ["write a script", "refactor", "bug", "python", "architect", "code"]
        if not force_local and use_cloud and (any(kw in query_lower for kw in coding_keywords) or len(query) > 300):
            # Free up local RAM so the host OS isn't choking while we process heavily in the cloud
            await self.force_evict_local_models()
            return "cloud", {"model": cloud_text_model}
            
        # 4. Agent Mode or Local Budget Route
        if agent_mode:
            if not force_local and use_cloud:
                return "cloud", {"model": cloud_text_model}
            return "local", {"model": "hermes3:8b", "context_size": 8192}
        
        if not force_local and use_cloud:
            return "cloud", {"model": cloud_text_model}
            
        return "local", {"model": best_local_model, "context_size": local_decision.get("context_size", 4096)}
