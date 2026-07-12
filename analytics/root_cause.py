import pandas as pd
import requests
import re
from config import OLLAMA_API_URL, OLLAMA_MODEL, LLM_TIMEOUT

class SystemicRootCauseEngine:
    def __init__(self):
        self.url = OLLAMA_API_URL
        self.model = OLLAMA_MODEL

    def cluster_and_analyze_patterns(self, df: pd.DataFrame) -> str:
        """Aggregates high-frequency noise items to drive local AI analytics passes efficiently."""
        if df.empty or 'subject' not in df.columns:
            return "Insufficient incident record history available to run systemic analytics."

        # Normalize casing parameters
        df['cleaned_subject'] = df['subject'].astype(str).str.lower().str.strip()
        top_patterns = df['cleaned_subject'].value_counts().head(5)
        
        pattern_summary_lines = []
        for phrase, count in top_patterns.items():
            pattern_summary_lines.append(f"- Incident Pattern: '{phrase}' occurred {count} times.")
            
        compiled_clusters_str = "\n".join(pattern_summary_lines)

        prompt = f"""
You are a Principal Enterprise Systems Architect. Analyze these high-frequency incident noise patterns:
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
                "num_predict": 300
            }
        }

        try:
            res = requests.post(self.url, json=payload, timeout=LLM_TIMEOUT)
            if res.status_code == 200:
                return res.json().get('response', '')
            return f"Ollama HTTP Processing Error Code: {res.status_code}"
        except Exception as e:
            return f"Systemic AI Infrastructure Connection Failure: {str(e)}"
