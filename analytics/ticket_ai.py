import json
import requests
from config import OLLAMA_MODEL

class LocalTicketAnalyzer:
    """Invokes local model weights to perform deep technical and operational handoff audits."""
    
    def __init__(self, endpoint="http://localhost:11434/api/generate"):
        self.endpoint = endpoint
        self.model = OLLAMA_MODEL

    def run_ticket_forensics(self, ticket: dict) -> dict:
        private_notes = ticket.get("notes") or ticket.get("resolution_note") or "No worklogs captured."
        
        prompt = f"""
You are an elite Site Reliability Engineering (SRE) Lead and Operational Auditor.
Analyze the following incident metadata and private shift notes to identify operational mistakes, handoff gaps, or workflow process errors.

### TICKET DATA
- Ticket ID: {ticket.get('ticket_id')}
- Subject: {ticket.get('subject')}
- Assigned Agent: {ticket.get('agent')}
- Severity: {ticket.get('priority')}
- Resolution Time: {ticket.get('resolution_hours')} hours

### AGENT WORKLOGS / PRIVATE NOTES
"{private_notes}"

### INSTRUCTIONS
Please analyze the data and notes, then construct a clear JSON response containing exactly these three markdown keys:
1. "Handoff_Process_Mistakes": Audit the notes for mistakes like shift-overlap errors, tickets assigned after resolution, duplicate alerts, or incorrect shift routing.
2. "Technical_Root_Cause": Identify what happened technically (e.g., memory utilization alerts, system state, alarms).
3. "Workflow_Optimization_Plan": Provide actionable operational advice to prevent this specific handoff or technical slip in the future.

Your output must be strictly valid JSON. Do not include any pre-prose or post-prose outside the JSON structure.
"""
        try:
            response = requests.post(
                self.endpoint,
                json={"model": self.model, "prompt": prompt, "format": "json", "stream": False},
                timeout=30
            )
            if response.status_code == 200:
                raw_txt = response.json().get("response", "{}")
                parsed = json.loads(raw_txt)
                parsed["Raw"] = raw_txt
                return parsed
            else:
                return {"error": f"Local model offline. Status Code: {response.status_code}"}
        except Exception as e:
            return {"error": f"Inference pipeline error: {str(e)}"}
