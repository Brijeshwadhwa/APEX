"""Specialist and coordinator agents for Scholarship Evaluation."""

from agents.intake_agent import IntakeAgent, IntakePlugin
from agents.eligibility_agent import EligibilityAgent, EligibilityPlugin
from agents.merit_agent import MeritAgent, MeritPlugin
from agents.financial_agent import FinancialAgent, FinancialNeedPlugin
from agents.achievement_agent import AchievementAgent, AchievementPlugin
from agents.panel_manager import PanelManagerAgent, PanelManagerPlugin
from agents.fairness_auditor import FairnessAuditorAgent, FairnessAuditPlugin

__all__ = [
    "IntakeAgent",
    "IntakePlugin",
    "EligibilityAgent",
    "EligibilityPlugin",
    "MeritAgent",
    "MeritPlugin",
    "FinancialAgent",
    "FinancialNeedPlugin",
    "AchievementAgent",
    "AchievementPlugin",
    "PanelManagerAgent",
    "PanelManagerPlugin",
    "FairnessAuditorAgent",
    "FairnessAuditPlugin",
]

