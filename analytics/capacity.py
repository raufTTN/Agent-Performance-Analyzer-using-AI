import pandas as pd

class AgentCapacityProfiler:
    @staticmethod
    def calculate_utilization(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates Agent Utilization & Capacity Profile.
        Determines if agents are Underutilized, Optimally Utilized, or Overutilized
        based on their logged effort minutes and ticket volumes compared to team averages.
        """
        if df.empty or 'agent' not in df.columns:
            return pd.DataFrame()
            
        # Create a copy for calculation and safely coerce effort_mins
        df_calc = df.copy()
        if 'effort_mins' in df_calc.columns:
            df_calc['effort_mins'] = pd.to_numeric(df_calc['effort_mins'], errors='coerce').fillna(0)
        else:
            df_calc['effort_mins'] = 0
            
        # Group by agent to aggregate metrics
        util_df = df_calc.groupby('agent').agg(
            Total_Tickets=('ticket_id', 'count'),
            Total_Effort_Mins=('effort_mins', 'sum')
        ).reset_index()
        
        # Strip out unassigned or system ticket noise tags
        util_df = util_df[~util_df['agent'].isin(['', 'nan', 'None'])]
        if util_df.empty:
            return pd.DataFrame()
            
        # Calculate Team-wide Statistical Benchmarks
        team_avg_effort = util_df['Total_Effort_Mins'].mean()
        # Ensure we have at least 1 for std to avoid division/comparison issues with single agent teams
        team_std_effort = util_df['Total_Effort_Mins'].std(ddof=0) if len(util_df) > 1 else 0
        
        team_avg_tickets = util_df['Total_Tickets'].mean()
        team_std_tickets = util_df['Total_Tickets'].std(ddof=0) if len(util_df) > 1 else 0
        
        effort_25th = util_df['Total_Effort_Mins'].quantile(0.25)
        ticket_25th = util_df['Total_Tickets'].quantile(0.25)
        
        def get_status(row):
            effort = row['Total_Effort_Mins']
            tickets = row['Total_Tickets']
            
            # Underutilized: both effort and ticket volume are significantly below team average (bottom 25%)
            if effort <= effort_25th and tickets <= ticket_25th:
                return "Underutilized"
            
            # Overutilized: exceptionally high effort or ticket volume compared to the rest of the team
            if effort > (team_avg_effort + team_std_effort) or tickets > (team_avg_tickets + team_std_tickets):
                return "Overutilized"
                
            # Otherwise, they fall within optimal utilization bands
            return "Optimally Utilized"
            
        util_df['Utilization_Status'] = util_df.apply(get_status, axis=1)
        
        return util_df
