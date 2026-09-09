import json
from datetime import datetime
from pathlib import Path
import pandas as pd
import pdfkit
import re

from analytics.scoring import OperationsLeaderboardScorer
from config import LLM_TIMEOUT, OLLAMA_API_URL, OLLAMA_MODEL, REPORTS_DIR


class AutomatedReportGenerator:
    @staticmethod
    def generate_rich_executive_report(df: pd.DataFrame, selected_agent: str = "All Agents", team_util_df: pd.DataFrame = None) -> dict:
        if df.empty:
            return {"error": "Execution skipped: Database scope currently empty."}

    @staticmethod
<<<<<<< HEAD
<<<<<<< HEAD
    def compile_executive_html(df: pd.DataFrame, selected_agent: str = "All Agents", team_util_df: pd.DataFrame = None) -> str:
        """
        Compiles all scoped metrics, agent scorecards, and AI remarks into a standalone HTML report.
        """
=======
=======
    def get_shift(dt) -> str:
        if pd.isna(dt):
            return "Unknown"
        
        try:
            hour = dt.hour
            minute = dt.minute
            time_val = hour + minute / 60.0
            
            # Morning: 6:30 AM to 3:00 PM
            if 6.5 <= time_val < 15.0:
                return "Morning"
            # Afternoon: 3:00 PM to 11:00 PM
            elif 15.0 <= time_val < 23.0:
                return "Afternoon"
            # Night: 11:00 PM to 6:30 AM
            else:
                return "Night"
        except:
            return "Unknown"

    @staticmethod
>>>>>>> 9975b0b (Fixing the ticket export field issue, it will only use the relevant columns which will be required from all fields ticket dump in runtime)
    def calculate_individual_pod_utilization(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "agent" not in df.columns:
            return pd.DataFrame()

        df_work = df.copy()
        if "created_dt" not in df_work.columns and "created_time" in df_work.columns:
            df_work["created_dt"] = pd.to_datetime(df_work["created_time"], errors="coerce")

        df_work["effort_hours"] = (pd.to_numeric(df_work.get("effort_mins", 0), errors="coerce").fillna(0)) / 60.0

        if "created_dt" in df_work.columns:
            df_work["shift"] = df_work["created_dt"].apply(AutomatedReportGenerator.get_shift)
        else:
            df_work["shift"] = "Unknown"

        company_col = "company" if "company" in df_work.columns else "status"
        valid_dates = df_work.dropna(subset=["created_dt"])

        weeks_count = valid_dates["created_dt"].dt.to_period("W").nunique() or 1
        months_count = valid_dates["created_dt"].dt.to_period("M").nunique() or 1
        total_pod_effort_hours = df_work["effort_hours"].sum() or 1.0

        agent_records = []
        for agent_name, agent_group in df_work.groupby("agent"):
            total_agent_hrs = round(agent_group["effort_hours"].sum(), 1)
            total_tickets = len(agent_group)
            
            # Calculate agent present days based on unique dates they handled tickets
            if "created_dt" in agent_group.columns and not agent_group["created_dt"].dropna().empty:
                # Can also include resolved_dt if we want more accuracy, but created_dt is a good proxy for now
                present_days = agent_group["created_dt"].dt.date.nunique()
            else:
                present_days = 1
                
            if present_days == 0:
                present_days = 1
                
            avg_daily_hrs = total_agent_hrs / present_days
            weekly_hrs = round(avg_daily_hrs * 5, 1) # 5 working days per week
            monthly_hrs = round(avg_daily_hrs * 21.67, 1) # ~21.67 working days per month
            pod_share = round((total_agent_hrs / total_pod_effort_hours) * 100, 1)

            proj_breakdown = ""
            if company_col in agent_group.columns:
                all_projs = (
                    agent_group.groupby(company_col)["effort_hours"]
                    .sum()
                    .round(1)
                    .sort_values(ascending=False)
                    .to_dict()
                )
                proj_breakdown = ", ".join([f"{k}: {v}h" for k, v in all_projs.items() if v > 0]) or "N/A"

            # Determine Primary Shift
            primary_shift = "Unknown"
            expected_daily = 8.0
            if "shift" in agent_group.columns and not agent_group["shift"].empty:
                valid_shifts = agent_group[agent_group["shift"] != "Unknown"]
                if not valid_shifts.empty:
                    primary_shift = valid_shifts["shift"].mode().iloc[0]
            
            if primary_shift == "Morning":
                expected_daily = 8.5
            elif primary_shift == "Afternoon":
                expected_daily = 8.0
            elif primary_shift == "Night":
                expected_daily = 7.5
                
            expected_weekly = expected_daily * 5
            utilization_pct = round((weekly_hrs / expected_weekly) * 100, 1) if expected_weekly > 0 else 0.0

            agent_records.append({
                "agent": agent_name,
                "primary_shift": primary_shift,
                "total_tickets": total_tickets,
                "total_effort_hrs": total_agent_hrs,
                "weekly_hrs": weekly_hrs,
                "expected_weekly": expected_weekly,
                "utilization_pct": utilization_pct,
                "monthly_hrs": monthly_hrs,
                "pod_share_pct": pod_share,
                "top_projects": proj_breakdown
            })

        util_df = pd.DataFrame(agent_records)
        return util_df.sort_values(by="total_effort_hrs", ascending=False)

    @staticmethod
    def _enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Adds calculated columns, statuses, and logic to the master dataframe."""
        df_work = df.copy()
        
        # 1. Exclude US SRE POD Handover tickets
        df_work = df_work[~df_work["subject"].astype(str).str.contains(r"(?i)US SRE.*Handover", na=False)]
        
        # Parse Dates
        if "created_time" in df_work.columns:
            df_work["created_dt"] = pd.to_datetime(df_work["created_time"], errors="coerce")
        if "resolved_time" in df_work.columns:
            df_work["resolved_dt"] = pd.to_datetime(df_work["resolved_time"], errors="coerce")
            
        # Determine Shift Based on created_dt
        if "created_dt" in df_work.columns:
            df_work["shift"] = df_work["created_dt"].apply(AutomatedReportGenerator.get_shift)
        else:
            df_work["shift"] = "Unknown"

        # 2. Identify SRs vs Incidents strictly based on Alarm Source
        alarm_source_norm = df_work["alarm_source"].astype(str).str.strip().str.upper()
        df_work["calc_type"] = "Incident"
        df_work.loc[alarm_source_norm == "SR", "calc_type"] = "Service Request"
        df_work["is_sr"] = df_work["calc_type"] == "Service Request"

        # Status Grouping
        def group_status(val):
            v = str(val).lower()
            if 'resolv' in v: return 'Resolved'
            if 'clos' in v: return 'Closed'
            if 'cancel' in v: return 'Cancelled'
            if 'pend' in v: return 'Pending'
            if 'progress' in v: return 'In Progress'
            return 'Open'
        
        if "status" in df_work.columns:
            df_work["status_group"] = df_work["status"].apply(group_status)
        else:
            df_work["status_group"] = "Unknown"
            
        df_work["is_resolved_closed"] = df_work["status_group"].isin(["Resolved", "Closed"])

        # Effort and Resolution Hours
        if "effort_mins" in df_work.columns:
            df_work["effort_hours"] = pd.to_numeric(df_work["effort_mins"], errors="coerce").fillna(0) / 60.0
        else:
            df_work["effort_hours"] = 0.0

        if "resolution_hours" in df_work.columns:
            df_work["resolution_hours_num"] = pd.to_numeric(df_work["resolution_hours"], errors="coerce")
        else:
            df_work["resolution_hours_num"] = pd.NA

        # Aging for Open Tickets
        reference_date = datetime.now()
        if "created_dt" in df_work.columns and not df_work["created_dt"].dropna().empty:
            max_dt = df_work["created_dt"].max()
            if max_dt < pd.Timestamp(datetime.now()) - pd.Timedelta(days=7):
                reference_date = max_dt
                
        df_work["age_days"] = pd.NA
        unresolved_mask = ~df_work["is_resolved_closed"]
        if "created_dt" in df_work.columns:
            df_work.loc[unresolved_mask, "age_days"] = (pd.to_datetime(reference_date) - df_work.loc[unresolved_mask, "created_dt"]).dt.total_seconds() / 86400.0

        def get_age_bucket(days):
            if pd.isna(days): return "N/A"
            if days <= 1: return "0-1 days"
            if days <= 3: return "2-3 days"
            if days <= 7: return "4-7 days"
            if days <= 14: return "8-14 days"
            if days <= 30: return "15-30 days"
            return "30+ days"
            
        df_work["age_bucket"] = df_work["age_days"].apply(get_age_bucket)

        return df_work

    @staticmethod
    def compile_executive_html(df: pd.DataFrame, selected_agent: str = "All Agents") -> str:
>>>>>>> d8bca66 (Reports Modified to show detailed agent performance with various metrics)
        if df.empty:
            return ""

        # Filter dataset for specific agent if requested
        if selected_agent != "All Agents" and "agent" in df.columns:
            agent_df = df[df["agent"] == selected_agent].copy()
        else:
            agent_df = df.copy()

<<<<<<< HEAD
        # Extract Date Range dynamically
        if "created_dt" in agent_df.columns and not agent_df["created_dt"].dropna().empty:
            min_d = agent_df["created_dt"].min().strftime('%d %b %Y')
            max_d = agent_df["created_dt"].max().strftime('%d %b %Y')
=======
        scoped_df = AutomatedReportGenerator._enrich_dataframe(scoped_df)

        if "created_dt" in scoped_df.columns and not scoped_df["created_dt"].dropna().empty:
            min_d = scoped_df["created_dt"].min().strftime('%d %b %Y')
            max_d = scoped_df["created_dt"].max().strftime('%d %b %Y')
>>>>>>> d8bca66 (Reports Modified to show detailed agent performance with various metrics)
            date_range_str = f"{min_d} – {max_d}"
        else:
            date_range_str = "Full History Scope"

<<<<<<< HEAD
        # 1. Executive Metrics Calculations
        total_tickets = len(agent_df)
        total_breaches = int(agent_df["sla_breached"].sum()) if "sla_breached" in agent_df.columns else 0
        compliance = round(((total_tickets - total_breaches) / total_tickets) * 100, 1) if total_tickets > 0 else 100.0
        avg_resolution = round(agent_df["resolution_hours"].mean(), 2) if "resolution_hours" in agent_df.columns else 0
        total_effort = round(agent_df["effort_mins"].sum(), 0) if "effort_mins" in agent_df.columns else 0

        # Calculate SR vs Incident count dynamically
        is_sr = pd.Series(False, index=agent_df.index)
        for col in agent_df.columns:
            if col.lower().strip() in ['category', 'type', 'ticket_type', 'ticket type']:
                is_sr = is_sr | agent_df[col].astype(str).str.contains(r"(?i)(service request|\bsr\b)", na=False)
        if "subject" in agent_df.columns:
            sr_keywords = r"(?i)(service request|\bsr\b|grant is awaiting|approve or deny|grant access|access request)"
            is_sr = is_sr | agent_df["subject"].astype(str).str.contains(sr_keywords, na=False)
            
        total_sr = int(is_sr.sum())
        total_incidents = total_tickets - total_sr

        # 2. Categorical & Company Distribution
        def get_dist(col_name):
            if col_name in agent_df.columns:
                return agent_df[col_name].value_counts().to_dict()
            return {}

        company_col = "company" if "company" in agent_df.columns else "status"
        company_dist = get_dist(company_col)
        priority_dist = get_dist("priority")
        type_dist = get_dist("ticket_type") if "ticket_type" in agent_df.columns else {}

        # 3. Per-Agent Leaderboard Rankings
        agent_rankings = pd.DataFrame()
        if "agent" in agent_df.columns:
            agent_rankings = OperationsLeaderboardScorer.compile_weighted_rankings(
                agent_df, context_type="All Types (SR & Incident)"
            )

        # 4. Local AI Generated Strategic Remarks
        ai_remarks = {}
        if not agent_rankings.empty:
            prompt_data = agent_rankings.head(10).to_dict(orient="records")
            prompt = f"""
You are an expert IT Operations Manager. Analyze this agent performance data:
{json.dumps(prompt_data, indent=2)}

Provide a very short (1 sentence) performance remark for each agent highlighting their key strength or weakness (e.g. "High volume but needs to improve SLA compliance").
Format your response as a strict JSON dictionary mapping the agent's name to the remark string.
"""
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2, "num_predict": 500}
            }
            try:
                res = requests.post(OLLAMA_API_URL, json=payload, timeout=LLM_TIMEOUT)
                if res.status_code == 200:
                    raw_resp = res.json().get('response', '{}')
                    ai_remarks = json.loads(raw_resp)
            except Exception:
                ai_remarks = {}
        
        date_range_str = datetime.now().strftime('%Y-%m-%d')
                
        # 5. Build HTML Content
        html_content = AutomatedReportGenerator._build_html(
            total_tickets, compliance, total_breaches, avg_resolution, total_effort,
            total_sr, total_incidents, agent_rankings, ai_remarks,
            company_dist, priority_dist, type_dist, selected_agent, date_range_str, team_util_df
        )
        
        # 6. PDF Generation Fallback
        pdf_bytes = None
        try:
            # pyrefly: ignore [missing-import]
            from xhtml2pdf import pisa
            import io
            result = io.BytesIO()
            # xhtml2pdf requires string or file-like object
            pdf = pisa.pisaDocument(io.StringIO(html_content), result)
            if not pdf.err:
                pdf_bytes = result.getvalue()
        except ImportError:
            pass
=======
        # Generate HTML report content
        html_content = AutomatedReportGenerator._build_comprehensive_html(scoped_df, date_range_str, selected_agent)
>>>>>>> d8bca66 (Reports Modified to show detailed agent performance with various metrics)

        filename = f"executive_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        report_path = REPORTS_DIR / filename
        
        # Ensure dir exists
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return str(report_path)

    @staticmethod
    def compile_executive_pdf(html_path: str) -> str:
        """
        Converts a compiled HTML executive report into a PDF document using pdfkit/wkhtmltopdf.
        """
        if not html_path or not Path(html_path).exists():
            return ""

        pdf_path = html_path.replace(".html", ".pdf")

        options = {
            'page-size': 'A4',
            'margin-top': '0.5in',
            'margin-right': '0.5in',
            'margin-bottom': '0.5in',
            'margin-left': '0.5in',
            'encoding': "UTF-8",
            'enable-local-file-access': None,
            'no-outline': None,
            'javascript-delay': '1000' # wait a bit for scripts
        }

        try:
            pdfkit.from_file(html_path, pdf_path, options=options)
            return pdf_path
        except Exception as e:
            print(f"❌ PDF Generation Error: {str(e)}")
            return ""

    @staticmethod
<<<<<<< HEAD
    def _build_html(total, compliance, breaches, avg_res, total_effort, total_sr, total_incidents, agent_rankings, remarks, c_dist, p_dist, t_dist, scope, date_range, team_util_df):
        now_str = datetime.now().strftime('%d %b %Y, %H:%M')

        # Generate rows for agent scorecard table
        agent_rows = ""
        if not agent_rankings.empty:
            for i, row in agent_rankings.reset_index(drop=True).iterrows():
                agent_name = row.get('agent', 'Unknown')
                score = row.get('Performance_Score', 'N/A')
                vol = row.get('Tickets_Handled', 0)
                res_hr = row.get('Avg_Resolution_Hours', 0)
                remark = remarks.get(agent_name, "Solid operational performance.")

                row_class = "row-alt" if i % 2 != 0 else ""

                agent_rows += f"""
                <tr class="{row_class}">
                    <td><strong>{agent_name}</strong></td>
                    <td><span class="badge badge-info">{score}%</span></td>
                    <td>{vol}</td>
                    <td>{res_hr} hrs</td>
                    <td style="font-size: 0.9em; color: #475569;">{remark}</td>
                </tr>
                """

        def dict_to_html_list(d):
            if not d:
                return "<li>No data available</li>"
            return "".join([f"<li><strong>{k}:</strong> {v}</li>" for k, v in list(d.items())[:5]])
            
        agent_util_html = ""
        if scope != "All Agents" and team_util_df is not None and not team_util_df.empty:
            agent_row = team_util_df[team_util_df['agent'] == scope]
            if not agent_row.empty:
                r_data = agent_row.iloc[0]
                status = r_data['Utilization_Status']
                effort_mins = int(r_data['Total_Effort_Mins'])
                hrs, mins = divmod(effort_mins, 60)
                effort_str = f"{hrs}h {mins}m"
                tickets = int(r_data['Total_Tickets'])
                
                status_color = "#10b981" if status == "Optimally Utilized" else "#ef4444" if status == "Overutilized" else "#f59e0b"
                
                agent_util_html = f"""
                <div class="card util-card" style="border-left-color: {status_color}; margin-bottom: 25px;">
                    <table style="width: 100%; border: none; margin: 0; padding: 0;">
                        <tr>
                            <td style="border: none; padding: 0; vertical-align: middle;">
                                <div class="section-title" style="border:none; margin:0; padding:0; font-size: 18px;">Agent Capacity & Utilization Profile</div>
                            </td>
                            <td style="border: none; padding: 0; text-align: right; vertical-align: middle;">
                                <span class="badge" style="background-color: {status_color}; color: #ffffff; font-size: 12px; padding: 6px 12px;">{status}</span>
                            </td>
                        </tr>
                    </table>
                    <table style="width: 100%; border: none; margin-top: 20px;">
                        <tr>
                            <td width="50%" style="border: none; padding: 0;">
                                <div class="card-title">Total Effort Logged</div>
                                <div class="card-value">{effort_str}</div>
                            </td>
                            <td width="50%" style="border: none; padding: 0;">
                                <div class="card-title">Total Tickets Handled</div>
                                <div class="card-value">{tickets}</div>
                            </td>
                        </tr>
                    </table>
                </div>
                """
=======
    def _build_comprehensive_html(df: pd.DataFrame, date_range: str, scope: str) -> str:
        now_str = datetime.now().strftime('%d %b %Y, %H:%M')
        
        # -- METRICS CALCULATION --
        total_tickets = len(df)
        total_srs = df["is_sr"].sum()
        total_incidents = total_tickets - total_srs
        
        resolved_df = df[df["is_resolved_closed"]]
        num_resolved_closed = len(resolved_df)
        
        num_open = len(df[df["status_group"] == "Open"])
        num_pending = len(df[df["status_group"] == "Pending"])
        num_in_progress = len(df[df["status_group"] == "In Progress"])
        num_cancelled = len(df[df["status_group"] == "Cancelled"])
        
        res_percentage = round((num_resolved_closed / total_tickets * 100), 1) if total_tickets > 0 else 0
        
        if "sla_breached" in df.columns:
            sla_breached = df["sla_breached"].fillna(0).astype(int).sum()
            sla_applicable = len(df)
            sla_met = sla_applicable - sla_breached
            sla_percentage = round((sla_met / sla_applicable * 100), 1) if sla_applicable > 0 else 0
        else:
            sla_breached = 0
            sla_met = 0
            sla_applicable = 0
            sla_percentage = 0
            
        avg_res_time = df["resolution_hours_num"].dropna().mean()
        avg_res_time_str = f"{avg_res_time:.1f} hrs" if pd.notna(avg_res_time) else "N/A"
        
        total_effort_hrs = df["effort_hours"].sum()
        
        # --- HTML TEMPLATE COMPONENTS ---
        
        def render_kpi_card(title, value, color_class="neutral"):
            return f"""
            <div class="kpi-card kpi-{color_class}">
                <div class="kpi-title">{title}</div>
                <div class="kpi-value">{value}</div>
            </div>
            """
            
        def generate_table(df_subset, columns_map):
            if df_subset.empty:
                return "<p style='color:#64748b;'>No records to display.</p>"
            
            headers = "".join([f"<th>{name}</th>" for _, name in columns_map.items()])
            rows = ""
            for _, row in df_subset.iterrows():
                row_cells = ""
                for col_key, _ in columns_map.items():
                    val = row.get(col_key, "")
                    if pd.isna(val): val = ""
                    # Truncate long strings
                    if isinstance(val, str) and len(val) > 100:
                        val = val[:97] + "..."
                    row_cells += f"<td>{val}</td>"
                rows += f"<tr>{row_cells}</tr>"
                
            return f"""
            <div class="table-container">
                <table class="styled-table">
                    <thead><tr>{headers}</tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
            """
>>>>>>> d8bca66 (Reports Modified to show detailed agent performance with various metrics)

        # 1. Executive Summary
        exec_summary_html = f"""
        <div class="section">
            <h2 class="section-title">1. Executive Summary</h2>
            <div class="kpi-grid">
                {render_kpi_card("Total Tickets", total_tickets, "primary")}
                {render_kpi_card("Total SRs", total_srs)}
                {render_kpi_card("Total Incidents", total_incidents)}
                {render_kpi_card("Resolved / Closed", num_resolved_closed, "success")}
                {render_kpi_card("Resolution Rate", f"{res_percentage}%", "success")}
                {render_kpi_card("Open / Pending", num_open + num_pending, "warning")}
                {render_kpi_card("SLA Compliance", f"{sla_percentage}%", "success" if sla_percentage >= 90 else "danger")}
                {render_kpi_card("Avg Resolution Time", avg_res_time_str)}
                {render_kpi_card("Total Effort", f"{total_effort_hrs:.1f} hrs")}
            </div>
        </div>
        """
        
        # 2. SR Details
        sr_df = df[df["is_sr"]]
        sr_res_count = len(sr_df[sr_df["is_resolved_closed"]])
        sr_res_rate = round(sr_res_count / len(sr_df) * 100, 1) if len(sr_df) > 0 else 0
        sr_avg_res = sr_df["resolution_hours_num"].mean()
        
        sr_cols = {
            "ticket_id": "Ticket ID",
            "created_dt": "Created Date",
            "status": "Status",
            "priority": "Priority",
            "effort_mins": "Effort_mins",
            "subject": "Case Subject"
        }
        
        sr_html = f"""
        <div class="section page-break-inside-avoid">
            <h2 class="section-title">2. Service Request Details</h2>
            <div class="kpi-grid">
                {render_kpi_card("Total SRs", len(sr_df))}
                {render_kpi_card("SRs Resolved", sr_res_count, "success")}
                {render_kpi_card("Resolution Rate", f"{sr_res_rate}%")}
                {render_kpi_card("Avg Res Time", f"{sr_avg_res:.1f} hrs" if pd.notna(sr_avg_res) else "N/A")}
            </div>
            <h3 class="subsection-title">Top 10 Highest-Effort Service Requests</h3>
            {generate_table(sr_df.sort_values(by="effort_mins", ascending=False, na_position="last").head(10), sr_cols)}
        </div>
        """
        
        # 3. Incident Details
        inc_df = df[~df["is_sr"]]
        inc_res_count = len(inc_df[inc_df["is_resolved_closed"]])
        inc_res_rate = round(inc_res_count / len(inc_df) * 100, 1) if len(inc_df) > 0 else 0
        inc_avg_res = inc_df["resolution_hours_num"].mean()
        
        inc_html = f"""
        <div class="section page-break-inside-avoid">
            <h2 class="section-title">3. Incident Details</h2>
            <div class="kpi-grid">
                {render_kpi_card("Total Incidents", len(inc_df))}
                {render_kpi_card("Incidents Resolved", inc_res_count, "success")}
                {render_kpi_card("Resolution Rate", f"{inc_res_rate}%")}
                {render_kpi_card("Avg Res Time", f"{inc_avg_res:.1f} hrs" if pd.notna(inc_avg_res) else "N/A")}
            </div>
            <h3 class="subsection-title">Top 10 Highest-Effort Incidents</h3>
            {generate_table(inc_df.sort_values(by="effort_mins", ascending=False, na_position="last").head(10), sr_cols)}
        </div>
        """
        
        # 4. Resolution Performance
        if len(resolved_df) > 0:
            fastest_res = resolved_df["resolution_hours_num"].min()
            longest_res = resolved_df["resolution_hours_num"].max()
            median_res = resolved_df["resolution_hours_num"].median()
        else:
            fastest_res = longest_res = median_res = pd.NA
            
        res_perf_html = f"""
        <div class="section page-break-inside-avoid">
            <h2 class="section-title">4. Resolution Performance</h2>
            <div class="kpi-grid">
                {render_kpi_card("Avg Resolution", avg_res_time_str)}
                {render_kpi_card("Median Resolution", f"{median_res:.1f} hrs" if pd.notna(median_res) else "N/A")}
                {render_kpi_card("Fastest Resolution", f"{fastest_res:.2f} hrs" if pd.notna(fastest_res) else "N/A", "success")}
                {render_kpi_card("Longest Resolution", f"{longest_res:.1f} hrs" if pd.notna(longest_res) else "N/A", "warning")}
            </div>
        </div>
        """
        
        # 5. SLA Performance
        sla_html = f"""
        <div class="section page-break-inside-avoid">
            <h2 class="section-title">5. SLA Performance</h2>
            <div class="kpi-grid">
                {render_kpi_card("SLA Applicable Records", sla_applicable)}
                {render_kpi_card("SLA Met", sla_met, "success")}
                {render_kpi_card("SLA Breached", sla_breached, "danger")}
                {render_kpi_card("SLA Compliance %", f"{sla_percentage}%")}
            </div>
            <h3 class="subsection-title">Breached Records</h3>
            {generate_table(df[df["sla_breached"] == 1], sr_cols)}
        </div>
        """
        
        # 6. Customer Feedback (Not available in dataset)
        feedback_html = f"""
        <div class="section page-break-inside-avoid">
            <h2 class="section-title">6. Customer Feedback</h2>
            <div class="alert alert-info">
                Customer feedback and interaction rating data is not currently present in the source dataset. 
            </div>
        </div>
        """
        
        # 7. Activity / Workload Summary
        util_df = AutomatedReportGenerator.calculate_individual_pod_utilization(df)
        util_cols = {
            "agent": "SRE Engineer",
            "total_tickets": "Tickets Handled",
            "total_effort_hrs": "Total Effort (Hrs)",
            "weekly_hrs": "Weekly Rate",
            "monthly_hrs": "Monthly Rate",
            "pod_share_pct": "Pod Workload Share (%)",
            "top_projects": "Project / Account Allocations"
        }
        
        workload_html = f"""
        <div class="section page-break-inside-avoid">
            <h2 class="section-title">7. Activity & Workload Summary</h2>
            <h3 class="subsection-title">Engineer Workload Distribution</h3>
            {generate_table(util_df, util_cols)}
        </div>
        """
        
        # 8. Aging Analysis
        unresolved_df = df[~df["is_resolved_closed"]].copy()
        aging_summary = unresolved_df.groupby("age_bucket").size().reset_index(name='count')
        # Order the buckets
        bucket_order = ["0-1 days", "2-3 days", "4-7 days", "8-14 days", "15-30 days", "30+ days", "N/A"]
        aging_summary["age_bucket"] = pd.Categorical(aging_summary["age_bucket"], categories=bucket_order, ordered=True)
        aging_summary = aging_summary.sort_values("age_bucket")
        
        aging_cols = {"age_bucket": "Aging Bucket", "count": "Number of Open Tickets"}
        
        aging_html = f"""
        <div class="section page-break-inside-avoid">
            <h2 class="section-title">8. Aging Analysis (Unresolved Tickets)</h2>
            <div class="kpi-grid">
                {render_kpi_card("Total Open/Pending", len(unresolved_df))}
                {render_kpi_card("Aging > 7 Days", len(unresolved_df[unresolved_df["age_days"] > 7]), "warning")}
            </div>
            <h3 class="subsection-title">Open Tickets by Age</h3>
            <div style="max-width: 400px;">
                {generate_table(aging_summary, aging_cols)}
            </div>
            <h3 class="subsection-title">Aging Records List (Top 50)</h3>
            {generate_table(unresolved_df.sort_values(by="age_days", ascending=False).head(50), 
                            {**sr_cols, "age_days": "Age (Days)"})}
        </div>
        """
        
        # Detailed Record-Level Data section removed as requested
        
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
<<<<<<< HEAD
            <title>Enterprise SRE & IT Operations Intelligence Report</title>
=======
            <title>Comprehensive Operations Review Report</title>
>>>>>>> d8bca66 (Reports Modified to show detailed agent performance with various metrics)
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
                
                @page {{
                    size: A4;
                    margin: 1.2cm;
                }}

                @media print {{
                    .card {{ page-break-inside: avoid; }}
                    tr {{ page-break-inside: avoid; page-break-after: auto; }}
                    table {{ page-break-inside: auto; }}
                    thead {{ display: table-header-group; }}
                }}

                body {{
<<<<<<< HEAD
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    background-color: #ffffff;
                    color: #1e293b;
                    margin: 0;
                    padding: 0;
                    line-height: 1.5;
                }}
                
                .header {{
                    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                    color: #ffffff;
                    padding: 25px 30px;
                    border-radius: 6px;
                    margin-bottom: 25px;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                }}
                
                .header h1 {{ margin: 0 0 6px 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }}
                .sub-author {{ margin: 0 0 12px 0; font-size: 12px; color: #38bdf8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
                .header p {{ margin: 0; color: #94a3b8; font-size: 13px; font-weight: 500; }}
                .header strong {{ color: #e2e8f0; }}
                
                .grid-kpi {{
                    width: 100%;
                    margin-bottom: 25px;
                    border-collapse: separate;
                    border-spacing: 12px;
                    margin-left: -12px;
                    margin-right: -12px;
                }}

                .card {{
                    background: #ffffff;
                    padding: 20px;
                    border-radius: 6px;
                    border: 1px solid #e2e8f0;
                    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
                }}
                
                .util-card {{
                    background: #f8fafc;
                    border-left: 5px solid #e2e8f0;
                }}
                
                .card-title {{
                    font-size: 11px;
                    text-transform: uppercase;
                    font-weight: 600;
                    color: #64748b;
                    margin-bottom: 8px;
                    letter-spacing: 0.5px;
                }}
                
                .card-value {{
                    font-size: 24px;
                    font-weight: 700;
                    color: #0f172a;
                    letter-spacing: -0.5px;
                }}
                
                .badge {{
                    display: inline-block;
                    padding: 3px 8px;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .badge-success {{ background: #dcfce7; color: #166534; }}
                .badge-danger {{ background: #fee2e2; color: #991b1b; }}
                .badge-info {{ background: #e0f2fe; color: #0369a1; }}
                
                table.data-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 15px;
                    border: 1px solid #e2e8f0;
                    border-radius: 4px;
                    overflow: hidden;
                }}
                
                table.data-table th, table.data-table td {{
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid #e2e8f0;
                    font-size: 13px;
                }}
                
                table.data-table th {{
                    background-color: #f8fafc;
                    font-weight: 600;
                    text-transform: uppercase;
                    color: #475569;
                    font-size: 11px;
                    letter-spacing: 0.5px;
=======
                    font-family: 'Inter', Helvetica, Arial, sans-serif;
                    background-color: #f8fafc;
                    color: #0f172a;
                    margin: 0;
                    padding: 30px;
                    line-height: 1.5;
                }}

                .report-header {{
                    background: #ffffff;
                    padding: 24px;
                    border-radius: 8px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    margin-bottom: 24px;
                    border-top: 4px solid #0ea5e9;
                }}

                .report-header h1 {{ margin: 0 0 8px 0; font-size: 24px; font-weight: 700; color: #0f172a; }}
                .report-header .sub-title {{ font-size: 12px; color: #0284c7; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }}
                .report-header .meta-grid {{
                    display: flex;
                    gap: 24px;
                    font-size: 12px;
                    color: #475569;
                }}
                .meta-item strong {{ color: #0f172a; }}

                .section {{
                    background: #ffffff;
                    padding: 24px;
                    border-radius: 8px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    margin-bottom: 24px;
                }}

                .page-break-inside-avoid {{
                    page-break-inside: avoid;
                }}

                .section-title {{
                    font-size: 18px;
                    font-weight: 700;
                    color: #0f172a;
                    margin: 0 0 16px 0;
                    padding-bottom: 8px;
                    border-bottom: 1px solid #e2e8f0;
                }}

                .subsection-title {{
                    font-size: 14px;
                    font-weight: 600;
                    color: #334155;
                    margin: 20px 0 10px 0;
                }}

                .kpi-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
                    gap: 16px;
                    margin-bottom: 20px;
                }}

                .kpi-card {{
                    padding: 16px;
                    border-radius: 6px;
                    border: 1px solid #e2e8f0;
                    background-color: #f8fafc;
                }}

                .kpi-card.kpi-primary {{ border-left: 4px solid #0ea5e9; }}
                .kpi-card.kpi-success {{ border-left: 4px solid #10b981; background-color: #ecfdf5; border-color: #d1fae5; }}
                .kpi-card.kpi-warning {{ border-left: 4px solid #f59e0b; background-color: #fffbeb; border-color: #fef3c7; }}
                .kpi-card.kpi-danger {{ border-left: 4px solid #ef4444; background-color: #fef2f2; border-color: #fee2e2; }}

                .kpi-title {{ font-size: 11px; color: #64748b; font-weight: 500; text-transform: uppercase; margin-bottom: 4px; }}
                .kpi-value {{ font-size: 22px; font-weight: 700; color: #0f172a; }}
                
                .kpi-success .kpi-value {{ color: #047857; }}
                .kpi-danger .kpi-value {{ color: #b91c1c; }}

                .table-container {{
                    overflow-x: auto;
                    margin-bottom: 16px;
                }}

                table.styled-table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 11px;
                }}
                
                table.styled-table th {{
                    background-color: #f1f5f9;
                    color: #475569;
                    font-weight: 600;
                    padding: 10px 12px;
                    text-align: left;
                    border-bottom: 2px solid #cbd5e1;
                }}
                
                table.styled-table td {{
                    padding: 10px 12px;
                    border-bottom: 1px solid #e2e8f0;
                    color: #334155;
                }}

                table.styled-table tr:nth-of-type(even) {{
                    background-color: #f8fafc;
                }}

                .alert {{
                    padding: 12px 16px;
                    border-radius: 6px;
                    font-size: 13px;
                }}
                .alert-info {{
                    background-color: #eff6ff;
                    border: 1px solid #bfdbfe;
                    color: #1d4ed8;
>>>>>>> d8bca66 (Reports Modified to show detailed agent performance with various metrics)
                }}
                
                tr.row-alt {{ background-color: #fcfcfc; }}
                
                .section-title {{
                    font-size: 16px;
                    font-weight: 700;
                    margin-top: 0;
                    margin-bottom: 15px;
                    color: #0f172a;
                    border-bottom: 1px solid #e2e8f0;
                    padding-bottom: 10px;
                }}
                
                ul {{ margin: 0; padding-left: 20px; color: #475569; font-size: 13px; }}
                li {{ margin-bottom: 6px; }}
            </style>
        </head>
        <body>
<<<<<<< HEAD
            <div class="header">
                <h1>Enterprise SRE & IT Operations Intelligence Report</h1>
                <div class="sub-author">Developed by Team Gamma (US SRE Pod)</div>
                <p>Scope Target: <strong>{scope}</strong> | Date Range: <strong>{date_range}</strong> | Generated: {now_str}</p>
            </div>
            
            <table class="grid-kpi">
                <tr>
                    <td width="33%">
                        <div class="card">
                            <div class="card-title">Total Handled</div>
                            <div class="card-value">{total}</div>
                        </div>
                    </td>
                    <td width="33%">
                        <div class="card">
                            <div class="card-title">SLA Compliance</div>
                            <div class="card-value">
                                {compliance}% 
                                <span class="badge {'badge-success' if compliance >= 90 else 'badge-danger'}">
                                    {breaches} Breaches
                                </span>
                            </div>
                        </div>
                    </td>
                    <td width="33%">
                        <div class="card">
                            <div class="card-title">Avg Resolution</div>
                            <div class="card-value">{avg_res} <span style="font-size:12px; color:#64748b;">Hrs</span></div>
                        </div>
                    </td>
                </tr>
                <tr>
                    <td width="33%">
                        <div class="card">
                            <div class="card-title">Total Effort Spent</div>
                            <div class="card-value">{total_effort} <span style="font-size:12px; color:#64748b;">Mins</span></div>
                        </div>
                    </td>
                    <td width="33%">
                        <div class="card">
                            <div class="card-title">Service Requests (SR)</div>
                            <div class="card-value">{total_sr}</div>
                        </div>
                    </td>
                    <td width="33%">
                        <div class="card">
                            <div class="card-title">Incidents Resolved</div>
                            <div class="card-value">{total_incidents}</div>
                        </div>
                    </td>
                </tr>
            </table>
            
            {agent_util_html}
            
            <div class="card" style="margin-bottom: 20px;">
                <div class="section-title">Engineering Scorecard & AI Remarks</div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Agent</th>
                            <th>Perf Score</th>
                            <th>Volume</th>
                            <th>Avg Speed</th>
                            <th>AI Strategic Review</th>
                        </tr>
                    </thead>
                    <tbody>
                        {agent_rows if agent_rows else '<tr><td colspan="5">No agent records found.</td></tr>'}
                    </tbody>
                </table>
            </div>
            
            <table width="100%" style="border-collapse: collapse;">
                <tr>
                    <td width="50%" valign="top" style="padding-right: 8px;">
                        <div class="card">
                            <div class="section-title">Top Associated Companies</div>
                            <ul>{dict_to_html_list(c_dist)}</ul>
                        </div>
                    </td>
                    <td width="50%" valign="top" style="padding-left: 8px;">
                        <div class="card">
                            <div class="section-title">Workload Distribution</div>
                            <ul>
                                <li><strong>By Priority:</strong></li>
                                <ul>{dict_to_html_list(p_dist)}</ul>
                                <li style="margin-top: 6px;"><strong>By Type:</strong></li>
                                <ul>{dict_to_html_list(t_dist)}</ul>
                            </ul>
                        </div>
                    </td>
                </tr>
            </table>
=======
            <div class="report-header">
                <h1>Comprehensive Operations & Performance Report</h1>
                <div class="sub-title">IT Service Management & Incident Resolution Metrics</div>
                <div class="meta-grid">
                    <div class="meta-item">Scope: <strong>{scope}</strong></div>
                    <div class="meta-item">Reporting Period: <strong>{date_range}</strong></div>
                    <div class="meta-item">Generated At: <strong>{now_str}</strong></div>
                </div>
            </div>

            {exec_summary_html}
            {sr_html}
            {inc_html}
            {res_perf_html}
            {sla_html}
            {feedback_html}
            {workload_html}
            {aging_html}
            
            <div style="text-align: center; margin-top: 40px; font-size: 10px; color: #94a3b8;">
                End of Report • Generated automatically from source operations data.
            </div>
>>>>>>> d8bca66 (Reports Modified to show detailed agent performance with various metrics)
        </body>
        </html>
        """
        
        return full_html
