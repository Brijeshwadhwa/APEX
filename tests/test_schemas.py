"""Unit tests for Pydantic v2 schemas and validation rules."""

from decimal import Decimal
import pytest
from pydantic import ValidationError

from core.schemas import (
    ApplicantProfile,
    AchievementRecord,
    AcademicEvaluationResult,
    FinancialEvaluationResult,
    AchievementEvaluationResult,
    EligibilityResult,
    AuditResult,
    ErrorRecord,
    TraceEvent,
)


def test_applicant_profile_missing_values_remain_none():
    profile = ApplicantProfile(
        applicant_id="APP-001",
        full_name="Aarav Sharma",
    )
    # Crucial rule: Missing mandatory values must NOT be replaced with zero
    assert profile.academic_percentage is None
    assert profile.household_income is None
    assert profile.email is None
    assert profile.achievements == []


def test_applicant_profile_with_valid_decimals():
    profile = ApplicantProfile(
        applicant_id="APP-002",
        full_name="Bhavya Patel",
        academic_percentage=Decimal("84.50"),
        household_income=Decimal("240000.00"),
    )
    assert profile.academic_percentage == Decimal("84.50")
    assert profile.household_income == Decimal("240000.00")


def test_applicant_profile_percentage_validation():
    with pytest.raises(ValidationError):
        ApplicantProfile(
            applicant_id="APP-003",
            full_name="Invalid Percent",
            academic_percentage=Decimal("105.0"),
        )
    with pytest.raises(ValidationError):
        ApplicantProfile(
            applicant_id="APP-004",
            full_name="Negative Percent",
            academic_percentage=Decimal("-2.0"),
        )


def test_achievement_record_level_normalization():
    ach = AchievementRecord(
        id="ACH-01",
        title="National Debate",
        level="national",  # lowercase should be normalized to uppercase
        is_verified=True,
    )
    assert ach.level == "NATIONAL"
    assert ach.is_verified is True


def test_evaluation_result_models():
    acad = AcademicEvaluationResult(
        applicant_id="APP-001",
        percentage=Decimal("78.0"),
        score=Decimal("31.2"),
        status="SUCCESS",
        justification="78.0% achieves 31.2/40.0 points.",
    )
    assert acad.score == Decimal("31.2")
    assert acad.applicant_id == "APP-001"

    fin = FinancialEvaluationResult(
        applicant_id="APP-001",
        annual_income=Decimal("180000.0"),
        score=Decimal("28.0"),
        income_band="₹150,001–₹250,000",
        status="SUCCESS",
        justification="Income qualifies for 28.0 need points.",
    )
    assert fin.score == Decimal("28.0")
    assert fin.income_band == "₹150,001–₹250,000"

    ach = AchievementEvaluationResult(
        applicant_id="APP-001",
        verified_count=2,
        raw_score=Decimal("25.0"),
        score=Decimal("25.0"),
        status="SUCCESS",
        justification="Verified 2 achievements.",
    )
    assert ach.score == Decimal("25.0")

    elig = EligibilityResult(
        applicant_id="APP-001",
        is_eligible=True,
        decision="ELIGIBLE",
        justification="Passed all criteria.",
    )
    assert elig.is_eligible is True
    assert elig.decision == "ELIGIBLE"

    audit = AuditResult(
        applicant_id="APP-001",
        passed=True,
        bias_detected=False,
        score_consistency_verified=True,
        audit_notes="Fairness checks verified.",
    )
    assert audit.passed is True
    assert audit.bias_detected is False


def test_error_record_and_trace_event():
    err = ErrorRecord(
        applicant_id="APP-009",
        agent_name="IntakeAgent",
        error_type="MissingDataError",
        message="Income field missing in application document",
        timestamp="2026-11-13T10:00:00Z",
    )
    assert err.agent_name == "IntakeAgent"
    assert err.error_type == "MissingDataError"

    trace = TraceEvent(
        event_id="evt_001",
        timestamp="2026-11-13T10:00:00Z",
        applicant_id="APP-009",
        sender="Coordinator",
        receiver="EligibilityAgent",
        event_type="DISPATCH",
        payload_summary="Sent applicant profile to eligibility verification",
    )
    assert trace.sender == "Coordinator"
    assert trace.receiver == "EligibilityAgent"

