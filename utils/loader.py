import pandas as pd
import re
from datetime import datetime
from utils.db_manager import get_db_connection

class LegacyDataStagingGateway:
    
    @staticmethod
    def _get_val(row_dict: dict, aliases: list) -> str:
        """Helper to find matching values across column name variants."""
        norm_dict = {re.sub(r'[\s_\-]+', '', str(k)).lower(): v for k, v in row_dict.items()}
        for a in aliases:
            norm_a = re.sub(r'[\s_\-]+', '', str(a)).lower()
            if norm_a in norm_dict and pd.notna(norm_dict[norm_a]):
                val = str(norm_dict[norm_a]).strip()
                if val.lower() not in {"nan", "null", "none", ""}:
                    return val
        return ""

    @classmethod
    def seed_database_from_csv(cls, file_path: str) -> int:
        """Parses CSV layout rows, extracts Freshservice fields, and seeds SQLite."""
        try:
            df = pd.read_csv(file_path)
            df.columns = df.columns.str.strip()

            with get_db_connection() as conn:
                cursor = conn.cursor()
                now_str = datetime.utcnow().isoformat()
                records_saved = 0

                for _, row in df.iterrows():
                    row_dict = row.to_dict()
                    t_id = cls._get_val(row_dict, ["Ticket Id", "ticket_id", "id"])
                    if not t_id:
                        continue

                    # Extract values safely across possible CSV header aliases
                    group_val = cls._get_val(row_dict, ["Group", "ticket_group", "assigned_group"])
                    alarm_source = cls._get_val(row_dict, ["Alarm Source", "alarm_source", "source"])
                    affected_ci = cls._get_val(row_dict, ["Affected CI", "affected_ci", "ci", "asset"])
                    issue_bucket = cls._get_val(row_dict, ["Issue Bucket", "issue_bucket", "bucket", "ticket_type", "type"])
                    urgency_val = cls._get_val(row_dict, ["Urgency", "urgency", "priority"])
                    company_val = cls._get_val(row_dict, ["Company", "company", "account_name"])
                    category_val = cls._get_val(row_dict, ["Category", "category"])
                    ticket_type_val = cls._get_val(row_dict, ["Ticket Type", "Type", "ticket_type", "type"])

                    effort_val = pd.to_numeric(row.get("Effort Required to Resolve (in mins)"), errors='coerce')
                    res_hours_val = pd.to_numeric(row.get("Resolution Hours"), errors='coerce')

                    cursor.execute("""
                        INSERT INTO tickets (
                            ticket_id, created_time, resolved_time, subject, description,
                            priority, urgency, ticket_group, company, ticket_type, category,
                            alarm_source, affected_ci, issue_bucket, agent, resolution_applied,
                            resolution_note, status, effort_mins, resolution_hours, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(ticket_id) DO UPDATE SET
                            agent=excluded.agent,
                            status=excluded.status,
                            priority=excluded.priority,
                            urgency=excluded.urgency,
                            ticket_group=excluded.ticket_group,
                            company=excluded.company,
                            ticket_type=excluded.ticket_type,
                            category=excluded.category,
                            alarm_source=excluded.alarm_source,
                            affected_ci=excluded.affected_ci,
                            issue_bucket=excluded.issue_bucket,
                            effort_mins=excluded.effort_mins,
                            resolution_hours=excluded.resolution_hours,
                            updated_at=excluded.updated_at
                    """, (
                        t_id, row.get("Created Time"), row.get("Resolved Time"),
                        row.get("Subject"), row.get("Description"), row.get("Priority"),
                        urgency_val, group_val, company_val, ticket_type_val, category_val,
                        alarm_source, affected_ci, issue_bucket, str(row.get("Agent", "")).strip(),
                        row.get("Resolution Applied"), row.get("Resolution Note"),
                        str(row.get("Status", "")),
                        float(effort_val if pd.notna(effort_val) else 0.0),
                        float(res_hours_val if pd.notna(res_hours_val) else 0.0),
                        now_str
                    ))
                    records_saved += 1
                conn.commit()
            return records_saved
        except Exception as e:
            print(f"❌ Ingestion Pipeline Failure: {e}")
            return 0
