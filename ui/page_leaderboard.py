"""Page 7: Committee Leaderboard — Official ranked awards, exclusion pools, and data exports."""

import json
import pandas as pd
import streamlit as st

from ui.styles import render_top_header, render_stat_card


def render_leaderboard_page(coordinator, store, logger, all_states, leaderboard):
    """Renders the official committee scholarship ranking leaderboard and export options."""
    render_top_header(
        title="Scholarship Committee Award Leaderboard",
        subtitle="Ranked composite allocation, merit-need scoring distribution, and exclusion isolation",
    )

    confirmed = leaderboard["confirmed_awardees"]
    waitlist = leaderboard["consider_waitlist"]
    ineligible = leaderboard["ineligible_disqualified"]
    needs_review = leaderboard["needs_review"]

    # --- TOP 4 METRIC CARDS ---
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_stat_card("Award Nominees", str(len(confirmed)), "High Priority & Recommended", "🏆", "#059669")
    with m2:
        render_stat_card("Waitlist Pool", str(len(waitlist)), "Consider Tiers (50 - 64.9)", "⏳", "#2563EB")
    with m3:
        render_stat_card("Disqualified", str(len(ineligible)), "Zero Award Slots (Barred)", "⛔", "#DC2626")
    with m4:
        render_stat_card("Needs Review", str(len(needs_review)), "Pending Documentation", "⚠️", "#D97706")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- CONFIRMED AWARDEES RANKED TABLE ---
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <div>
            <div style="font-size: 1.15rem; font-weight: 700; color: #0F2042;">
                Confirmed Scholarship Award Nominees (Ranked Order)
            </div>
            <div style="font-size: 0.85rem; color: #64748B;">
                Eligible candidates strictly sorted in descending order of composite score (Max 100.0 pts)
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if confirmed:
        ranked_records = []
        for idx, c in enumerate(confirmed, start=1):
            medal = "🥇 " if idx == 1 else ("🥈 " if idx == 2 else ("🥉 " if idx == 3 else ""))
            tot_str = f"{c['total_score']:.2f} / 100" if c.get("total_score") is not None else "Pending / N/A"
            acad_str = f"{c['academic_score']:.2f}" if c.get("academic_score") is not None else "—"
            fin_str = f"{c['financial_score']:.1f}" if c.get("financial_score") is not None else "—"
            ach_str = f"{c['achievement_score']:.1f}" if c.get("achievement_score") is not None else "—"
            rec_str = c.get("recommendation") or "Pending"
            audit_str = "✅ Certified" if c.get("audit_passed") else ("❌ Flagged" if c.get("audit_passed") is False else "—")
            ranked_records.append({
                "Rank": f"{medal}#{idx}",
                "Applicant ID": c["applicant_id"],
                "Candidate Name": c["full_name"],
                "Total Score": tot_str,
                "Merit (40)": acad_str,
                "Need (35)": fin_str,
                "Achievement (25)": ach_str,
                "Recommendation": rec_str,
                "Audit Status": audit_str,
            })

        df_confirmed = pd.DataFrame(ranked_records)
        st.dataframe(df_confirmed, width="stretch", hide_index=True)

        # CSV Download Button
        csv_data = df_confirmed.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Export Confirmed Leaderboard (CSV)",
            data=csv_data,
            file_name="scholarship_confirmed_awards.csv",
            mime="text/csv",
        )
    else:
        st.info("No confirmed awardees yet. Run evaluation from the sidebar Demo Controls.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- WAITLIST POOL ---
    st.markdown("""
    <div style="font-size: 1.15rem; font-weight: 700; color: #0F2042; margin-bottom: 8px;">
        Secondary Allocation & Waitlist Pool (Scores 50.0 – 64.9)
    </div>
    <div style="font-size: 0.85rem; color: #64748B; margin-bottom: 12px;">
        Candidates meeting minimum criteria pending secondary quota seat release
    </div>
    """, unsafe_allow_html=True)

    if waitlist:
        wait_records = []
        for idx, w in enumerate(waitlist, start=1):
            tot_str = f"{w['total_score']:.2f} / 100" if w.get("total_score") is not None else "Pending Evaluation"
            acad_str = f"{w['academic_score']:.2f}" if w.get("academic_score") is not None else "—"
            fin_str = f"{w['financial_score']:.1f}" if w.get("financial_score") is not None else "—"
            ach_str = f"{w['achievement_score']:.1f}" if w.get("achievement_score") is not None else "—"
            rec_str = w.get("recommendation") or "Not Evaluated"
            audit_str = "✅ Certified" if w.get("audit_passed") else ("❌ Flagged" if w.get("audit_passed") is False else "—")
            rank_label = f"WL-{idx}" if w.get("total_score") is not None else f"PEN-{idx}"
            wait_records.append({
                "Pool Rank": rank_label,
                "Applicant ID": w["applicant_id"],
                "Candidate Name": w["full_name"],
                "Total Score": tot_str,
                "Merit (40)": acad_str,
                "Need (35)": fin_str,
                "Achievement (25)": ach_str,
                "Recommendation": rec_str,
                "Audit Status": audit_str,
            })
        st.dataframe(pd.DataFrame(wait_records), width="stretch", hide_index=True)
    else:
        st.caption("No candidates currently in the secondary allocation pool.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- EXCLUSION & HOLD POOLS (Kept strictly OUT of rankings) ---
    st.markdown("""
    <div style="font-size: 1.15rem; font-weight: 700; color: #0F2042; margin-bottom: 8px;">
        Committee Disqualification & Administrative Hold Pools
    </div>
    <div style="font-size: 0.85rem; color: #64748B; margin-bottom: 12px;">
        Strictly excluded from award allocation per Clauses 1.1, 1.2, and 1.3
    </div>
    """, unsafe_allow_html=True)

    tab_inelig, tab_review = st.tabs(["⛔ Disqualified Ineligible Pool", "⚠️ Incomplete Needs Review Pool"])

    with tab_inelig:
        st.caption("Candidates failing mandatory minimum criteria (Clause 1.1 Academic < 60% or Clause 1.2 Income > ₹600,000):")
        if ineligible:
            inelig_df = pd.DataFrame(ineligible)[
                ["applicant_id", "full_name", "academic_percentage", "household_income", "disqualification_reasons", "status"]
            ].rename(columns={
                "applicant_id": "Applicant ID",
                "full_name": "Candidate Name",
                "academic_percentage": "Academic %",
                "household_income": "Household Income",
                "disqualification_reasons": "Disqualification Grounds",
                "status": "Verdict",
            })
            inelig_df["Academic %"] = inelig_df["Academic %"].apply(lambda x: f"{x:.1f}%" if pd.notnull(x) else "Missing")
            inelig_df["Household Income"] = inelig_df["Household Income"].apply(lambda x: f"₹{x:,.0f}" if pd.notnull(x) else "Missing")
            st.dataframe(inelig_df, width="stretch", hide_index=True)
        else:
            st.info("No disqualified applicants.")

    with tab_review:
        st.caption("Candidates with missing mandatory documentation requiring manual human verification (Clause 1.3):")
        if needs_review:
            nr_df = pd.DataFrame(needs_review)[
                ["applicant_id", "full_name", "academic_percentage", "household_income", "missing_fields", "status"]
            ].rename(columns={
                "applicant_id": "Applicant ID",
                "full_name": "Candidate Name",
                "academic_percentage": "Academic %",
                "household_income": "Household Income",
                "missing_fields": "Missing Documentation",
                "status": "Review Status",
            })
            nr_df["Academic %"] = nr_df["Academic %"].apply(lambda x: f"{x:.1f}%" if pd.notnull(x) else "Missing (None)")
            nr_df["Household Income"] = nr_df["Household Income"].apply(lambda x: f"₹{x:,.0f}" if pd.notnull(x) else "Missing (None)")
            st.dataframe(nr_df, width="stretch", hide_index=True)
        else:
            st.info("No applications currently on administrative hold.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- JSON STATE STORE EXPORT ---
    with st.expander("💾 Complete State Store Snapshot (JSON)"):
        raw_state_json = json.dumps(
            {st_item.applicant_id: json.loads(st_item.model_dump_json()) for st_item in all_states},
            indent=2
        )
        st.download_button(
            label="Download Complete State Snapshot (JSON)",
            data=raw_state_json,
            file_name="scholarship_state_store.json",
            mime="application/json",
        )
