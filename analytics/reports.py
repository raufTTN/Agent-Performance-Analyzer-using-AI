import pandas as pd
import numpy as np

class ExcelReportsGenerator:
    """Generates Excel-style operations and utilization reports directly from the active DataFrame."""

    @staticmethod
    def generate_top_accounts_report(df: pd.DataFrame, working_days: float = 20.0) -> pd.DataFrame:
        if df.empty: return pd.DataFrame()
        
        # Ensure numeric
        df_calc = df.copy()
        df_calc['effort_mins'] = pd.to_numeric(df_calc['effort_mins'], errors='coerce').fillna(0)
        
        grouped = df_calc.groupby('company').agg(
            tickets=('ticket_id', 'count'),
            total_efforts_mins=('effort_mins', 'sum')
        ).reset_index()
        
        grouped['efforts_per_ticket'] = (grouped['total_efforts_mins'] / grouped['tickets']).round(2)
        # Utilization = (total mins / 60 hrs / 8 hrs_per_day) / working_days
        grouped['utilization_pct'] = ((grouped['total_efforts_mins'] / 60 / 8) / working_days).round(4)
        
        grouped = grouped.sort_values(by='tickets', ascending=False)
        
        report_df = grouped.rename(columns={
            'company': 'Top Accounts',
            'tickets': 'Ticket Resolved by L1 Team',
            'total_efforts_mins': 'Total L1 Efforts in the account (Mints)',
            'efforts_per_ticket': 'Efforts (Mint/ticket)',
            'utilization_pct': 'L1 Team Utilization per Account'
        })
        return report_df

    @staticmethod
    def generate_agent_working_stats(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return pd.DataFrame()
        
        df_calc = df.copy()
        df_calc['effort_mins'] = pd.to_numeric(df_calc['effort_mins'], errors='coerce').fillna(0)
        
        # Filter out invalid agents
        df_calc = df_calc[~df_calc['agent'].isin(['', 'nan', 'None'])]
        
        grouped = df_calc.groupby('agent').agg(
            total_tickets=('ticket_id', 'count'),
            total_mins=('effort_mins', 'sum')
        ).reset_index()
        
        grouped['total_hours'] = (grouped['total_mins'] / 60).round(2)
        grouped['total_days'] = (grouped['total_hours'] / 8).round(2)
        grouped['per_ticket_effort'] = (grouped['total_mins'] / grouped['total_tickets']).round(1)
        
        report_df = grouped[['agent', 'total_days', 'total_hours', 'total_mins', 'total_tickets', 'per_ticket_effort']]
        report_df = report_df.rename(columns={
            'agent': 'Agent Name',
            'total_days': 'Total Working days',
            'total_hours': 'Total working hours',
            'total_mins': 'Total working Minutes',
            'total_tickets': 'Total tickets',
            'per_ticket_effort': 'Per Ticket Effort (in mins)'
        })
        
        # Calculate Average row
        if not report_df.empty:
            avg_row = pd.DataFrame([{
                'Agent Name': 'Average',
                'Total Working days': report_df['Total Working days'].mean().round(3),
                'Total working hours': report_df['Total working hours'].mean().round(2),
                'Total working Minutes': report_df['Total working Minutes'].mean().round(2),
                'Total tickets': report_df['Total tickets'].mean().round(0),
                'Per Ticket Effort (in mins)': report_df['Per Ticket Effort (in mins)'].mean().round(1)
            }])
            report_df = pd.concat([report_df, avg_row], ignore_index=True)
            
        return report_df

    @staticmethod
    def generate_agent_pivot(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return pd.DataFrame()
        
        df_calc = df.copy()
        df_calc['effort_mins'] = pd.to_numeric(df_calc['effort_mins'], errors='coerce').fillna(0)
        df_calc = df_calc[~df_calc['agent'].isin(['', 'nan', 'None'])]
        
        grouped = df_calc.groupby('agent').agg(
            sum_effort=('effort_mins', 'sum'),
            count_tickets=('ticket_id', 'count')
        ).reset_index()
        
        grouped['avg_effort'] = (grouped['sum_effort'] / grouped['count_tickets']).round(2)
        
        report_df = grouped.rename(columns={
            'agent': 'Agent',
            'sum_effort': 'SUM of Effort Required to Resolve (in mins)',
            'count_tickets': 'COUNTA of Ticket Id',
            'avg_effort': 'Average Efforts in min per tickets'
        })
        
        if not report_df.empty:
            total_row = pd.DataFrame([{
                'Agent': 'Grand Total',
                'SUM of Effort Required to Resolve (in mins)': report_df['SUM of Effort Required to Resolve (in mins)'].sum(),
                'COUNTA of Ticket Id': report_df['COUNTA of Ticket Id'].sum(),
                'Average Efforts in min per tickets': (report_df['SUM of Effort Required to Resolve (in mins)'].sum() / report_df['COUNTA of Ticket Id'].sum()).round(2)
            }])
            report_df = pd.concat([report_df, total_row], ignore_index=True)
            
        return report_df

    @staticmethod
    def generate_agent_utilization(df: pd.DataFrame, working_days: float = 20.0) -> pd.DataFrame:
        if df.empty: return pd.DataFrame()
        
        df_calc = df.copy()
        df_calc['effort_mins'] = pd.to_numeric(df_calc['effort_mins'], errors='coerce').fillna(0)
        df_calc = df_calc[~df_calc['agent'].isin(['', 'nan', 'None'])]
        
        grouped = df_calc.groupby('agent').agg(
            sum_effort_mins=('effort_mins', 'sum')
        ).reset_index()
        
        grouped['agent_level'] = 'L1'  # Hardcoded per user request
        grouped['sum_effort_hrs'] = (grouped['sum_effort_mins'] / 60).round(3)
        grouped['total_efforts_days'] = (grouped['sum_effort_hrs'] / 8).round(2)
        grouped['utilization_pct'] = (grouped['total_efforts_days'] / working_days).round(4) # Styler will convert 0.4453 to 44.53%
        
        report_df = grouped[['agent', 'agent_level', 'sum_effort_hrs', 'total_efforts_days', 'utilization_pct']]
        report_df = report_df.rename(columns={
            'agent': 'Agent',
            'agent_level': 'Agent Level',
            'sum_effort_hrs': 'SUM of Effort spent in hrs',
            'total_efforts_days': 'Total Efforts (in Days)',
            'utilization_pct': 'Utilization %'
        })
        
        return report_df

    @staticmethod
    def generate_client_ticket_count(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return pd.DataFrame()
        
        grouped = df.groupby('company').agg(
            count_tickets=('ticket_id', 'count')
        ).reset_index()
        
        grouped = grouped.sort_values(by='company')
        
        report_df = grouped.rename(columns={
            'company': 'Company',
            'count_tickets': 'COUNTA of Ticket Id'
        })
        
        if not report_df.empty:
            total_row = pd.DataFrame([{
                'Company': 'Grand Total',
                'COUNTA of Ticket Id': report_df['COUNTA of Ticket Id'].sum()
            }])
            report_df = pd.concat([report_df, total_row], ignore_index=True)
            
        return report_df
