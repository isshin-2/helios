import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from router.memory import MemoryManager
import sqlite3

@pytest.fixture
def mock_db():
    conn = sqlite3.connect("file:memorydb?mode=memory&cache=shared", uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            fact TEXT NOT NULL,
            embedding TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("DELETE FROM memories")
    conn.commit()
    return conn

@pytest.fixture
def mock_provider():
    provider = MagicMock()
    # Mock generation
    provider.generate = AsyncMock(return_value={"response": "- User likes Python\n- Working on HELIOS"})
    
    # Mock embeddings to return a dummy vector
    provider.get_embeddings = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return provider

@pytest.mark.asyncio
async def test_extract_and_save_facts(mock_provider, mock_db):
    def get_shared_db():
        conn = sqlite3.connect("file:memorydb?mode=memory&cache=shared", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
        
    with patch("router.memory.get_db", side_effect=get_shared_db):
        manager = MemoryManager(mock_provider)
        await manager.extract_and_save_facts(1, "I like Python and I am working on HELIOS.")
        
        # Check DB
        cursor = mock_db.cursor()
        cursor.execute("SELECT * FROM memories WHERE user_id = 1")
        rows = cursor.fetchall()
        
        assert len(rows) == 2
        assert rows[0]["fact"] == "User likes Python"
        assert rows[1]["fact"] == "Working on HELIOS"
        
@pytest.mark.asyncio
async def test_search_memory(mock_provider, mock_db):
    def get_shared_db():
        conn = sqlite3.connect("file:memorydb?mode=memory&cache=shared", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
        
    with patch("router.memory.get_db", side_effect=get_shared_db):
        manager = MemoryManager(mock_provider)
        
        # Insert dummy memory
        cursor = mock_db.cursor()
        cursor.execute(
            "INSERT INTO memories (user_id, fact, embedding) VALUES (?, ?, ?)",
            (1, "User likes Python", json.dumps([0.1, 0.2, 0.3]))
        )
        mock_db.commit()
        
        # Provider get_embeddings is already mocked to return [0.1, 0.2, 0.3]
        results = await manager.search_memory(1, "What does the user like?")
        
        assert len(results) == 1
        assert results[0] == "User likes Python"
