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
st.sidebar.header("🎛️ Operations Control Panel")

# Discover CSV datasets dynamically from DATA_DIR
csv_files = sorted([f.name for f in DATA_DIR.glob("*.csv")]) if DATA_DIR.exists() else []

if not csv_files:
    st.sidebar.warning("No CSV files found in the data directory.")
else:
    st.sidebar.caption(f"Found {len(csv_files)} dataset(s):")
    for f in csv_files:
        st.sidebar.text(f"📄 {f}")
        
    csv_paths = [str(DATA_DIR / f) for f in csv_files]

    if st.sidebar.button("🔄 Sync All Datasets", key="sync_selected_dataset_btn"):
        with st.spinner(f"Syncing {len(csv_files)} files into unified dataset..."):
            run_system_sync_sequence(csv_paths)

        st.sidebar.success("✅ Local database synchronized successfully.")
        st.rerun()

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
st.title("🛡️ Enterprise SRE & IT Operations Intelligence Platform")
st.markdown("<small style='color: #38bdf8; font-weight: 600;'>Developed by Team Gamma (US SRE Pod)</small>", unsafe_allow_html=True)
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

st.write("")
c1, c2, c3 = st.columns(3)
c1.metric("Total Tickets", f"{len(filtered_df):,}")
c2.metric("SLA Compliance Rate Percentage", f"{sla_metrics['compliance_pct']}%")
c3.metric(
    "Total SLA Resolution Breaches",
    f"{sla_metrics['breach_count']} Failed",
    delta_color="inverse",
)

st.write("")
st.write("")
c4, c5, c6, c7 = st.columns(4)
c4.metric("Pod Total Effort (US SRE)", f"{total_effort_hrs:.1f} Hrs")
c5.metric("Weekly Effort Rate", f"{weekly_effort_rate:.1f} Hrs/Wk")
c6.metric("Monthly Effort Capacity", f"{monthly_effort_capacity:.1f} Hrs/Mo")
c7.metric("Avg Effort Per Ticket", f"{avg_effort_mins:.1f} Mins")





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
    st.dataframe(display_util, use_container_width=True, hide_index=True)
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
                st.dataframe(alerts_df, use_container_width=True, hide_index=True)
                
                st.markdown("#### 🧠 AI Security & Efficiency Impact Summary")
                with st.expander("View Strategic Insights", expanded=True):
                    st.info(strategic_review["insights"])
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

# Section 7: Local AI Agent Career Coaching Workshop
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
