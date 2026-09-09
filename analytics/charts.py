import pandas as pd
# pyrefly: ignore [missing-import]
import plotly.express as px

def _apply_premium_layout(fig):
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#8B949E', family='Inter, sans-serif', size=12),
        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', zeroline=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', zeroline=False),
        margin=dict(l=20, r=20, t=30, b=20),
    )
    return fig

def render_priority_distribution(df: pd.DataFrame):
    if df.empty or 'priority' not in df.columns:
        return None
    counts = df['priority'].value_counts().reset_index()
    counts.columns = ['Priority', 'Count']
    fig = px.bar(
        counts, x='Priority', y='Count', 
        color_discrete_sequence=['#3B82F6'],
        template='plotly_dark'
    )
    fig.update_traces(marker_line_width=0, opacity=0.9, width=0.5)
    fig.update_layout(height=300, showlegend=False, xaxis_title=None, yaxis_title="Tickets")
    return _apply_premium_layout(fig)

def render_workload_allocation(df: pd.DataFrame):
    if df.empty or 'agent' not in df.columns:
        return None
    counts = df['agent'].value_counts().head(10).reset_index()
    counts.columns = ['Agent', 'Tickets']
    fig = px.bar(
        counts, x='Tickets', y='Agent', orientation='h', 
        color_discrete_sequence=['#10B981'],
        template='plotly_dark'
    )
    fig.update_traces(marker_line_width=0, opacity=0.9, width=0.6)
    fig.update_layout(height=300, yaxis={'categoryorder':'total ascending'}, xaxis_title="Tickets Handled", yaxis_title=None)
    return _apply_premium_layout(fig)