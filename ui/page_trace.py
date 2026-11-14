"""Page 5: Agent Activity and Execution Trace — Visualizes Fan-Out / Fan-In coordination and tool telemetry."""

import json
import pandas as pd
import streamlit as st

from ui.styles import render_top_header


def render_trace_page(coordinator, store, logger, all_states):
    """Renders the multi-agent activity, execution trace stream, and parallel coordination flow."""
    render_top_header(
        title="Multi-Agent Orchestration & Execution Activity",
        subtitle="Live telemetry, inter-agent messaging, and Semantic Kernel tool execution trace for academic defense",
    )

    # --- TOP: VISUAL FAN-OUT / FAN-IN WORKFLOW DIAGRAM ---
    st.markdown("""
    <div style="font-size: 1.15rem; font-weight: 700; color: #0F2042; margin-bottom: 12px;">
        Multi-Agent Pipeline Architecture (Fan-Out / Fan-In)
    </div>
    """, unsafe_allow_html=True)

    # Clean Visual Workflow Cards
    w1, w2, w3, w4, w5 = st.columns([1.2, 1.3, 2.5, 1.5, 1.5])

    with w1:
        st.markdown("""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 3px solid #1E3A8A; border-radius: 8px; padding: 14px 12px; height: 100%;">
            <div style="font-size: 0.75rem; font-weight: 700; color: #64748B; text-transform: uppercase;">Stage 1: Intake</div>
            <div style="font-weight: 800; color: #0F2042; font-size: 0.95rem; margin: 4px 0;">Intake Agent</div>
            <div style="font-size: 0.78rem; color: #475569; line-height: 1.4;">
                • Schema validation<br>
                • Data ingestion<br>
                • State allocation
            </div>
        </div>
        """, unsafe_allow_html=True)

    with w2:
        st.markdown(r"""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 3px solid #0D9488; border-radius: 8px; padding: 14px 12px; height: 100%;">
            <div style="font-size: 0.75rem; font-weight: 700; color: #64748B; text-transform: uppercase;">Stage 2: Gate</div>
            <div style="font-weight: 800; color: #0F2042; font-size: 0.95rem; margin: 4px 0;">Eligibility Agent</div>
            <div style="font-size: 0.78rem; color: #475569; line-height: 1.4;">
                • Acad $\ge 60\%$<br>
                • Inc $\le ₹600\text{k}$<br>
                • Early exclusion gate
            </div>
        </div>
        """, unsafe_allow_html=True)

    with w3:
        st.markdown("""
        <div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-top: 3px solid #059669; border-radius: 8px; padding: 14px 12px; height: 100%;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.75rem; font-weight: 700; color: #047857; text-transform: uppercase;">Stage 3: Fan-Out</span>
                <span style="background: #DCFCE7; color: #15803D; font-size: 0.7rem; font-weight: 700; padding: 1px 6px; border-radius: 4px;">PARALLEL</span>
            </div>
            <div style="font-weight: 800; color: #065F46; font-size: 0.95rem; margin: 4px 0;">3 Specialist Scorers</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; font-size: 0.75rem; margin-top: 6px;">
                <div style="background: #FFFFFF; padding: 5px 6px; border-radius: 4px; border: 1px solid #A7F3D0; text-align: center;">
                    <b>Merit</b><br><span style="color:#0D9488;">40 pts</span>
                </div>
                <div style="background: #FFFFFF; padding: 5px 6px; border-radius: 4px; border: 1px solid #A7F3D0; text-align: center;">
                    <b>Need</b><br><span style="color:#0D9488;">35 pts</span>
                </div>
                <div style="background: #FFFFFF; padding: 5px 6px; border-radius: 4px; border: 1px solid #A7F3D0; text-align: center;">
                    <b>Achieve</b><br><span style="color:#0D9488;">25 pts</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with w4:
        st.markdown("""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 3px solid #2563EB; border-radius: 8px; padding: 14px 12px; height: 100%;">
            <div style="font-size: 0.75rem; font-weight: 700; color: #64748B; text-transform: uppercase;">Stage 4: Fan-In</div>
            <div style="font-weight: 800; color: #0F2042; font-size: 0.95rem; margin: 4px 0;">Panel Manager</div>
            <div style="font-size: 0.78rem; color: #475569; line-height: 1.4;">
                • Score aggregation<br>
                • 40/35/25 weighting<br>
                • Committee tier
            </div>
        </div>
        """, unsafe_allow_html=True)

    with w5:
        st.markdown("""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 3px solid #7C3AED; border-radius: 8px; padding: 14px 12px; height: 100%;">
            <div style="font-size: 0.75rem; font-weight: 700; color: #64748B; text-transform: uppercase;">Stage 5: Audit</div>
            <div style="font-weight: 800; color: #0F2042; font-size: 0.95rem; margin: 4px 0;">Fairness Auditor</div>
            <div style="font-size: 0.78rem; color: #475569; line-height: 1.4;">
                • Demographic scan<br>
                • Arithmetic check<br>
                • Commit to State
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if not all_states:
        st.warning("No applicants evaluated yet. Run an evaluation from the sidebar to generate live traces.")
        return

    # Applicant selector for trace inspection
    app_ids = [s.applicant_id for s in all_states]
    target_id = st.selectbox(
        "Select Candidate to Inspect Execution Activity:",
        options=app_ids,
        format_func=lambda x: f"{x} — {next(s.profile.full_name for s in all_states if s.applicant_id == x)} ({next(s.recommendation or 'Pending' for s in all_states if s.applicant_id == x)})",
    )

    state = next(s for s in all_states if s.applicant_id == target_id)

    # --- TWO COLUMN TELEMETRY: Trace Events + Semantic Kernel Tools ---
    col_trace, col_tools = st.columns([1.1, 1.1])

    with col_trace:
        st.markdown(f"""
        <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; margin-bottom: 12px;">
            Inter-Agent Message Stream ({len(state.trace_events)} Events)
        </div>
        """, unsafe_allow_html=True)

        if state.trace_events:
            for i, evt in enumerate(state.trace_events, start=1):
                badge_bg = "#EFF6FF" if "FAN" in evt.event_type else ("#F0FDF4" if "EVAL" in evt.event_type else "#F8FAFC")
                badge_fg = "#1E40AF" if "FAN" in evt.event_type else ("#15803D" if "EVAL" in evt.event_type else "#475569")
                st.markdown(f"""
                <div class="trace-item">
                    <div class="trace-item-header">
                        <span class="trace-item-agents">{i}. {evt.sender} ➔ {evt.receiver}</span>
                        <span class="trace-item-type" style="background: {badge_bg}; color: {badge_fg};">{evt.event_type}</span>
                    </div>
                    <div class="trace-item-text">{evt.payload_summary}</div>
                    <div style="font-size: 0.74rem; color: #94A3B8; margin-top: 4px;">Recorded: {evt.timestamp}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No inter-agent events recorded for this dossier yet.")

    with col_tools:
        st.markdown("""
        <div style="font-size: 1.05rem; font-weight: 700; color: #0F2042; margin-bottom: 12px;">
            Semantic Kernel Native Tool Invocations
        </div>
        """, unsafe_allow_html=True)

        app_logs = logger.get_applicant_logs(target_id)
        if app_logs:
            for j, log in enumerate(app_logs, start=1):
                with st.expander(f"Tool {j}: {log['agent_name']} ➔ `{log['tool_name']}` ({log['duration_seconds']}s)", expanded=(j <= 2)):
                    st.markdown(f"**Agent:** `{log['agent_name']}` | **Tool:** `{log['tool_name']}`")
                    st.markdown(f"**Status:** <span style='color:#059669; font-weight:700;'>{log['execution_status']}</span> ({log['duration_seconds']}s)", unsafe_allow_html=True)
                    st.markdown(f"**Input:** `{log['input_summary']}`")
                    st.markdown(f"**Output:** `{log['output_summary']}`")
                    st.caption(f"Rubric: {log['rubric_version']} | Hash: {log['config_hash'][:12]}... | {log['timestamp']}")
        else:
            st.info(f"No tool execution logs found for {target_id}. Run an evaluation to generate telemetry.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- COMPLETE IMMUTABLE AUDIT LOG TABLE ---
    with st.expander("🔍 Complete Append-Only System Audit Log (All Applicants & Executions)"):
        all_logs = logger.read_all_logs()
        if all_logs:
            audit_df = pd.DataFrame(all_logs)[
                ["timestamp", "applicant_id", "agent_name", "tool_name", "execution_status", "duration_seconds", "input_summary", "output_summary"]
            ]
            st.dataframe(audit_df, use_container_width=True, hide_index=True)
        else:
            st.info("Audit log file is empty.")
