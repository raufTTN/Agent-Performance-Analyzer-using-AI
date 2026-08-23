import json
from datetime import datetime
from pathlib import Path
import pandas as pd
import pdfkit
import requests

from analytics.scoring import OperationsLeaderboardScorer
from config import LLM_TIMEOUT, OLLAMA_API_URL, OLLAMA_MODEL, REPORTS_DIR


class AutomatedReportGenerator:

    @staticmethod
    def calculate_individual_pod_utilization(df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes granular time utilization (in Hours) for each individual engineer in the pod:
        Total Hours, Weekly Rate (Hrs/Wk), Monthly Rate (Hrs/Mo), Full Project Allocations, and Pod Share %.
        """
        if df.empty or "agent" not in df.columns:
            return pd.DataFrame()

        df_work = df.copy()
        if "created_dt" not in df_work.columns and "created_time" in df_work.columns:
            df_work["created_dt"] = pd.to_datetime(df_work["created_time"], errors="coerce")

        # Convert effort minutes to hours
        df_work["effort_hours"] = (pd.to_numeric(df_work.get("effort_mins", 0), errors="coerce").fillna(0)) / 60.0

        company_col = "company" if "company" in df_work.columns else "status"
        valid_dates = df_work.dropna(subset=["created_dt"])

        # Timeline boundaries for weekly and monthly run-rate calculations
        weeks_count = valid_dates["created_dt"].dt.to_period("W").nunique() or 1
        months_count = valid_dates["created_dt"].dt.to_period("M").nunique() or 1
        total_pod_effort_hours = df_work["effort_hours"].sum() or 1.0

        agent_records = []
        for agent_name, agent_group in df_work.groupby("agent"):
            total_agent_hrs = round(agent_group["effort_hours"].sum(), 1)
            total_tickets = len(agent_group)
            weekly_hrs = round(total_agent_hrs / weeks_count, 1)
            monthly_hrs = round(total_agent_hrs / months_count, 1)
            pod_share = round((total_agent_hrs / total_pod_effort_hours) * 100, 1)

            # Full Project / Company-wise breakdown in hours (shows ALL clients)
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

            agent_records.append({
                "agent": agent_name,
                "total_tickets": total_tickets,
                "total_effort_hrs": total_agent_hrs,
                "weekly_hrs": weekly_hrs,
                "monthly_hrs": monthly_hrs,
                "pod_share_pct": pod_share,
                "top_projects": proj_breakdown
            })

        util_df = pd.DataFrame(agent_records)
        return util_df.sort_values(by="total_effort_hrs", ascending=False)

    @staticmethod
    def compile_executive_html(df: pd.DataFrame, selected_agent: str = "All Agents") -> str:
        if df.empty:
            return ""

        if selected_agent != "All Agents" and "agent" in df.columns:
            scoped_df = df[df["agent"] == selected_agent].copy()
        else:
            scoped_df = df.copy()

        if "created_dt" not in scoped_df.columns and "created_time" in scoped_df.columns:
            scoped_df["created_dt"] = pd.to_datetime(scoped_df["created_time"], errors="coerce")

        if "created_dt" in scoped_df.columns and not scoped_df["created_dt"].dropna().empty:
            min_d = scoped_df["created_dt"].min().strftime('%d %b %Y')
            max_d = scoped_df["created_dt"].max().strftime('%d %b %Y')
            date_range_str = f"{min_d} – {max_d}"
        else:
            date_range_str = "Full History Scope"

        total_tickets = len(scoped_df)
        total_breaches = int(scoped_df["sla_breached"].sum()) if "sla_breached" in scoped_df.columns else 0
        compliance = round(((total_tickets - total_breaches) / total_tickets) * 100, 1) if total_tickets > 0 else 100.0
        
        total_effort_hrs = round((scoped_df["effort_mins"].sum() / 60.0), 1) if "effort_mins" in scoped_df.columns else 0.0
        avg_effort_mins = round(scoped_df["effort_mins"].mean(), 1) if "effort_mins" in scoped_df.columns else 0.0

        valid_dates = scoped_df.dropna(subset=["created_dt"])
        if not valid_dates.empty:
            weeks_count = valid_dates["created_dt"].dt.to_period("W").nunique() or 1
            months_count = valid_dates["created_dt"].dt.to_period("M").nunique() or 1
            weekly_effort_hrs = round(total_effort_hrs / weeks_count, 1)
            monthly_effort_hrs = round(total_effort_hrs / months_count, 1)
        else:
            weekly_effort_hrs = 0.0
            monthly_effort_hrs = 0.0

        # Calculate Individual Utilization Table for the Pod (with ALL clients)
        indiv_util_df = AutomatedReportGenerator.calculate_individual_pod_utilization(scoped_df)

        # Rankings for Top Performer and Fastest Resolver banners
        rankings_df = OperationsLeaderboardScorer.compile_weighted_rankings(
            scoped_df, context_type="All Types (SR & Incident)"
        )

        top_agent_text = ""
        fastest_agent_text = ""

        if not rankings_df.empty:
            top_agent = rankings_df.iloc[0]
            top_agent_text = f"<strong>{top_agent['agent']}</strong> leading the active view bounds with an efficiency score of <strong>{top_agent['Performance_Score']}%</strong> across <strong>{top_agent['Tickets_Handled']}</strong> cases."
            
            # Filter for valid non-zero resolution times (> 0.05 hrs) to prevent 0.0h artifacts
            valid_resolvers = rankings_df[
                (rankings_df["Tickets_Handled"] >= 3) & 
                (rankings_df["Avg_Resolution_Hours"] > 0.05)
            ]
            if valid_resolvers.empty:
                valid_resolvers = rankings_df[rankings_df["Avg_Resolution_Hours"] > 0]
            if valid_resolvers.empty:
                valid_resolvers = rankings_df

            fastest_agent = valid_resolvers.sort_values(by="Avg_Resolution_Hours", ascending=True).iloc[0]
            fast_hrs = float(fastest_agent['Avg_Resolution_Hours'])
            fast_mins = int(fast_hrs * 60)
            speed_display = f"{fast_hrs:.2f} Hours ({fast_mins} Mins)" if fast_hrs < 1.0 else f"{fast_hrs:.1f} Hours"

            fastest_agent_text = f"<strong>{fastest_agent['agent']}</strong> leading response operations with a handling speed averaging <strong>{speed_display}</strong> per ticket."

        # Compile HTML
        html_content = AutomatedReportGenerator._build_html(
            total_tickets, compliance, total_breaches, total_effort_hrs,
            weekly_effort_hrs, monthly_effort_hrs, avg_effort_mins,
            top_agent_text, fastest_agent_text, indiv_util_df, selected_agent, date_range_str
        )

        filename = f"executive_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        report_path = REPORTS_DIR / filename
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return str(report_path)

    @staticmethod
    def compile_executive_pdf(html_path: str) -> str:
        if not html_path or not Path(html_path).exists():
            return ""

        pdf_path = html_path.replace(".html", ".pdf")
        options = {
            'page-size': 'A4',
            'orientation': 'Landscape',
            'margin-top': '0.4in',
            'margin-right': '0.4in',
            'margin-bottom': '0.4in',
            'margin-left': '0.4in',
            'encoding': "UTF-8",
            'enable-local-file-access': None,
            'no-outline': None
        }

        try:
            pdfkit.from_file(html_path, pdf_path, options=options)
            return pdf_path
        except Exception as e:
            print(f"❌ PDF Generation Error: {str(e)}")
            return ""

    @staticmethod
    def _build_html(total, compliance, breaches, total_effort, weekly_rate, monthly_cap, avg_effort, top_text, fast_text, util_df, scope, date_range):
        now_str = datetime.now().strftime('%d %b %Y, %H:%M')

        util_rows = ""
        if not util_df.empty:
            for i, row in util_df.reset_index(drop=True).iterrows():
                agent_name = row.get('agent', 'Unknown')
                tks = row.get('total_tickets', 0)
                tot_hrs = row.get('total_effort_hrs', 0.0)
                wk_hrs = row.get('weekly_hrs', 0.0)
                mo_hrs = row.get('monthly_hrs', 0.0)
                share = row.get('pod_share_pct', 0.0)
                projs = row.get('top_projects', 'N/A')

                util_rows += f"""
                <tr>
                    <td style="font-weight: 600; color: #1e293b;">{agent_name}</td>
                    <td style="text-align: center;">{tks}</td>
                    <td style="text-align: center;">{tot_hrs}</td>
                    <td style="text-align: center;">{wk_hrs}</td>
                    <td style="text-align: center;">{mo_hrs}</td>
                    <td style="text-align: center;">{share}%</td>
                    <td style="color: #334155; font-size: 10px; line-height: 1.4;">{projs}</td>
                </tr>
                """
        else:
            util_rows = "<tr><td colspan='7' style='text-align:center;'>No individual pod utilization records mapped.</td></tr>"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>US SRE Pod Executive Operations & Utilization Report</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
                
                body {{
                    font-family: 'Inter', Helvetica, Arial, sans-serif;
                    background-color: #ffffff;
                    color: #0f172a;
                    margin: 0;
                    padding: 24px;
                }}

                .header {{
                    border-bottom: 2px solid #e2e8f0;
                    padding-bottom: 12px;
                    margin-bottom: 20px;
                }}
                .header h1 {{ margin: 0 0 4px 0; font-size: 20px; font-weight: 700; color: #0f172a; }}
                .sub-author {{ font-size: 11px; color: #0284c7; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }}
                .meta-line {{ font-size: 11px; color: #64748b; margin: 0; }}

                .highlight-grid {{
                    width: 100%;
                    border-collapse: separate;
                    border-spacing: 12px;
                    margin-bottom: 12px;
                }}
                .highlight-card-green {{
                    background-color: #f0fdf4;
                    border: 1px solid #bbf7d0;
                    border-left: 4px solid #16a34a;
                    padding: 10px 14px;
                    border-radius: 6px;
                    font-size: 12px;
                    color: #15803d;
                }}
                .highlight-card-blue {{
                    background-color: #eff6ff;
                    border: 1px solid #bfdbfe;
                    border-left: 4px solid #2563eb;
                    padding: 10px 14px;
                    border-radius: 6px;
                    font-size: 12px;
                    color: #1d4ed8;
                }}

                .divider {{
                    height: 1px;
                    background-color: #e2e8f0;
                    margin: 20px 0;
                }}

                .metric-row {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }}
                .metric-cell {{
                    vertical-align: top;
                    padding-right: 20px;
                }}
                .metric-label {{
                    font-size: 11px;
                    color: #475569;
                    margin-bottom: 4px;
                }}
                .metric-value {{
                    font-size: 22px;
                    font-weight: 700;
                    color: #0f172a;
                }}

                .section-title {{
                    font-size: 15px;
                    font-weight: 700;
                    color: #0f172a;
                    margin: 0 0 4px 0;
                }}
                .section-subtitle {{
                    font-size: 11px;
                    color: #64748b;
                    margin: 0 0 12px 0;
                }}

                table.styled-table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 11px;
                    border-top: 1px solid #e2e8f0;
                }}
                table.styled-table th {{
                    background-color: #f8fafc;
                    color: #475569;
                    font-weight: 600;
                    padding: 8px 10px;
                    text-align: left;
                    border-bottom: 1px solid #cbd5e1;
                }}
                table.styled-table td {{
                    padding: 9px 10px;
                    border-bottom: 1px solid #f1f5f9;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Enterprise SRE Operations & Executive Intelligence Review</h1>
                <div class="sub-author">Developed by Team Gamma (US SRE Pod)</div>
                <p class="meta-line">Scope Target: <strong>{scope}</strong> | Date Range: <strong>{date_range}</strong> | Generated: {now_str}</p>
            </div>

            <!-- Top Highlight Cards -->
            <table class="highlight-grid">
                <tr>
                    <td width="50%" style="padding: 0;">
                        <div class="highlight-card-green">
                            {top_text if top_text else "Team top performer active scope calculated."}
                        </div>
                    </td>
                    <td width="50%" style="padding: 0;">
                        <div class="highlight-card-blue">
                            {fast_text if fast_text else "Fastest resolver active scope calculated."}
                        </div>
                    </td>
                </tr>
            </table>

            <div class="divider"></div>

            <!-- Row 1 Metrics -->
            <table class="metric-row">
                <tr>
                    <td width="33%" class="metric-cell">
                        <div class="metric-label">Total Tickets</div>
                        <div class="metric-value">{total}</div>
                    </td>
                    <td width="33%" class="metric-cell">
                        <div class="metric-label">SLA Compliance Rate Percentage</div>
                        <div class="metric-value">{compliance}%</div>
                    </td>
                    <td width="33%" class="metric-cell">
                        <div class="metric-label">Total SLA Resolution Breaches</div>
                        <div class="metric-value">{breaches} Failed</div>
                    </td>
                </tr>
            </table>

            <!-- Row 2 Metrics -->
            <table class="metric-row">
                <tr>
                    <td width="25%" class="metric-cell">
                        <div class="metric-label">Pod Total Effort (US SRE)</div>
                        <div class="metric-value">{total_effort} Hrs</div>
                    </td>
                    <td width="25%" class="metric-cell">
                        <div class="metric-label">Weekly Effort Rate</div>
                        <div class="metric-value">{weekly_rate} Hrs/Wk</div>
                    </td>
                    <td width="25%" class="metric-cell">
                        <div class="metric-label">Monthly Effort Capacity</div>
                        <div class="metric-value">{monthly_cap} Hrs/Mo</div>
                    </td>
                    <td width="25%" class="metric-cell">
                        <div class="metric-label">Avg Effort Per Ticket</div>
                        <div class="metric-value">{avg_effort} Mins</div>
                    </td>
                </tr>
            </table>

            <div class="divider"></div>

            <!-- Individual Engineer Time Utilization Table (With ALL Clients) -->
            <div>
                <div class="section-title">⏱️ Individual Engineer Time Utilization (US SRE Pod)</div>
                <div class="section-subtitle">Calculates individual engineer workload in hours: Total Time, Weekly Rate (Hrs/Wk), Monthly Capacity (Hrs/Mo), and Project Allocations.</div>
                
                <table class="styled-table">
                    <thead>
                        <tr>
                            <th style="width: 14%;">SRE Engineer</th>
                            <th style="width: 8%; text-align: center;">Tickets Handled</th>
                            <th style="width: 11%; text-align: center;">Total Effort (Hours)</th>
                            <th style="width: 11%; text-align: center;">Weekly Rate (Hrs/Wk)</th>
                            <th style="width: 11%; text-align: center;">Monthly Rate (Hrs/Mo)</th>
                            <th style="width: 10%; text-align: center;">Pod Workload Share</th>
                            <th style="width: 35%;">Project / Account Allocations (Hours)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {util_rows}
                    </tbody>
                </table>
            </div>

            <div class="divider"></div>
        </body>
        </html>
        """
