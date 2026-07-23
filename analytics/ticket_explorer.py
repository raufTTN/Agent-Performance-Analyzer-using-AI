import streamlit as st
import pandas as pd
from analytics.ticket_ai import LocalTicketAnalyzer
from ai.rag_engine import LocalTicketVectorStore

def show_ai_investigator_ui(df: pd.DataFrame):
    """Renders the internal ticket audit panel augmented with detailed metric previews and RAG vector matching."""
    st.markdown("---")
    st.subheader("🔍 Deep Ticket Forensics Explorer & AI Auditor")
    st.caption("Secured local LLM processing layer + native vector lookup. Zero network dependencies.")

    target_id = st.text_input("Enter target Ticket ID to spin up deep forensic loop:", key="explorer_id_input")

    if target_id:
        match = df[df["ticket_id"].astype(str) == str(target_id)]
        if not match.empty:
            ticket = match.iloc[0].to_dict()
            
            # --- EXTRACT METRIC PARTICULARS ---
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
            
            # Determine dynamic badge formatting for the SLA target status
            sla_breached = ticket.get('sla_breached', 0)
            sla_status_text = "🚨 BREACHED" if sla_breached == 1 else "✅ WITHIN SLA"
            
            # --- RENDER ENHANCED METRIC HUD BLOCK ---
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
            
            col_actions1, col_actions2 = st.columns(2)
            
            with col_actions1:
                if st.button("🚀 Execute Forensic Ingestion Audit", width="stretch"):
                    with st.spinner("Invoking local LLM model weights..."):
                        analyzer = LocalTicketAnalyzer()
                        findings = analyzer.run_ticket_forensics(ticket)
                        
                        if "error" in findings:
                            st.error(findings["error"])
                        else:
                            st.success("Analysis Complete.")
                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown("### 📋 Incident Diagnostics")
                                st.markdown(f"**Incident Summary:**\n{findings.get('Incident Summary')}")
                                st.markdown(f"**Root Cause Analysis:**\n{findings.get('Root Cause Analysis')}")
                            with c2:
                                st.markdown("### 🛠️ Handling Quality Review")
                                st.markdown(f"**Resolution Quality Review:**\n{findings.get('Resolution Quality Review')}")
                                
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