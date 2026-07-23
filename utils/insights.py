import pandas as pd
from datetime import datetime
import json
import requests
from config import REPORTS_DIR, OLLAMA_API_URL, OLLAMA_MODEL, LLM_TIMEOUT
from analytics.scoring import OperationsLeaderboardScorer

class AutomatedReportGenerator:
    @staticmethod
    def generate_rich_executive_report(df: pd.DataFrame, selected_agent: str = "All Agents") -> dict:
        if df.empty:
            return {"error": "Execution skipped: Database scope currently empty."}

        # Handle agent filtering
        if selected_agent != "All Agents" and "agent" in df.columns:
            agent_df = df[df["agent"] == selected_agent].copy()
        else:
            agent_df = df.copy()
            
        if agent_df.empty:
            return {"error": f"No data found for agent: {selected_agent}"}

        # 1. Compute Global KPIs
        total_tickets = len(agent_df)
        total_breaches = int(agent_df["sla_breached"].sum()) if "sla_breached" in agent_df.columns else 0
        compliance = round(((total_tickets - total_breaches) / total_tickets) * 100, 1) if total_tickets > 0 else 100.0
        avg_resolution = round(agent_df["resolution_hours"].mean(), 2) if "resolution_hours" in agent_df.columns else 0
        total_effort = round(agent_df["effort_mins"].sum(), 0) if "effort_mins" in agent_df.columns else 0
        
        # 2. Categorical & Company Distribution
        def get_dist(col_name):
            if col_name in agent_df.columns:
                return agent_df[col_name].value_counts().to_dict()
            return {}

        company_col = "company" if "company" in agent_df.columns else "status"
        company_dist = get_dist(company_col)
        priority_dist = get_dist("priority")
        type_dist = get_dist("ticket_type") if "ticket_type" in agent_df.columns else {}
        
        # 3. Per-Agent Breakdown
        agent_rankings = pd.DataFrame()
        if "agent" in agent_df.columns:
            agent_rankings = OperationsLeaderboardScorer.compile_weighted_rankings(agent_df, context_type="All Types (SR & Incident)")
            
        # 4. Generate AI Remarks
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
                    ai_remarks = json.loads(res.json().get('response', '{}'))
            except Exception:
                pass
                
        # 5. Build HTML Report (CSS Grid & Print Styles)
        html_content = AutomatedReportGenerator._build_html(
            total_tickets, compliance, total_breaches, avg_resolution, total_effort,
            agent_rankings, ai_remarks, company_dist, priority_dist, type_dist, selected_agent
        )
        
        # 6. PDF Generation Fallback
        pdf_bytes = None
        try:
            from xhtml2pdf import pisa
            import io
            result = io.BytesIO()
            # xhtml2pdf requires string or file-like object
            pdf = pisa.pisaDocument(io.StringIO(html_content), result)
            if not pdf.err:
                pdf_bytes = result.getvalue()
        except ImportError:
            pass

        return {
            "html": html_content,
            "pdf": pdf_bytes
        }

    @staticmethod
    def _build_html(total, compliance, breaches, avg_res, total_effort, agent_rankings, remarks, c_dist, p_dist, t_dist, scope):
        now_str = datetime.now().strftime('%d %b %Y, %H:%M')
        
        # Generate rows for agent table
        agent_rows = ""
        for _, row in agent_rankings.iterrows():
            agent_name = row['agent']
            score = row.get('Performance_Score', 'N/A')
            vol = row.get('Tickets_Handled', 0)
            res_hr = row.get('Avg_Resolution_Hours', 0)
            remark = remarks.get(agent_name, "Solid operational performance.")
            
            agent_rows += f"""
            <tr>
                <td><strong>{agent_name}</strong></td>
                <td>{score}</td>
                <td>{vol}</td>
                <td>{res_hr} hrs</td>
                <td style="font-size: 0.9em; color: #555;">{remark}</td>
            </tr>
            """
            
        def dict_to_html_list(d):
            if not d: return "<li>No data available</li>"
            return "".join([f"<li><strong>{k}:</strong> {v}</li>" for k,v in list(d.items())[:5]])

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Executive Operations Review</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
                
                body {{
                    font-family: 'Inter', sans-serif;
                    background-color: #f8fafc;
                    color: #0f172a;
                    margin: 0;
                    padding: 40px;
                }}
                
                .header {{
                    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 12px;
                    margin-bottom: 30px;
                    box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
                }}
                
                .header h1 {{ margin: 0 0 10px 0; font-size: 28px; }}
                .header p {{ margin: 0; color: #94a3b8; font-size: 14px; }}
                
                .grid-kpi {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                
                .card {{
                    background: white;
                    padding: 24px;
                    border-radius: 12px;
                    box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
                    border: 1px solid #e2e8f0;
                }}
                
                .card-title {{
                    font-size: 13px;
                    text-transform: uppercase;
                    font-weight: 600;
                    color: #64748b;
                    margin-bottom: 10px;
                }}
                
                .card-value {{
                    font-size: 28px;
                    font-weight: 700;
                    color: #0f172a;
                }}
                
                .badge {{
                    display: inline-block;
                    padding: 4px 10px;
                    border-radius: 999px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                .badge-success {{ background: #dcfce7; color: #166534; }}
                .badge-danger {{ background: #fee2e2; color: #991b1b; }}
                
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }}
                
                th, td {{
                    padding: 12px 16px;
                    text-align: left;
                    border-bottom: 1px solid #e2e8f0;
                }}
                
                th {{
                    background-color: #f1f5f9;
                    font-size: 13px;
                    text-transform: uppercase;
                    color: #475569;
                }}
                
                .grid-dist {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    margin-top: 30px;
                }}
                
                ul {{ margin: 0; padding-left: 20px; color: #475569; }}
                li {{ margin-bottom: 8px; }}
                
                @media print {{
                    body {{ background: white; padding: 0; }}
                    .card {{ box-shadow: none; border: 1px solid #ccc; break-inside: avoid; }}
                    .header {{ background: #0f172a; color: white; print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Executive Operations Analytics Review</h1>
                <p>Scope: {scope} | Generated: {now_str}</p>
            </div>
            
            <div class="grid-kpi">
                <div class="card">
                    <div class="card-title">Total Handled</div>
                    <div class="card-value">{total}</div>
                </div>
                <div class="card">
                    <div class="card-title">SLA Compliance</div>
                    <div class="card-value">
                        {compliance}% 
                        <span class="badge {'badge-success' if compliance >= 90 else 'badge-danger'}">
                            {breaches} Breaches
                        </span>
                    </div>
                </div>
                <div class="card">
                    <div class="card-title">Avg Resolution Time</div>
                    <div class="card-value">{avg_res} <span style="font-size:16px; color:#64748b;">Hrs</span></div>
                </div>
                <div class="card">
                    <div class="card-title">Total Effort Spent</div>
                    <div class="card-value">{total_effort} <span style="font-size:16px; color:#64748b;">Mins</span></div>
                </div>
            </div>
            
            <div class="card">
                <h3 style="margin-top: 0; color: #0f172a;">Engineering Scorecard & AI Remarks</h3>
                <table>
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
            
            <div class="grid-dist">
                <div class="card">
                    <h3 style="margin-top: 0; color: #0f172a;">Top Associated Companies</h3>
                    <ul>{dict_to_html_list(c_dist)}</ul>
                </div>
                <div class="card">
                    <h3 style="margin-top: 0; color: #0f172a;">Workload Distribution</h3>
                    <ul>
                        <li><strong>By Priority:</strong></li>
                        <ul>{dict_to_html_list(p_dist)}</ul>
                        <li style="margin-top: 10px;"><strong>By Type:</strong></li>
                        <ul>{dict_to_html_list(t_dist)}</ul>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
