"""Page: AI Assistant & Committee Advisor — Powered by Google Gemini and Microsoft Semantic Kernel."""

import streamlit as st
import pandas as pd

from ui.styles import render_top_header, render_stat_card
from core.gemini_service import GeminiService
from core.shared_state import StateStore, EvaluationState
from rag.retriever import RubricRetriever


def render_ai_assistant_page(
    gemini_service: GeminiService,
    store: StateStore,
    retriever: RubricRetriever,
    all_states: list,
):
    """Renders the interactive AI Assistant powered by Google Gemini."""
    render_top_header(
        title="Institutional AI Assistant & Policy Advisor",
        subtitle="Powered by Google Gemini — Grounded rubric consultation and dossier analysis",
    )

    # --- TOP: GEMINI STATUS & TELEMETRY CARD ---
    is_cfg = gemini_service.is_configured
    status_label = "Configured" if is_cfg else "Not Configured"
    status_color = "#059669" if is_cfg else "#D97706"
    status_icon = "🟢" if is_cfg else "🟠"

    with st.container(border=True):
        col_st1, col_st2 = st.columns([3.5, 1.5])
        with col_st1:
            st.markdown(f"""
            <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; display: flex; align-items: center; gap: 8px;">
                <span>{status_icon} Google Gemini Service Status</span>
                <span style="font-size: 0.8rem; background: #F1F5F9; color: {status_color}; font-weight: 700; padding: 2px 8px; border-radius: 6px;">
                    {status_label}
                </span>
            </div>
            <div style="font-size: 0.85rem; color: #64748B; margin-top: 4px;">
                Active Model: <b>{gemini_service.model_name}</b> | Credentials: <b>{'Loaded securely from .env' if is_cfg else 'Missing in .env'}</b>
            </div>
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 12px; margin-top: 8px; font-size: 0.8rem; color: #334155; line-height: 1.4;">
                🔒 <b>External LLM Processing & Privacy Disclosure:</b> Qualitative synthesis is performed externally via Google Gemini. In strict adherence to institutional data governance (Clause 4.1), all direct identifiers (names, applicant IDs) are redacted prior to API transmission, and financial data is minimized into broad categorical bands.
            </div>
            """, unsafe_allow_html=True)
        with col_st2:
            test_clicked = st.button("⚡ Test Gemini Connectivity", key="test_gemini_btn", width="stretch")

    if test_clicked:
        with st.spinner("Pinging Google Gemini API..."):
            success, msg = gemini_service.verify_connection(force_refresh=True)
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

    # --- TWO TABS: DOSSIER ANALYSIS & RUBRIC CONSULTATION ---
    tab_dossier, tab_rubric = st.tabs([
        "📋 Applicant Dossier Explanations & Reports",
        "📖 Grounded Rubric Policy Q&A",
    ])

    # =========================================================================
    # TAB 1: APPLICANT DOSSIER EXPLANATIONS & REPORTS
    # =========================================================================
    with tab_dossier:
        if not all_states:
            st.info("No applicant dossiers are loaded. Reload dossiers from the sidebar.")
            return

        app_ids = [s.applicant_id for s in all_states]
        sel_app_id = st.selectbox(
            "Select Applicant Dossier for AI Consultation:",
            options=app_ids,
            format_func=lambda x: f"{x} — {next(s.profile.full_name for s in all_states if s.applicant_id == x)} ({next(s.recommendation or 'Not Evaluated' for s in all_states if s.applicant_id == x)})",
            key="ai_assistant_app_sel",
        )

        selected_state = next(s for s in all_states if s.applicant_id == sel_app_id)
        prof = selected_state.profile

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn1, col_btn2, col_btn3 = st.columns(3)

        with col_btn1:
            gen_analysis = st.button("🔍 Generate Dossier Profile Analysis", width="stretch")
        with col_btn2:
            gen_explain = st.button("💡 Explain Multi-Agent Findings", width="stretch")
        with col_btn3:
            gen_report = st.button("📜 Generate Committee Evaluation Report", width="stretch", type="primary")

        # Action 1: Dossier Profile Analysis
        if gen_analysis:
            with st.spinner(f"Analyzing dossier {sel_app_id} with Gemini..."):
                analysis = gemini_service.analyze_applicant_profile(prof)
                with st.container(border=True):
                    st.markdown("""
                    <div style="font-size: 1.1rem; font-weight: 700; color: #0F2042; margin-bottom: 12px;">
                        Applicant Profile Intelligence
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"**Overview:** {analysis.profile_summary}")
                    st.markdown(f"**Academic Observations:** {analysis.academic_observations}")
                    st.markdown(f"**Financial Circumstances:** {analysis.financial_summary}")
                    st.markdown(f"**Achievement Portfolio:** {analysis.achievement_summary}")

                    c_str, c_warn = st.columns(2)
                    with c_str:
                        st.markdown("**Key Candidate Strengths:**")
                        for s in analysis.strengths:
                            st.markdown(f"• {s}")
                    with c_warn:
                        st.markdown("**Verification & Administrative Warnings:**")
                        for w in analysis.missing_information_warnings:
                            st.markdown(f"• ⚠️ {w}")
                        for v in analysis.areas_requiring_verification:
                            st.markdown(f"• 🔍 Verify: {v}")

        # Action 2: Multi-Agent Findings Explanation
        if gen_explain:
            with st.spinner(f"Synthesizing specialist explanations for {sel_app_id}..."):
                explanation = gemini_service.explain_evaluation_results(selected_state)
                with st.container(border=True):
                    st.markdown("""
                    <div style="font-size: 1.1rem; font-weight: 700; color: #0F2042; margin-bottom: 12px;">
                        Grounded Multi-Agent Findings Explanation
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"**Eligibility Gate Check:** {explanation.eligibility_explanation}")
                    st.markdown(f"**Merit / Academic Assessment (40 pts):** {explanation.merit_explanation}")
                    st.markdown(f"**Financial Need Assessment (35 pts):** {explanation.financial_need_explanation}")
                    st.markdown(f"**Achievement Assessment (25 pts):** {explanation.achievement_explanation}")
                    st.markdown(f"**Panel Manager Composite Synthesis:** {explanation.panel_recommendation_explanation}")
                    st.markdown(f"**Fairness Auditor Verification:** {explanation.fairness_audit_explanation}")

                    st.caption("🔒 All explanations are strictly derived from deterministic specialist agent findings.")

        # Action 3: Formal Committee Evaluation Report
        if gen_report:
            with st.spinner(f"Drafting formal committee evaluation report for {sel_app_id}..."):
                report = gemini_service.generate_committee_report(selected_state)
                with st.container(border=True):
                    st.markdown(f"""
                    <div style="font-size: 1.25rem; font-weight: 800; color: #0F2042; margin-bottom: 6px;">
                        {report.report_title}
                    </div>
                    <div style="font-size: 0.85rem; color: #64748B; margin-bottom: 14px;">
                        Governing Clauses Cited: <b>{', '.join(report.rubric_references)}</b>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown("### Executive Summary")
                    st.write(report.executive_summary)

                    st.markdown("### Evaluation Breakdown")
                    st.write(report.evaluation_breakdown)

                    st.markdown("### Recommendation Rationale")
                    st.write(report.recommendation_explanation)

                    with st.expander("📄 View Full Formal Markdown Report Document", expanded=False):
                        st.markdown(report.full_report_markdown)

    # =========================================================================
    # TAB 2: GROUNDED RUBRIC POLICY Q&A
    # =========================================================================
    with tab_rubric:
        with st.container(border=True):
            st.markdown("""
            <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; margin-bottom: 6px;">
                Ask Questions About the Scholarship Evaluation Policy
            </div>
            <div style="font-size: 0.85rem; color: #64748B; margin-bottom: 14px;">
                Gemini answers your policy questions strictly grounded in official rubric clauses (Clauses 1.1–4.2) with verified citations.
            </div>
            """, unsafe_allow_html=True)

            sample_prompts = [
                "What is the minimum academic percentage required for eligibility?",
                "What is the maximum household income ceiling under Clause 1.2?",
                "How are financial need brackets and points assigned?",
                "How are international and national level achievements scored and capped?",
                "What happens if an applicant has missing academic or financial records?",
                "Are demographic attributes like gender or caste allowed to influence scoring?",
            ]

            preset_q = st.selectbox(
                "Quick-Select Suggested Policy Questions:",
                ["-- Select a suggested question or write below --"] + sample_prompts,
                key="rag_suggested_select",
            )

            user_q = st.text_input(
                "Enter your question for the AI Policy Advisor:",
                value="" if preset_q.startswith("--") else preset_q,
                placeholder="e.g. Under what conditions is an applicant placed on administrative review hold?",
                key="rag_custom_input",
            )

            top_k = st.slider("Passage Retrieval Depth (Top-K):", min_value=1, max_value=5, value=3, key="rag_top_k_slider")
            ask_clicked = st.button("💬 Ask Policy Advisor", type="primary", key="rag_ask_btn")

        if ask_clicked and user_q.strip():
            with st.spinner("Retrieving clauses and generating grounded policy answer..."):
                rag_result = gemini_service.answer_rubric_question(
                    question=user_q.strip(),
                    retriever=retriever,
                    top_k=top_k,
                )

                status_bg = "#ECFDF5" if rag_result.rubric_coverage_status == "COVERED_IN_RUBRIC" else "#FFFBEB"
                status_fg = "#065F46" if rag_result.rubric_coverage_status == "COVERED_IN_RUBRIC" else "#92400E"

                st.markdown(f"""
                <div style="background: {status_bg}; border: 1px solid #E2E8F0; border-radius: 10px; padding: 18px; margin-top: 14px;">
                    <div style="font-size: 0.8rem; font-weight: 700; color: {status_fg}; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">
                        💡 Grounded Policy Advisor Response
                    </div>
                    <div style="font-size: 0.95rem; color: #0F172A; line-height: 1.6;">
                        {rag_result.answer}
                    </div>
                    <div style="font-size: 0.8rem; color: #64748B; margin-top: 10px;">
                        <b>Governing Clauses Cited:</b> {', '.join(rag_result.cited_clauses) if rag_result.cited_clauses else 'None'}
                    </div>
                </div>
                """, unsafe_allow_html=True)
