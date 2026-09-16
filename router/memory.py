import json
import numpy as np
from typing import List, Dict, Any, Optional
from db import get_db
import logging

logger = logging.getLogger("helios.memory")

# Config for embedding model
EMBEDDING_MODEL = "nomic-embed-text"
FACT_EXTRACTION_MODEL = "llama3.2:3b"

def cosine_similarity(a: List[float], b: List[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    dot = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))

from providers.base import BaseProvider

class MemoryManager:
    """
    HELIOS 5-Layer Hybrid Memory Manager.
    1. Working Memory (Short-term context, handled via messages)
    2. Core Memory (System persona and user facts, always in context)
    3. Task Memory (Handled via Phase 2 checkpoints)
    4. Episodic Memory (Conversation summaries, searched via vector)
    5. Archival Memory (Facts, searched via vector)
    """
    def __init__(self, provider: BaseProvider):
        self.provider = provider

    # ─── ARCHIVAL MEMORY (Facts) ─────────────────────────────────────────

    async def extract_and_save_facts(self, user_id: int, message: str, force_category: Optional[str] = None):
        """
        Extract facts and optionally force a specific category (e.g. 'tool_result').
        If force_category is None, the LLM will decide the category.
        """
        if force_category:
            # If it's a forced category like tool_result, we don't need the LLM to extract facts,
            # we just directly save the whole message as a fact.
            await self.save_fact(user_id, message, category=force_category)
            return

        prompt = (
            "Extract any key personal facts, preferences, project details, or system/tool discoveries from the following message. "
            "Only extract important factual statements that should be remembered long-term. "
            "If there are no clear facts to remember, reply with 'NONE'.\n"
            "Format the output as a JSON array of objects with a 'category' and 'fact'. Categories can be whatever makes sense (e.g. user_preference, project_info, tool_discovery, system_state).\n"
            'Example: [{"category": "user_preference", "fact": "The user prefers Python"}, {"category": "tool_discovery", "fact": "Docker is not running on the system"}]\n\n'
            f"Message: {message}"
        )
        try:
            response = await self.provider.generate(model=FACT_EXTRACTION_MODEL, prompt=prompt, stream=False)
            output = response.get("response", "").strip()
            
            if not output or "NONE" in output.upper():
                return
                
            # Attempt to parse JSON
            import json
            import re
            
            # Find the JSON array in the output
            json_match = re.search(r'\[.*\]', output, re.DOTALL)
            if json_match:
                facts_data = json.loads(json_match.group(0))
                for item in facts_data:
                    fact = item.get("fact")
                    category = item.get("category", "general")
                    if fact:
                        await self.save_fact(user_id, fact, category=category)
        except Exception as e:
            logger.error(f"Error extracting facts: {e}")

    async def save_fact(self, user_id: int, fact: str, category: str = "general"):
        try:
            embedding = await self.provider.get_embeddings(EMBEDDING_MODEL, fact)
            if not embedding:
                return
            emb_json = json.dumps(embedding)
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO memories (user_id, category, fact, embedding) VALUES (?, ?, ?, ?)",
                (user_id, category, fact, emb_json)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving fact: {e}")

    async def search_memory(self, user_id: int, query: str, threshold: float = 0.5, limit: int = 3) -> List[str]:
        try:
            query_emb = await self.provider.get_embeddings(EMBEDDING_MODEL, query)
            if not query_emb:
                return []
                
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT fact, embedding FROM memories WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            conn.close()
            
            results = []
            for row in rows:
                fact = row["fact"]
                emb = json.loads(row["embedding"])
                sim = cosine_similarity(query_emb, emb)
                if sim >= threshold:
                    results.append({"fact": fact, "score": sim})
            
            results.sort(key=lambda x: x["score"], reverse=True)
            return [r["fact"] for r in results[:limit]]
        except Exception as e:
            logger.error(f"Error searching memory: {e}")
            return []

    # ─── CORE MEMORY (Always in Context) ─────────────────────────────────

    async def get_core_memory(self, user_id: int) -> str:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT section, content FROM core_memory WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return "Core Memory is currently empty."
                
            out = ""
            for row in rows:
                out += f"### {row['section'].upper()} ###\n{row['content']}\n\n"
            return out.strip()
        except Exception as e:
            logger.error(f"Error retrieving core memory: {e}")
            return "Error retrieving core memory."

    async def append_core_memory(self, user_id: int, section: str, content: str) -> bool:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM core_memory WHERE user_id = ? AND section = ?", (user_id, section))
            row = cursor.fetchone()
            
            if row:
                new_content = row["content"] + "\n" + content
                cursor.execute(
                    "UPDATE core_memory SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND section = ?",
                    (new_content, user_id, section)
                )
            else:
                cursor.execute(
                    "INSERT INTO core_memory (user_id, section, content) VALUES (?, ?, ?)",
                    (user_id, section, content)
                )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error appending to core memory: {e}")
            return False

    # ─── EPISODIC MEMORY (Conversations) ─────────────────────────────────

    async def summarize_and_save_session(self, user_id: int, session_id: int, text_log: str):
        prompt = (
            "Summarize the following conversation log into a brief, dense paragraph detailing what was achieved.\n\n"
            f"{text_log}"
        )
        try:
            response = await self.provider.generate(model=FACT_EXTRACTION_MODEL, prompt=prompt, stream=False)
            summary = response.get("response", "").strip()
            
            if summary:
                embedding = await self.provider.get_embeddings(EMBEDDING_MODEL, summary)
                if embedding:
                    emb_json = json.dumps(embedding)
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO episodic_memory (user_id, session_id, summary, embedding) VALUES (?, ?, ?, ?)",
                        (user_id, session_id, summary, emb_json)
                    )
                    conn.commit()
                    conn.close()
        except Exception as e:
            logger.error(f"Error saving episodic memory: {e}")

    async def search_episodic_memory(self, user_id: int, query: str, threshold: float = 0.5, limit: int = 3) -> List[str]:
        try:
            query_emb = await self.provider.get_embeddings(EMBEDDING_MODEL, query)
            if not query_emb:
                return []
                
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT summary, embedding FROM episodic_memory WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            conn.close()
            
            results = []
            for row in rows:
                summary = row["summary"]
                emb = json.loads(row["embedding"])
                sim = cosine_similarity(query_emb, emb)
                if sim >= threshold:
                    results.append({"summary": summary, "score": sim})
            
            results.sort(key=lambda x: x["score"], reverse=True)
            return [r["summary"] for r in results[:limit]]
        except Exception as e:
            logger.error(f"Error searching episodic memory: {e}")
            return []
