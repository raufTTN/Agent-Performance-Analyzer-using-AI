import sqlite3
from config import DB_PATH

def get_db_connection():
    """Establishes thread-safe client connection context to local database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """Initializes primary tables and index maps inside storage architecture."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Primary Relational Tickets Storage Table Structure
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                created_time TEXT,
                resolved_time TEXT,
                subject TEXT,
                description TEXT,
                priority TEXT,
                agent TEXT,
                resolution_applied TEXT,
                resolution_note TEXT,
                status TEXT,
                effort_mins REAL,
                resolution_hours REAL,
                sla_breached INTEGER DEFAULT 0,
                updated_at TEXT
            )
        """)
        
        # Performance indexes for heavy data grouping runs
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_agent ON tickets(agent);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);")
        conn.commit()

if __name__ == "__main__":
    initialize_database()
    print("✅ Local SQLite database layer operational.")
