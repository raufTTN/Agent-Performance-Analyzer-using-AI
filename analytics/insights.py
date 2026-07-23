import requests
from config import OLLAMA_API_URL, OLLAMA_MODEL, LLM_TIMEOUT

class LocalAgentCoachingEngine:
    def __init__(self):
        self.url = OLLAMA_API_URL
        self.model = OLLAMA_MODEL

    def build_agent_coaching_matrix(self, agent_name: str, tickets: list) -> str:
        if not tickets:
            return "No baseline history records located for this target engineer context."
            
        summary_stack = []
        for idx, t in enumerate(tickets[:5]):
            summary_stack.append(f"Case {idx+1} | Subject: {t.get('subject')} | Resolution Note: {t.get('resolution_note')}")
        compiled_cases = "\n".join(summary_stack)

        prompt = f"""
You are an Elite Technical Operations Director compiling a professional evaluation profile.
Review the resolution notes for Engineer: '{agent_name}' and provide structured, actionable coaching assessments.

TICKET FOOTPRINT OVERVIEW:
{compiled_cases}

REQUIRED OUTPUT FORMAT:
[ENGINEER STRENGTHS]
(Highlight technical domains or systems they handle efficiently)

[DOCUMENTATION QUALITY REVIEW]
(Provide clear feedback on log recording accuracy and runbook detail usage patterns)

[TARGETED RECOMMENDATIONS]
(Suggest specific operational runbooks or code domains they should study next)
"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 500}
        }
        try:
            res = requests.post(self.url, json=payload, timeout=LLM_TIMEOUT)
            return res.json().get("response", "Inference error.") if res.status_code == 200 else "HTTP error."
        except Exception as e:
            return f"Coaching pipeline connection error: {str(e)}"