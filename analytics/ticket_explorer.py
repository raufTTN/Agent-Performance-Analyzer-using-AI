# pyrefly: ignore [missing-import]
import streamlit as st
import pandas as pd
from analytics.ticket_ai import LocalTicketAnalyzer
from ai.rag_engine import LocalTicketVectorStore


def validate_freshservice_fields(ticket: dict) -> dict:
    """
    Validates ticket fields based on standard Freshservice requirements.
    Detects missing mandatory fields, invalid defaults ('--', 'nan'), and empty inputs.
    """
    invalid_tokens = ["", "nan", "none", "--", "null", "undefined", "n/a"]

    # Mandatory Fields definition mapped across potential column name variations
    fields_to_check = {
        "Group": ticket.get("ticket_group") or ticket.get("group"),
        "Priority / Urgency": ticket.get("priority") or ticket.get("urgency"),
        "Company": ticket.get("company"),
        "Ticket Type": ticket.get("ticket_type") or ticket.get("type"),
        "Category": ticket.get("category"),
    }

    missing_mandatory = []
    for field_name, val in fields_to_check.items():
        if not val or str(val).strip().lower() in invalid_tokens:
            missing_mandatory.append(field_name)

    # Secondary / Quality Warnings
    quality_warnings = []

    # Sub-Category Check (Checks if defaulted to '--' or blank)
    sub_cat = str(ticket.get("sub_category", ticket.get("sub-category", ""))).strip().lower()
    if sub_cat in invalid_tokens:
        quality_warnings.append("Sub-Category is not populated or set to '--'")

    # Subscriber ID / Sub-Company Check
    sub_id = str(ticket.get("subscriber_id", ticket.get("sub_company", ""))).strip().lower()
    if sub_id in invalid_tokens:
        quality_warnings.append("Subscriber Id / Sub-Company field is unassigned")

    # Source Check
    source_val = str(ticket.get("source", "")).strip().lower()
    if source_val in invalid_tokens:
        quality_warnings.append("Ticket Source is unassigned")

    # Calculate Hygiene Compliance Score
    deductions = (len(missing_mandatory) * 20) + (len(quality_warnings) * 10)
    compliance_score = max(0, 100 - deductions)

    return {
        "is_compliant": len(missing_mandatory) == 0,
        "missing_mandatory": missing_mandatory,
        "quality_warnings": quality_warnings,
        "compliance_score": compliance_score
    }


def show_ai_investigator_ui(df: pd.DataFrame):
    """Renders the forensic analysis panel with operational handoff, mistake audit, and field validation logic."""
    st.markdown("---")
    st.subheader("🔍 Deep Ticket Forensics Explorer & AI Auditor")
    st.caption("Secured local LLM processing layer + native vector lookup + field validation engine.")

    target_id = st.text_input("Enter target Ticket ID to spin up deep forensic loop:", key="explorer_id_input")

    if target_id:
        match = df[df["ticket_id"].astype(str) == str(target_id)]
        if not match.empty:
            ticket = match.iloc[0].to_dict()

            # --- 1. FRESHSERVICE FORM FIELD VALIDATION ---
            validation = validate_freshservice_fields(ticket)

            st.markdown("#### 📋 Freshservice Form Field Hygiene & Validation Audit")
            col_v1, col_v2 = st.columns([1, 3])

            with col_v1:
                if validation["is_compliant"]:
                    st.success("✅ **Mandatory Fields Complete**")
                else:
                    st.error("❌ **Mandatory Fields Missing**")
                st.metric("Field Quality Score", f"{validation['compliance_score']}%")

            with col_v2:
                if validation["missing_mandatory"]:
                    st.markdown(f"**Missing Mandatory Fields:** `{'`, `'.join(validation['missing_mandatory'])}`")
                if validation["quality_warnings"]:
                    st.markdown("**Field Hygiene Warnings:**")
                    for w in validation["quality_warnings"]:
                        st.caption(f"• {w}")
                if not validation["missing_mandatory"] and not validation["quality_warnings"]:
                    st.caption("All form attributes (Company, Category, Sub-Category, Group, Type) are filled accurately.")

            st.markdown("---")

            # --- 2. EXTRACT METRICS ---
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

            # --- 3. PRIVATE NOTES & WORKLOG FORENSIC INGESTION ---
            st.markdown("##### 📝 Private Notes & Operational Worklogs")
            default_note = ticket.get("notes") or ticket.get("resolution_note") or "No worklog captured."
            user_notes = st.text_area(
                "Audit agent notes for mistakes, shift handoff slips, or double allocation:",
                value=default_note,
                height=90
            )
            ticket["notes"] = user_notes

            col_actions1, col_actions2 = st.columns(2)

            with col_actions1:
                if st.button("🚀 Execute Forensic & Process Audit", use_container_width=True):
                    with st.spinner("Analyzing operational handoffs and engineering process slips..."):
                        analyzer = LocalTicketAnalyzer()
                        findings = analyzer.run_ticket_forensics(ticket)

                        if "error" in findings:
                            st.error(findings["error"])
                        else:
                            st.success("Operational & Technical Audit Complete.")

                            st.markdown("### ⚠️ Process Gaps & Handoff Audit")
                            handoff_slip = findings.get("Handoff_Process_Mistakes") or "No obvious handoff mistakes detected in notes."
                            st.warning(handoff_slip)

                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown("### 📋 Incident Diagnostics")
                                st.markdown(f"**Technical Root Cause:**\n{findings.get('Technical_Root_Cause', 'N/A')}")
                            with c2:
                                st.markdown("### 🛠️ Process Improvement")
                                st.markdown(f"**Workflow Optimization Plan:**\n{findings.get('Workflow_Optimization_Plan', 'N/A')}")

                            with st.expander("View Raw LLM Unparsed Generative Output"):
                                st.code(findings.get("Raw", ""))

            with col_actions2:
                if st.button("🧠 Surface Similar Historical Solved Tickets", use_container_width=True):
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
