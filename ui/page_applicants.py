"""Page 2: Applicant Management — Master dossier table, responsive filtering, searching, and quick actions."""

import asyncio
from decimal import Decimal
import pandas as pd
import streamlit as st

from ui.styles import render_top_header, get_recommendation_badge_html, get_eligibility_badge_html


def render_applicants_page(coordinator, store, logger, all_states, on_select_applicant_cb):
    """Renders the master applicant registry."""
    render_top_header(
        title="Applicant Registry & Dossier Management",
        subtitle="Search, filter, and review submitted scholarship dossiers across all evaluation tiers",
    )

    if not all_states:
        st.warning("No applicants are currently loaded in the system. Use 'Reload 17 Sample Applicants' in the sidebar.")
        return

    # Build master records list
    records = []
    for st_item in all_states:
        p = st_item.profile
        acad_pct = float(p.academic_percentage) if p.academic_percentage is not None else None
        income = float(p.household_income) if p.household_income is not None else None
        ach_count = len(p.achievements)
        elig_decision = st_item.eligibility.decision if st_item.eligibility else "PENDING"
        total_score = float(st_item.total_score) if st_item.total_score is not None else None
        rec = st_item.recommendation or "Not Evaluated"

        records.append({
            "applicant_id": st_item.applicant_id,
            "full_name": p.full_name,
            "program": p.program_of_study or "General Studies",
            "academic_percentage": acad_pct,
            "household_income": income,
            "achievements_count": ach_count,
            "eligibility": elig_decision,
            "final_score": total_score,
            "recommendation": rec,
            "status": st_item.status,
            "state_ref": st_item,
        })

    df = pd.DataFrame(records)

    # --- SEARCH & FILTER CONTROLS (Responsive grid) ---
    with st.container(border=True):
        f1, f2, f3, f4 = st.columns([2.2, 1.2, 1.3, 1.3])

        with f1:
            search_query = st.text_input("Search dossiers:", placeholder="Search by name, ID, or degree program...", label_visibility="collapsed").strip().lower()

        with f2:
            elig_options = ["All Eligibility"] + sorted(list(df["eligibility"].unique()))
            selected_elig = st.selectbox("Eligibility Filter", elig_options, label_visibility="collapsed")

        with f3:
            rec_options = ["All Recommendations"] + sorted(list(df["recommendation"].unique()))
            selected_rec = st.selectbox("Recommendation Filter", rec_options, label_visibility="collapsed")

        with f4:
            sort_by = st.selectbox(
                "Sort Order",
                ["Score: High to Low", "Academic %: High to Low", "Income: Low to High", "Applicant ID"],
                label_visibility="collapsed",
            )

    # Apply filters
    filtered_df = df.copy()

    if search_query:
        filtered_df = filtered_df[
            filtered_df["full_name"].str.lower().str.contains(search_query) |
            filtered_df["applicant_id"].str.lower().str.contains(search_query) |
            filtered_df["program"].str.lower().str.contains(search_query)
        ]

    if selected_elig != "All Eligibility":
        filtered_df = filtered_df[filtered_df["eligibility"] == selected_elig]

    if selected_rec != "All Recommendations":
        filtered_df = filtered_df[filtered_df["recommendation"] == selected_rec]

    # Apply sorting
    if sort_by == "Score: High to Low":
        filtered_df = filtered_df.sort_values(by="final_score", ascending=False, na_position="last")
    elif sort_by == "Academic %: High to Low":
        filtered_df = filtered_df.sort_values(by="academic_percentage", ascending=False, na_position="last")
    elif sort_by == "Income: Low to High":
        filtered_df = filtered_df.sort_values(by="household_income", ascending=True, na_position="last")
    elif sort_by == "Applicant ID":
        filtered_df = filtered_df.sort_values(by="applicant_id")

    # Table Count Header
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <span style="font-size: 0.92rem; font-weight: 600; color: #475569;">
            Showing <b>{len(filtered_df)}</b> of <b>{len(df)}</b> candidate dossiers
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Clean Responsive Table Formatting
    display_df = filtered_df.copy()
    display_df["Academic %"] = display_df["academic_percentage"].apply(lambda x: f"{x:.1f}%" if pd.notnull(x) else "Missing (None)")
    display_df["Household Income"] = display_df["household_income"].apply(lambda x: f"₹{x:,.0f}" if pd.notnull(x) else "Missing (None)")
    display_df["Final Score"] = display_df["final_score"].apply(lambda x: f"{x:.2f} / 100" if pd.notnull(x) else "Excluded")

    view_columns = ["applicant_id", "full_name", "Academic %", "Household Income", "achievements_count", "eligibility", "Final Score", "recommendation"]
    final_view = display_df[view_columns].rename(columns={
        "applicant_id": "Applicant ID",
        "full_name": "Applicant Name",
        "achievements_count": "Achievements",
        "eligibility": "Eligibility",
        "recommendation": "Recommendation Tier",
    })

    st.dataframe(final_view, width="stretch", hide_index=True)

    # --- DOSSIER ACTIONS & INSPECTOR ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; margin-bottom: 12px;">
        Dossier Inspection & Direct Actions
    </div>
    """, unsafe_allow_html=True)

    c_sel, c_act1, c_act2 = st.columns([2.5, 1.2, 1.3])

    with c_sel:
        target_id = st.selectbox(
            "Select dossier to inspect:",
            options=filtered_df["applicant_id"].tolist(),
            format_func=lambda x: f"{x} — {df[df['applicant_id'] == x]['full_name'].values[0]} ({df[df['applicant_id'] == x]['recommendation'].values[0]})",
            label_visibility="collapsed",
        )

    with c_act1:
        if st.button("🔍 View Complete Dossier", width="stretch"):
            on_select_applicant_cb(target_id)

    with c_act2:
        if st.button("▶ Re-Evaluate This Dossier", width="stretch", type="primary"):
            target_raw = next(s.profile.model_dump() for s in all_states if s.applicant_id == target_id)
            for k in ["academic_percentage", "household_income"]:
                if target_raw.get(k) is not None:
                    target_raw[k] = float(target_raw[k])

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                updated_state = loop.run_until_complete(coordinator.evaluate_applicant(target_raw))
                st.success(f"Evaluated {target_id}: Status {updated_state.status}, Recommendation: '{updated_state.recommendation}'")
                st.rerun()
            finally:
                loop.close()
