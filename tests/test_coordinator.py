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


@pytest.mark.asyncio
async def test_ineligible_applicant_skips_specialists(coordinator):
    """Proves that ineligible applicants stop at Eligibility Gate and do NOT invoke specialist agents."""
    ineligible_raw = {
        "applicant_id": "APP-TEST-INELIG",
        "full_name": "Ineligible Academic Candidate",
        "academic_percentage": 52.0,  # Below 60% cutoff
        "household_income": 150000.0,
        "achievements": [],
    }
    state = await coordinator.evaluate_applicant(ineligible_raw)

    assert state.status == "INELIGIBLE"
    assert state.total_score is None
    # Specialist scoring results must NOT be generated
    assert state.academic_result is None
    assert state.financial_result is None
    assert state.achievement_result is None
    # Trace must explicitly record that specialist scoring was skipped
    skip_events = [t for t in state.trace_events if t.event_type == "SPECIALIST_SCORING_SKIPPED"]
    assert len(skip_events) == 1
    assert "INELIGIBLE" in skip_events[0].payload_summary

    # Ensure applicant is excluded from confirmed awardees
    leaderboard = await coordinator.get_ranked_leaderboard()
    confirmed_ids = [c["applicant_id"] for c in leaderboard["confirmed_awardees"]]
    assert "APP-TEST-INELIG" not in confirmed_ids
    ineligible_ids = [d["applicant_id"] for d in leaderboard["ineligible_disqualified"]]
    assert "APP-TEST-INELIG" in ineligible_ids


@pytest.mark.asyncio
async def test_incomplete_applicant_skips_specialists(coordinator):
    """Proves that incomplete applicants stop at Eligibility Gate and do NOT invoke specialist agents."""
    incomplete_raw = {
        "applicant_id": "APP-TEST-INCOMP",
        "full_name": "Incomplete Candidate",
        "academic_percentage": None,  # Missing mandatory academic record
        "household_income": 200000.0,
        "achievements": [],
    }
    state = await coordinator.evaluate_applicant(incomplete_raw)

    assert state.status == "NEEDS_REVIEW"
    assert state.total_score is None
    # Specialist scoring results must NOT be generated
    assert state.academic_result is None
    assert state.financial_result is None
    assert state.achievement_result is None
    skip_events = [t for t in state.trace_events if t.event_type == "SPECIALIST_SCORING_SKIPPED"]
    assert len(skip_events) == 1
    assert "NEEDS_REVIEW" in skip_events[0].payload_summary

    # Ensure applicant is excluded from confirmed awardees
    leaderboard = await coordinator.get_ranked_leaderboard()
    confirmed_ids = [c["applicant_id"] for c in leaderboard["confirmed_awardees"]]
    assert "APP-TEST-INCOMP" not in confirmed_ids
    needs_review_ids = [n["applicant_id"] for n in leaderboard["needs_review"]]
    assert "APP-TEST-INCOMP" in needs_review_ids


@pytest.mark.asyncio
async def test_fairness_failure_blocks_confirmed_ranking(coordinator, applicants_data):
    """Proves that failing the fairness audit quarantines candidate and blocks confirmed ranking."""
    app_data = applicants_data[0].copy()  # Eligible high scorer
    app_data["applicant_id"] = "APP-TEST-BIAS"

    # Evaluate applicant normally first
    state = await coordinator.evaluate_applicant(app_data)
    assert state.status == "ELIGIBLE_CONFIRMED"

    # Simulate an audit failure (e.g. prohibited attribute bias flag)
    from core.schemas import AuditResult
    state.audit_result = AuditResult(
        applicant_id="APP-TEST-BIAS",
        passed=False,
        audit_status="FAIL",
        bias_detected=True,
        flagged_attributes=["gender"],
        score_consistency_verified=True,
        audit_notes="BIAS DETECTED: Disallowed attribute ['gender'] referenced.",
    )
    state.status = "FLAGGED_FAIRNESS"
    state.recommendation = "Under Review - Fairness Audit Flagged"
    await coordinator.store.save_state(state)

    leaderboard = await coordinator.get_ranked_leaderboard()
    confirmed_ids = [c["applicant_id"] for c in leaderboard["confirmed_awardees"]]
    quarantined_ids = [q["applicant_id"] for q in leaderboard["fairness_quarantine_pool"]]

    # Applicant MUST be barred from confirmed awards and present in quarantine pool
    assert "APP-TEST-BIAS" not in confirmed_ids
    assert "APP-TEST-BIAS" in quarantined_ids


@pytest.mark.asyncio
async def test_persistence_across_simulated_restart(tmp_path, applicants_data):
    """Proves that evaluation states persist to disk and survive application reload."""
    db_file = str(tmp_path / "persistent_state.json")
    store1 = StateStore(persistence_file_path=db_file)
    logger = AuditLogger(str(tmp_path / "audit.jsonl"))
    coord1 = ScholarshipCoordinator(store=store1, logger=logger)

    app_data = applicants_data[0].copy()
    app_data["applicant_id"] = "APP-PERSIST-01"
    evaluated_state = await coord1.evaluate_applicant(app_data)
    assert evaluated_state.total_score is not None

    # Simulate application restart with a fresh store instance pointing to same file
    store2 = StateStore(persistence_file_path=db_file)
    restored_state = await store2.get_state("APP-PERSIST-01")

    assert restored_state is not None
    assert restored_state.applicant_id == "APP-PERSIST-01"
    assert restored_state.total_score == evaluated_state.total_score
    assert restored_state.status == evaluated_state.status
    assert restored_state.recommendation == evaluated_state.recommendation


@pytest.mark.asyncio
async def test_specialist_trace_events_fully_preserved_without_duplicates(coordinator, applicants_data):
    """Proves that all specialist trace events are preserved without truncation and without duplicates."""
    sample = applicants_data[0]  # Aarav Sharma: has multiple achievements
    state = await coordinator.evaluate_applicant(sample)

    event_ids = [e.event_id for e in state.trace_events]
    assert len(event_ids) == len(set(event_ids)), "Duplicate trace event IDs detected!"

    senders = [e.sender for e in state.trace_events]
    event_types = [e.event_type for e in state.trace_events]

    assert "MeritAgent" in senders
    assert "FinancialAgent" in senders
    assert "AchievementAgent" in senders
    assert "ACADEMIC_EVALUATED" in event_types
    assert "FINANCIAL_EVALUATED" in event_types
    assert "ACHIEVEMENT_EVALUATED" in event_types
    assert "PANEL_DECISION" in event_types or "DECISION_ADJUDICATED" in event_types
    assert "AUDIT_COMPLETED" in event_types


