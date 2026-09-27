import httpx
import numpy as np
from typing import Dict, Any, List

# Core prototype sentences for each intent category
PROTOTYPES = {
    "casual": [
        "hello", "hi there", "how are you", "what's up", "good morning",
        "thanks for the help", "goodbye", "ok cool", "that makes sense"
    ],
    "coding": [
        "write a python script", "debug this react component", "fix this error",
        "how do I use websockets in javascript", "create a tailwind UI",
        "why is my code throwing a segmentation fault"
    ],
    "browsing": [
        "search the web for the latest news", "look up the weather",
        "find information about", "who won the game yesterday",
        "scrape this webpage", "browse the documentation for"
    ],
    "planning": [
        "break this down into steps", "plan a full app architecture",
        "how should I approach this massive project", "create a step-by-step guide",
        "orchestrate this refactor", "research this topic deeply"
    ],
    "system": [
        "check memory", "what is my cpu usage", "list running processes",
        "start the server", "run this command", "read the file", "list the directory"
    ]
}

# Cache for prototype embeddings to avoid re-embedding them every request
_prototype_embeddings = {}

async def get_embedding(text: str) -> np.ndarray:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.post(
                "http://127.0.0.1:11434/api/embeddings",
                json={"model": "nomic-embed-text:latest", "prompt": text}
            )
            if response.status_code == 200:
                data = response.json()
                return np.array(data["embedding"])
    except Exception as e:
        pass
    return None

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

async def initialize_prototypes():
    global _prototype_embeddings
    if _prototype_embeddings:
        return
        
    for intent, examples in PROTOTYPES.items():
        _prototype_embeddings[intent] = []
        for text in examples:
            emb = await get_embedding(text)
            if emb is not None:
                _prototype_embeddings[intent].append(emb)

async def classify_intent(prompt: str) -> str:
    await initialize_prototypes()
    
    prompt_emb = await get_embedding(prompt)
    if prompt_emb is None:
        return "general" 
        
    scores = {}
    for intent, embs in _prototype_embeddings.items():
        if not embs:
            continue
        max_sim = max(cosine_similarity(prompt_emb, e) for e in embs)
        scores[intent] = max_sim
        
    best_intent = max(scores.items(), key=lambda x: x[1])
    
    if best_intent[1] < 0.4:
        return "general"
        
    return best_intent[0]
