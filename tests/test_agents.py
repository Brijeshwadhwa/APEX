"""Unit tests verifying all specialist agents and their Semantic Kernel plugin tools."""

from decimal import Decimal
import pytest

from core.schemas import ApplicantProfile, AchievementRecord
from core.shared_state import EvaluationState
from core.audit_logger import AuditLogger
from agents.intake_agent import IntakeAgent
from agents.eligibility_agent import EligibilityAgent
from agents.merit_agent import MeritAgent
from agents.financial_agent import FinancialAgent
from agents.achievement_agent import AchievementAgent
from agents.panel_manager import PanelManagerAgent
from agents.fairness_auditor import FairnessAuditorAgent


@pytest.fixture
def audit_logger(tmp_path):
    return AuditLogger(str(tmp_path / "agent_test_audit.jsonl"))


@pytest.fixture
def high_priority_raw():
    return {
        "applicant_id": "APP-TEST-001",
        "full_name": "Test High Performer",
        "academic_percentage": 90.0,
        "household_income": 120000.0,
        "achievements": [
            {"id": "A1", "title": "International Coding Gold", "level": "INTERNATIONAL", "is_verified": True},
            {"id": "A2", "title": "National Science Winner", "level": "NATIONAL", "is_verified": True},
        ],
    }


@pytest.mark.asyncio
async def test_intake_agent(high_priority_raw, audit_logger):
    agent = IntakeAgent(logger=audit_logger)
    state = await agent.process_applicant(high_priority_raw)

    assert state.applicant_id == "APP-TEST-001"
    assert state.profile.full_name == "Test High Performer"
    assert state.profile.academic_percentage == Decimal("90.0")
    assert state.status == "PENDING"
    assert len(state.trace_events) >= 1
    assert len(state.history) >= 1


@pytest.mark.asyncio
async def test_eligibility_agent_pass(high_priority_raw, audit_logger):
    intake = IntakeAgent(logger=audit_logger)
    state = await intake.process_applicant(high_priority_raw)

    agent = EligibilityAgent(logger=audit_logger)
    state = await agent.evaluate_applicant(state)

    assert state.eligibility is not None
    assert state.eligibility.is_eligible is True
    assert state.eligibility.decision == "ELIGIBLE"
    assert len(state.eligibility.rubric_references) >= 1


@pytest.mark.asyncio
async def test_eligibility_agent_ineligible_academic(audit_logger):
    raw = {
        "applicant_id": "APP-LOW-ACAD",
        "full_name": "Low Acad",
        "academic_percentage": 52.0,
        "household_income": 100000.0,
    }
    intake = IntakeAgent(logger=audit_logger)
    state = await intake.process_applicant(raw)

    agent = EligibilityAgent(logger=audit_logger)
    state = await agent.evaluate_applicant(state)

    assert state.eligibility.is_eligible is False
    assert state.eligibility.decision == "INELIGIBLE"
    assert state.status == "INELIGIBLE"
    assert any("below minimum threshold" in r for r in state.eligibility.failed_rules)


@pytest.mark.asyncio
async def test_eligibility_agent_ineligible_income(audit_logger):
    raw = {
        "applicant_id": "APP-HIGH-INC",
        "full_name": "High Income",
        "academic_percentage": 85.0,
        "household_income": 800000.0,
    }
    intake = IntakeAgent(logger=audit_logger)
    state = await intake.process_applicant(raw)

    agent = EligibilityAgent(logger=audit_logger)
    state = await agent.evaluate_applicant(state)

    assert state.eligibility.is_eligible is False
    assert state.eligibility.decision == "INELIGIBLE"
    assert any("exceeds ceiling" in r for r in state.eligibility.failed_rules)


@pytest.mark.asyncio
async def test_eligibility_agent_incomplete_needs_review(audit_logger):
    raw = {
        "applicant_id": "APP-MISSING",
        "full_name": "Missing Doc",
        "academic_percentage": None,
        "household_income": 200000.0,
    }
    intake = IntakeAgent(logger=audit_logger)
    state = await intake.process_applicant(raw)

    agent = EligibilityAgent(logger=audit_logger)
    state = await agent.evaluate_applicant(state)

    assert state.eligibility.is_eligible is None
    assert state.eligibility.decision == "NEEDS_REVIEW"
    assert state.status == "NEEDS_REVIEW"
    assert "Academic Percentage" in state.eligibility.missing_fields


@pytest.mark.asyncio
async def test_merit_agent_scoring(high_priority_raw, audit_logger):
    intake = IntakeAgent(logger=audit_logger)
    state = await intake.process_applicant(high_priority_raw)

    agent = MeritAgent(logger=audit_logger)
    state = await agent.evaluate_applicant(state)

    assert state.academic_result is not None
    # (90.0 / 100) * 40 = 36.00
    assert state.academic_result.score == Decimal("36.00")
    assert state.academic_result.status == "SUCCESS"
    assert "Clause 2.1" in state.academic_result.rubric_reference


@pytest.mark.asyncio
async def test_financial_agent_scoring(high_priority_raw, audit_logger):
    intake = IntakeAgent(logger=audit_logger)
    state = await intake.process_applicant(high_priority_raw)

    agent = FinancialAgent(logger=audit_logger)
    state = await agent.evaluate_applicant(state)

    assert state.financial_result is not None
    # 120,000 -> Band A (<= 150k) -> 35.0
    assert state.financial_result.score == Decimal("35.0")
    assert state.financial_result.income_band == "₹0–₹150,000"
    assert "Clause 2.2" in state.financial_result.rubric_reference


@pytest.mark.asyncio
async def test_achievement_agent_scoring(high_priority_raw, audit_logger):
    intake = IntakeAgent(logger=audit_logger)
    state = await intake.process_applicant(high_priority_raw)

    agent = AchievementAgent(logger=audit_logger)
    state = await agent.evaluate_applicant(state)

    assert state.achievement_result is not None
    # International (15) + National (10) = 25.0
    assert state.achievement_result.score == Decimal("25.0")
    assert state.achievement_result.verified_count == 2
    assert "Clause 2.3" in state.achievement_result.rubric_reference


@pytest.mark.asyncio
async def test_full_pipeline_fan_out_fan_in(high_priority_raw, audit_logger):
    # 1. Intake
    intake = IntakeAgent(logger=audit_logger)
    state = await intake.process_applicant(high_priority_raw)

    # 2. Eligibility
    elig_agent = EligibilityAgent(logger=audit_logger)
    state = await elig_agent.evaluate_applicant(state)

    # 3. Fan-out specialist agents
    merit_agent = MeritAgent(logger=audit_logger)
    fin_agent = FinancialAgent(logger=audit_logger)
    ach_agent = AchievementAgent(logger=audit_logger)

    state = await merit_agent.evaluate_applicant(state)
    state = await fin_agent.evaluate_applicant(state)
    state = await ach_agent.evaluate_applicant(state)

    # 4. Fan-in through Panel Manager
    panel_manager = PanelManagerAgent(logger=audit_logger)
    state = await panel_manager.adjudicate_applicant(state)

    # 36.00 (Acad) + 35.0 (Fin) + 25.0 (Ach) = 96.00 -> High Priority
    assert state.status == "ELIGIBLE_CONFIRMED"
    assert state.total_score == Decimal("96.00")
    assert state.recommendation == "High Priority"

    # 5. Fairness Auditor
    auditor = FairnessAuditorAgent(logger=audit_logger)
    state = await auditor.audit_applicant(state)

    assert state.audit_result is not None
    assert state.audit_result.passed is True
    assert state.audit_result.bias_detected is False
    assert state.audit_result.score_consistency_verified is True


@pytest.mark.asyncio
async def test_disqualified_applicant_exclusion_in_panel(audit_logger):
    raw = {
        "applicant_id": "APP-FAIL-ACAD",
        "full_name": "Disqualified Candidate",
        "academic_percentage": 50.0,
        "household_income": 120000.0,
    }
    intake = IntakeAgent(logger=audit_logger)
    state = await intake.process_applicant(raw)

    elig_agent = EligibilityAgent(logger=audit_logger)
    state = await elig_agent.evaluate_applicant(state)

    # Specialists still run
    state = await MeritAgent(logger=audit_logger).evaluate_applicant(state)
    state = await FinancialAgent(logger=audit_logger).evaluate_applicant(state)
    state = await AchievementAgent(logger=audit_logger).evaluate_applicant(state)

    # Panel Manager MUST exclude disqualified candidate from confirmed score
    panel = PanelManagerAgent(logger=audit_logger)
    state = await panel.adjudicate_applicant(state)

    assert state.status == "INELIGIBLE"
    assert state.total_score is None
    assert "Ineligible" in (state.recommendation or "")

