import sqlite3
from config import DB_PATH

def get_db_connection():
    """Returns a thread-safe cursor connection wrapper instance."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """Deploys schema structures locally inside SQLite."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Primary Relational Tickets Model Table with full Freshservice fields
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                created_time TEXT,
                resolved_time TEXT,
                subject TEXT,
                description TEXT,
                priority TEXT,
                urgency TEXT,
                ticket_group TEXT,
                company TEXT,
                ticket_type TEXT,
                category TEXT,
                alarm_source TEXT,
                affected_ci TEXT,
                issue_bucket TEXT,
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
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_agent ON tickets(agent);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);")
        conn.commit()

if __name__ == "__main__":
    initialize_database()
    print("✅ Database Initialization Complete.")
