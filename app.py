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
from analytics.validator import FreshserviceFieldValidator

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


def run_system_sync_sequence(csv_path):
    if Path(csv_path).exists():
        LegacyDataStagingGateway.seed_database_from_csv(csv_path)

    CoreSLADiagnosticEngine.execute_global_sla_audit()


# --- SIDEBAR CONTROL FILTERS ---
st.sidebar.header("🎛️ Operations Control Panel")

# Discover CSV datasets dynamically from DATA_DIR
csv_files = sorted([f.name for f in DATA_DIR.glob("*.csv")]) if DATA_DIR.exists() else []

if not csv_files:
    st.sidebar.warning("No CSV files found in the data directory.")
    selected_csv_path = None
else:
    # Set default selection index to 'tickets.csv' if present
    default_idx = 0
    if "tickets.csv" in csv_files:
        default_idx = csv_files.index("tickets.csv")

    selected_csv = st.sidebar.selectbox("📂 Select CSV Dataset", csv_files, index=default_idx)
    selected_csv_path = DATA_DIR / selected_csv
    st.session_state["selected_csv"] = str(selected_csv_path)

    st.sidebar.caption(f"Selected Dataset: **{selected_csv}**")

    if st.sidebar.button("🔄 Sync Selected Dataset", key="sync_selected_dataset_btn"):
        with st.spinner(f"Syncing {selected_csv}..."):
            run_system_sync_sequence(str(selected_csv_path))

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
)
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

    for col in filtered_df.columns:
        if col.lower().strip() in ["category", "type", "ticket_type", "ticket type"]:
            is_sr = is_sr | filtered_df[col].astype(str).str.contains(
                r"(?i)(service request|\bsr\b)", na=False
            )

    if "subject" in filtered_df.columns:
        sr_keywords = r"(?i)(service request|\bsr\b|grant is awaiting|approve or deny|grant access|access request)"
        is_sr = is_sr | filtered_df["subject"].astype(str).str.contains(
            sr_keywords, na=False
        )

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

# --- SECTION: MONTH-WISE HISTORICAL CHAMPIONS TRACKER ---
st.markdown("---")
st.subheader("📅 Chronological Month-Wise Operational Performers")

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

# Section 1: Scoped Insights & Accolades Highlight Panel
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
        # Filter for valid non-zero resolution times (> 0.05 hrs / 3 mins) to avoid 0.0 artifacts
        valid_resolvers = rankings_df[
            (rankings_df["Tickets_Handled"] >= 3) & 
            (rankings_df["Avg_Resolution_Hours"] > 0.05)
        ]
        if valid_resolvers.empty:
            valid_resolvers = rankings_df[rankings_df["Avg_Resolution_Hours"] > 0]
        if valid_resolvers.empty:
            valid_resolvers = rankings_df

        fastest_agent = valid_resolvers.sort_values(
            by="Avg_Resolution_Hours", ascending=True
        ).iloc[0]
        
        fast_hrs = float(fastest_agent['Avg_Resolution_Hours'])
        fast_mins = int(fast_hrs * 60)
        speed_display = f"{fast_hrs:.2f} Hours ({fast_mins} Mins)" if fast_hrs < 1.0 else f"{fast_hrs:.1f} Hours"

        st.info(
            f"**{fastest_agent['agent']}** leading response operations with a handling speed averaging **{speed_display}** per ticket."
        )
    else:
        st.caption(
            "Insufficient execution duration footprints mapped to extract speed parameters."
        )

# Section 2: Executive KPI & Pod Time Utilization Cards Grid
st.markdown("---")
sla_metrics = CoreSLADiagnosticEngine.fetch_sla_summary(filtered_df)

total_effort_hrs = round((filtered_df["effort_mins"].sum() / 60.0), 1) if "effort_mins" in filtered_df.columns else 0.0

if "created_dt" in filtered_df.columns and not filtered_df["created_dt"].dropna().empty:
    weeks_count = filtered_df["created_dt"].dt.to_period("W").nunique() or 1
    months_count = filtered_df["created_dt"].dt.to_period("M").nunique() or 1
    weekly_effort_hrs = round(total_effort_hrs / weeks_count, 1)
    monthly_effort_hrs = round(total_effort_hrs / months_count, 1)
else:
    weekly_effort_hrs = 0.0
    monthly_effort_hrs = 0.0

if selected_type == "All Types (SR & Incident)":
    avg_res_hours = None
else:
    avg_res_hours = filtered_df["resolution_hours"].mean() if "resolution_hours" in filtered_df.columns else None

# Row 1: Executive Volumes
c1, c2, c3 = st.columns(3)
c1.metric("Total Tickets", f"{len(filtered_df):,}")
c2.metric("SLA Compliance Rate Percentage", f"{sla_metrics['compliance_pct']}%")
c3.metric(
    "Total SLA Resolution Breaches",
    f"{sla_metrics['breach_count']} Failed",
    delta_color="inverse",
)

# Row 2: Pod Time Utilization
u1, u2, u3, u4 = st.columns(4)
u1.metric("Pod Total Effort (US SRE)", f"{total_effort_hrs} Hrs")
u2.metric("Weekly Effort Rate", f"{weekly_effort_hrs} Hrs/Wk")
u3.metric("Monthly Effort Capacity", f"{monthly_effort_hrs} Hrs/Mo")
if avg_res_hours is not None and not pd.isna(avg_res_hours):
    u4.metric("Avg Resolution Duration", f"{avg_res_hours:.1f} Hours")
else:
    u4.metric("Avg Effort Per Ticket", f"{round(filtered_df['effort_mins'].mean(), 0) if 'effort_mins' in filtered_df.columns else 0} Mins")


# Section 3: Individual Engineer Time Utilization (US SRE Pod)
st.markdown("---")
st.subheader("⏱️ Individual Engineer Time Utilization (US SRE Pod)")
st.caption("Calculates individual engineer workload in hours: Total Time, Weekly Rate (Hrs/Wk), Monthly Capacity (Hrs/Mo), and Project Allocations.")

pod_util_df = AutomatedReportGenerator.calculate_individual_pod_utilization(filtered_df)

if not pod_util_df.empty:
    display_util = pod_util_df.rename(columns={
        "agent": "SRE Engineer",
        "total_tickets": "Tickets Handled",
        "total_effort_hrs": "Total Effort (Hours)",
        "weekly_hrs": "Weekly Rate (Hrs/Wk)",
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


# Section 5: Freshservice Field Validation & Form Hygiene Hub
st.markdown("---")
st.subheader("📋 Freshservice Field Validation & Form Hygiene Hub")
st.caption("Audits mandatory field completeness (Group, Priority, Status, Company, Category, Type) across tickets and engineers.")

audited_df = FreshserviceFieldValidator.batch_audit_dataframe(filtered_df)

tab_agent_hygiene, tab_ticket_hygiene = st.tabs([
    "👤 Agent-Wise Field Hygiene Scorecard",
    "🎟️ Ticket-Wise Field Validation Inspector"
])

# 1. Agent-Wise Hygiene Scorecard Tab
with tab_agent_hygiene:
    agent_hygiene_df = FreshserviceFieldValidator.generate_agent_scorecard(audited_df)
    if not agent_hygiene_df.empty:
        display_agent_hygiene = agent_hygiene_df.rename(columns={
            "agent": "Assigned SRE / Agent",
            "Total_Tickets": "Total Tickets Handled",
            "Compliant_Forms": "100% Perfect Forms",
            "Missing_Field_Tickets": "Tickets With Missing Fields",
            "Compliance_Rate": "Form Compliance Rate (%)",
            "Avg_Form_Quality_Score": "Average Hygiene Score (%)"
        })
        st.dataframe(display_agent_hygiene, use_container_width=True, hide_index=True)
    else:
        st.caption("No agent form records found in the current operational scope.")

# 2. Ticket-Wise Validation Inspector Tab
with tab_ticket_hygiene:
    flagged_tickets = audited_df[audited_df["field_compliant"] == 0]
    perfect_tickets = audited_df[audited_df["field_compliant"] == 1]

    subtab_flagged, subtab_perfect = st.tabs([
        f"🚨 Flagged / Missing Fields ({len(flagged_tickets):,})",
        f"✅ 100% Compliant Tickets ({len(perfect_tickets):,})"
    ])

    cols_to_inspect = [
        "ticket_id", "subject", "agent", "company", "ticket_type",
        "missing_fields_list", "form_quality_score"
    ]
    rename_inspect = {
        "ticket_id": "Ticket ID",
        "subject": "Case Subject",
        "agent": "Assigned SRE",
        "company": "Company",
        "ticket_type": "Type",
        "missing_fields_list": "Missing Mandatory Fields",
        "form_quality_score": "Score (%)"
    }

    avail_inspect_cols = [c for c in cols_to_inspect if c in audited_df.columns]

    with subtab_flagged:
        if not flagged_tickets.empty:
            st.dataframe(
                flagged_tickets[avail_inspect_cols].rename(columns=rename_inspect),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("🎉 Operational perfection! All tickets within the active scope meet full field validation standards.")

    with subtab_perfect:
        if not perfect_tickets.empty:
            st.dataframe(
                perfect_tickets[avail_inspect_cols].rename(columns=rename_inspect),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.caption("No fully compliant tickets available in this view scope.")


# Section 6: Systemic Root Cause & Security Compliance Diagnostics
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


# Section 7: Interactive Plotly Chart Columns Block
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


# Section 8: Engineering Scorecard Performance Leaderboard
st.markdown("---")
st.subheader("🏆 Performance Score Leaderboard System Matrix")
if not rankings_df.empty:
    st.dataframe(rankings_df, width=1200, hide_index=True)
else:
    st.caption(
        "Insufficient active records available to calculate team metrics ranking values."
    )

# Section 9: Local AI Agent Career Coaching Workshop
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

# Section 10: Deep Forensic Ticket Investigation Module Injection Anchor
show_ai_investigator_ui(filtered_df)

# Section 11: Automated Operations Executive Review Compiler (Dual Export: HTML & PDF)
st.markdown("---")
st.subheader("📋 Automated Operations Executive Review Compiler")
st.caption("Generate and download standardized executive performance reports in HTML or PDF formats.")

col_comp1, col_comp2 = st.columns(2)

with col_comp1:
    if st.button("🌐 Compile Executive HTML Report", key="compile_html_btn", use_container_width=True):
        html_path = AutomatedReportGenerator.compile_executive_html(filtered_df, selected_agent)
        if html_path and os.path.exists(html_path):
            st.session_state["generated_html_path"] = html_path
            st.success(f"HTML review generated: `{html_path}`")
        else:
            st.error("HTML Report compilation failed or returned empty scope.")

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

with col_comp2:
    if st.button("📄 Compile Executive PDF Report", key="compile_pdf_btn", use_container_width=True):
        if "generated_html_path" not in st.session_state or not os.path.exists(st.session_state["generated_html_path"]):
            st.session_state["generated_html_path"] = AutomatedReportGenerator.compile_executive_html(filtered_df, selected_agent)

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
