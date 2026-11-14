"""Unit tests for EvaluationState and StateStore: isolation, concurrency, deep-copy, and persistence."""

import asyncio
from decimal import Decimal
import os
import pytest

from core.schemas import (
    ApplicantProfile,
    AcademicEvaluationResult,
    FinancialEvaluationResult,
    AchievementEvaluationResult,
    EligibilityResult,
)
from core.shared_state import EvaluationState, StateStore


@pytest.fixture
def sample_profile_1():
    return ApplicantProfile(
        applicant_id="APP-001",
        full_name="Candidate One",
        academic_percentage=Decimal("85.0"),
        household_income=Decimal("120000.0"),
    )


@pytest.fixture
def sample_profile_2():
    return ApplicantProfile(
        applicant_id="APP-002",
        full_name="Candidate Two",
        academic_percentage=Decimal("70.0"),
        household_income=Decimal("300000.0"),
    )


def test_independent_applicant_state_isolation(sample_profile_1, sample_profile_2):
    s1 = EvaluationState(applicant_id="APP-001", profile=sample_profile_1)
    s2 = EvaluationState(applicant_id="APP-002", profile=sample_profile_2)

    # Mutating s1 should not leak into s2
    s1.record_trace("AgentA", "AgentB", "TEST", "Trace for applicant 1")
    assert len(s1.trace_events) == 1
    assert len(s2.trace_events) == 0

    s1.academic_result = AcademicEvaluationResult(
        applicant_id="APP-001",
        percentage=Decimal("85.0"),
        score=Decimal("34.0"),
        status="SUCCESS",
        justification="Score for app 1",
    )
    assert s2.academic_result is None


def test_total_score_and_recommendation_computation(sample_profile_1):
    state = EvaluationState(applicant_id="APP-001", profile=sample_profile_1)
    state.eligibility = EligibilityResult(
        applicant_id="APP-001",
        is_eligible=True,
        decision="ELIGIBLE",
        justification="Eligible",
    )
    state.academic_result = AcademicEvaluationResult(
        applicant_id="APP-001",
        percentage=Decimal("85.0"),
        score=Decimal("34.0"),
        status="SUCCESS",
        justification="Academic score",
    )
    state.financial_result = FinancialEvaluationResult(
        applicant_id="APP-001",
        annual_income=Decimal("120000.0"),
        score=Decimal("35.0"),
        status="SUCCESS",
        justification="Financial score",
    )
    state.achievement_result = AchievementEvaluationResult(
        applicant_id="APP-001",
        score=Decimal("15.0"),
        status="SUCCESS",
        justification="Achievement score",
    )

    total = state.compute_total_if_eligible()
    # 34.0 + 35.0 + 15.0 = 84.0 -> High Priority
    assert total == Decimal("84.0")
    assert state.total_score == Decimal("84.0")
    assert state.recommendation == "High Priority"
    assert state.status == "ELIGIBLE_CONFIRMED"


def test_ineligible_applicant_excluded_from_confirmed_ranking(sample_profile_1):
    state = EvaluationState(applicant_id="APP-001", profile=sample_profile_1)
    state.eligibility = EligibilityResult(
        applicant_id="APP-001",
        is_eligible=False,
        decision="INELIGIBLE",
        failed_rules=["Academic percentage below 60%"],
        justification="Disqualified",
    )
    state.academic_result = AcademicEvaluationResult(
        applicant_id="APP-001",
        score=Decimal("20.0"),
        status="SUCCESS",
        justification="Sub-par",
    )
    state.financial_result = FinancialEvaluationResult(
        applicant_id="APP-001",
        score=Decimal("35.0"),
        status="SUCCESS",
        justification="Need",
    )
    state.achievement_result = AchievementEvaluationResult(
        applicant_id="APP-001",
        score=Decimal("10.0"),
        status="SUCCESS",
        justification="Achievements",
    )

    total = state.compute_total_if_eligible()
    assert total is None
    assert state.total_score is None
    assert state.status == "INELIGIBLE"
    assert "Ineligible" in (state.recommendation or "")


@pytest.mark.asyncio
async def test_statestore_deep_copy_behavior(sample_profile_1):
    store = StateStore()
    state = EvaluationState(applicant_id="APP-001", profile=sample_profile_1)
    await store.save_state(state)

    # Fetching state returns a deep copy
    fetched_1 = await store.get_state("APP-001")
    assert fetched_1 is not None
    fetched_1.status = "MUTATED_OUTSIDE"

    # Store state remains unmodified
    fetched_2 = await store.get_state("APP-001")
    assert fetched_2 is not None
    assert fetched_2.status == "PENDING"


@pytest.mark.asyncio
async def test_statestore_concurrent_operations(sample_profile_1, sample_profile_2):
    store = StateStore()
    await store.save_state(EvaluationState(applicant_id="APP-001", profile=sample_profile_1))
    await store.save_state(EvaluationState(applicant_id="APP-002", profile=sample_profile_2))

    async def update_applicant_1():
        for i in range(10):
            await store.update_state(
                "APP-001",
                lambda st: st.record_trace("Coord", "AgentX", "CONCURRENT", f"Step {i}"),
            )
            await asyncio.sleep(0.001)

    async def update_applicant_2():
        for i in range(10):
            await store.update_state(
                "APP-002",
                lambda st: st.record_trace("Coord", "AgentY", "CONCURRENT", f"Step {i}"),
            )
            await asyncio.sleep(0.001)

    await asyncio.gather(update_applicant_1(), update_applicant_2())

    st1 = await store.get_state("APP-001")
    st2 = await store.get_state("APP-002")
    assert st1 is not None and len(st1.trace_events) == 10
    assert st2 is not None and len(st2.trace_events) == 10


def test_statestore_json_persistence(tmp_path, sample_profile_1, sample_profile_2):
    store = StateStore()
    s1 = EvaluationState(applicant_id="APP-001", profile=sample_profile_1)
    s2 = EvaluationState(applicant_id="APP-002", profile=sample_profile_2)
    s1.take_snapshot("Intake complete")

    store._states["APP-001"] = s1
    store._states["APP-002"] = s2

    json_file = str(tmp_path / "test_store.json")
    store.save_to_json(json_file)
    assert os.path.exists(json_file)

    new_store = StateStore()
    new_store.load_from_json(json_file)

    loaded_s1 = new_store._states.get("APP-001")
    assert loaded_s1 is not None
    assert loaded_s1.profile.full_name == "Candidate One"
    assert len(loaded_s1.history) == 1
    assert loaded_s1.history[0]["snapshot_label"] == "Intake complete"

