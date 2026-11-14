"""UI package exposing page components and styles."""

from ui.styles import (
    inject_custom_css,
    render_top_header,
    render_stat_card,
    get_recommendation_badge_html,
    get_eligibility_badge_html,
)
from ui.page_overview import render_overview_page
from ui.page_applicants import render_applicants_page
from ui.page_new_application import render_new_application_page
from ui.page_results import render_results_page
from ui.page_trace import render_trace_page
from ui.page_rag import render_rag_page
from ui.page_ai_assistant import render_ai_assistant_page
from ui.page_leaderboard import render_leaderboard_page

# Aliases for backward compatibility
render_header = render_top_header
render_kpi = render_stat_card

__all__ = [
    "inject_custom_css",
    "render_top_header",
    "render_header",
    "render_stat_card",
    "render_kpi",
    "get_recommendation_badge_html",
    "get_eligibility_badge_html",
    "render_overview_page",
    "render_applicants_page",
    "render_new_application_page",
    "render_results_page",
    "render_trace_page",
    "render_rag_page",
    "render_ai_assistant_page",
    "render_leaderboard_page",
]
