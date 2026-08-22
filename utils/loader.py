
# New Version Kaynat 

import pandas as pd
from datetime import datetime
from utils.db_manager import get_db_connection


class LegacyDataStagingGateway:
    @staticmethod
    def seed_database_from_csv(file_path: str) -> int:
        """Parses CSV rows and seeds SQLite with the selected dataset."""
        try:
            df = pd.read_csv(file_path)

            # Remove unwanted spaces from CSV column names
            df.columns = df.columns.str.strip()

            # ---------------------------------------------------------
            # CSV COLUMN MAPPING
            # CSV names -> SQLite database names
            # ---------------------------------------------------------
            column_mapping = {
                "Affected CI": "affected_ci",
                "Other Affected CI": "other_affected_ci",
                "Issue Bucket": "issue_bucket",
                "Resolution Note": "resolution_note",
                "Escalation": "escalation",
            }

            # Rename only the columns that exist in the CSV
            df.rename(columns=column_mapping, inplace=True)

            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Clear previous dataset to allow clean CSV switching
                cursor.execute("DELETE FROM tickets")
                conn.commit()

                now_str = datetime.utcnow().isoformat()
                records_saved = 0

                for _, row in df.iterrows():

                    # -------------------------------------------------
                    # Ticket ID
                    # -------------------------------------------------
                    t_id = str(
                        row.get(
                            "Ticket Id",
                            row.get("ticket_id", "")
                        )
                    ).strip()

                    if not t_id or t_id.lower() == "nan":
                        continue

                    # -------------------------------------------------
                    # Effort
                    # -------------------------------------------------
                    effort_val = pd.to_numeric(
                        row.get("Effort Required to Resolve (in mins)"),
                        errors="coerce"
                    )

                    # -------------------------------------------------
                    # Resolution Hours
                    # -------------------------------------------------
                    res_hours_val = pd.to_numeric(
                        row.get("Resolution Hours"),
                        errors="coerce"
                    )

                    created_raw = row.get("Created Time")
                    resolved_raw = row.get("Resolved Time")

                    # Calculate Resolution Hours if CSV value is
                    # missing or zero
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

                            c_dt = datetime.strptime(
                                str(created_raw).strip(),
                                fmt
                            )

                            r_dt = datetime.strptime(
                                str(resolved_raw).strip(),
                                fmt
                            )

                            res_hours_val = max(
                                0.0,
                                (r_dt - c_dt).total_seconds() / 3600.0
                            )

                        except Exception:
                            res_hours_val = 0.0

                    # -------------------------------------------------
                    # Helper function for safe CSV values
                    # -------------------------------------------------
                    def clean_value(value, default=""):
                        if pd.isna(value):
                            return default

                        value = str(value).strip()

                        if value.lower() == "nan":
                            return default

                        return value

                    # -------------------------------------------------
                    # New Columns
                    # -------------------------------------------------
                    affected_ci = clean_value(
                        row.get("affected_ci")
                    )

                    other_affected_ci = clean_value(
                        row.get("other_affected_ci")
                    )

                    issue_bucket = clean_value(
                        row.get("issue_bucket")
                    )

                    escalation = clean_value(
                        row.get("escalation")
                    )

                    resolution_note = clean_value(
                        row.get("resolution_note")
                    )

                    # -------------------------------------------------
                    # Insert Ticket
                    # -------------------------------------------------
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
                            category,
                            sub_category,
                            affected_ci,
                            other_affected_ci,
                            issue_bucket,
                            agent,
                            resolution_applied,
                            resolution_note,
                            escalation,
                            status,
                            effort_mins,
                            resolution_hours,
                            updated_at
                        )
                        VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?
                        )

                        ON CONFLICT(ticket_id) DO UPDATE SET
                            created_time = excluded.created_time,
                            resolved_time = excluded.resolved_time,
                            subject = excluded.subject,
                            description = excluded.description,
                            priority = excluded.priority,
                            company = excluded.company,
                            ticket_type = excluded.ticket_type,
                            category = excluded.category,
                            sub_category = excluded.sub_category,
                            affected_ci = excluded.affected_ci,
                            other_affected_ci = excluded.other_affected_ci,
                            issue_bucket = excluded.issue_bucket,
                            agent = excluded.agent,
                            resolution_applied = excluded.resolution_applied,
                            resolution_note = excluded.resolution_note,
                            escalation = excluded.escalation,
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

                            # Company
                            clean_value(
                                row.get(
                                    "Company",
                                    row.get(
                                        "Companies",
                                        "Unknown Company"
                                    )
                                ),
                                "Unknown Company"
                            ),

                            # Ticket Type
                            clean_value(
                                row.get(
                                    "Type",
                                    row.get("ticket_type", "")
                                )
                            ),

                            # Category
                            clean_value(
                                row.get(
                                    "Category",
                                    row.get("category", "")
                                )
                            ),

                            # Sub Category
                            clean_value(
                                row.get(
                                    "Sub Category",
                                    row.get("sub_category", "")
                                )
                            ),

                            # NEW COLUMNS
                            affected_ci,
                            other_affected_ci,
                            issue_bucket,

                            # Agent
                            clean_value(
                                row.get("Agent")
                            ),

                            # Resolution Applied
                            clean_value(
                                row.get("Resolution Applied")
                            ),

                            # Resolution Note
                            resolution_note,

                            # Escalation
                            escalation,

                            # Status
                            clean_value(
                                row.get("Status")
                            ),

                            # Effort
                            float(
                                effort_val
                                if pd.notna(effort_val)
                                else 0.0
                            ),

                            # Resolution Hours
                            float(
                                res_hours_val
                                if pd.notna(res_hours_val)
                                else 0.0
                            ),

                            # Updated At
                            now_str,
                        ),
                    )

                    records_saved += 1

                conn.commit()

            print(
                f"✅ Imported {records_saved} records from {file_path}"
            )

            return records_saved

        except Exception as e:
            print(
                f"❌ Ingestion Pipeline Failure: {e}"
            )
            return 0