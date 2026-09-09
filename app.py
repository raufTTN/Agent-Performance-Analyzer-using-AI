import os
# pyrefly: ignore [missing-import]
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

# Absolute backend orchestration system hooks import
from config import DB_PATH, OLLAMA_MODEL, DATA_DIR
from utils.db_manager import initialize_database, get_db_connection
from utils.loader import LegacyDataStagingGateway
from analytics.sla import CoreSLADiagnosticEngine
from analytics.scoring import OperationsLeaderboardScorer
from analytics.charts import render_priority_distribution, render_workload_allocation
from analytics.insights import LocalAgentCoachingEngine
from analytics.ticket_explorer import show_ai_investigator_ui
from utils.insights import AutomatedReportGenerator
from analytics.root_cause import SystemicRootCauseEngine
from analytics.capacity import AgentCapacityProfiler
from analytics.hygiene import FieldValidationAuditor

# Initialize local database schema tables setup handshake protocol immediately
initialize_database()

st.set_page_config(
    page_title="Operations Analyzer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* CSS Variables for Enterprise Theme */
    :root {
        --bg-color: #0B0E14;
        --card-bg: #151921;
        --text-primary: #F8FAFC;
        --text-secondary: #8B949E;
        --border-color: rgba(255,255,255,0.08);
        --accent-blue: #3B82F6;
        --accent-green: #10B981;
        --accent-red: #EF4444;
        --accent-yellow: #F59E0B;
        --font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    
    /* Global App Background & Typography */
    .stApp {
        background-color: var(--bg-color);
        font-family: var(--font-family);
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: var(--card-bg) !important;
        border-right: 1px solid var(--border-color);
    }
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Premium Cards */
    .premium-card {
        background-color: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        transition: transform 0.2s ease, border-color 0.2s ease;
        margin-bottom: 1rem;
    }
    .premium-card:hover {
        transform: translateY(-2px);
        border-color: rgba(255,255,255,0.2);
    }
    
    /* Fix sidebar scrolling */
    [data-testid="stSidebarUserContent"], [data-testid="stSidebarNav"] {
        overflow-y: auto !important;
        max-height: 100vh;
    }
    
    /* Fix dropdown popup menus */
    div[data-baseweb="popover"] {
        max-height: 300px;
        overflow-y: auto;
    }
    
    /* Reduce padding between sidebar elements */
    [data-testid="stSidebarUserContent"] .stSelectbox {
        margin-bottom: -15px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


def run_system_sync_sequence(csv_paths):
    for i, csv_path in enumerate(csv_paths):
        if Path(csv_path).exists():
            clear_db = (i == 0)
            LegacyDataStagingGateway.seed_database_from_csv(csv_path, clear_db=clear_db)

    CoreSLADiagnosticEngine.execute_global_sla_audit()


# --- SIDEBAR CONTROL FILTERS ---
st.sidebar.markdown(
    """
    <div style="padding: 10px 0 20px 0;">
        <h2 style="margin: 0; font-size: 18px; font-weight: 600; color: var(--text-primary);">🎛️ Operations Control</h2>
        <p style="margin: 4px 0 0 0; color: var(--text-secondary); font-size: 12px;">Global filter orchestration & sync</p>
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.markdown("<h3 style='font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: var(--text-secondary); margin-bottom: 10px; border-bottom: 1px solid var(--border-color); padding-bottom: 8px;'>Data Sources</h3>", unsafe_allow_html=True)

# Discover CSV datasets dynamically from DATA_DIR
csv_files = sorted([f.name for f in DATA_DIR.glob("*.csv")]) if DATA_DIR.exists() else []

if not csv_files:
    st.sidebar.warning("No CSV files found in the data directory.")
else:
    st.sidebar.caption(f"Found {len(csv_files)} dataset(s):")
    for f in csv_files:
        st.sidebar.markdown(f"<div style='background: rgba(255,255,255,0.03); padding: 8px 12px; border-radius: 6px; font-size: 12px; margin-bottom: 5px; border: 1px solid rgba(255,255,255,0.05);'>📄 <code>{f}</code></div>", unsafe_allow_html=True)
        
    csv_paths = [str(DATA_DIR / f) for f in csv_files]

    st.sidebar.write("")
    if st.sidebar.button("🔄 Sync All Datasets", key="sync_selected_dataset_btn", use_container_width=True):
        with st.spinner(f"Syncing {len(csv_files)} files into unified dataset..."):
            run_system_sync_sequence(csv_paths)

        st.sidebar.success("✅ Local database synchronized successfully.")
        st.rerun()

st.sidebar.write("")
st.sidebar.markdown("<h3 style='font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: var(--text-secondary); margin-top: 10px; margin-bottom: 10px; border-bottom: 1px solid var(--border-color); padding-bottom: 8px;'>Dashboard Filters</h3>", unsafe_allow_html=True)

# Read staging frame out of relational database storage
with get_db_connection() as conn:
    df_master = pd.read_sql_query("SELECT * FROM tickets", conn)

if df_master.empty:
    st.info(
        "💡 Storage engines empty. Click 'Sync Selected Dataset' in the sidebar panel to ingest your records."
    )
    st.stop()

# Ensure timestamps are parsed safely for timeline filtering
df_master["created_dt"] = pd.to_datetime(df_master["created_time"], errors="coerce")

# Generate sorting-friendly tracking keys like '2025-03' and visual names like 'March 2025'
df_master["month_year_str"] = df_master["created_dt"].dt.strftime("%B %Y")
df_master["month_sort_key"] = df_master["created_dt"].dt.to_period("M")

# --- 1. EXCLUDE AUTO-RESOLVED TICKETS NATIVELY ---
# Filtering out system automated closures to prevent skewed metrics
system_automation_identifiers = ["Auto-Resolve", "System Agent", "bot", "auto_resolver"]
df_filtered_base = df_master[
    ~df_master["agent"]
    .str.lower()
    .isin([s.lower() for s in system_automation_identifiers])
    & ~df_master["subject"]
    .str.lower()
    .str.contains("auto-resolve|auto_resolved", na=False)
].copy()

# --- 2. DROPDOWNS: DYNAMIC DATE, COMPANY & TICKET TYPE SELECTORS ---
min_date = (
    df_filtered_base["created_dt"].min().date()
    if not df_filtered_base["created_dt"].dropna().empty
    else datetime.today().date()
)
max_date = (
    df_filtered_base["created_dt"].max().date()
    if not df_filtered_base["created_dt"].dropna().empty
    else datetime.today().date()
)

selected_date_range = st.sidebar.date_input(
    "Filter View by Date Range:",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

# Company Selector
company_column = (
    "company" if "company" in df_filtered_base.columns else "status"
)  # fallback if not fully migrated
companies = ["All Companies"] + sorted(
    df_filtered_base[company_column].dropna().unique().tolist()
)
selected_company = st.sidebar.selectbox("🏢 Select Target Company Context:", companies)

# Ticket Classification Type Selector (SR vs Incident)
ticket_types = ["All Types (SR & Incident)", "Incident", "SR (Service Request)"]
selected_type = st.sidebar.selectbox("🎟️ Ticket Classification Type:", ticket_types)

agent_options = ["All Agents"] + sorted(
    df_filtered_base["agent"].dropna().unique().tolist()
)
selected_agent = st.sidebar.selectbox("Filter view context by Agent:", agent_options)

priority_options = ["All Priorities"] + sorted(
    df_filtered_base["priority"].dropna().unique().tolist()
)
selected_priority = st.sidebar.selectbox(
    "Filter view context by Severity:", priority_options
)

effort_options = ["1 min", "2 min", "3 min", "4 min", "5 min"]
selected_effort_exclusion = st.sidebar.multiselect(
    "Exclude Tickets by Effort (mins):", effort_options, default=[]
)

st.sidebar.markdown("---")
exclude_merge = st.sidebar.checkbox("🚫 Exclude Merged Tickets", value=False, help="Filters out tickets where the Issue Bucket indicates they were merged.")

# --- EXECUTE MULTI-FILTER ROUTING PARSING ---
filtered_df = df_filtered_base.copy()

# Apply Date Range filter   
if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
    start_date, end_date = selected_date_range
    filtered_df = filtered_df[
        (filtered_df["created_dt"].dt.date >= start_date)
        & (filtered_df["created_dt"].dt.date <= end_date)
    ]

# Apply Company filter
if selected_company != "All Companies":
    filtered_df = filtered_df[filtered_df[company_column] == selected_company]

# --- DYNAMIC SR vs INCIDENT ROUTING ---
if selected_type != "All Types (SR & Incident)":
    is_sr = pd.Series(False, index=filtered_df.index)

    # 1. Dynamically search ANY column that might hold Type/Category data
    for col in filtered_df.columns:
        if col.lower().strip() in ["category", "type", "ticket_type", "ticket type"]:
            is_sr = is_sr | filtered_df[col].astype(str).str.contains(
                r"(?i)(service request|\bsr\b)", na=False
            )

    # 2. Force-check the Subject line to catch automated access requests that lack a Category tag
    if "subject" in filtered_df.columns:
        sr_keywords = r"(?i)(service request|\bsr\b|grant is awaiting|approve or deny|grant access|access request)"
        is_sr = is_sr | filtered_df["subject"].astype(str).str.contains(
            sr_keywords, na=False
        )

    # 3. Final Routing Execution
    if selected_type == "SR (Service Request)":
        filtered_df = filtered_df[is_sr]
    elif selected_type == "Incident":
        filtered_df = filtered_df[~is_sr]

# Apply Merged Ticket Exclusion
if exclude_merge and "issue_bucket" in filtered_df.columns:
    filtered_df = filtered_df[~filtered_df["issue_bucket"].astype(str).str.lower().str.contains("merged", na=False)]

# Calculate utilization metrics on the team-wide data (before filtering for specific agent)
team_utilization_df = AgentCapacityProfiler.calculate_utilization(filtered_df)

# Apply Agent Filter
if selected_agent != "All Agents":
    filtered_df = filtered_df[filtered_df["agent"] == selected_agent]

# Apply Priority Filter
if selected_priority != "All Priorities":
    filtered_df = filtered_df[filtered_df["priority"] == selected_priority]

# Apply Effort Exclusion Filter
if selected_effort_exclusion:
    if "effort_mins" in filtered_df.columns:
        try:
            exclude_mins = [int(opt.split()[0]) for opt in selected_effort_exclusion]
            effort_numeric = pd.to_numeric(filtered_df["effort_mins"], errors="coerce")
            filtered_df = filtered_df[~effort_numeric.isin(exclude_mins)]
        except Exception:
            pass

# Calculate rankings out of the scoped dataset window immediately, passing the context type
rankings_df = OperationsLeaderboardScorer.compile_weighted_rankings(
    filtered_df, context_type=selected_type
)

# --- MAIN RENDER FRAME UI ---
st.markdown(
    f"""
    <div style="padding: 1rem 0 1.5rem 0; display: flex; align-items: center; gap: 15px; margin-bottom: 1.5rem;">
        <div style="background: linear-gradient(135deg, var(--accent-blue), #818cf8); padding: 12px; border-radius: 12px; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);">
            <span style="font-size: 28px; line-height: 1;">🛡️</span>
        </div>
        <div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <h1 style="margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">Enterprise SRE & IT Operations Intelligence Platform</h1>
                <span style="background: rgba(16, 185, 129, 0.1); color: var(--accent-green); padding: 4px 10px; border-radius: 100px; font-size: 11px; font-weight: 600; border: 1px solid rgba(16, 185, 129, 0.2);">LIVE</span>
            </div>
            <p style="margin: 4px 0 0 0; color: var(--text-secondary); font-size: 13px;">
                Agent Performance Analyzer Pipeline • Node: Air-Gapped Local • Model Active: <code style="background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px;">{OLLAMA_MODEL}</code>
            </p>
            <p style="margin: 4px 0 0 0; color: #38bdf8; font-size: 12px; font-weight: 600;">Developed by Team Gamma (US SRE Pod)</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# --- REFINEMENT WORKSPACE: MONTH-WISE HISTORICAL CHAMPIONS TRACKER ---
st.markdown("---")
st.subheader("📅 Chronological Month-Wise Operational Performers")

# Extract unique months present in the filtered base set sorted chronologically
available_months = df_filtered_base.dropna(subset=["month_sort_key"]).sort_values(
    by="month_sort_key"
)
month_names = ["Show Full Timeline Review"] + sorted(
    available_months["month_year_str"].unique().tolist(), reverse=True
)

selected_analysis_month = st.selectbox(
    "Select target month context to isolate historic leadership anomalies:",
    options=month_names,
)

if selected_analysis_month == "Show Full Timeline Review":
    unique_months = sorted(
        df_filtered_base["month_sort_key"].dropna().unique(), reverse=True
    )
    timeline_cols = st.columns(min(len(unique_months), 4))
    for idx, period in enumerate(unique_months):
        month_df = df_filtered_base[df_filtered_base["month_sort_key"] == period]
        month_label = period.strftime("%B %Y")
        month_rankings = OperationsLeaderboardScorer.compile_weighted_rankings(
            month_df, context_type=selected_type
        )

        col_to_use = timeline_cols[idx % min(len(unique_months), 4)]
        with col_to_use:
            st.markdown(f"##### 🗓️ {month_label}")
            if not month_rankings.empty:
                champion = month_rankings.iloc[0]
                st.success(
                    f"**{champion['agent']}**\nScore: `{champion['Performance_Score']}%`\nTickets: `{champion['Tickets_Handled']}`"
                )
            else:
                st.caption("No records mapped.")
else:
    target_month_df = df_filtered_base[
        df_filtered_base["month_year_str"] == selected_analysis_month
    ]
    month_rankings = OperationsLeaderboardScorer.compile_weighted_rankings(
        target_month_df, context_type=selected_type
    )

    mc1, mc2 = st.columns(2)
    with mc1:
        st.markdown(f"#### 🏆 Top Performer in {selected_analysis_month}")
        if not month_rankings.empty:
            champ = month_rankings.iloc[0]
            st.success(
                f"**{champ['agent']}** was the top operational performer in **{selected_analysis_month}**, securing a matrix rating score of **{champ['Performance_Score']}%** while handling **{champ['Tickets_Handled']}** tickets."
            )
        else:
            st.caption("No metrics calculated for this period segment.")
    with mc2:
        st.markdown(f"#### ⚡ Fastest Resolver in {selected_analysis_month}")
        if not month_rankings.empty:
            fastest_m = month_rankings.sort_values(
                by="Avg_Resolution_Hours", ascending=True
            ).iloc[0]
            st.info(
                f"**{fastest_m['agent']}** led target triage speed in **{selected_analysis_month}** with a response time averaging **{fastest_m['Avg_Resolution_Hours']} Hours** per issue."
            )
        else:
            st.caption("No metrics calculated for this period segment.")

# Section 1: Scoped Insights & Accolades Highlight Panel (Global filtered context)
st.markdown("---")
h1, h2 = st.columns(2)

with h1:
    if not rankings_df.empty:
        top_agent = rankings_df.iloc[0]
        st.markdown(f"""
        <div class="premium-card">
            <h4 style="margin: 0 0 10px 0; color: var(--text-secondary); font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">🏆 Scoped Team Top Performer</h4>
            <h2 style="margin: 0; font-size: 24px; color: var(--text-primary);">{top_agent['agent']}</h2>
            <div style="display: flex; gap: 15px; margin-top: 15px;">
                <div>
                    <span style="display: block; font-size: 11px; color: var(--text-secondary);">Efficiency Score</span>
                    <span style="font-size: 16px; font-weight: 600; color: var(--accent-green);">{top_agent['Performance_Score']}%</span>
                </div>
                <div>
                    <span style="display: block; font-size: 11px; color: var(--text-secondary);">Tickets Handled</span>
                    <span style="font-size: 16px; font-weight: 600; color: var(--text-primary);">{top_agent['Tickets_Handled']}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.caption("Insufficient performance scoring records to establish metrics leadership bounds.")

with h2:
    if not rankings_df.empty:
        valid_resolvers = rankings_df[rankings_df["Tickets_Handled"] >= 5]
        if valid_resolvers.empty:
            valid_resolvers = rankings_df
        fastest_agent = valid_resolvers.sort_values(
            by="Avg_Resolution_Hours", ascending=True
        ).iloc[0]
        st.markdown(f"""
        <div class="premium-card">
            <h4 style="margin: 0 0 10px 0; color: var(--text-secondary); font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">⚡ Scoped Fastest Ticket Resolver</h4>
            <h2 style="margin: 0; font-size: 24px; color: var(--text-primary);">{fastest_agent['agent']}</h2>
            <div style="display: flex; gap: 15px; margin-top: 15px;">
                <div>
                    <span style="display: block; font-size: 11px; color: var(--text-secondary);">Avg. Resolution</span>
                    <span style="font-size: 16px; font-weight: 600; color: var(--accent-blue);">{fastest_agent['Avg_Resolution_Hours']} Hrs / Ticket</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.caption(
            "Insufficient execution duration footprints mapped to extract speed parameters."
        )

# Section 2: Executive KPI Cards Grid
st.markdown("---")
st.subheader("📊 Agent Capacity & Utilization Profile")
sla_metrics = CoreSLADiagnosticEngine.fetch_sla_summary(filtered_df)

if "effort_mins" in filtered_df.columns:
    filtered_df["effort_hours"] = pd.to_numeric(filtered_df["effort_mins"], errors="coerce").fillna(0) / 60.0
else:
    filtered_df["effort_hours"] = 0.0

total_effort_hrs = filtered_df["effort_hours"].sum()

if "created_dt" in filtered_df.columns:
    valid_dates = filtered_df.dropna(subset=["created_dt"])
    weeks_count = valid_dates["created_dt"].dt.to_period("W").nunique() if not valid_dates.empty else 1
    months_count = valid_dates["created_dt"].dt.to_period("M").nunique() if not valid_dates.empty else 1
else:
    weeks_count = 1
    months_count = 1

weekly_effort_rate = total_effort_hrs / weeks_count if weeks_count > 0 else 0
monthly_effort_capacity = total_effort_hrs / months_count if months_count > 0 else 0
avg_effort_mins = pd.to_numeric(filtered_df["effort_mins"], errors="coerce").mean() if "effort_mins" in filtered_df.columns else 0

def render_kpi_card(title, value, accent_color, subtitle=""):
    return f"""
    <div class="premium-card" style="padding: 16px;">
        <h4 style="margin: 0 0 8px 0; color: var(--text-secondary); font-size: 12px; font-weight: 500;">{title}</h4>
        <h2 style="margin: 0; font-size: 28px; font-weight: 600; color: var(--text-primary);">{value}</h2>
        <span style="font-size: 12px; color: {accent_color}; font-weight: 500;">{subtitle}</span>
    </div>
    """

st.write("")
c1, c2, c3 = st.columns(3)
with c1: st.markdown(render_kpi_card("Total Tickets", f"{len(filtered_df):,}", "var(--text-secondary)", ""), unsafe_allow_html=True)
with c2: st.markdown(render_kpi_card("SLA Compliance Rate Percentage", f"{sla_metrics['compliance_pct']}%", "var(--accent-green)", ""), unsafe_allow_html=True)
with c3: st.markdown(render_kpi_card("Total SLA Resolution Breaches", f"{sla_metrics['breach_count']}", "var(--accent-red)", "Failed"), unsafe_allow_html=True)

st.write("")
c4, c5, c6, c7 = st.columns(4)
with c4: st.markdown(render_kpi_card("Pod Total Effort (US SRE)", f"{total_effort_hrs:.1f} Hrs", "var(--text-secondary)", ""), unsafe_allow_html=True)
with c5: st.markdown(render_kpi_card("Weekly Effort Rate", f"{weekly_effort_rate:.1f} Hrs/Wk", "var(--text-secondary)", ""), unsafe_allow_html=True)
with c6: st.markdown(render_kpi_card("Monthly Effort Capacity", f"{monthly_effort_capacity:.1f} Hrs/Mo", "var(--text-secondary)", ""), unsafe_allow_html=True)
with c7: st.markdown(render_kpi_card("Avg Effort Per Ticket", f"{avg_effort_mins:.1f} Mins", "var(--text-secondary)", ""), unsafe_allow_html=True)





# Section 3: Individual Engineer Time Utilization (US SRE Pod)
st.markdown("---")
st.subheader("⏱️ Individual Engineer Time Utilization (US SRE Pod)")
st.caption("Calculates individual engineer workload in hours: Total Time, Weekly Rate (Hrs/Wk), Monthly Capacity (Hrs/Mo), and Project Allocations. Includes dynamic expected hours based on ticket shift timings.")

pod_util_df = AutomatedReportGenerator.calculate_individual_pod_utilization(filtered_df)

if not pod_util_df.empty:
    display_util = pod_util_df.rename(columns={
        "agent": "SRE Engineer",
        "primary_shift": "Primary Shift",
        "total_tickets": "Tickets Handled",
        "total_effort_hrs": "Total Effort (Hours)",
        "expected_weekly": "Expected Capacity (Hrs/Wk)",
        "weekly_hrs": "Actual Rate (Hrs/Wk)",
        "utilization_pct": "Utilization (%)",
        "monthly_hrs": "Monthly Rate (Hrs/Mo)",
        "pod_share_pct": "Pod Workload Share (%)",
        "top_projects": "Project / Account Allocations (Hours)"
    })
    
    def highlight_utilization(val):
        try:
            v = float(str(val).replace('%', ''))
            if v > 95: return 'color: #ef4444; font-weight: bold'
            if v < 60: return 'color: #f59e0b; font-weight: bold'
            return 'color: #10b981; font-weight: bold'
        except:
            return ''

    styled_util = display_util.style.map(highlight_utilization, subset=['Utilization (%)'])
    st.dataframe(styled_util, use_container_width=True, hide_index=True)
else:
    st.caption("No individual pod utilization records available in current scope.")


# Section 4: SLA Compliance Target Ticket Data Grid
st.markdown("---")
st.subheader("📋 SLA Inception Status Tracking Tables")

columns_to_show = [
    "ticket_id",
    "subject",
    "ticket_type",
    "agent",
    "priority",
    "resolution_hours",
    "status",
]
rename_map = {
    "ticket_id": "Ticket ID",
    "ticket_type": "Ticket Type",
    "subject": "Case Subject",
    "agent": "Assigned SRE",
    "priority": "Severity Level",
    "resolution_hours": "Resolution Duration (Hrs)",
    "status": "State Status",
}

# Ensure all target display columns exist before filtering dataframe
available_columns = [col for col in columns_to_show if col in filtered_df.columns]

breached_records = filtered_df[filtered_df["sla_breached"] == 1][
    available_columns
].rename(columns=rename_map)
compliant_records = filtered_df[filtered_df["sla_breached"] == 0][
    available_columns
].rename(columns=rename_map)

def style_severity(val):
    val_str = str(val).lower()
    if any(x in val_str for x in ['urgent', 'high', 'p0', 'p1']): return 'color: #ef4444; font-weight: 600;'
    if any(x in val_str for x in ['medium', 'p2']): return 'color: #f59e0b; font-weight: 600;'
    return 'color: #10b981; font-weight: 600;'

def style_state(val):
    val_str = str(val).lower()
    if any(x in val_str for x in ['closed', 'resolved']): return 'color: #10b981; font-weight: 600;'
    return 'color: #3b82f6; font-weight: 600;'

tab_compliant, tab_breached = st.tabs(
    ["🟢 Within SLA (Compliant)", "🔴 Breached SLA (Failed Target)"]
)

with tab_compliant:
    st.markdown(
        f"**Showing {len(compliant_records):,} tickets keeping within strict SRE milestone parameters:**"
    )
    if not compliant_records.empty:
        styled_comp = compliant_records.style.map(style_severity, subset=['Severity Level']).map(style_state, subset=['State Status'])
        st.dataframe(styled_comp, use_container_width=True, hide_index=True)
    else:
        st.caption("No compliant records encountered in current scope parameters.")

with tab_breached:
    st.markdown(
        f"**Showing {len(breached_records):,} high-exposure tickets breaking corporate delivery timelines:**"
    )
    if not breached_records.empty:
        styled_breach = breached_records.style.map(style_severity, subset=['Severity Level']).map(style_state, subset=['State Status'])
        st.dataframe(styled_breach, use_container_width=True, hide_index=True)
    else:
        st.info(
            "🎉 Operational excellence confirmed! Zero SLA resolution breaches mapped under current view filters."
        )


# Section 4: Systemic Root Cause & Security Compliance Diagnostics
st.markdown("---")
st.subheader("🛡️ Infrastructure Noise & Top 5 Systemic Alerts")
st.caption("Scans high-volume repeating noise clusters to construct air-gapped security playbooks and engineering efficiency strategies.")

if st.button("🔮 Analyze Infrastructure Noise Clusters & Security Exposure", key="root_cause_btn"):
    with st.spinner(
        "Extracting pattern matrices and driving local inference weights..."
    ):
        rc_engine = SystemicRootCauseEngine()
        strategic_review = rc_engine.cluster_and_analyze_patterns(filtered_df)
        
        if isinstance(strategic_review, dict):
            if "error" in strategic_review:
                st.warning(strategic_review["error"])
            else:
                st.markdown("#### 🚨 Top 5 Noisy Alerts")
                alerts_df = pd.DataFrame(strategic_review["top_alerts"])
                alerts_df = alerts_df.rename(columns={
                    "Target Company Context": "Company Name",
                    "Total Occurrence Count": "Frequency Count"
                })
                
                # Apply subtle styling to the Top 5 alerts table
                def highlight_high_frequency(val):
                    try:
                        if int(val) > 10: return 'color: #f59e0b; font-weight: bold'
                        return 'color: #3b82f6;'
                    except: return ''
                
                styled_alerts = alerts_df.style.map(highlight_high_frequency, subset=['Frequency Count'])
                st.dataframe(styled_alerts, use_container_width=True, hide_index=True)
                
                st.markdown("#### 🧠 AI Security & Efficiency Impact Summary")
                
                raw_insights = strategic_review["insights"]
                # Visually style the prompt-requested bracketed sections without changing the text
                styled_insights = raw_insights.replace(
                    "[EFFICIENCY BOTTLENECK ANALYSIS]", 
                    "<h4 style='color: var(--accent-yellow); margin-top: 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;'>⚙️ EFFICIENCY BOTTLENECK ANALYSIS</h4>"
                ).replace(
                    "[SECURITY POSTURE ASSESSMENT]", 
                    "<h4 style='color: var(--accent-red); margin-top: 24px; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;'>🛡️ SECURITY POSTURE ASSESSMENT</h4>"
                ).replace(
                    "[AUTOMATION PLAYBOOK RECOMMENDATIONS]", 
                    "<h4 style='color: var(--accent-green); margin-top: 24px; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;'>✅ AUTOMATION PLAYBOOK RECOMMENDATIONS</h4>"
                )
                
                st.markdown(f"""
                <div class="premium-card" style="border-top: 4px solid var(--accent-blue);">
                    <div style="color: var(--text-primary); font-size: 14px; line-height: 1.6;">
                        {styled_insights}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info(strategic_review)


# Section 5: Interactive Plotly Chart Columns Block
st.markdown("---")
st.subheader("📈 Workflow Diagnostics & Workload Aggregations")
g1, g2 = st.columns(2)

with g1:
    fig_p = render_priority_distribution(filtered_df)
    if fig_p is not None:
        st.plotly_chart(fig_p, width=600)
    else:
        st.caption("No diagnostic priority layouts mapped.")

with g2:
    fig_w = render_workload_allocation(filtered_df)
    if fig_w is not None:
        st.plotly_chart(fig_w, width=600)
    else:
        st.caption("No workload allocation metrics mapped.")


# Section 6: Engineering Scorecard Performance Leaderboard
st.markdown("---")
st.subheader("🏆 Performance Score Leaderboard System Matrix")
if not rankings_df.empty:
    st.dataframe(rankings_df, width=1200, hide_index=True)
else:
    st.caption(
        "Insufficient active records available to calculate team metrics ranking values."
    )

# Section 7: Freshservice Field Validation & Form Hygiene Hub
st.markdown("---")
st.subheader("📋 Freshservice Field Validation & Form Hygiene Hub")
st.caption("Audits mandatory field completeness (Group, Priority, Company, Category, Type) and sub-category hygiene across tickets and engineers.")

# Generate DataFrames
agent_scorecard = FieldValidationAuditor.generate_agent_scorecard(filtered_df)
flagged_tickets, compliant_tickets = FieldValidationAuditor.generate_ticket_inspector(filtered_df)

tab_agent, tab_ticket = st.tabs([
    "👤 Agent-Wise Field Hygiene Scorecard",
    "🎟️ Ticket-Wise Field Validation Inspector"
])

with tab_agent:
    if not agent_scorecard.empty:
        st.dataframe(agent_scorecard, use_container_width=True, hide_index=True)
    else:
        st.caption("No agent form hygiene records to display.")

with tab_ticket:
    sub_flagged, sub_compliant = st.tabs([
        f"🚨 Flagged / Missing Fields ({len(flagged_tickets)})",
        f"✅ 100% Compliant Tickets ({len(compliant_tickets):,})"
    ])
    
    with sub_flagged:
        if not flagged_tickets.empty:
            st.dataframe(flagged_tickets, use_container_width=True, hide_index=True)
        else:
            st.success("All tickets are 100% compliant!")
            
    with sub_compliant:
        if not compliant_tickets.empty:
            st.dataframe(compliant_tickets, use_container_width=True, hide_index=True)
        else:
            st.caption("No perfectly compliant tickets found.")

# Section 8: Local AI Agent Career Coaching Workshop
st.markdown("---")
st.subheader("🧠 Air-Gapped Local AI Agent Career Coaching Workshop")
coach_target = st.selectbox(
    "Select Target Engineer for Review Profile Assessment:",
    sorted(df_filtered_base["agent"].dropna().unique().tolist()),
)

if st.button("🔮 Construct AI Coaching Assessment Profile", key="coaching_btn"):
    with st.spinner(
        "Processing historical ticket logs inside local LLM context window..."
    ):
        coach = LocalAgentCoachingEngine()
        agent_set = df_filtered_base[df_filtered_base["agent"] == coach_target].to_dict(
            "records"
        )
        st.info(coach.build_agent_coaching_matrix(coach_target, agent_set))

# Section 8: Deep Forensic Ticket Investigation Module Injection Anchor
show_ai_investigator_ui(filtered_df)

# Section 9: Automated Operations Executive Review Compiler (Dual Export: HTML & PDF)
st.markdown("---")
st.subheader("📋 Automated Operations Executive Review Compiler")
st.caption("Generate and download standardized executive performance reports in HTML or PDF formats.")

col_comp1, col_comp2 = st.columns(2)
with col_comp1:
    if st.button("🌐 Compile Executive HTML Report", key="compile_html_btn", use_container_width=True):
        html_path = AutomatedReportGenerator.compile_executive_html(filtered_df, selected_agent, team_utilization_df)
        if html_path and os.path.exists(html_path):
            st.session_state["generated_html_path"] = html_path
            st.success(f"HTML review generated: `{html_path}`")
        else:
            st.error("HTML Report compilation failed or returned empty scope.")

with col_comp1:
    if "generated_html_path" in st.session_state and os.path.exists(st.session_state["generated_html_path"]):
        with open(st.session_state["generated_html_path"], "r", encoding="utf-8") as f:
            html_data = f.read()
        st.download_button(
            label="💾 Download Compiled Executive HTML Report",
            data=html_data,
            file_name=os.path.basename(st.session_state["generated_html_path"]),
            mime="text/html",
            key="dl_html_btn",
            use_container_width=True
        )

if st.button("📥 Generate Rich Executive Reports"):
    with st.spinner("Analyzing operational footprints and generating AI remarks..."):
        report_data = AutomatedReportGenerator.generate_rich_executive_report(filtered_df, selected_agent, team_utilization_df)
        st.session_state["executive_report_data"] = report_data

with col_comp2:
    if st.button("📄 Compile Executive PDF Report", key="compile_pdf_btn", use_container_width=True):
        # Auto-compile HTML base if it doesn't exist yet in current session
        if "generated_html_path" not in st.session_state or not os.path.exists(st.session_state["generated_html_path"]):
            st.session_state["generated_html_path"] = AutomatedReportGenerator.compile_executive_html(filtered_df, selected_agent, team_utilization_df)

        with st.spinner("Converting HTML document to PDF format..."):
            pdf_path = AutomatedReportGenerator.compile_executive_pdf(st.session_state["generated_html_path"])
            if pdf_path and os.path.exists(pdf_path):
                st.session_state["generated_pdf_path"] = pdf_path
                st.success(f"PDF review generated: `{pdf_path}`")
            else:
                st.error("Failed to compile PDF. Please verify 'wkhtmltopdf' is installed on your Linux system (`sudo apt install wkhtmltopdf`).")

    if "generated_pdf_path" in st.session_state and os.path.exists(st.session_state["generated_pdf_path"]):
        with open(st.session_state["generated_pdf_path"], "rb") as f:
            pdf_bytes = f.read()
        st.download_button(
            label="💾 Download Compiled Executive PDF Report",
            data=pdf_bytes,
            file_name=os.path.basename(st.session_state["generated_pdf_path"]),
            mime="application/pdf",
            key="dl_pdf_btn",
            use_container_width=True
        )
