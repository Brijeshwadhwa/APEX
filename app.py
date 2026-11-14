"""Master Streamlit Institutional Application: AI Grant and Scholarship Evaluator.

Course: CSE476 Agentic AI & Intelligent Automation (CA2 - Task 2 Q12)
Framework: Microsoft Semantic Kernel for Python + Google Gemini API Integration
Architecture: 7-Agent Fan-Out / Fan-In with Grounded RAG, Shared State, and JSONL Logging.
"""

import asyncio
from decimal import Decimal
import json
import os
import sys
import dotenv

# Load environment variables before importing services
_app_dir = os.path.dirname(os.path.abspath(__file__))
_env_file = os.path.join(_app_dir, ".env")
if os.path.exists(_env_file):
    dotenv.load_dotenv(_env_file, override=True)
else:
    dotenv.load_dotenv(override=True)

import streamlit as st

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import ensure_sk_compatibility
from core.shared_state import StateStore, EvaluationState
from core.audit_logger import AuditLogger
from core.scoring_config import RUBRIC_VERSION, get_configuration_hash
from core.gemini_service import GeminiService
from rag.retriever import RubricRetriever
from orchestration.coordinator import ScholarshipCoordinator

from ui.styles import inject_custom_css
from ui.page_overview import render_overview_page
from ui.page_applicants import render_applicants_page
from ui.page_new_application import render_new_application_page
from ui.page_results import render_results_page
from ui.page_trace import render_trace_page
from ui.page_rag import render_rag_page
from ui.page_ai_assistant import render_ai_assistant_page
from ui.page_leaderboard import render_leaderboard_page

# Apply Semantic Kernel compatibility fix
ensure_sk_compatibility()

# Page configuration
st.set_page_config(
    page_title="Apex Scholar Portal — Institutional Adjudication System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom design system CSS
inject_custom_css()


@st.cache_resource
def init_system_resources():
    """Initializes the persistent coordinator, state store, audit logger, RAG retriever, and Gemini service."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(base_dir, "execution_audit.jsonl")
    data_path = os.path.join(base_dir, "data", "applicants.json")
    rubric_path = os.path.join(base_dir, "rag", "scholarship_rubric.md")

    store = StateStore()
    logger = AuditLogger(log_path)
    retriever = RubricRetriever(rubric_path)
    coordinator = ScholarshipCoordinator(store=store, logger=logger, retriever=retriever)
    gemini_service = GeminiService()

    with open(data_path, "r", encoding="utf-8") as f:
        default_applicants = json.load(f)

    return coordinator, store, logger, retriever, default_applicants, gemini_service


coordinator, store, logger, retriever, default_applicants, gemini_service = init_system_resources()

# Session State tracking for active page and selected applicant
if "active_page" not in st.session_state:
    st.session_state.active_page = "Dashboard"
if "selected_applicant_id" not in st.session_state:
    st.session_state.selected_applicant_id = "APP-2026-001"
if "initial_loaded" not in st.session_state:
    # Ensure default applicants are registered in store
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        current_states = loop.run_until_complete(store.list_all())
        if not current_states:
            from core.schemas import ApplicantProfile
            for raw in default_applicants:
                prof = ApplicantProfile.model_validate(raw)
                st_init = EvaluationState(applicant_id=prof.applicant_id, profile=prof)
                loop.run_until_complete(store.save_state(st_init))
        st.session_state.initial_loaded = True
    finally:
        loop.close()


def switch_to_results(applicant_id: str):
    """Callback to switch page to Evaluation Results with targeted applicant."""
    st.session_state.selected_applicant_id = applicant_id
    st.session_state.active_page = "Evaluation Results"
    st.rerun()


# --- SIDEBAR: INSTITUTIONAL BRANDING, NAVIGATION & CONTROLS ---
with st.sidebar:
    st.markdown("""
    <div style="padding: 12px 6px 20px 6px; border-bottom: 1px solid #E2E8F0; margin-bottom: 16px;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="background: linear-gradient(135deg, #0F2042 0%, #1E3A8A 100%); width: 42px; height: 42px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #FFFFFF; font-size: 1.4rem; font-weight: 800; box-shadow: 0 2px 6px rgba(15,32,66,0.25);">
                🎓
            </div>
            <div>
                <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.15rem; font-weight: 800; color: #0F2042; line-height: 1.1;">
                    Apex Scholar
                </div>
                <div style="font-size: 0.76rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px;">
                    Committee Portal
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Clean Professional Navigation
    PAGES = [
        "Dashboard",
        "Applicants",
        "New Application",
        "Evaluation Results",
        "Agent Activity",
        "RAG Rubric",
        "AI Assistant",
        "Committee Leaderboard",
    ]

    current_idx = PAGES.index(st.session_state.active_page) if st.session_state.active_page in PAGES else 0

    selected_page = st.radio(
        "Navigation Menu",
        options=PAGES,
        index=current_idx,
        label_visibility="collapsed",
    )
    st.session_state.active_page = selected_page

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #64748B; margin-bottom: 8px;">
        Demo & System Controls
    </div>
    """, unsafe_allow_html=True)

    # Run Batch Evaluation
    if st.button("▶ Run Full Batch Evaluation", type="primary", width="stretch"):
        with st.spinner("Executing 7-agent pipeline over all applicant dossiers..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                states = loop.run_until_complete(store.list_all())
                raw_dossiers = [s.profile.model_dump() for s in states]
                for d in raw_dossiers:
                    for k in ["academic_percentage", "household_income"]:
                        if d.get(k) is not None:
                            d[k] = float(d[k])

                results = loop.run_until_complete(coordinator.evaluate_batch(raw_dossiers))
                st.sidebar.success(f"Evaluated {len(results)} dossiers!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error: {e}")
            finally:
                loop.close()

    # Reload Default Mock Applicants
    if st.button("↺ Reload 17 Sample Applicants", width="stretch"):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(store.clear())
            from core.schemas import ApplicantProfile
            for raw in default_applicants:
                prof = ApplicantProfile.model_validate(raw)
                st_init = EvaluationState(applicant_id=prof.applicant_id, profile=prof)
                loop.run_until_complete(store.save_state(st_init))
            st.sidebar.success("Reset to 17 initial dossiers.")
            st.rerun()
        finally:
            loop.close()

    # --- GEMINI STATUS WIDGET ---
    st.markdown("<br>", unsafe_allow_html=True)
    cfg_color = "#059669" if gemini_service.is_configured else "#D97706"
    cfg_text = "Key Set (.env)" if gemini_service.is_configured else "Not Configured"
    st.markdown(f"""
    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px; font-size: 0.78rem; color: #475569; margin-bottom: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <span style="font-weight: 700; color: #0F2042;">Google Gemini AI</span>
            <span style="color: {cfg_color}; font-weight: 700;">● {cfg_text}</span>
        </div>
        <div>• Model: <code>{gemini_service.model_name}</code></div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("⚡ Test Gemini Connectivity", width="stretch", key="sidebar_test_gemini"):
        with st.spinner("Testing API..."):
            success, msg = gemini_service.verify_connection(force_refresh=True)
            if success:
                st.sidebar.success(msg)
            else:
                st.sidebar.warning(msg)

    st.markdown(f"""
    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px; font-size: 0.78rem; color: #475569; margin-top: 8px;">
        <div style="font-weight: 700; color: #0F2042; margin-bottom: 4px;">System Specifications</div>
        <div>• <b>Course:</b> CSE476 Agentic AI</div>
        <div>• <b>Engine:</b> Semantic Kernel 1.47</div>
        <div>• <b>Rubric:</b> v{RUBRIC_VERSION}</div>
        <div>• <b>Config Hash:</b> <code>{get_configuration_hash()[:10]}...</code></div>
    </div>
    """, unsafe_allow_html=True)


# --- FETCH CURRENT SYSTEM STATE ---
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    all_states = loop.run_until_complete(store.list_all())
    leaderboard = loop.run_until_complete(coordinator.get_ranked_leaderboard())
finally:
    loop.close()


# --- ROUTER DISPATCH TO SELECTED PAGE ---
if st.session_state.active_page == "Dashboard":
    render_overview_page(coordinator, store, logger, all_states, leaderboard)

elif st.session_state.active_page == "Applicants":
    render_applicants_page(coordinator, store, logger, all_states, on_select_applicant_cb=switch_to_results)

elif st.session_state.active_page == "New Application":
    render_new_application_page(coordinator, store, logger, all_states, on_evaluate_new_cb=switch_to_results)

elif st.session_state.active_page == "Evaluation Results":
    render_results_page(
        coordinator,
        store,
        logger,
        all_states,
        selected_applicant_id=st.session_state.selected_applicant_id,
        gemini_service=gemini_service,
    )

elif st.session_state.active_page == "Agent Activity":
    render_trace_page(coordinator, store, logger, all_states)

elif st.session_state.active_page == "RAG Rubric":
    render_rag_page(retriever, gemini_service=gemini_service)

elif st.session_state.active_page == "AI Assistant":
    render_ai_assistant_page(gemini_service, store, retriever, all_states)

elif st.session_state.active_page == "Committee Leaderboard":
    render_leaderboard_page(coordinator, store, logger, all_states, leaderboard)
