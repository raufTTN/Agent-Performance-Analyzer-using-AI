import pandas as pd
import numpy as np

class FieldValidationAuditor:
    """Audits ticket metadata to enforce rigorous data hygiene and reporting completeness."""
    
    # Fields considered mandatory for a perfect form
    MANDATORY_FIELDS = {
        "priority": "Priority",
        "company": "Company", 
        "ticket_type": "Type",
        "category": "Category",
        "assigned_group": "Group",
        "alarm_source": "Alarm Source",
        "issue_bucket": "Issue Bucket"
    }

    @staticmethod
    def _evaluate_ticket_hygiene(row):
        """Scans a single ticket row and returns missing fields and hygiene score."""
        missing = []
        for col_name, display_name in FieldValidationAuditor.MANDATORY_FIELDS.items():
            val = str(row.get(col_name, "")).strip().lower()
            if not val or val == "nan" or val == "none" or val == "null" or val == "undefined":
                missing.append(display_name)
                
        total_fields = len(FieldValidationAuditor.MANDATORY_FIELDS)
        missing_count = len(missing)
        
        # Calculate percentage score
        score = ((total_fields - missing_count) / total_fields) * 100
        
        missing_str = ", ".join(missing) if missing else "None"
        return pd.Series([missing_str, round(score, 1), missing_count == 0])

    @staticmethod
    def generate_ticket_inspector(df: pd.DataFrame):
        """Generates detailed ticket-wise validation breakdown."""
        if df.empty:
            return pd.DataFrame(), pd.DataFrame()
            
        inspector_df = df.copy()
        
        # Calculate missing fields and scores
        inspector_df[['Missing Mandatory Fields', 'Score (%)', 'Is_Perfect']] = inspector_df.apply(
            FieldValidationAuditor._evaluate_ticket_hygiene, axis=1
        )
        
        # Map columns for UI
        display_df = inspector_df[[
            'ticket_id', 'subject', 'agent', 'company', 'ticket_type', 
            'Missing Mandatory Fields', 'Score (%)', 'Is_Perfect'
        ]].rename(columns={
            'ticket_id': 'Ticket ID',
            'subject': 'Case Subject',
            'agent': 'Assigned SRE',
            'company': 'Company',
            'ticket_type': 'Type'
        })
        
        # Split into flagged and compliant
        flagged_df = display_df[~display_df['Is_Perfect']].drop(columns=['Is_Perfect'])
        compliant_df = display_df[display_df['Is_Perfect']].drop(columns=['Is_Perfect'])
        
        return flagged_df, compliant_df

    @staticmethod
    def generate_agent_scorecard(df: pd.DataFrame):
        """Generates aggregated field hygiene metrics per SRE engineer."""
        if df.empty:
            return pd.DataFrame()
            
        metrics_df = df.copy()
        metrics_df[['Missing Mandatory Fields', 'Score (%)', 'Is_Perfect']] = metrics_df.apply(
            FieldValidationAuditor._evaluate_ticket_hygiene, axis=1
        )
        
        # Group by Agent
        grouped = metrics_df.groupby('agent').agg(
            total_tickets=('ticket_id', 'count'),
            perfect_forms=('Is_Perfect', 'sum'),
            avg_score=('Score (%)', 'mean')
        ).reset_index()
        
        # Calculate derived metrics
        grouped['missing_forms'] = grouped['total_tickets'] - grouped['perfect_forms']
        grouped['compliance_rate'] = (grouped['perfect_forms'] / grouped['total_tickets']) * 100
        
        # Format for UI
        grouped = grouped.round({'compliance_rate': 1, 'avg_score': 1})
        
        scorecard_df = grouped.rename(columns={
            'agent': 'Assigned SRE / Agent',
            'total_tickets': 'Total Tickets Handled',
            'perfect_forms': '100% Perfect Forms',
            'missing_forms': 'Tickets With Missing Fields',
            'compliance_rate': 'Form Compliance Rate (%)',
            'avg_score': 'Average Hygiene Score (%)'
        })
        
        # Sort by worst compliance first
        return scorecard_df.sort_values(by='Form Compliance Rate (%)', ascending=True)
