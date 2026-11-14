"""Unit and integration tests for ScholarshipCoordinator and full batch pipeline."""

import json
import os
import pytest

from core.shared_state import StateStore
from core.audit_logger import AuditLogger
from orchestration.coordinator import ScholarshipCoordinator


@pytest.fixture
def applicants_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "data", "applicants.json")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def coordinator(tmp_path):
    store = StateStore()
    logger = AuditLogger(str(tmp_path / "coordinator_audit.jsonl"))
    return ScholarshipCoordinator(store=store, logger=logger)


@pytest.mark.asyncio
async def test_coordinator_single_evaluation(coordinator, applicants_data):
    first_app = applicants_data[0]  # Aarav Sharma
    state = await coordinator.evaluate_applicant(first_app)

    assert state.applicant_id == "APP-2026-001"
    assert state.status == "ELIGIBLE_CONFIRMED"
    assert state.recommendation == "High Priority"
    assert state.total_score is not None and state.total_score >= 80.0
    assert state.audit_result is not None and state.audit_result.passed is True
    assert len(state.history) >= 4


@pytest.mark.asyncio
async def test_coordinator_batch_evaluation_all_17(coordinator, applicants_data):
    results = await coordinator.evaluate_batch(applicants_data)
    assert len(results) == len(applicants_data)

    leaderboard = await coordinator.get_ranked_leaderboard()

    # Confirmed awardees should have valid total scores and be sorted descending
    confirmed = leaderboard["confirmed_awardees"]
    assert len(confirmed) > 0
    scores = [item["total_score"] for item in confirmed]
    assert scores == sorted(scores, reverse=True)
    assert all(item["recommendation"] in ("High Priority", "Recommended") for item in confirmed)

    # Ineligible candidates must be segregated and have None total score
    ineligible = leaderboard["ineligible_disqualified"]
    assert len(ineligible) >= 3
    for disq in ineligible:
        assert disq["total_score"] is None
        assert disq["status"] == "INELIGIBLE"
        assert len(disq["disqualification_reasons"]) > 0

    # Incomplete records must be in needs review and have None total score
    needs_review = leaderboard["needs_review"]
    assert len(needs_review) >= 2
    for nr in needs_review:
        assert nr["total_score"] is None
        assert nr["status"] == "NEEDS_REVIEW"
        assert len(nr["missing_fields"]) > 0

    # Ensure all 17 applicants are accounted for across pools
    total_tracked = len(confirmed) + len(leaderboard["consider_waitlist"]) + len(ineligible) + len(needs_review)
    assert total_tracked == len(applicants_data)


@pytest.mark.asyncio
async def test_audit_logs_recorded_during_pipeline(coordinator, applicants_data):
    sample = applicants_data[:3]
    await coordinator.evaluate_batch(sample)

    logs = coordinator.logger.read_all_logs()
    assert len(logs) >= len(sample) * 6  # At least 6 tools/events per applicant

    agents_logged = {l["agent_name"] for l in logs}
    assert "IntakeAgent" in agents_logged
    assert "EligibilityAgent" in agents_logged
    assert "MeritAgent" in agents_logged
    assert "FinancialAgent" in agents_logged
    assert "AchievementAgent" in agents_logged
    assert "PanelManagerAgent" in agents_logged
    assert "FairnessAuditorAgent" in agents_logged

