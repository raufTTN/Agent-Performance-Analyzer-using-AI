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
        
        # Safely migrate existing tables by attempting to add new columns
        try:
            cursor.execute("ALTER TABLE tickets ADD COLUMN assigned_group TEXT")
            cursor.execute("ALTER TABLE tickets ADD COLUMN alarm_source TEXT")
            cursor.execute("ALTER TABLE tickets ADD COLUMN issue_bucket TEXT")
        except sqlite3.OperationalError:
            pass # Columns already exist or table doesn't exist yet
            
        # Primary Relational Tickets Storage Table Structure
        # Included company, ticket_type, category, and sub_category
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                created_time TEXT,
                resolved_time TEXT,
                subject TEXT,
                description TEXT,
                priority TEXT,
                company TEXT,
                ticket_type TEXT,
                category TEXT,
                sub_category TEXT,
                assigned_group TEXT,
                alarm_source TEXT,
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
        
        # Performance indexes for heavy data grouping runs
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_agent ON tickets(agent);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_company ON tickets(company);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_type ON tickets(ticket_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);")
        conn.commit()

if __name__ == "__main__":
    initialize_database()
    print("✅ Local SQLite database layer operational with Company, Type, and Category tracking.")