import pandas as pd
from datetime import datetime
from config import REPORTS_DIR

class AutomatedReportGenerator:
    @staticmethod
    def compile_executive_html(df: pd.DataFrame) -> str:
        if df.empty:
            return "Execution skipped: Database scope currently empty."
            
        total_incidents = len(df)
        total_breaches = int(df["sla_breached"].sum()) if "sla_breached" in df.columns else 0
        compliance = round(((total_incidents - total_breaches) / total_incidents) * 100, 1) if total_incidents > 0 else 100.0
        
        filename = f"Executive_Operations_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        target_path = REPORTS_DIR / filename

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Operations Review</title>
            <style>
                body {{ font-family: sans-serif; margin: 40px; background: #f8f9fa; color: #212529; }}
                .card {{ background: white; padding: 24px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
                .metric {{ font-size: 42px; font-weight: bold; color: #0d6efd; margin-top: 10px; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
                th {{ background: #f1f3f5; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>🛡️ Executive SRE Operations Review</h2>
                <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Air-Gapped Secure Node</p>
                <hr>
                <table>
                    <tr><th>Parameter Description</th><th>Value Footprint</th></tr>
                    <tr><td>Total Logged Incidents Scope</td><td><strong>{total_incidents:,}</strong></td></tr>
                    <tr><td>Global Operational SLA Compliance Rate</td><td class="metric">{compliance}%</td></tr>
                    <tr><td>Total SLA Resolution Breaches Count</td><td style="color:#dc3545; font-weight:bold;">{total_breaches} Failed Cases</td></tr>
                </table>
            </div>
        </body>
        </html>
        """
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(html)
        return str(target_path)
