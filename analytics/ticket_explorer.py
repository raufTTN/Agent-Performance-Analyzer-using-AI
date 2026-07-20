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
            res_hours = ticket.get('resolution_hours', 0.0)
            effort_mins = ticket.get('effort_mins', 0.0)
            sla_breached = ticket.get('sla_breached', 0)
            sla_status_text = "🚨 BREACHED" if sla_breached == 1 else "✅ WITHIN SLA"
            
            st.info(f"**Loaded Case:** {ticket.get('subject')} | **Engineer Assigned:** {ticket.get('agent')}")
            
            # Display HUD Row
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("SLA Status", sla_status_text)
            m2.metric("Severity Tier", priority)
            m3.metric("Resolution Time (Hrs)", f"{res_hours:.2f} Hrs")
            m4.metric("Effort Required (Mins)", f"{effort_mins:.1f} Mins")
            m5.metric("Ticket State Status", status)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- AGENT NOTES & PRIVATE WORKLOG INPUT ---
            st.markdown("##### 📝 Private Notes & Operational Worklogs")
            default_note = ticket.get("notes") or ticket.get("resolution_note") or "This ticket was resolved in morning shift but still it was given in afternoon shift"
            user_notes = st.text_area(
                "Modify or paste agent notes / private worklogs here to audit for handoff or operational mistakes:",
                value=default_note,
                height=100
            )
            # Update ticket dict dynamically for prompt context injection
            ticket["notes"] = user_notes
            
            col_actions1, col_actions2 = st.columns(2)
            
            with col_actions1:
                if st.button("🚀 Execute Forensic Ingestion Audit", width="stretch"):
                    with st.spinner("Invoking local LLM model weights..."):
                        analyzer = LocalTicketAnalyzer()
                        findings = analyzer.run_ticket_forensics(ticket)
                        
                        if "error" in findings:
                            st.error(findings["error"])
                        else:
                            st.success("Operational & Technical Audit Complete.")
                            
                            # RENDER PROCESS AUDIT (Highlights handoff mistakes cleanly via warning banner)
                            st.markdown("### ⚠️ Process Gaps & Handoff Audit")
                            handoff_slip = findings.get("Handoff_Process_Mistakes") or "No obvious handoff mistakes detected in notes."
                            st.warning(handoff_slip)
                            
                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown("### 📋 Incident Diagnostics")
                                st.markdown(f"**Technical Root Cause:**\n{findings.get('Technical_Root_Cause')}")
                            with c2:
                                st.markdown("### 🛠️ Process Improvement")
                                st.markdown(f"**Workflow Optimization Plan:**\n{findings.get('Workflow_Optimization_Plan')}")
                                
                            with st.expander("View Raw LLM Unparsed Generative Output"):
                                st.code(findings.get("Raw"))
                                
            with col_actions2:
                if st.button("🧠 Surface Similar Historical Solved Tickets", width="stretch"):
                    with st.spinner("Calculating vector similarity distances natively..."):
                        v_store = LocalTicketVectorStore()
                        similar_cases = v_store.surface_similar_resolutions(
                            ticket.get("subject", ""), 
                            ticket.get("description", "")
                        )
                        
                        if not similar_cases:
                            st.warning("No semantically overlapping historical cases found inside local database.")
                        else:
                            st.success(f"Discovered {len(similar_cases)} relevant matching incident profiles:")
                            for idx, case in enumerate(similar_cases):
                                with st.container():
                                    st.markdown(f"##### {idx+1}. Ticket #{case['ticket_id']} (Match Confidence: {case['confidence']}% )")
                                    st.markdown(f"**Subject Alignment:** {case['subject']}")
                                    st.markdown(f"**Verified Fix Applied by {case['agent']}:**")
                                    st.info(case['resolution_note'])
                                    st.markdown("---")
        else:
            st.error("Ticket ID not discovered inside the current operational scope.")