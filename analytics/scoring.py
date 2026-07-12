import pandas as pd
from config import SCORING_WEIGHTS

class OperationsLeaderboardScorer:
    @staticmethod
    def compile_weighted_rankings(df: pd.DataFrame) -> pd.DataFrame:
        """Computes balanced performance metrics rankings, safely handling zero bounds."""
        if df.empty or 'agent' not in df.columns:
            return pd.DataFrame()
            
        summary = df.groupby('agent').agg(
            Tickets_Handled=('ticket_id', 'count'),
            Avg_Resolution_Hours=('resolution_hours', 'mean'),
            Avg_Effort_Mins=('effort_mins', 'mean'),
            Compliant_Tickets=('sla_breached', lambda x: (x == 0).sum())
        ).reset_index()
        
        summary = summary[~summary['agent'].isin(['', 'nan', 'None'])]
        if summary.empty:
            return pd.DataFrame()

        # Step 1: Normalization using relative max bounds across active metrics queues
        max_vol = summary["Tickets_Handled"].max() or 1
        max_speed = summary["Avg_Resolution_Hours"].max() or 1
        max_effort = summary["Avg_Effort_Mins"].max() or 1

        # Step 2: Scale vectors safely
        vol_score = summary["Tickets_Handled"] / max_vol
        speed_score = 1 - (summary["Avg_Resolution_Hours"] / max_speed)
        sla_score = summary["Compliant_Tickets"] / summary["Tickets_Handled"]
        effort_score = 1 - (summary["Avg_Effort_Mins"] / max_effort)

        # Step 3: Weighted combination formula application
        summary["Performance_Score"] = (
            (sla_score * SCORING_WEIGHTS["sla_compliance"]) +
            (speed_score * SCORING_WEIGHTS["resolution_speed"]) +
            (vol_score * SCORING_WEIGHTS["volume_impact"]) +
            (effort_score * SCORING_WEIGHTS["effort_efficiency"])
        ) * 100

        summary["Performance_Score"] = summary["Performance_Score"].round(1)
        summary["Avg_Resolution_Hours"] = summary["Avg_Resolution_Hours"].round(1)
        summary["Avg_Effort_Mins"] = summary["Avg_Effort_Mins"].round(0)

        return summary[[
            "agent", "Tickets_Handled", "Avg_Resolution_Hours", 
            "Avg_Effort_Mins", "Performance_Score"
        ]].sort_values(by="Performance_Score", ascending=False)
