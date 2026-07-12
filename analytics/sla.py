import pandas as pd
from utils.db_manager import get_db_connection

class CoreSLADiagnosticEngine:
    @staticmethod
    def execute_global_sla_audit():
        """
        Validates all stored records against SLA thresholds to update breach flags.
        Handles flexible text casing and data cleaning dynamically.
        """
        # Precise operational time mapping targets
        sla_targets = {
            "urgent": 4.0,   # P0
            "high": 8.0,     # P1
            "medium": 16.0,  # P2
            "low": 24.0      # P3
        }

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticket_id, priority, resolution_hours FROM tickets")
            rows = cursor.fetchall()
            
            for row in rows:
                t_id = row["ticket_id"]
                
                # Strip out trailing spaces and clean up casing variations
                raw_priority = str(row["priority"]).strip().lower() if row["priority"] else ""
                raw_res_hours = row["resolution_hours"]
                
                # Quick fallback: Map standard alternatives just in case
                if "p0" in raw_priority: raw_priority = "urgent"
                elif "p1" in raw_priority: raw_priority = "high"
                elif "p2" in raw_priority: raw_priority = "medium"
                elif "p3" in raw_priority: raw_priority = "low"
                
                # Safely convert to float, default to None if invalid
                try:
                    res_hours = float(raw_res_hours) if raw_res_hours is not None else None
                except ValueError:
                    res_hours = None
                
                # If data is missing or priority doesn't match targets, default to non-breached
                if res_hours is None or raw_priority not in sla_targets:
                    cursor.execute("UPDATE tickets SET sla_breached = 0 WHERE ticket_id = ?", (t_id,))
                    continue
                    
                target_limit = sla_targets[raw_priority]
                breach_flag = 1 if res_hours > target_limit else 0
                
                cursor.execute(
                    "UPDATE tickets SET sla_breached = ? WHERE ticket_id = ?",
                    (breach_flag, t_id)
                )
            conn.commit()

    @staticmethod
    def fetch_sla_summary(df: pd.DataFrame) -> dict:
        """Returns verified total breaches and corporate compliance scores."""
        if df.empty:
            return {"compliance_pct": 100.0, "breach_count": 0}
        total = len(df)
        breaches = int(df["sla_breached"].sum()) if "sla_breached" in df.columns else 0
        compliance = ((total - breaches) / total) * 100 if total > 0 else 100.0
        return {"compliance_pct": round(compliance, 1), "breach_count": breaches}
