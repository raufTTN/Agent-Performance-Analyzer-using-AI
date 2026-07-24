# import pandas as pd
# from datetime import datetime
# from utils.db_manager import get_db_connection

# class LegacyDataStagingGateway:
#     @staticmethod
#     def seed_database_from_csv(file_path: str) -> int:
#         """Parses CSV layout rows, dynamically calculates missing metrics, and seeds SQLite."""
#         try:
#             df = pd.read_csv(file_path)
#             df.columns = df.columns.str.strip()
#             with get_db_connection() as conn:
#                 cursor = conn.cursor()

#                 # Clear previous dataset
#                 cursor.execute("DELETE FROM tickets")
#                 conn.commit()

#                 now_str = datetime.utcnow().isoformat()

#                 for _, row in df.iterrows():
#             # with get_db_connection() as conn:
#             #     cursor = conn.cursor()
#             #     now_str = datetime.utcnow().isoformat()
#             #     records_saved = 0

#             #     for _, row in df.iterrows():
#                     t_id = str(row.get("Ticket Id", row.get("ticket_id", ""))).strip()
#                     if not t_id or t_id == "nan" or t_id == "":
#                         continue

#                     # Core Numeric Parse Gauges
#                     effort_val = pd.to_numeric(row.get("Effort Required to Resolve (in mins)"), errors='coerce')
#                     res_hours_val = pd.to_numeric(row.get("Resolution Hours"), errors='coerce')

#                     # Dynamic Fallback: Calculate hours from timestamps if column is missing/zero
#                     created_raw = row.get("Created Time")
#                     resolved_raw = row.get("Resolved Time")

#                     if (pd.isna(res_hours_val) or res_hours_val == 0.0) and pd.notna(created_raw) and pd.notna(resolved_raw):
#                         try:
#                             # Adapt dynamically to common Freshservice timestamp formats
#                             fmt = "%Y-%m-%d %H:%M:%S" if "-" in str(created_raw) else "%d/%m/%Y %H:%M"
#                             c_dt = datetime.strptime(str(created_raw).strip(), fmt)
#                             r_dt = datetime.strptime(str(resolved_raw).strip(), fmt)
#                             calculated_hours = (r_dt - c_dt).total_seconds() / 3600.0
#                             res_hours_val = max(0.0, calculated_hours)
#                         except Exception:
#                             res_hours_val = 0.0

#                     cursor.execute("""
#                         INSERT INTO tickets (
#                             ticket_id, created_time, resolved_time, subject, description,
#                             priority, company, agent, resolution_applied, resolution_note, status,
#                             effort_mins, resolution_hours, updated_at
#                         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#                         ON CONFLICT(ticket_id) DO UPDATE SET
#                             company=excluded.company,
#                             agent=excluded.agent,
#                             status=excluded.status,
#                             priority=excluded.priority,
#                             effort_mins=excluded.effort_mins,
#                             resolution_hours=excluded.resolution_hours,
#                             updated_at=excluded.updated_at
#                     """, (
#                         t_id, row.get("Created Time"), row.get("Resolved Time"),
#                         row.get("Subject"), row.get("Description"), row.get("Priority"),
#                         str(row.get("Company", row.get("Companies", "Unknown Company"))).strip(), # NEW: Capturing Company
#                         str(row.get("Agent")).strip(), row.get("Resolution Applied"), row.get("Resolution Note"),
#                         str(row.get("Status")),
#                         float(effort_val if pd.notna(effort_val) else 0.0),
#                         float(res_hours_val if pd.notna(res_hours_val) else 0.0),
#                         now_str
#                     ))
#                     records_saved += 1
#                 conn.commit()
#             return records_saved
#         except Exception as e:
#             print(f"❌ Ingestion Pipeline Failure: {e}")
#             return 0

# Kaynat
import pandas as pd
from datetime import datetime
from utils.db_manager import get_db_connection


class LegacyDataStagingGateway:
    @staticmethod
    def seed_database_from_csv(file_path: str) -> int:
        """Parses CSV rows and seeds SQLite with the selected dataset."""
        try:
            df = pd.read_csv(file_path)
            df.columns = df.columns.str.strip()

            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Clear previous dataset to allow clean switching
                cursor.execute("DELETE FROM tickets")
                conn.commit()
                
                now_str = datetime.utcnow().isoformat()
                records_saved = 0

                for _, row in df.iterrows():
                    t_id = str(row.get("Ticket Id", row.get("ticket_id", ""))).strip()

                    if not t_id or t_id.lower() == "nan":
                        continue
                    effort_val = pd.to_numeric(
                        row.get("Effort Required to Resolve (in mins)"), errors="coerce"
                    )

                    res_hours_val = pd.to_numeric(
                        row.get("Resolution Hours"), errors="coerce"
                    )
                    created_raw = row.get("Created Time")
                    resolved_raw = row.get("Resolved Time")

                    if (
                        (pd.isna(res_hours_val) or res_hours_val == 0.0)
                        and pd.notna(created_raw)
                        and pd.notna(resolved_raw)
                    ):
                        try:
                            fmt = (
                                "%Y-%m-%d %H:%M:%S"
                                if "-" in str(created_raw)
                                else "%d/%m/%Y %H:%M"
                            )

                            c_dt = datetime.strptime(str(created_raw).strip(), fmt)
                            r_dt = datetime.strptime(str(resolved_raw).strip(), fmt)
                            res_hours_val = max(
                                0.0, (r_dt - c_dt).total_seconds() / 3600.0
                            )
                        except Exception:
                            res_hours_val = 0.0

                    cursor.execute(
                        """
    INSERT INTO tickets (
        ticket_id,
        created_time,
        resolved_time,
        subject,
        description,
        priority,
        company,
        ticket_type,
        agent,
        resolution_applied,
        resolution_note,
        status,
        effort_mins,
        resolution_hours,
        updated_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

    ON CONFLICT(ticket_id) DO UPDATE SET
        created_time = excluded.created_time,
        resolved_time = excluded.resolved_time,
        subject = excluded.subject,
        description = excluded.description,
        priority = excluded.priority,
        company = excluded.company,
        ticket_type = excluded.ticket_type,
        agent = excluded.agent,
        resolution_applied = excluded.resolution_applied,
        resolution_note = excluded.resolution_note,
        status = excluded.status,
        effort_mins = excluded.effort_mins,
        resolution_hours = excluded.resolution_hours,
        updated_at = excluded.updated_at
""",
                        (
                            t_id,
                            row.get("Created Time"),
                            row.get("Resolved Time"),
                            row.get("Subject"),
                            row.get("Description"),
                            row.get("Priority"),
                            str(
                                row.get(
                                    "Company", row.get("Companies", "Unknown Company")
                                )
                            ).strip(),
                            str(row.get("Type")).strip(),
                            str(row.get("Agent")).strip(),
                            row.get("Resolution Applied"),
                            row.get("Resolution Note"),
                            str(row.get("Status")),
                            float(effort_val if pd.notna(effort_val) else 0.0),
                            float(res_hours_val if pd.notna(res_hours_val) else 0.0),
                            now_str,
                        ),
                    )

                    records_saved += 1

                conn.commit()

            print(f"✅ Imported {records_saved} records from {file_path}")
            return records_saved

        except Exception as e:
            print(f"❌ Ingestion Pipeline Failure: {e}")
            return 0
