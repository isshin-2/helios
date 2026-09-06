import json
import numpy as np
from typing import List, Dict, Any, Optional
from db import get_db
import logging

logger = logging.getLogger(__name__)

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
    def __init__(self, provider: BaseProvider):
        self.provider = provider

    async def extract_and_save_facts(self, user_id: int, message: str):
        """Asynchronously extracts facts from a user message and saves them to long-term memory."""
        prompt = (
            "Extract any key personal facts, preferences, or ongoing project details from the following message. "
            "Only extract factual statements about the user or their work. "
            "Critically, IGNORE any hypothetical scenarios, ethical dilemmas, 'what-if' questions, or roleplay situations. Do not extract facts about HELIOS itself. "
            "If there are no clear facts to remember, reply with 'NONE'.\n"
            "Format the output as a concise bulleted list of facts.\n\n"
            f"Message: {message}"
        )
        
        try:
            response = await self.provider.generate(model=FACT_EXTRACTION_MODEL, prompt=prompt, stream=False)
            output = response.get("response", "").strip()
            
            if not output or "NONE" in output.upper():
                return
                
            # We found facts. Let's process them.
            # We can split by newlines if it's a list, or just save the whole summary as one chunk.
            lines = [line.strip("- *") for line in output.split("\n") if line.strip()]
            for fact in lines:
                if fact:
                    await self.save_fact(user_id, fact)
        except Exception as e:
            logger.error(f"Error extracting facts: {e}")

    async def save_fact(self, user_id: int, fact: str):
        """Embeds a fact and saves it to the SQLite database."""
        try:
            embedding = await self.provider.get_embeddings(EMBEDDING_MODEL, fact)
            if not embedding:
                return
                
            emb_json = json.dumps(embedding)
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO memories (user_id, fact, embedding) VALUES (?, ?, ?)",
                (user_id, fact, emb_json)
            )
            conn.commit()
            conn.close()
            logger.info(f"Saved new memory for user {user_id}: {fact}")
        except Exception as e:
            logger.error(f"Error saving fact: {e}")

    async def search_memory(self, user_id: int, query: str, threshold: float = 0.5, limit: int = 3) -> List[str]:
        """Searches long-term memory for facts relevant to the query."""
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
        """Retrieves all core memory sections combined into a single string for the prompt."""
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
        """Appends to a specific section in core memory. Creates section if missing."""
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

