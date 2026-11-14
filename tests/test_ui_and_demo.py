"""Integration and live scenario tests verifying demo scenarios A, B, and C."""

import asyncio
from decimal import Decimal
import os
import pytest

from core.shared_state import StateStore
from core.audit_logger import AuditLogger
from rag.retriever import RubricRetriever
from orchestration.coordinator import ScholarshipCoordinator


@pytest.fixture
def test_system(tmp_path):
    store = StateStore()
    logger = AuditLogger(str(tmp_path / "scenario_audit.jsonl"))
    retriever = RubricRetriever()
    coordinator = ScholarshipCoordinator(store=store, logger=logger, retriever=retriever)
    return coordinator, store, logger, retriever


@pytest.mark.asyncio
async def test_scenario_a_eligible_high_priority(test_system):
    """Scenario A: Valid applicant -> full agent evaluation -> High Priority recommendation -> ranked on leaderboard."""
    coordinator, store, logger, retriever = test_system

    candidate = {
        "applicant_id": "APP-SCENARIO-A",
        "full_name": "Ananya Raman",
        "email": "ananya.r@example.edu",
        "academic_percentage": 94.0,
        "household_income": 110000.0,
        "achievements": [
            {"id": "A1", "title": "International AI Olympiad Gold", "level": "INTERNATIONAL", "is_verified": True}
        ],
    }

    state = await coordinator.evaluate_applicant(candidate)

    # 1. Verify eligibility passed
    assert state.eligibility.is_eligible is True
    assert state.eligibility.decision == "ELIGIBLE"

    # 2. Verify score computations:
    # Acad: (94.0 / 100) * 40 = 37.60
    # Fin: 110k (<= 150k) = 35.0
    # Ach: International = 15.0
    # Total: 37.60 + 35.0 + 15.0 = 87.60 -> High Priority
    assert state.total_score == Decimal("87.60")
    assert state.recommendation == "High Priority"
    assert state.status == "ELIGIBLE_CONFIRMED"

    # 3. Verify presence on official confirmed leaderboard
    leaderboard = await coordinator.get_ranked_leaderboard()
    confirmed = leaderboard["confirmed_awardees"]
    assert any(c["applicant_id"] == "APP-SCENARIO-A" for c in confirmed)


@pytest.mark.asyncio
async def test_scenario_b_ineligible_disqualified(test_system):
    """Scenario B: Fails mandatory eligibility (<60% academic) -> Disqualified -> Excluded from confirmed awards."""
    coordinator, store, logger, retriever = test_system

    candidate = {
        "applicant_id": "APP-SCENARIO-B",
        "full_name": "Vikram Rathore",
        "email": "vikram.r@example.edu",
        "academic_percentage": 52.0,  # Below 60%
        "household_income": 140000.0,
        "achievements": [],
    }

    state = await coordinator.evaluate_applicant(candidate)

    # 1. Verify eligibility failed
    assert state.eligibility.is_eligible is False
    assert state.eligibility.decision == "INELIGIBLE"
    assert state.status == "INELIGIBLE"
    assert state.total_score is None

    # 2. Verify strictly barred from confirmed awards
    leaderboard = await coordinator.get_ranked_leaderboard()
    confirmed = leaderboard["confirmed_awardees"]
    assert not any(c["applicant_id"] == "APP-SCENARIO-B" for c in confirmed)

    # 3. Must be segregated in disqualified pool
    disqualified = leaderboard["ineligible_disqualified"]
    assert any(d["applicant_id"] == "APP-SCENARIO-B" for d in disqualified)


@pytest.mark.asyncio
async def test_scenario_c_incomplete_needs_review(test_system):
    """Scenario C: Missing mandatory income document -> Needs Review -> Cannot receive confirmed final ranking."""
    coordinator, store, logger, retriever = test_system

    candidate = {
        "applicant_id": "APP-SCENARIO-C",
        "full_name": "Siddharth Sen",
        "email": "siddharth.s@example.edu",
        "academic_percentage": 86.0,
        "household_income": None,  # Missing income record
        "achievements": [],
    }

    state = await coordinator.evaluate_applicant(candidate)

    # 1. Verify needs review decision
    assert state.eligibility.is_eligible is None
    assert state.eligibility.decision == "NEEDS_REVIEW"
    assert state.status == "NEEDS_REVIEW"
    assert state.total_score is None
    assert "Academic" not in state.eligibility.missing_fields
    assert "Household Income" in state.eligibility.missing_fields

    # 2. Verify strictly barred from confirmed awards
    leaderboard = await coordinator.get_ranked_leaderboard()
    confirmed = leaderboard["confirmed_awardees"]
    assert not any(c["applicant_id"] == "APP-SCENARIO-C" for c in confirmed)

    # 3. Must be present in needs review pool
    review_pool = leaderboard["needs_review"]
    assert any(r["applicant_id"] == "APP-SCENARIO-C" for r in review_pool)

