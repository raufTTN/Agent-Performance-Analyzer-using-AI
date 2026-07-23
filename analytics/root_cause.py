import pandas as pd
import requests
import re
from config import OLLAMA_API_URL, OLLAMA_MODEL, LLM_TIMEOUT

class SystemicRootCauseEngine:
    def __init__(self):
        self.url = OLLAMA_API_URL
        self.model = OLLAMA_MODEL

    def cluster_and_analyze_patterns(self, df: pd.DataFrame) -> dict:
        """Aggregates high-frequency noise items to drive local AI analytics passes efficiently."""
        if df.empty or 'subject' not in df.columns:
            return {"error": "Insufficient incident record history available to run systemic analytics."}

        df_local = df.copy()
        company_col = 'company' if 'company' in df_local.columns else 'status'
        if company_col not in df_local.columns:
            df_local['fallback_company'] = 'Unknown'
            company_col = 'fallback_company'

        # Normalize casing parameters
        df_local['cleaned_subject'] = df_local['subject'].astype(str).str.strip()
        
        # Group by cleaned_subject and company_col to get top 5 patterns
        grouped = df_local.groupby(['cleaned_subject', company_col]).size().reset_index(name='count')
        top_5 = grouped.sort_values(by='count', ascending=False).head(5)
        
        top_alerts = []
        pattern_summary_lines = []
        for idx, row in enumerate(top_5.itertuples(), start=1):
            subject = row.cleaned_subject
            company = getattr(row, company_col)
            count = row.count
            
            top_alerts.append({
                "Rank": idx,
                "Target Company Context": company,
                "Alert Subject": subject,
                "Total Occurrence Count": count
            })
            pattern_summary_lines.append(f"- Rank {idx}: '{subject}' (Company/Context: {company}) occurred {count} times.")
            
        compiled_clusters_str = "\n".join(pattern_summary_lines)

        prompt = f"""
You are a Principal Enterprise Systems Architect. Analyze these Top 5 high-frequency incident noise patterns:
{compiled_clusters_str}

Provide a brief evaluation broken down into these three sections using brackets:
[EFFICIENCY BOTTLENECK ANALYSIS]
(Suggest alerting threshold adjustments or automated suppression rules)

[SECURITY POSTURE ASSESSMENT]
(Evaluate if any indicate configuration drifts or security gaps)

[AUTOMATION PLAYBOOK RECOMMENDATIONS]
(Provide actionable recommendations to reduce manual human effort)
"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 400
            }
        }

        ai_summary = ""
        try:
            res = requests.post(self.url, json=payload, timeout=LLM_TIMEOUT)
            if res.status_code == 200:
                ai_summary = res.json().get('response', '')
            else:
                ai_summary = f"Ollama HTTP Processing Error Code: {res.status_code}"
        except Exception as e:
            ai_summary = f"Systemic AI Infrastructure Connection Failure: {str(e)}"
            
        return {
            "top_alerts": top_alerts,
            "insights": ai_summary
        }