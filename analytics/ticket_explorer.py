# pyrefly: ignore [missing-import]
import streamlit as st
import pandas as pd
from analytics.ticket_ai import LocalTicketAnalyzer
from ai.rag_engine import LocalTicketVectorStore

def show_ai_investigator_ui(df: pd.DataFrame):
    """Renders the forensic analysis panel with operational handoff and mistake audit logic."""
    st.markdown("---")
    st.subheader("🔍 Deep Ticket Forensics Explorer & AI Auditor")
    st.caption("Secured local LLM processing layer + native vector lookup. Zero network dependencies.")

    target_id = st.text_input("Enter target Ticket ID to spin up deep forensic loop:", key="explorer_id_input")

    if target_id:
        match = df[df["ticket_id"].astype(str) == str(target_id)]
        if not match.empty:
            ticket = match.iloc[0].to_dict()
            
            # --- EXTRACT METRICS ---
            priority = str(ticket.get('priority', 'N/A')).upper()
            status = str(ticket.get('status', 'N/A'))
            
            resolved_time_raw = ticket.get('resolved_time')
            closure_time_str = "Not Closed Yet"
            if resolved_time_raw and pd.notna(resolved_time_raw):
                try:
                    dt = pd.to_datetime(resolved_time_raw)
                    if pd.notna(dt):
                        closure_time_str = dt.strftime("%d %b %Y, %I:%M %p")
                except Exception:
                    closure_time_str = "N/A"
                    
            effort_mins = ticket.get('effort_mins', 0.0)
            sla_breached = ticket.get('sla_breached', 0)
            sla_status_text = "🚨 BREACHED" if sla_breached == 1 else "✅ WITHIN SLA"
            
            st.info(f"**Loaded Case:** {ticket.get('subject')} | **Engineer Assigned:** {ticket.get('agent')}")
            
            # Use columns to present the structural metadata cleanly
            m1, m2, m3, m4, m5 = st.columns([1, 1, 1.5, 1, 1])
            m1.metric("SLA Status", sla_status_text)
            m2.metric("Severity Tier", priority)
            
            with m3:
                st.markdown("<p style='font-size: 14px; color: gray; margin-bottom: 0;'>Ticket Closure Time</p>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size: 1.5rem; font-weight: bold; white-space: nowrap;'>{closure_time_str}</div>", unsafe_allow_html=True)
                
            m4.metric("Effort Required (Mins)", f"{effort_mins:.1f} Mins")
            m5.metric("Ticket State Status", status)
            
            st.markdown("<br>", unsafe_allow_html=True)
            

        else:
            st.error("Ticket ID not discovered inside the current operational scope.")