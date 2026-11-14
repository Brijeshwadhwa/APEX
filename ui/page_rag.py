"""Page 6: RAG Rubric Explorer — Grounded Gemini RAG search and policy clause citations."""

import os
import streamlit as st

from ui.styles import render_top_header
from rag.retriever import RubricRetriever
from core.gemini_service import GeminiService


def render_rag_page(retriever: RubricRetriever, gemini_service: GeminiService = None):
    """Renders the Grounded RAG search and policy clause explorer with Gemini synthesis."""
    render_top_header(
        title="Grounded Policy & Rubric Explorer",
        subtitle="Deterministic retrieval over official scholarship evaluation criteria and governing clauses",
    )

    # Policy Context Box
    gemini_badge = f" • <b>Gemini {gemini_service.model_name} Active</b>" if (gemini_service and gemini_service.is_configured) else " • <b>Deterministic Mode</b>"
    st.markdown(f"""
    <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 4px solid #0D9488; border-radius: 8px; padding: 14px 18px; margin-bottom: 20px;">
        <div style="font-weight: 700; color: #0F2042; font-size: 0.95rem; margin-bottom: 4px;">
            Institutional Assessment Knowledge Base (Clause Model v1.0.0){gemini_badge}
        </div>
        <div style="font-size: 0.85rem; color: #475569; line-height: 1.5;">
            Governing rubric indexed deterministically without generative hallucination. All answers cite official clauses (Clauses 1.1–4.2).
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- SEARCH INTERFACE ---
    with st.container(border=True):
        st.markdown("""
        <div style="font-size: 1.1rem; font-weight: 700; color: #0F2042; margin-bottom: 12px;">
            Query the Evaluation Rubric
        </div>
        """, unsafe_allow_html=True)

        sample_queries = [
            "minimum academic percentage threshold",
            "maximum household income ceiling",
            "financial need income brackets and points",
            "achievement portfolio tiers and cap",
            "recommendation classification score thresholds",
            "prohibited demographic scoring attributes",
        ]

        selected_sample = st.selectbox(
            "Suggested Pre-Configured Rubric Queries:",
            ["-- Enter a custom query or select a pre-configured topic --"] + sample_queries,
        )

        col_q, col_k = st.columns([4, 1])
        with col_q:
            user_query = st.text_input(
                "Enter policy question or keywords:",
                value="" if selected_sample.startswith("--") else selected_sample,
                placeholder="e.g. What is the minimum academic percentage for eligibility?",
            )
        with col_k:
            k_val = st.selectbox("Top-K Clauses", [1, 2, 3, 4, 5], index=1)

        search_clicked = st.button("🔍 Search Rubric", type="primary")

    active_query = user_query.strip()
    if active_query:
        # If Gemini service available, use Grounded RAG with strict clause-citation prompt
        if gemini_service:
            with st.spinner("Retrieving clauses and synthesizing grounded answer..."):
                rag_res = gemini_service.answer_rubric_question(
                    question=active_query,
                    retriever=retriever,
                    top_k=k_val,
                )

            # Grounded Policy Answer Box
            status_bg = "#F0FDF4" if rag_res.rubric_coverage_status == "COVERED_IN_RUBRIC" else "#FFFBEB"
            status_fg = "#047857" if rag_res.rubric_coverage_status == "COVERED_IN_RUBRIC" else "#B45309"

            st.markdown(f"""
            <div style="background: {status_bg}; border: 1px solid #BBF7D0; border-radius: 10px; padding: 18px; margin-bottom: 22px;">
                <div style="font-size: 0.82rem; font-weight: 700; color: {status_fg}; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px;">
                    💡 Grounded Policy Advisor Answer (Google Gemini)
                </div>
                <div style="font-size: 0.95rem; color: #064E3B; line-height: 1.6;">
                    {rag_res.answer}
                </div>
                <div style="font-size: 0.8rem; color: #64748B; margin-top: 10px;">
                    <b>Cited Clauses:</b> {', '.join(rag_res.cited_clauses) if rag_res.cited_clauses else 'None'}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Also retrieve and display the exact source passages
        results = retriever.retrieve_relevant_clauses(active_query, top_k=k_val)
        if results:
            st.markdown("""
            <div style="font-size: 1.1rem; font-weight: 700; color: #0F2042; margin-bottom: 12px;">
                Retrieved Policy Clauses & Governing Text
            </div>
            """, unsafe_allow_html=True)

            for idx, clause in enumerate(results, start=1):
                with st.expander(f"Clause {clause.clause_id}: {clause.title} (Section: {clause.section})", expanded=True):
                    st.markdown(f"**Governing Policy Text:**")
                    st.markdown(f"""
                    <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-left: 3px solid #0D9488; padding: 12px; border-radius: 6px; font-size: 0.9rem; color: #1E293B; line-height: 1.5;">
                        {clause.text}
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"Source: `{os.path.basename(retriever.rubric_file_path)}` | Clause ID: `{clause.clause_id}` | Matched Keywords: `{', '.join(clause.keywords[:8])}`")
        else:
            st.warning("No matching rubric clauses met the relevance threshold. Try broadening your keywords.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- COMPLETE UNABRIDGED RUBRIC DOCUMENT ---
    with st.expander("📖 View Complete Unabridged Scholarship Rubric (Markdown Document)"):
        if os.path.exists(retriever.rubric_file_path):
            with open(retriever.rubric_file_path, "r", encoding="utf-8") as f:
                st.markdown(f.read())
        else:
            st.error("Rubric file not found on disk.")
