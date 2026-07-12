import pandas as pd
import plotly.express as px

def render_priority_distribution(df: pd.DataFrame):
    if df.empty or 'priority' not in df.columns:
        return None
    counts = df['priority'].value_counts().reset_index()
    counts.columns = ['Priority', 'Count']
    fig = px.bar(counts, x='Priority', y='Count', color='Priority', template='plotly_dark')
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300, showlegend=False)
    return fig

def render_workload_allocation(df: pd.DataFrame):
    if df.empty or 'agent' not in df.columns:
        return None
    counts = df['agent'].value_counts().head(10).reset_index()
    counts.columns = ['Agent', 'Active Tickets']
    fig = px.bar(counts, x='Active Tickets', y='Agent', orientation='h', template='plotly_dark')
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300)
    return fig
