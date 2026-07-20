import os
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

# Absolute backend orchestration system hooks import
# from config import DB_PATH, CSV_PATH, OLLAMA_MODEL, DATA_DIR
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

# Initialize local database schema tables setup handshake protocol immediately
initialize_database()

st.set_page_config(
    page_title="Operations Analyzer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def run_system_sync_sequence(csv_path):
    if Path(csv_path).exists():
        LegacyDataStagingGateway.seed_database_from_csv(csv_path)

    CoreSLADiagnosticEngine.execute_global_sla_audit()


# --- SIDEBAR CONTROL FILTERS ---
st.sidebar.header("🎛️ Operations Control Panel")

# List all CSV files in the data directory
csv_files = sorted([f.name for f in DATA_DIR.glob("*.csv")])

if not csv_files:
    st.sidebar.warning("No CSV files found in the data directory.")
else:
    selected_csv = st.sidebar.selectbox("📂 Select CSV Dataset", csv_files)

    selected_csv_path = DATA_DIR / selected_csv

    st.sidebar.caption(f"Selected Dataset: **{selected_csv}**")

    if st.sidebar.button("🔄 Sync Selected Dataset"):
        with st.spinner(f"Syncing {selected_csv}..."):
            run_system_sync_sequence(str(selected_csv_path))

        st.sidebar.success("✅ Local database synchronized successfully.")
        st.rerun()
# Read staging frame out of relational database storage
with get_db_connection() as conn:
    df_master = pd.read_sql_query("SELECT * FROM tickets", conn)

if df_master.empty:
    st.info(
        "💡 Storage engines empty. Click 'Sync Local Data Layer Pipeline' in the sidebar panel to ingest your records out of data/tickets.csv."
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

# --- 2. NEW DROPDOWNS: DYNAMIC DATE, COMPANY & TICKET TYPE SELECTORS ---
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

# --- 🚀 DYNAMIC, FAIL-PROOF SR vs INCIDENT ROUTING ---
if selected_type != "All Types (SR & Incident)":
    is_sr = pd.Series(False, index=filtered_df.index)

    # 1. Dynamically search ANY column that might hold Type/Category data (ignores case/spelling mismatch)
    for col in filtered_df.columns:
        if col.lower().strip() in ["category", "type", "ticket_type", "ticket type"]:
            is_sr = is_sr | filtered_df[col].astype(str).str.contains(
                r"(?i)(service request|\bsr\b)", na=False
            )

    # 2. Force-check the Subject line to catch automated access requests that lack a Category tag
    if "subject" in filtered_df.columns:
        # Matches typical SR subjects like the ones in your screenshot
        sr_keywords = r"(?i)(service request|\bsr\b|grant is awaiting|approve or deny|grant access|access request)"
        is_sr = is_sr | filtered_df["subject"].astype(str).str.contains(
            sr_keywords, na=False
        )

    # 3. Final Routing Execution
    if selected_type == "SR (Service Request)":
        filtered_df = filtered_df[is_sr]
    elif selected_type == "Incident":
        filtered_df = filtered_df[~is_sr]

# Apply Agent Filter
if selected_agent != "All Agents":
    filtered_df = filtered_df[filtered_df["agent"] == selected_agent]

# Apply Priority Filter
if selected_priority != "All Priorities":
    filtered_df = filtered_df[filtered_df["priority"] == selected_priority]

# Calculate rankings out of the scoped dataset window immediately, passing the context type
rankings_df = OperationsLeaderboardScorer.compile_weighted_rankings(
    filtered_df, context_type=selected_type
)

# --- MAIN RENDER FRAME UI ---
st.title("🛡️ Enterprise SRE & IT Operations Intelligence Platform")
st.caption(
    f"Agent Performance Analyzer Module Pipeline | Node: Air-Gapped Local | Model Active: `{OLLAMA_MODEL}`"
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
    st.markdown("### 🏆 Scoped Team Top Performer")
    if not rankings_df.empty:
        top_agent = rankings_df.iloc[0]
        st.success(
            f"**{top_agent['agent']}** leading the active view bounds with an efficiency score of **{top_agent['Performance_Score']}%** across **{top_agent['Tickets_Handled']}** cases."
        )
    else:
        st.caption(
            "Insufficient performance scoring records to establish metrics leadership bounds."
        )

with h2:
    st.markdown("### ⚡ Scoped Fastest Ticket Resolver")
    if not rankings_df.empty:
        valid_resolvers = rankings_df[rankings_df["Tickets_Handled"] >= 5]
        if valid_resolvers.empty:
            valid_resolvers = rankings_df
        fastest_agent = valid_resolvers.sort_values(
            by="Avg_Resolution_Hours", ascending=True
        ).iloc[0]
        st.info(
            f"**{fastest_agent['agent']}** leading response operations with a handling speed averaging **{fastest_agent['Avg_Resolution_Hours']} Hours** per ticket."
        )
    else:
        st.caption(
            "Insufficient execution duration footprints mapped to extract speed parameters."
        )

# Section 2: Executive KPI Cards Grid
st.markdown("---")
sla_metrics = CoreSLADiagnosticEngine.fetch_sla_summary(filtered_df)
avg_effort = (
    filtered_df["effort_mins"].mean() if "effort_mins" in filtered_df.columns else 0
)
avg_res_hours = (
    filtered_df["resolution_hours"].mean()
    if "resolution_hours" in filtered_df.columns
    else 0
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Incident Cases Scope", f"{len(filtered_df):,}")
c2.metric("SLA Compliance Rate Percentage", f"{sla_metrics['compliance_pct']}%")
c3.metric(
    "Total SLA Resolution Breaches",
    f"{sla_metrics['breach_count']} Failed",
    delta_color="inverse",
)
c4.metric("Avg Resolution Duration", f"{avg_res_hours:.1f} Hours")


# Section 3: SLA Compliance Target Ticket Data Grid
st.markdown("---")
st.subheader("📋 SLA Inception Status Tracking Tables")

columns_to_show = [
    "ticket_id",
    "subject",
    "agent",
    "priority",
    "resolution_hours",
    "status",
]
rename_map = {
    "ticket_id": "Ticket ID",
    "subject": "Case Subject",
    "agent": "Assigned SRE",
    "priority": "Severity Level",
    "resolution_hours": "Resolution Duration (Hrs)",
    "status": "State Status",
}

breached_records = filtered_df[filtered_df["sla_breached"] == 1][
    columns_to_show
].rename(columns=rename_map)
compliant_records = filtered_df[filtered_df["sla_breached"] == 0][
    columns_to_show
].rename(columns=rename_map)

tab_compliant, tab_breached = st.tabs(
    ["🟢 Within SLA (Compliant)", "🔴 Breached SLA (Failed Target)"]
)

with tab_compliant:
    st.markdown(
        f"**Showing {len(compliant_records):,} tickets keeping within strict SRE milestone parameters:**"
    )
    if not compliant_records.empty:
        st.dataframe(compliant_records, width=1200, hide_index=True)
    else:
        st.caption("No compliant records encountered in current scope parameters.")

with tab_breached:
    st.markdown(
        f"**Showing {len(breached_records):,} high-exposure tickets breaking corporate delivery timelines:**"
    )
    if not breached_records.empty:
        st.dataframe(breached_records, width=1200, hide_index=True)
    else:
        st.info(
            "🎉 Operational excellence confirmed! Zero SLA resolution breaches mapped under current view filters."
        )


# Section 4: Systemic Root Cause & Security Compliance Diagnostics
st.markdown("---")
st.subheader("🛡️ Systemic Infrastructure Root Cause & Security Compliance Diagnostics")
st.caption(
    "Scans high-volume repeating noise clusters to construct air-gapped security playbooks and engineering efficiency strategies."
)

if st.button("🔮 Analyze Infrastructure Noise Clusters & Security Exposure"):
    with st.spinner(
        "Extracting pattern matrices and driving local inference weights..."
    ):
        rc_engine = SystemicRootCauseEngine()
        strategic_review = rc_engine.cluster_and_analyze_patterns(filtered_df)
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

# Section 7: Local AI Agent Career Coaching Workshop
st.markdown("---")
st.subheader("🧠 Air-Gapped Local AI Agent Career Coaching Workshop")
coach_target = st.selectbox(
    "Select Target Engineer for Review Profile Assessment:",
    sorted(df_filtered_base["agent"].dropna().unique().tolist()),
)

if st.button("🔮 Construct AI Coaching Assessment Profile"):
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

# Section 9: Automated Report Generation Block
st.markdown("---")
st.subheader("📋 Automated Operations Executive Review Compiler")
if st.button("📥 Compile Standalone Executive HTML Operations Review File"):
    compiled_path = AutomatedReportGenerator.compile_executive_html(filtered_df)
    st.success(f"HTML executive review file saved successfully to: `{compiled_path}`")
