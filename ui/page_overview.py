"""Page 1: Executive Dashboard — High-level institutional KPIs, distributions, and activity telemetry."""

from decimal import Decimal
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ui.styles import render_top_header, render_stat_card, get_recommendation_badge_html


def render_overview_page(coordinator, store, logger, all_states, leaderboard):
    """Renders the executive summary dashboard."""
    # Top Header
    render_top_header(
        title="Scholarship Committee Dashboard",
        subtitle="Real-time multi-agent adjudication intelligence, telemetry & decision metrics",
    )

    confirmed = leaderboard["confirmed_awardees"]
    waitlist = leaderboard["consider_waitlist"]
    ineligible = leaderboard["ineligible_disqualified"]
    needs_review = leaderboard["needs_review"]

    total_evaluated = len(all_states)
    total_eligible = len(confirmed) + len(waitlist)
    total_ineligible = len(ineligible)
    total_review = len(needs_review)

    # Average score computation among eligible candidates with valid scores
    eligible_scores = [c["total_score"] for c in confirmed if c["total_score"] is not None] + \
                      [w["total_score"] for w in waitlist if w["total_score"] is not None]
    avg_score = (sum(eligible_scores) / len(eligible_scores)) if eligible_scores else 0.0
    high_priority_count = sum(1 for c in confirmed if "high" in (c["recommendation"] or "").lower())

    # --- TOP 4 STATISTIC CARDS (Exact user requirement) ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_stat_card("Total Applicants", str(total_evaluated), "Submitted dossiers", "📁", "#0F2042")
    with c2:
        pct_elig = f"{(total_eligible / total_evaluated * 100):.1f}% of pool" if total_evaluated else "0%"
        render_stat_card("Eligible Nominees", str(total_eligible), pct_elig, "✅", "#059669")
    with c3:
        pct_inelig = f"{(total_ineligible / total_evaluated * 100):.1f}% of pool" if total_evaluated else "0%"
        render_stat_card("Ineligible Disqualified", str(total_ineligible), pct_inelig, "⛔", "#DC2626")
    with c4:
        pct_rev = f"{(total_review / total_evaluated * 100):.1f}% of pool" if total_evaluated else "0%"
        render_stat_card("Needs Manual Review", str(total_review), pct_rev, "⚠️", "#D97706")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- SECONDARY KPI METRICS ---
    if getattr(store, "last_persistence_error", None):
        st.error(f"⚠️ Persistence Warning: {store.last_persistence_error}")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_stat_card("Mean Composite Score", f"{avg_score:.2f} / 100", "Eligible cohort average", "📈", "#2563EB")
    with k2:
        render_stat_card("High Priority Awards", str(high_priority_count), "Direct Tier-1 Nominees", "⭐", "#0D9488")
    with k3:
        adjudicated_count = sum(1 for s in all_states if s.status != "INTAKE")
        render_stat_card("Evaluation Progress", f"{adjudicated_count} / {total_evaluated}", f"{(adjudicated_count/total_evaluated*100):.0f}% adjudicated" if total_evaluated else "0%", "⚙️", "#475569")
    with k4:
        p_status = getattr(store, "persistence_status", "Active")
        p_color = "#DC2626" if "Error" in p_status else "#059669"
        render_stat_card("State Persistence", p_status, "Atomic JSON Storage", "💾", p_color)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- CHARTS ROW ---
    col_chart1, col_chart2 = st.columns([1.1, 0.9])

    with col_chart1:
        st.markdown("""
        <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; margin-bottom: 8px;">
            Composite Score Distribution
        </div>
        """, unsafe_allow_html=True)
        if eligible_scores:
            fig_hist = px.histogram(
                x=eligible_scores,
                nbins=10,
                labels={"x": "Composite Score (0 - 100)"},
                color_discrete_sequence=["#1E3A8A"],
            )
            fig_hist.update_layout(
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                font=dict(family="Inter, sans-serif", color="#334155", size=12),
                xaxis=dict(title="Score Range (out of 100)", showgrid=True, gridcolor="#F1F5F9"),
                yaxis=dict(title="Candidate Count", showgrid=True, gridcolor="#F1F5F9"),
                margin=dict(l=10, r=10, t=10, b=10),
                height=280,
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("No evaluated eligible candidates available to chart yet.")

    with col_chart2:
        st.markdown("""
        <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; margin-bottom: 8px;">
            Eligibility & Decision Pool Breakdown
        </div>
        """, unsafe_allow_html=True)
        pool_labels = ["Confirmed Awardees", "Waitlist Pool", "Ineligible", "Needs Review"]
        pool_counts = [len(confirmed), len(waitlist), total_ineligible, total_review]
        if sum(pool_counts) > 0:
            fig_donut = go.Figure(data=[go.Pie(
                labels=pool_labels,
                values=pool_counts,
                hole=0.6,
                marker=dict(colors=["#059669", "#2563EB", "#DC2626", "#D97706"]),
                textinfo="percent+label",
                textposition="outside",
                showlegend=False,
            )])
            fig_donut.update_layout(
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                font=dict(family="Inter, sans-serif", color="#334155", size=11),
                margin=dict(l=10, r=10, t=10, b=10),
                height=280,
            )
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("Run evaluation to visualize decision pools.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- RECENT APPLICATIONS & RECENT AGENT ACTIVITY (Two columns) ---
    col_rec_app, col_rec_act = st.columns([1, 1])

    with col_rec_app:
        st.markdown("""
        <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
            <span>Recent Applications</span>
            <span style="font-size: 0.8rem; font-weight: 500; color: #64748B;">Latest dossiers</span>
        </div>
        """, unsafe_allow_html=True)
        if all_states:
            recent_list = []
            for s in all_states[:6]:
                p = s.profile
                recent_list.append({
                    "ID": s.applicant_id,
                    "Name": p.full_name,
                    "Academic %": f"{float(p.academic_percentage):.1f}%" if p.academic_percentage is not None else "Missing",
                    "Income": f"₹{float(p.household_income):,.0f}" if p.household_income is not None else "Missing",
                    "Status": s.status,
                    "Recommendation": s.recommendation or "Pending",
                })
            st.dataframe(pd.DataFrame(recent_list), width="stretch", hide_index=True)
        else:
            st.info("No applications found.")

    with col_rec_act:
        st.markdown("""
        <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
            <span>Recent Agent Tool Telemetry</span>
            <span style="font-size: 0.8rem; font-weight: 500; color: #64748B;">Append-only audit log</span>
        </div>
        """, unsafe_allow_html=True)
        logs = logger.read_all_logs()
        if logs:
            recent_logs = logs[-6:]
            log_display = []
            for l in reversed(recent_logs):
                log_display.append({
                    "Agent": l.get("agent_name", "N/A"),
                    "Tool": l.get("tool_name", "N/A"),
                    "Applicant": l.get("applicant_id", "N/A"),
                    "Duration": f"{l.get('duration_seconds', 0):.3f}s",
                    "Status": l.get("execution_status", "N/A"),
                })
            st.dataframe(pd.DataFrame(log_display), width="stretch", hide_index=True)
        else:
            st.info("No agent tool execution logs yet. Run evaluation from sidebar controls.")
