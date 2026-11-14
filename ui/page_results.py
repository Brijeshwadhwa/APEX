"""Page 4: Evaluation Results — Individual dossier report with specialist agent findings and grounded citations."""

from decimal import Decimal
import streamlit as st

from ui.styles import render_top_header, render_stat_card, get_recommendation_badge_html, get_eligibility_badge_html


def render_results_page(coordinator, store, logger, all_states, selected_applicant_id=None, gemini_service=None):
    """Renders the comprehensive evaluation report for a single candidate dossier."""
    render_top_header(
        title="Candidate Adjudication Report & Dossier",
        subtitle="Multi-agent evaluation findings, composite score breakdown, and grounded rubric citations",
    )

    if not all_states:
        st.warning("No applicants are currently evaluated in the system.")
        return

    # Select applicant dropdown
    app_ids = [s.applicant_id for s in all_states]
    default_index = 0
    if selected_applicant_id and selected_applicant_id in app_ids:
        default_index = app_ids.index(selected_applicant_id)

    def format_applicant_label(app_id):
        st_match = next((s for s in all_states if s.applicant_id == app_id), None)
        if st_match:
            return f"{app_id} — {st_match.profile.full_name} ({st_match.recommendation or 'Not Evaluated'})"
        return app_id

    target_id = st.selectbox(
        "Select Candidate Dossier:",
        options=app_ids,
        index=default_index,
        format_func=format_applicant_label,
    )

    state = next(s for s in all_states if s.applicant_id == target_id)
    profile = state.profile

    # --- TOP DOSSIER SUMMARY CARD ---
    with st.container(border=True):
        col_info1, col_info2, col_info3 = st.columns([2.2, 2.2, 1.6])
        with col_info1:
            st.markdown(f"""
            <div style="font-size: 1.35rem; font-weight: 800; color: #0F2042; margin-bottom: 4px;">
                {profile.full_name}
            </div>
            <div style="font-size: 0.85rem; color: #64748B; margin-bottom: 12px;">
                Dossier ID: <b>{state.applicant_id}</b> | Email: <b>{profile.email or 'N/A'}</b>
            </div>
            <div style="font-size: 0.88rem; color: #334155;">
                <div>• <b>Program:</b> {profile.program_of_study or 'N/A'}</div>
                <div>• <b>Institution:</b> {profile.institution or 'N/A'}</div>
            </div>
            """, unsafe_allow_html=True)

        with col_info2:
            acad_display = f"<b>{profile.academic_percentage:.2f}%</b>" if profile.academic_percentage is not None else "<span style='color:#DC2626; font-weight:600;'>Missing (None)</span>"
            inc_display = f"<b>₹{profile.household_income:,.0f}</b>" if profile.household_income is not None else "<span style='color:#DC2626; font-weight:600;'>Missing (None)</span>"
            st.markdown(f"""
            <div style="font-size: 0.88rem; color: #334155; padding-top: 6px;">
                <div>• Academic Score: {acad_display}</div>
                <div>• Household Income: {inc_display}</div>
                <div>• Achievements: <b>{len(profile.achievements)} recorded</b></div>
                <div>• Demographics (Audit): <b>{profile.gender or 'N/A'}, {profile.category or 'N/A'}</b></div>
            </div>
            """, unsafe_allow_html=True)

        with col_info3:
            if state.status == "ELIGIBLE_CONFIRMED":
                score_txt = f"{state.total_score:.2f}"
                sub_txt = "Certified Composite Score"
                accent_c = "#059669"
            elif state.status == "INELIGIBLE":
                score_txt = "Excluded"
                sub_txt = "Disqualified from Ranking"
                accent_c = "#DC2626"
            else:
                score_txt = "On Hold"
                sub_txt = "Pending Missing Records"
                accent_c = "#D97706"

            render_stat_card("Adjudicated Score", f"{score_txt}", sub_txt, "🎯", accent_c)

    # --- VERDICT / STATUS BANNER ---
    if state.status == "INELIGIBLE":
        st.error(f"""
        ⛔ **COMMITTEE DISQUALIFICATION ENFORCED (Clause 1.1 / 1.2)**  
        This applicant failed mandatory eligibility criteria and is **strictly barred from entering the confirmed scholarship ranking**.  
        **Reason:** {state.eligibility.justification if state.eligibility else 'Disqualified'}  
        **Failed Gates:** {', '.join(state.eligibility.failed_rules) if state.eligibility else 'Mandatory Threshold Violation'}
        """)
    elif state.status == "NEEDS_REVIEW":
        st.warning(f"""
        ⚠️ **ADMINISTRATIVE HOLD — MANDATORY DOCUMENTATION MISSING (Clause 1.3)**  
        This dossier is incomplete. Per Clause 1.3, missing mandatory data cannot be assumed to be zero or waived.  
        The applicant cannot receive a confirmed final ranking slot until verified documentation is supplied.  
        **Missing Records:** {', '.join(state.eligibility.missing_fields) if state.eligibility else 'Documentation Required'}
        """)
    elif state.status == "ELIGIBLE_CONFIRMED":
        st.success(f"""
        ✅ **ELIGIBILITY VERIFIED & CERTIFIED**  
        All mandatory minimums satisfied. Composite score of **{state.total_score:.2f} / 100.0** qualifies candidate for **'{state.recommendation}'** committee allocation.
        """)

    # --- GEMINI AI COMMITTEE REPORT GENERATION ---
    if gemini_service:
        with st.expander("🤖 AI Committee Adjudication Report (Google Gemini)", expanded=False):
            col_g_info, col_g_btn = st.columns([3, 1.2])
            with col_g_info:
                st.markdown(f"Generate a formal publication-grade committee dossier analysis using **{gemini_service.model_name}**.")
                st.caption("🔒 Privacy Disclosure: Candidate name and ID are stripped prior to external Gemini processing; financial figures are minimized to broad bands.")
            with col_g_btn:
                do_gen = st.button("Generate Detailed AI Report", key=f"btn_rep_{target_id}", type="primary", use_container_width=True)

            rep_key = f"gemini_report_{target_id}"
            if do_gen:
                with st.spinner("Generating formal committee report with Google Gemini..."):
                    report_res = gemini_service.generate_committee_report(state)
                    st.session_state[rep_key] = report_res

            if rep_key in st.session_state:
                report_res = st.session_state[rep_key]
                st.markdown(f"#### {report_res.report_title}")
                st.markdown(f"**Executive Summary:** {report_res.executive_summary}")
                st.markdown(f"**Evaluation Breakdown:** {report_res.evaluation_breakdown}")
                st.markdown(f"**Recommendation Rationale:** {report_res.recommendation_explanation}")
                st.caption(f"Cited Governing Clauses: {', '.join(report_res.rubric_references)}")
                with st.expander("📄 View Full Markdown Attestation Document"):
                    st.markdown(report_res.full_report_markdown)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- SPECIALIST AGENTS BREAKDOWN (2x2 Grid) ---
    st.markdown("""
    <div style="font-size: 1.15rem; font-weight: 700; color: #0F2042; margin-bottom: 14px;">
        Specialist Agent Findings & Score Proofs
    </div>
    """, unsafe_allow_html=True)

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        # Agent 1: Eligibility Agent
        with st.container(border=True):
            h1, h2 = st.columns([3, 1.2])
            with h1:
                st.markdown("<div style='font-weight: 700; color: #0F2042; font-size: 0.95rem;'>1. Eligibility Verification Agent</div><div style='font-size: 0.78rem; color: #64748B;'>Mandatory Minimum Gatekeeper</div>", unsafe_allow_html=True)
            with h2:
                if state.eligibility:
                    st.markdown(get_eligibility_badge_html(state.eligibility.decision), unsafe_allow_html=True)
            if state.eligibility:
                st.write(f"**Findings:** {state.eligibility.justification}")
                if state.eligibility.rubric_references:
                    st.markdown(f'<div class="agent-citation-chip"><b>Cited Clauses:</b> {", ".join(state.eligibility.rubric_references)}</div>', unsafe_allow_html=True)
            else:
                st.info("Pending eligibility check.")

        # Agent 2: Merit Agent
        with st.container(border=True):
            h1, h2 = st.columns([3, 1.2])
            with h1:
                st.markdown("<div style='font-weight: 700; color: #0F2042; font-size: 0.95rem;'>2. Merit Evaluation Agent</div><div style='font-size: 0.78rem; color: #64748B;'>Academic Performance Normalizer (Weight 40%)</div>", unsafe_allow_html=True)
            with h2:
                if state.academic_result and state.academic_result.score is not None:
                    st.markdown(f'<span class="agent-score-pts">{state.academic_result.score:.2f} / 40.0</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="agent-score-pts" style="color: #64748B; background: #F1F5F9; border-color: #E2E8F0;">Excluded</span>', unsafe_allow_html=True)
            if state.academic_result:
                st.write(f"**Normalization Logic:** {state.academic_result.justification}")
                st.markdown(f'<div class="agent-citation-chip"><b>Governing Clause:</b> {state.academic_result.rubric_reference}</div>', unsafe_allow_html=True)
            else:
                st.info("Merit evaluation pending.")

    with col_g2:
        # Agent 3: Financial Need Agent
        with st.container(border=True):
            h1, h2 = st.columns([3, 1.2])
            with h1:
                st.markdown("<div style='font-weight: 700; color: #0F2042; font-size: 0.95rem;'>3. Financial Need Evaluation Agent</div><div style='font-size: 0.78rem; color: #64748B;'>Socio-Economic Bracketing (Weight 35%)</div>", unsafe_allow_html=True)
            with h2:
                if state.financial_result and state.financial_result.score is not None:
                    st.markdown(f'<span class="agent-score-pts">{state.financial_result.score:.1f} / 35.0</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="agent-score-pts" style="color: #64748B; background: #F1F5F9; border-color: #E2E8F0;">Excluded</span>', unsafe_allow_html=True)
            if state.financial_result:
                st.write(f"**Bracket Assigned:** <b>{state.financial_result.income_band or 'N/A'}</b>")
                st.write(f"**Assessment:** {state.financial_result.justification}")
                st.markdown(f'<div class="agent-citation-chip"><b>Governing Clause:</b> {state.financial_result.rubric_reference}</div>', unsafe_allow_html=True)
            else:
                st.info("Financial evaluation pending.")

        # Agent 4: Achievement Portfolio Agent
        with st.container(border=True):
            h1, h2 = st.columns([3, 1.2])
            with h1:
                st.markdown("<div style='font-weight: 700; color: #0F2042; font-size: 0.95rem;'>4. Achievement Portfolio Agent</div><div style='font-size: 0.78rem; color: #64748B;'>Extracurricular & Co-curricular (Weight 25%)</div>", unsafe_allow_html=True)
            with h2:
                if state.achievement_result and state.achievement_result.score is not None:
                    st.markdown(f'<span class="agent-score-pts">{state.achievement_result.score:.1f} / 25.0</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="agent-score-pts" style="color: #64748B; background: #F1F5F9; border-color: #E2E8F0;">Excluded</span>', unsafe_allow_html=True)
            if state.achievement_result:
                ach = state.achievement_result
                st.write(f"**Portfolio Audit:** {ach.verified_count} verified, {ach.rejected_or_duplicate_count} unverified / duplicate.")
                st.write(f"**Scoring Breakdown:** Raw: {ach.raw_score:.1f} pts ➔ Capped Final: {ach.score:.1f} / 25.0 pts.")
                st.write(f"**Assessment:** {ach.justification}")
                st.markdown(f'<div class="agent-citation-chip"><b>Governing Clause:</b> {ach.rubric_reference}</div>', unsafe_allow_html=True)
            else:
                st.info("Achievement evaluation pending.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- ROW: PANEL MANAGER & FAIRNESS AUDITOR ---
    col_pm, col_fa = st.columns(2)

    with col_pm:
        with st.container(border=True):
            st.markdown("<div style='font-weight: 700; color: #0F2042; font-size: 0.95rem;'>5. Panel Manager Agent (Fan-In Synthesizer)</div><div style='font-size: 0.78rem; color: #64748B; margin-bottom: 8px;'>Composite Weighting & Recommendation Decision</div>", unsafe_allow_html=True)
            if state.recommendation:
                score_txt = f"{state.total_score:.2f} / 100.0" if state.total_score is not None else "Excluded"
                st.write(f"**Recommendation Category:** <b>{state.recommendation}</b>")
                st.write(f"**Mathematical Formula:** `Total = Merit (40) + Need (35) + Achievement (25)`")
                st.write(f"**Composite Score:** `{score_txt}`")
                st.markdown('<div class="agent-citation-chip"><b>Governing Clauses:</b> Clause 3.1 & Clause 3.2</div>', unsafe_allow_html=True)
            else:
                st.info("Panel synthesis pending.")

    with col_fa:
        with st.container(border=True):
            st.markdown("<div style='font-weight: 700; color: #0F2042; font-size: 0.95rem;'>6. Fairness Auditor Agent</div><div style='font-size: 0.78rem; color: #64748B; margin-bottom: 8px;'>Ethical Non-Discrimination & Mathematical Proof</div>", unsafe_allow_html=True)
            if state.audit_result:
                ar = state.audit_result
                status_badge = "✅ Passed" if ar.passed else "❌ Flagged"
                st.write(f"**Compliance Status:** <b>{status_badge}</b> (Flagged Demographics: `{len(ar.flagged_attributes)}`)")
                st.write(f"**Demographic Bias Scan:** Bias Detected: `{ar.bias_detected}`. Prohibited Attributes Flagged: `{', '.join(ar.flagged_attributes) if ar.flagged_attributes else 'None'}`.")
                st.write(f"**Arithmetic Verification:** Verified sum equality: `{ar.score_consistency_verified}`.")
                st.write(f"**Audit Notes:** {ar.audit_notes}")
                st.markdown('<div class="agent-citation-chip"><b>Governing Clauses:</b> Clause 4.1 & Clause 4.2</div>', unsafe_allow_html=True)
            else:
                st.info("Fairness audit pending.")
