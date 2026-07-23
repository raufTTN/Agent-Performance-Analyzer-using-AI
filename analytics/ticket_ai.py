import requests
import re
from config import OLLAMA_API_URL, OLLAMA_MODEL, LLM_TIMEOUT, MAX_TEXT_WINDOW

class LocalTicketAnalyzer:
    def __init__(self):
        self.url = OLLAMA_API_URL
        self.model = OLLAMA_MODEL

    def _clean_and_truncate(self, text: str) -> str:
        if not text:
            return "N/A"
        clean = re.sub(r"\s+", " ", str(text)).strip()
        return clean[:MAX_TEXT_WINDOW] + "... [Truncated]" if len(clean) > MAX_TEXT_WINDOW else clean

    def run_ticket_forensics(self, ticket: dict) -> dict:
        clean_desc = self._clean_and_truncate(ticket.get("description", ""))
        clean_note = self._clean_and_truncate(ticket.get("resolution_note", ""))
        
        prompt = f"""
You are a Senior SRE Director auditing ticket resolution metrics. Review the log details below and draft a brief summary matching the exact sections requested.

TICKET FORENSICS
- ID: {ticket.get('ticket_id')}
- Assigned Agent: {ticket.get('agent')}
- Priority: {ticket.get('priority')}
- Subject: {ticket.get('subject')}
- Description Logs: {clean_desc}
- Resolution Applied: {clean_note}

REQUIRED RESPONSE FORMAT:
Provide your analysis broken down into these EXACT 3 sections enclosed in brackets. Keep it concise.

[INCIDENT SUMMARY]
(What broke and who it impacted)

[ROOT CAUSE ANALYSIS]
(The technical underlying system failure)

[RESOLUTION QUALITY REVIEW]
(Critique of the fix path applied by the engineer)
"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 450}
        }

        try:
            res = requests.post(self.url, json=payload, timeout=LLM_TIMEOUT)
            if res.status_code == 200:
                raw = res.json().get("response", "")
                return self._parse_output(raw)
            return {"error": f"Ollama HTTP Failure: {res.status_code}"}
        except Exception as e:
            return {"error": f"Inference pipeline error: {str(e)}"}

    def _parse_output(self, text: str) -> dict:
        regions = {"Summary": "Incident Summary", "Root_Cause": "Root Cause Analysis", "Review": "Resolution Quality Review"}
        patterns = {
            "Summary": r"\[INCIDENT\s+SUMMARY\](.*?)(?=\[ROOT|$)",
            "Root_Cause": r"\[ROOT\s+CAUSE\s+ANALYSIS\](.*?)(?=\[RESOLUTION|$)",
            "Review": r"\[RESOLUTION\s+QUALITY\s+REVIEW\](.*)$"
        }
        extracted = {}
        for k, p in patterns.items():
            m = re.search(p, text, re.DOTALL | re.IGNORECASE)
            extracted[regions[k]] = m.group(1).strip() if m else "Analysis section extraction boundary missed."
        extracted["Raw"] = text
        return extracted
