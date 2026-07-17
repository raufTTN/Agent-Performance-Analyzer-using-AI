import pandas as pd

class OperationsLeaderboardScorer:
    @staticmethod
    def compile_weighted_rankings(df: pd.DataFrame, context_type="All Types (SR & Incident)") -> pd.DataFrame:
        """
        Dynamically calculates rankings based on whether we are analyzing 
        Incidents (prioritizing speed/SLA) or Service Requests (prioritizing volume).
        """
        if df.empty or 'agent' not in df.columns:
            return pd.DataFrame()
            
        summary = df.groupby('agent').agg(
            Tickets_Handled=('ticket_id', 'count'),
            Avg_Resolution_Hours=('resolution_hours', 'mean'),
            Avg_Effort_Mins=('effort_mins', 'mean'),
            Compliant_Tickets=('sla_breached', lambda x: (x == 0).sum())
        ).reset_index()
        
        # Strip out unassigned or system ticket noise tags
        summary = summary[~summary['agent'].isin(['', 'nan', 'None'])]
        if summary.empty:
            return pd.DataFrame()

        # --- CUSTOM OPERATION WEIGHT MODIFIERS BASED ON CONTEXT ---
        if context_type == "Incident":
            # Incidents demand high recovery speeds and absolute SLA tracking
            weights = {"sla": 0.50, "speed": 0.35, "volume": 0.10, "effort": 0.05}
        elif context_type == "SR (Service Request)":
            # Service Requests are volume/effort heavy tasks (e.g. access provisioning)
            weights = {"sla": 0.20, "speed": 0.20, "volume": 0.40, "effort": 0.20}
        else:
            # Balanced Standard Matrix Configs (All Types)
            weights = {"sla": 0.40, "speed": 0.30, "volume": 0.20, "effort": 0.10}

        # Normalization using relative max bounds across active metrics queues
        max_vol = summary["Tickets_Handled"].max() or 1
        max_speed = summary["Avg_Resolution_Hours"].max() or 1
        max_effort = summary["Avg_Effort_Mins"].max() or 1

        # Scale vectors (Inverting speed/effort so lower time = better score)
        vol_score = summary["Tickets_Handled"] / max_vol
        speed_score = 1 - (summary["Avg_Resolution_Hours"] / max_speed)
        sla_score = summary["Compliant_Tickets"] / summary["Tickets_Handled"]
        effort_score = 1 - (summary["Avg_Effort_Mins"] / max_effort)

        # Apply the dynamically selected weights
        summary["Performance_Score"] = (
            (sla_score * weights["sla"]) +
            (speed_score * weights["speed"]) +
            (vol_score * weights["volume"]) +
            (effort_score * weights["effort"])
        ) * 100

        # Enforce output formatting styles
        summary["Performance_Score"] = summary["Performance_Score"].round(1)
        summary["Avg_Resolution_Hours"] = summary["Avg_Resolution_Hours"].round(1)
        summary["Avg_Effort_Mins"] = summary["Avg_Effort_Mins"].round(0)

        return summary[[
            "agent", "Tickets_Handled", "Avg_Resolution_Hours", 
            "Avg_Effort_Mins", "Performance_Score"
        ]].sort_values(by="Performance_Score", ascending=False)