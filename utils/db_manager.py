# import sqlite3
# from config import DB_PATH

# def get_db_connection():
#     """Establishes thread-safe client connection context to local database."""
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     return conn

# def initialize_database():
#     """Initializes primary tables and index maps inside storage architecture."""
#     with get_db_connection() as conn:
#         cursor = conn.cursor()
        
#         # Primary Relational Tickets Storage Table Structure
#         # Included company, ticket_type, category, and sub_category
#         cursor.execute("""
#             CREATE TABLE IF NOT EXISTS tickets (
#                 ticket_id TEXT PRIMARY KEY,
#                 created_time TEXT,
#                 resolved_time TEXT,
#                 subject TEXT,
#                 description TEXT,
#                 priority TEXT,
#                 company TEXT,
#                 ticket_type TEXT,
#                 category TEXT,
#                 sub_category TEXT,
#                 agent TEXT,
#                 resolution_applied TEXT,
#                 resolution_note TEXT,
#                 status TEXT,
#                 effort_mins REAL,
#                 resolution_hours REAL,
#                 sla_breached INTEGER DEFAULT 0,
#                 updated_at TEXT
#             )
#         """)
        
#         # Performance indexes for heavy data grouping runs
#         cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_agent ON tickets(agent);")
#         cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);")
#         cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_company ON tickets(company);")
#         cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_type ON tickets(ticket_type);")
#         cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);")
#         conn.commit()

# if __name__ == "__main__":
#     initialize_database()
#     print("✅ Local SQLite database layer operational with Company, Type, and Category tracking.")

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
                company TEXT,
                ticket_type TEXT,
                category TEXT,
                sub_category TEXT,
                affected_ci TEXT,
                other_affected_ci TEXT,
                issue_bucket TEXT,
                agent TEXT,
                resolution_applied TEXT,
                resolution_note TEXT,
                escalation TEXT,
                status TEXT,
                effort_mins REAL,
                resolution_hours REAL,
                sla_breached INTEGER DEFAULT 0,
                updated_at TEXT
            )
        """)

        # ---------------------------------------------------------
        # DATABASE MIGRATION
        # Required because analyzer.db may already exist
        # ---------------------------------------------------------
        existing_columns = {
            row[1]
            for row in cursor.execute(
                "PRAGMA table_info(tickets)"
            ).fetchall()
        }

        new_columns = {
            "affected_ci": "TEXT",
            "other_affected_ci": "TEXT",
            "issue_bucket": "TEXT",
            "escalation": "TEXT",
        }

        for column_name, column_type in new_columns.items():
            if column_name not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE tickets ADD COLUMN {column_name} {column_type}"
                )

        # Performance indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_agent ON tickets(agent);"
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);"
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_company ON tickets(company);"
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_type ON tickets(ticket_type);"
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);"
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_issue_bucket ON tickets(issue_bucket);"
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_affected_ci ON tickets(affected_ci);"
        )

        conn.commit()


if __name__ == "__main__":
    initialize_database()
    print("✅ Local SQLite database layer operational with CI, Issue Bucket, Escalation and Category tracking.")