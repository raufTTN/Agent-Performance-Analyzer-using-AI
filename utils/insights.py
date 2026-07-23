from datetime import datetime
import pandas as pd
from config import REPORTS_DIR


class AutomatedReportGenerator:

    @staticmethod
    def compile_executive_html(df: pd.DataFrame, selected_agent: str = "All Agents") -> str:
        if df.empty:
            return "Execution skipped: Database scope currently empty."

        # Ensure df is filtered for the specific agent if it hasn't been already
        if selected_agent != "All Agents" and "agent" in df.columns:
            agent_df = df[df["agent"] == selected_agent].copy()
        else:
            agent_df = df.copy()

        total_tickets = len(agent_df)
        total_breaches = (
            int(agent_df["sla_breached"].sum())
            if "sla_breached" in agent_df.columns
            else 0
        )

        compliance = (
            round(((total_tickets - total_breaches) / total_tickets) * 100, 1)
            if total_tickets > 0
            else 100.0
        )

        avg_resolution = (
            round(agent_df["resolution_hours"].mean(), 2)
            if "resolution_hours" in agent_df.columns
            else 0
        )

        avg_effort = (
            round(agent_df["effort_mins"].mean(), 2)
            if "effort_mins" in agent_df.columns
            else 0
        )

        filename = f"Executive_Operations_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        target_path = REPORTS_DIR / filename

        if selected_agent != "All Agents":
            resolved = (
                len(agent_df[agent_df["status"].astype(str).str.lower().isin(["resolved", "closed"])])
                if "status" in agent_df.columns
                else 0
            )
            open_cases = total_tickets - resolved

        # ... Rest of individual agent HTML formatting using agent_df ...

        # ==================================================
        # INDIVIDUAL AGENT REPORT
        # ==================================================
        if selected_agent != "All Agents":

            resolved = (
                len(df[df["status"].astype(str).str.lower().isin(["resolved", "closed"])])
                if "status" in df.columns
                else 0
            )

            open_cases = total_tickets - resolved

            strengths = []

            if compliance >= 95:
                strengths.append("Excellent SLA compliance.")

            if avg_resolution <= 8:
                strengths.append("Fast ticket resolution.")

            if avg_effort <= 60:
                strengths.append("Efficient effort utilization.")

            improvements = []

            if compliance < 95:
                improvements.append("Improve SLA adherence.")

            if avg_resolution > 8:
                improvements.append("Reduce average resolution time.")

            if total_breaches > 0:
                improvements.append("Minimize SLA breaches.")

            if not strengths:
                strengths.append("Consistent operational contribution.")

            if not improvements:
                improvements.append("Maintain current performance standards.")

            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <style>
            body {{
                font-family: Arial;
                margin:40px;
                background:#f4f6f8;
            }}

            .card {{
                background:white;
                padding:25px;
                border-radius:10px;
                margin-bottom:20px;
            }}

            table {{
                width:100%;
                border-collapse:collapse;
            }}

            th,td {{
                padding:10px;
                border:1px solid #ddd;
            }}

            th {{
                background:#0d6efd;
                color:white;
            }}

            h2 {{
                color:#0d6efd;
            }}

            </style>
            </head>

            <body>

            <div class="card">

            <h2>Agent Performance Review</h2>

            <p><b>Agent :</b> {selected_agent}</p>

            <p><b>Generated :</b> {datetime.now().strftime('%d-%b-%Y %H:%M')}</p>

            </div>

            <div class="card">

            <h3>Performance Summary</h3>

            <table>

            <tr><th>Metric</th><th>Value</th></tr>

            <tr><td>Total Tickets</td><td>{total_tickets}</td></tr>

            <tr><td>Resolved Tickets</td><td>{resolved}</td></tr>

            <tr><td>Open Tickets</td><td>{open_cases}</td></tr>

            <tr><td>SLA Compliance</td><td>{compliance}%</td></tr>

            <tr><td>SLA Breaches</td><td>{total_breaches}</td></tr>

            <tr><td>Average Resolution Time</td><td>{avg_resolution} Hours</td></tr>

            <tr><td>Average Effort</td><td>{avg_effort} Minutes</td></tr>

            </table>

            </div>

            <div class="card">

            <h3>Key Strengths</h3>

            <ul>

            {''.join(f'<li>{x}</li>' for x in strengths)}

            </ul>

            </div>

            <div class="card">

            <h3>Areas for Improvement</h3>

            <ul>

            {''.join(f'<li>{x}</li>' for x in improvements)}

            </ul>

            </div>

            </body>

            </html>
            """

        # ==================================================
        # EXECUTIVE SUMMARY
        # ==================================================
        else:

            top_agents = (
                df.groupby("agent")
                .size()
                .sort_values(ascending=False)
                .head(10)
            )

            rows = ""

            for agent, count in top_agents.items():
                rows += f"<tr><td>{agent}</td><td>{count}</td></tr>"

            html = f"""
            <!DOCTYPE html>
            <html>
            <head>

            <style>

            body {{
                font-family:Arial;
                margin:40px;
                background:#f4f6f8;
            }}

            .card {{
                background:white;
                padding:25px;
                border-radius:10px;
                margin-bottom:20px;
            }}

            table {{
                width:100%;
                border-collapse:collapse;
            }}

            th,td {{
                border:1px solid #ddd;
                padding:10px;
            }}

            th {{
                background:#0d6efd;
                color:white;
            }}

            </style>

            </head>

            <body>

            <div class="card">

            <h2>Executive Operations Summary</h2>

            <table>

            <tr><th>Metric</th><th>Value</th></tr>

            <tr><td>Total Tickets</td><td>{total_tickets}</td></tr>

            <tr><td>SLA Compliance</td><td>{compliance}%</td></tr>

            <tr><td>SLA Breaches</td><td>{total_breaches}</td></tr>

            <tr><td>Average Resolution Time</td><td>{avg_resolution} Hours</td></tr>

            </table>

            </div>

            <div class="card">

            <h3>Top Contributors</h3>

            <table>

            <tr>
            <th>Agent</th>
            <th>Tickets Handled</th>
            </tr>

            {rows}

            </table>

            </div>

            </body>

            </html>
            """

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(html)

        return str(target_path)