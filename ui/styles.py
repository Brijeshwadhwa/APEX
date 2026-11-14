"""Enterprise UI Design System & Component Library for Scholarship Management Portal.

Color Palette:
- Primary Navy: #0F2042, #1E3A8A
- Accent Teal: #0D9488, #14B8A6
- Background: #F8FAFC (Slate-50)
- Surface/Card: #FFFFFF
- Text Main: #0F172A (Slate-900)
- Text Muted: #475569 (Slate-600)
- Border: #E2E8F0 (Slate-200)
- Status: Emerald (#059669), Amber (#D97706), Rose (#DC2626), Blue (#2563EB)
"""

import streamlit as st


def inject_custom_css():
    """Injects comprehensive light-theme CSS overrides and responsive styles."""
    css = """
    <style>
        /* Import clean modern typography */
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

        /* Global resets and text contrast */
        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            color: #0F172A !important;
            background-color: #F8FAFC !important;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            color: #0F2042 !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
        }

        /* Streamlit main view container */
        .stApp {
            background-color: #F8FAFC !important;
        }

        .main .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 3rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            max-width: 1400px !important;
        }

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 1px solid #E2E8F0 !important;
            box-shadow: 1px 0 3px rgba(0, 0, 0, 0.02) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            padding: 1.25rem 1rem !important;
        }
        section[data-testid="stSidebar"] h1, 
        section[data-testid="stSidebar"] h2, 
        section[data-testid="stSidebar"] h3 {
            color: #0F2042 !important;
        }
        section[data-testid="stSidebar"] .stRadio label {
            font-size: 0.95rem !important;
            font-weight: 500 !important;
            color: #334155 !important;
            padding: 8px 12px !important;
            border-radius: 8px !important;
            margin-bottom: 4px !important;
            transition: all 0.15s ease-in-out !important;
        }
        section[data-testid="stSidebar"] .stRadio label:hover {
            background-color: #F1F5F9 !important;
            color: #0F2042 !important;
        }

        /* Top Page Header */
        .portal-header {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }
        .portal-header-left {
            flex: 1;
            min-width: 280px;
        }
        .portal-header-title {
            font-size: 1.6rem;
            font-weight: 800;
            color: #0F2042;
            margin: 0;
            line-height: 1.2;
        }
        .portal-header-subtitle {
            font-size: 0.92rem;
            color: #64748B;
            margin: 6px 0 0 0;
            font-weight: 400;
        }
        .portal-header-badges {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }
        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background-color: #F0FDFA;
            color: #0D9488;
            border: 1px solid #CCFBF1;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .status-dot {
            width: 7px;
            height: 7px;
            background-color: #0D9488;
            border-radius: 50%;
            display: inline-block;
        }

        /* Universal Card Container */
        .portal-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 22px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        }
        .portal-card-header {
            font-size: 1.1rem;
            font-weight: 700;
            color: #0F2042;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            border-bottom: 1px solid #F1F5F9;
            padding-bottom: 10px;
        }

        /* Compact Metric Stat Cards */
        .stat-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 18px 20px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
        }
        .stat-card-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .stat-label {
            font-size: 0.82rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #64748B;
        }
        .stat-icon {
            font-size: 1.25rem;
            opacity: 0.85;
        }
        .stat-value {
            font-size: 2.1rem;
            font-weight: 800;
            color: #0F2042;
            line-height: 1.1;
            margin: 4px 0 6px 0;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }
        .stat-subtext {
            font-size: 0.8rem;
            color: #64748B;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        /* Badges */
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 4px 11px;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
            letter-spacing: 0.01em;
            line-height: 1.2;
        }
        .badge-eligible {
            background-color: #ECFDF5;
            color: #065F46;
            border: 1px solid #A7F3D0;
        }
        .badge-ineligible {
            background-color: #FEF2F2;
            color: #991B1B;
            border: 1px solid #FECACA;
        }
        .badge-review {
            background-color: #FFFBEB;
            color: #92400E;
            border: 1px solid #FDE68A;
        }
        .badge-high {
            background-color: #EFF6FF;
            color: #1E40AF;
            border: 1px solid #BFDBFE;
        }
        .badge-neutral {
            background-color: #F8FAFC;
            color: #475569;
            border: 1px solid #E2E8F0;
        }

        /* Form Inputs & Streamlit Widgets Overrides */
        .stTextInput input, .stNumberInput input, .stSelectbox select {
            background-color: #FFFFFF !important;
            color: #0F172A !important;
            border: 1px solid #CBD5E1 !important;
            border-radius: 8px !important;
            font-size: 0.95rem !important;
            padding: 9px 12px !important;
        }
        .stTextInput input:focus, .stNumberInput input:focus {
            border-color: #1E3A8A !important;
            box-shadow: 0 0 0 2px rgba(30, 58, 138, 0.15) !important;
        }
        label[data-testid="stWidgetLabel"] p {
            font-size: 0.88rem !important;
            font-weight: 600 !important;
            color: #1E293B !important;
            margin-bottom: 4px !important;
        }

        /* Streamlit Buttons */
        .stButton button {
            background-color: #FFFFFF !important;
            color: #1E293B !important;
            border: 1px solid #CBD5E1 !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 0.9rem !important;
            padding: 8px 16px !important;
            transition: all 0.15s ease !important;
        }
        .stButton button:hover {
            background-color: #F1F5F9 !important;
            border-color: #94A3B8 !important;
            color: #0F2042 !important;
        }
        .stButton button[kind="primary"] {
            background-color: #0F2042 !important;
            color: #FFFFFF !important;
            border: 1px solid #0F2042 !important;
            box-shadow: 0 1px 2px rgba(15, 32, 66, 0.2) !important;
        }
        .stButton button[kind="primary"]:hover {
            background-color: #1E3A8A !important;
            border-color: #1E3A8A !important;
            color: #FFFFFF !important;
            box-shadow: 0 3px 6px rgba(15, 32, 66, 0.3) !important;
        }

        /* Streamlit Tables & DataFrames */
        [data-testid="stDataFrame"] {
            border: 1px solid #E2E8F0 !important;
            border-radius: 10px !important;
            overflow: hidden !important;
            background-color: #FFFFFF !important;
        }

        /* Custom Section Titles */
        .section-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: #0F2042;
            margin: 24px 0 12px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* Agent Evaluation Card in Results */
        .agent-score-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 18px;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .agent-score-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
            border-bottom: 1px solid #F1F5F9;
            padding-bottom: 10px;
        }
        .agent-score-name {
            font-weight: 700;
            color: #0F2042;
            font-size: 0.98rem;
        }
        .agent-score-pts {
            background-color: #F0FDFA;
            color: #0D9488;
            border: 1px solid #CCFBF1;
            padding: 3px 10px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.95rem;
        }
        .agent-score-body {
            font-size: 0.88rem;
            color: #334155;
            line-height: 1.5;
        }
        .agent-citation-chip {
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-left: 3px solid #0D9488;
            padding: 6px 10px;
            border-radius: 0 6px 6px 0;
            font-size: 0.78rem;
            color: #475569;
            margin-top: 10px;
        }

        /* Trace Event Box */
        .trace-item {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-left: 4px solid #1E3A8A;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 10px;
        }
        .trace-item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.82rem;
            color: #64748B;
            margin-bottom: 6px;
        }
        .trace-item-agents {
            font-weight: 700;
            color: #0F2042;
        }
        .trace-item-type {
            background-color: #F1F5F9;
            color: #334155;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .trace-item-text {
            font-size: 0.88rem;
            color: #1E293B;
            margin: 0;
        }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_top_header(title: str, subtitle: str, extra_badges: list = None):
    """Renders a sleek, modern, light-theme portal header with live status badges."""
    from core.scoring_config import RUBRIC_VERSION

    badges_html = f"""
    <div class="status-pill">
        <span class="status-dot"></span>
        <span>7 Agents Active</span>
    </div>
    <div class="status-pill" style="background-color: #EFF6FF; color: #1E40AF; border-color: #DBEAFE;">
        <span>Rubric v{RUBRIC_VERSION}</span>
    </div>
    """

    if extra_badges:
        for b in extra_badges:
            badges_html += f"""
            <div class="status-pill" style="background-color: #F8FAFC; color: #475569; border-color: #E2E8F0;">
                <span>{b}</span>
            </div>
            """

    header_html = f"""
    <div class="portal-header">
        <div class="portal-header-left">
            <h1 class="portal-header-title">{title}</h1>
            <p class="portal-header-subtitle">{subtitle}</p>
        </div>
        <div class="portal-header-badges">
            {badges_html}
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


def render_stat_card(label: str, value: str, subtext: str = "", icon: str = "📊", border_accent: str = "#E2E8F0"):
    """Renders an elegant, compact statistic card."""
    card_html = f"""
    <div class="stat-card" style="border-top: 3px solid {border_accent};">
        <div class="stat-card-top">
            <span class="stat-label">{label}</span>
            <span class="stat-icon">{icon}</span>
        </div>
        <div class="stat-value">{value}</div>
        <div class="stat-subtext">{subtext}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def get_recommendation_badge_html(rec: str) -> str:
    """Returns accessible, high-contrast status badge HTML."""
    if not rec:
        return '<span class="status-badge badge-neutral">Not Evaluated</span>'
    r = rec.lower()
    if "high" in r:
        return f'<span class="status-badge badge-eligible">⭐ {rec}</span>'
    elif "recommended" in r:
        return f'<span class="status-badge badge-high">✅ {rec}</span>'
    elif "consider" in r:
        return f'<span class="status-badge badge-review">⏳ {rec}</span>'
    elif "ineligible" in r or "disqualified" in r:
        return f'<span class="status-badge badge-ineligible">❌ {rec}</span>'
    elif "review" in r:
        return f'<span class="status-badge badge-review">⚠️ {rec}</span>'
    else:
        return f'<span class="status-badge badge-neutral">{rec}</span>'


def get_eligibility_badge_html(decision: str) -> str:
    """Returns accessible badge HTML for eligibility status."""
    if not decision:
        return '<span class="status-badge badge-neutral">PENDING</span>'
    d = decision.upper()
    if d == "ELIGIBLE":
        return '<span class="status-badge badge-eligible">● ELIGIBLE</span>'
    elif d == "INELIGIBLE":
        return '<span class="status-badge badge-ineligible">● INELIGIBLE</span>'
    elif d == "NEEDS_REVIEW":
        return '<span class="status-badge badge-review">● NEEDS REVIEW</span>'
    return f'<span class="status-badge badge-neutral">{d}</span>'
