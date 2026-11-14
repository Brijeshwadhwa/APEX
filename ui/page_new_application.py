"""Page 3: New Application — Clean multi-section intake form with validation and demonstration presets."""

import asyncio
from decimal import Decimal
import time
import streamlit as st

from ui.styles import render_top_header
from core.schemas import ApplicantProfile


def render_new_application_page(coordinator, store, logger, all_states, on_evaluate_new_cb):
    """Renders the scholarship intake form organized into clean sections."""
    render_top_header(
        title="Candidate Dossier Intake & Submission",
        subtitle="Submit new scholarship applications for multi-agent evaluation and committee ranking",
    )

    # Initialize preset values in session state
    if "form_name" not in st.session_state:
        st.session_state.form_name = "Kavya Singhania"
    if "form_id" not in st.session_state:
        st.session_state.form_id = f"APP-2026-{len(all_states) + 1:03d}"
    if "form_email" not in st.session_state:
        st.session_state.form_email = "kavya.s@example.edu"
    if "form_acad_val" not in st.session_state:
        st.session_state.form_acad_val = 88.5
    if "form_acad_missing" not in st.session_state:
        st.session_state.form_acad_missing = False
    if "form_inc_val" not in st.session_state:
        st.session_state.form_inc_val = 135000.0
    if "form_inc_missing" not in st.session_state:
        st.session_state.form_inc_missing = False
    if "form_program" not in st.session_state:
        st.session_state.form_program = "B.Tech Computer Science"
    if "form_inst" not in st.session_state:
        st.session_state.form_inst = "Institute of Advanced Technology"
    if "form_ach_title" not in st.session_state:
        st.session_state.form_ach_title = "National Level Cyber Security Challenge"
    if "form_ach_level" not in st.session_state:
        st.session_state.form_ach_level = "NATIONAL"
    if "form_ach_verified" not in st.session_state:
        st.session_state.form_ach_verified = True
    if "form_ach_cert" not in st.session_state:
        st.session_state.form_ach_cert = "CERT-NAT-883"

    # --- TOP PRESET SELECTOR (1-Click Viva Presets) ---
    with st.container(border=True):
        st.markdown("""
        <div style="font-size: 0.88rem; font-weight: 700; color: #0F2042; margin-bottom: 8px;">
            🎯 Demonstration Quick-Load Presets (1-Click Test Scenarios)
        </div>
        """, unsafe_allow_html=True)

        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            if st.button("🌟 Scenario A: Eligible High-Priority", width="stretch"):
                st.session_state.form_id = f"APP-DEMO-A{int(time.time())%1000}"
                st.session_state.form_name = "Ananya Raman"
                st.session_state.form_acad_val = 94.0
                st.session_state.form_acad_missing = False
                st.session_state.form_inc_val = 110000.0
                st.session_state.form_inc_missing = False
                st.session_state.form_ach_title = "International AI Olympiad Gold Medal"
                st.session_state.form_ach_level = "INTERNATIONAL"
                st.session_state.form_ach_verified = True
                st.session_state.form_ach_cert = "CERT-INT-999"
                st.rerun()

        with p_col2:
            if st.button("⛔ Scenario B: Ineligible (Failed Gate)", width="stretch"):
                st.session_state.form_id = f"APP-DEMO-B{int(time.time())%1000}"
                st.session_state.form_name = "Vikram Rathore"
                st.session_state.form_acad_val = 52.0  # Fails minimum 60%
                st.session_state.form_acad_missing = False
                st.session_state.form_inc_val = 140000.0
                st.session_state.form_inc_missing = False
                st.session_state.form_ach_title = "State Level Debate Participant"
                st.session_state.form_ach_level = "STATE"
                st.session_state.form_ach_verified = True
                st.session_state.form_ach_cert = "CERT-STA-112"
                st.rerun()

        with p_col3:
            if st.button("⚠️ Scenario C: Incomplete (Needs Review)", width="stretch"):
                st.session_state.form_id = f"APP-DEMO-C{int(time.time())%1000}"
                st.session_state.form_name = "Siddharth Sen"
                st.session_state.form_acad_val = 86.0
                st.session_state.form_acad_missing = False
                st.session_state.form_inc_missing = True  # Missing Income Document
                st.session_state.form_ach_title = "District Robotics Winner"
                st.session_state.form_ach_level = "DISTRICT"
                st.session_state.form_ach_verified = True
                st.session_state.form_ach_cert = "CERT-DIS-004"
                st.rerun()

    # --- MULTI-SECTION FORM ---
    with st.form("new_application_form"):
        # Section 1: Personal Information
        st.markdown("""
        <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; margin-bottom: 12px; border-bottom: 1px solid #F1F5F9; padding-bottom: 6px;">
            1. Personal & Institutional Information
        </div>
        """, unsafe_allow_html=True)
        c_f1, c_f2, c_f3 = st.columns([1.5, 2, 2])
        with c_f1:
            app_id = st.text_input("Applicant ID *", value=st.session_state.form_id)
        with c_f2:
            full_name = st.text_input("Full Legal Name *", value=st.session_state.form_name)
        with c_f3:
            email = st.text_input("Contact Email", value=st.session_state.form_email)

        col_prg1, col_prg2 = st.columns(2)
        with col_prg1:
            program = st.text_input("Enrolled Degree / Program", value=st.session_state.form_program)
        with col_prg2:
            institution = st.text_input("Institution Name", value=st.session_state.form_inst)

        st.markdown("<br>", unsafe_allow_html=True)

        # Section 2 & 3: Academic & Financial Criteria
        col_sec2, col_sec3 = st.columns(2)

        with col_sec2:
            st.markdown("""
            <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; margin-bottom: 12px; border-bottom: 1px solid #F1F5F9; padding-bottom: 6px;">
                2. Academic Record (Clause 1.1)
            </div>
            """, unsafe_allow_html=True)
            missing_acad = st.checkbox("Transcript Document Missing / Unverified", value=st.session_state.form_acad_missing)
            if not missing_acad:
                acad_pct = st.number_input(
                    "Qualifying Academic Percentage (%) *",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state.form_acad_val),
                    step=0.5,
                    format="%.2f",
                    help="Mandatory minimum threshold: 60.0%",
                )
            else:
                acad_pct = None
                st.info("Academic percentage marked as missing (will trigger Clause 1.3 review hold).")

        with col_sec3:
            st.markdown("""
            <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; margin-bottom: 12px; border-bottom: 1px solid #F1F5F9; padding-bottom: 6px;">
                3. Financial Information (Clause 1.2)
            </div>
            """, unsafe_allow_html=True)
            missing_inc = st.checkbox("Income Certificate Missing / Unverified", value=st.session_state.form_inc_missing)
            if not missing_inc:
                income = st.number_input(
                    "Annual Gross Household Income (INR) *",
                    min_value=0.0,
                    max_value=5000000.0,
                    value=float(st.session_state.form_inc_val),
                    step=10000.0,
                    format="%.2f",
                    help="Mandatory maximum ceiling: ₹6,00,000",
                )
            else:
                income = None
                st.info("Household income marked as missing (will trigger Clause 1.3 review hold).")

        st.markdown("<br>", unsafe_allow_html=True)

        # Section 4: Achievements
        st.markdown("""
        <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; margin-bottom: 12px; border-bottom: 1px solid #F1F5F9; padding-bottom: 6px;">
            4. Achievement Portfolio (Clause 2.3)
        </div>
        """, unsafe_allow_html=True)
        a_c1, a_c2, a_c3, a_c4 = st.columns([2.5, 1.5, 1.5, 1.2])
        with a_c1:
            ach_title = st.text_input("Achievement Title", value=st.session_state.form_ach_title)
        with a_c2:
            ach_level = st.selectbox(
                "Recognition Tier",
                ["INTERNATIONAL", "NATIONAL", "STATE", "DISTRICT", "INSTITUTIONAL"],
                index=["INTERNATIONAL", "NATIONAL", "STATE", "DISTRICT", "INSTITUTIONAL"].index(st.session_state.form_ach_level),
            )
        with a_c3:
            ach_cert = st.text_input("Certificate ID", value=st.session_state.form_ach_cert)
        with a_c4:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            ach_verified = st.checkbox("Verified", value=st.session_state.form_ach_verified)

        st.markdown("<br>", unsafe_allow_html=True)

        # Section 5: Review & Submit
        st.markdown("""
        <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; margin-bottom: 12px; border-bottom: 1px solid #F1F5F9; padding-bottom: 6px;">
            5. Review, Compliance Audit & Submission
        </div>
        """, unsafe_allow_html=True)

        d_c1, d_c2, d_c3 = st.columns(3)
        with d_c1:
            gender = st.selectbox("Gender (Audit Tracked)", ["Female", "Male", "Non-Binary", "Prefer not to disclose"])
        with d_c2:
            category = st.selectbox("Category (Audit Tracked)", ["General", "OBC", "SC", "ST", "EWS", "Minority"])
        with d_c3:
            religion = st.text_input("Religion (Audit Tracked)", value="Hindu")

        st.caption("🔒 **Clause 4.1 Compliance:** Demographic fields are strictly isolated for non-discrimination fairness audits and never factored into scoring algorithms.")

        eval_immediately = st.checkbox("⚡ Immediately execute 7-agent evaluation pipeline upon submission", value=True)

        submitted = st.form_submit_button("📥 Submit & Adjudicate Dossier", type="primary", use_container_width=True)

    if submitted:
        if not app_id.strip():
            st.error("Applicant ID is required.")
            return
        if not full_name.strip():
            st.error("Full Legal Name is required.")
            return

        achievements_list = []
        if ach_title.strip():
            achievements_list.append({
                "id": f"ACH-{int(time.time())%10000}",
                "title": ach_title.strip(),
                "level": ach_level,
                "is_verified": ach_verified,
                "certificate_id": ach_cert.strip() if ach_cert.strip() else None,
                "year": 2026,
            })

        applicant_raw = {
            "applicant_id": app_id.strip(),
            "full_name": full_name.strip(),
            "email": email.strip() if email.strip() else None,
            "academic_percentage": acad_pct,
            "household_income": income,
            "program_of_study": program.strip() if program.strip() else None,
            "institution": institution.strip() if institution.strip() else None,
            "achievements": achievements_list,
            "gender": gender,
            "category": category,
            "religion": religion.strip() if religion.strip() else None,
            "notes": "Dossier submitted via web intake portal.",
        }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if eval_immediately:
                with st.spinner(f"Executing multi-agent pipeline for {app_id}..."):
                    eval_state = loop.run_until_complete(coordinator.evaluate_applicant(applicant_raw))
                    st.success(f"Dossier {app_id} successfully evaluated! Status: {eval_state.status}, Recommendation: '{eval_state.recommendation}'.")
                    on_evaluate_new_cb(app_id)
            else:
                profile = ApplicantProfile.model_validate(applicant_raw)
                from core.shared_state import EvaluationState
                new_state = EvaluationState(applicant_id=app_id, profile=profile)
                loop.run_until_complete(store.save_state(new_state))
                st.success(f"Dossier {app_id} registered successfully in state store.")
                on_evaluate_new_cb(app_id)
        except Exception as e:
            st.error(f"Submission Error: {str(e)}")
        finally:
            loop.close()
