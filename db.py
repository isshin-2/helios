import sqlite3
import json
import os

DB_PATH = "helios.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            system_access TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Sessions table (Chat History)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    
    # Long Term Memory (RAG)
    # We store the embedding as a JSON string of floats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            fact TEXT NOT NULL,
            embedding TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Audit Log for system access operations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tool TEXT NOT NULL,
            operation TEXT NOT NULL,
            target TEXT,
            permission_result TEXT NOT NULL,
            execution_result TEXT,
            error TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ─── Self-Modification Authoritative State ────────────────────────────────
    
    # Experiments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            objective TEXT NOT NULL,
            risk_level TEXT DEFAULT 'LOW',
            status TEXT DEFAULT 'DRAFT',
            diff_stats TEXT,
            deployment TEXT
        )
    """)

    # Experiment Files
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiment_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT NOT NULL,
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            baseline_sha256 TEXT,
            pre_deploy_sha256 TEXT,
            deployed_sha256 TEXT,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        )
    """)

    # Evaluation Runs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            evaluator_version TEXT,
            classification TEXT,
            baseline_hash TEXT,
            critical_regressions TEXT,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        )
    """)

    # Evaluation Comparisons
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id INTEGER NOT NULL,
            metric TEXT NOT NULL,
            direction TEXT NOT NULL,
            baseline_result TEXT NOT NULL,
            experiment_result TEXT NOT NULL,
            change_percent REAL,
            result TEXT NOT NULL,
            FOREIGN KEY (evaluation_id) REFERENCES evaluation_runs(id)
        )
    """)

    # Experiment Audit Log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiment_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actor TEXT NOT NULL,
            experiment_id TEXT NOT NULL,
            action TEXT NOT NULL,
            previous_state TEXT,
            new_state TEXT,
            reason TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def migrate_db():
    """Safe migration for existing databases. Adds new columns without data loss."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Add system_access column to users if it doesn't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN system_access TEXT DEFAULT '{}'")
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists — this is fine
        pass
    
    conn.close()

if not os.path.exists(DB_PATH):
    init_db()
else:
    # Ensure tables exist and run migrations
    init_db()
    migrate_db()
