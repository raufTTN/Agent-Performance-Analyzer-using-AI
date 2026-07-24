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
    def compile_executive_html(df: pd.DataFrame, selected_agent: str = "All Agents") -> str:
        """
        Compiles all scoped metrics, agent scorecards, and AI remarks into a standalone HTML report.
        """
        if df.empty:
            return ""

        # Filter dataset for specific agent if requested
        if selected_agent != "All Agents" and "agent" in df.columns:
            agent_df = df[df["agent"] == selected_agent].copy()
        else:
            agent_df = df.copy()

        # Extract Date Range dynamically
        if "created_dt" in agent_df.columns and not agent_df["created_dt"].dropna().empty:
            min_d = agent_df["created_dt"].min().strftime('%d %b %Y')
            max_d = agent_df["created_dt"].max().strftime('%d %b %Y')
            date_range_str = f"{min_d} – {max_d}"
        else:
            date_range_str = "Full History Scope"

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

        # 5. Build HTML Content
        html_content = AutomatedReportGenerator._build_html(
            total_tickets, compliance, total_breaches, avg_resolution, total_effort,
            total_sr, total_incidents, agent_rankings, ai_remarks,
            company_dist, priority_dist, type_dist, selected_agent, date_range_str
        )

        filename = f"executive_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        report_path = REPORTS_DIR / filename
        
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
            'no-outline': None
        }

        try:
            pdfkit.from_file(html_path, pdf_path, options=options)
            return pdf_path
        except Exception as e:
            print(f"❌ PDF Generation Error: {str(e)}")
            return ""

    @staticmethod
    def _build_html(total, compliance, breaches, avg_res, total_effort, total_sr, total_incidents, agent_rankings, remarks, c_dist, p_dist, t_dist, scope, date_range):
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

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Enterprise SRE & IT Operations Intelligence Report</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
                
                @page {{
                    size: A4;
                    margin: 0.8cm;
                }}

                body {{
                    font-family: 'Inter', Helvetica, Arial, sans-serif;
                    background-color: #ffffff;
                    color: #0f172a;
                    margin: 0;
                    padding: 10px;
                }}
                
                .header {{
                    background: #0f172a;
                    color: #ffffff;
                    padding: 20px 25px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }}
                
                .header h1 {{ margin: 0 0 4px 0; font-size: 22px; font-weight: 700; }}
                .sub-author {{ margin: 0 0 10px 0; font-size: 11px; color: #38bdf8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
                .header p {{ margin: 0; color: #cbd5e1; font-size: 12px; }}
                
                .grid-kpi {{
                    width: 100%;
                    margin-bottom: 20px;
                    border-collapse: separate;
                    border-spacing: 10px;
                }}

                .card {{
                    background: #f8fafc;
                    padding: 15px;
                    border-radius: 8px;
                    border: 1px solid #e2e8f0;
                }}
                
                .card-title {{
                    font-size: 11px;
                    text-transform: uppercase;
                    font-weight: 600;
                    color: #64748b;
                    margin-bottom: 6px;
                }}
                
                .card-value {{
                    font-size: 20px;
                    font-weight: 700;
                    color: #0f172a;
                }}
                
                .badge {{
                    display: inline-block;
                    padding: 2px 8px;
                    border-radius: 10px;
                    font-size: 10px;
                    font-weight: 600;
                }}
                .badge-success {{ background: #dcfce7; color: #166534; }}
                .badge-danger {{ background: #fee2e2; color: #991b1b; }}
                .badge-info {{ background: #e0f2fe; color: #0369a1; }}
                
                table.data-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                    border: 1px solid #e2e8f0;
                }}
                
                table.data-table th, table.data-table td {{
                    padding: 10px 12px;
                    text-align: left;
                    border-bottom: 1px solid #e2e8f0;
                    font-size: 12px;
                }}
                
                table.data-table th {{
                    background-color: #f1f5f9;
                    font-weight: 600;
                    text-transform: uppercase;
                    color: #475569;
                }}
                
                tr.row-alt {{ background-color: #f8fafc; }}
                
                .section-title {{
                    font-size: 15px;
                    font-weight: 700;
                    margin-top: 0;
                    margin-bottom: 12px;
                    color: #0f172a;
                    border-bottom: 2px solid #e2e8f0;
                    padding-bottom: 6px;
                }}
                
                ul {{ margin: 0; padding-left: 18px; color: #475569; font-size: 12px; }}
                li {{ margin-bottom: 4px; }}
            </style>
        </head>
        <body>
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
        </body>
        </html>
        """
