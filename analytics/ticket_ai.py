"""
Local Ticket AI Diagnostics Module
Provides local LLM inference via Ollama for SRE and IT operations ticket forensics.
"""

import json
import logging
import requests
from config import OLLAMA_API_URL, OLLAMA_MODEL, LLM_TIMEOUT, MAX_TEXT_WINDOW

logger = logging.getLogger("LocalTicketAnalyzer")


class LocalTicketAnalyzer:
    """Invokes local Ollama inference models for operational ticket forensics and handoff audit."""

    def __init__(self):
        self.api_url = OLLAMA_API_URL
        self.model = OLLAMA_MODEL
        self.timeout = LLM_TIMEOUT  # Set to 180 seconds from config.py

    def run_ticket_forensics(self, ticket: dict) -> dict:
        """Runs deep forensic evaluation on a single ticket dictionary using local Ollama LLM.

        Args:
            ticket (dict): Dictionary containing ticket attributes (subject, agent, notes, etc.)

        Returns:
            dict: Structured analysis containing technical root cause, handoff mistakes, and optimization plan.
        """
        # Truncate notes if they exceed max window safety limits
        notes_text = str(ticket.get("notes") or ticket.get("resolution_note") or "No notes provided")
        if len(notes_text) > MAX_TEXT_WINDOW:
            notes_text = notes_text[:MAX_TEXT_WINDOW] + "... [Truncated]"

        prompt = f"""
You are an expert SRE and IT Operations Forensic Auditor.
Analyze the following ticket details and agent private notes for process mistakes, handoff failures, shift transfer errors, or technical root causes.

TICKET METADATA:
- Ticket ID: {ticket.get('ticket_id', 'N/A')}
- Subject: {ticket.get('subject', 'N/A')}
- Assigned Engineer: {ticket.get('agent', 'N/A')}
- Priority / Severity: {ticket.get('priority', 'N/A')}
- Current Status: {ticket.get('status', 'N/A')}
- Private Worklogs & Notes: {notes_text}

INSTRUCTIONS:
1. Identify the Technical Root Cause behind the incident.
2. Audit the Private Worklogs for Handoff or Operational Mistakes (e.g., ticket resolved in morning shift but assigned again in afternoon, lack of communication, missed escalation steps).
3. Provide a concrete Workflow Optimization Plan to avoid this mistake in future shifts.

Return your analysis strictly as a JSON object matching this schema:
{{
    "Technical_Root_Cause": "Clear explanation of technical issue",
    "Handoff_Process_Mistakes": "Detailed audit of handoff errors or operational mistakes found in worklogs/notes",
    "Workflow_Optimization_Plan": "Steps to prevent this operational or handoff issue in the future"
}}
"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }

        try:
            logger.info(f"Invoking Ollama inference at {self.api_url} with timeout={self.timeout}s...")
            
            # Request execution with 180s timeout
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()

            raw_response = response.json().get("response", "")

            # Attempt to parse output cleanly
            try:
                # Clean up markdown tags if present
                clean_json_str = raw_response.strip()
                if clean_json_str.startswith("```json"):
                    clean_json_str = clean_json_str[7:]
                if clean_json_str.startswith("```"):
                    clean_json_str = clean_json_str[3:]
                if clean_json_str.endswith("```"):
                    clean_json_str = clean_json_str[:-3]

                parsed_data = json.loads(clean_json_str.strip())
                parsed_data["Raw"] = raw_response
                return parsed_data

            except json.JSONDecodeError:
                # Fallback if model fails strict JSON output
                return {
                    "Technical_Root_Cause": "Raw response generated (non-JSON format).",
                    "Handoff_Process_Mistakes": raw_response,
                    "Workflow_Optimization_Plan": "Review raw logs below for actionable items.",
                    "Raw": raw_response
                }

        except requests.exceptions.Timeout:
            logger.error(f"Ollama inference timed out after {self.timeout} seconds.")
            return {
                "error": f"Inference pipeline timed out (> {self.timeout}s). Try running 'ollama run {self.model} \"\" --keepalive 2h' in your terminal to keep the model pre-loaded in memory."
            }

        except requests.exceptions.ConnectionError:
            logger.error(f"Failed to connect to Ollama server at {self.api_url}.")
            return {
                "error": f"Cannot connect to local Ollama server at {self.api_url}. Please ensure Ollama is running (`ollama serve`)."
            }

        except Exception as e:
            logger.error(f"Unexpected error during inference: {e}")
            return {"error": f"Inference pipeline error: {str(e)}"}
