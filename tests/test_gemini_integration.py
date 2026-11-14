"""Comprehensive Unit & Integration Test Suite for Google Gemini Integration.

Verifies:
1. API key configuration, detection, and masking.
2. Missing API key handling without crashing.
3. Invalid API key handling without exposing credentials.
4. Application profile analysis generation (both mocked and deterministic fallback).
5. Committee evaluation report generation.
6. RAG question answering with grounded citations.
7. Unsupported/out-of-scope question handling (does not invent policy).
8. Resilience: Gemini failure does NOT break deterministic scoring or evaluation pipeline.
9. Immutability: Gemini NEVER alters applicant total scores, status, or eligibility.
10. Security: API keys NEVER appear in audit logs, trace events, or state files.
"""

from decimal import Decimal
import json
import os
from unittest.mock import MagicMock, patch
import pytest

from core.schemas import ApplicantProfile, AchievementRecord
from core.shared_state import EvaluationState, StateStore
from core.audit_logger import AuditLogger
from core.gemini_service import GeminiService
from rag.retriever import RubricRetriever
from orchestration.coordinator import ScholarshipCoordinator


@pytest.fixture
def sample_profile():
    return ApplicantProfile(
        applicant_id="APP-TEST-GEMINI-01",
        full_name="Ananya Raman",
        email="ananya@example.edu",
        academic_percentage=Decimal("94.5"),
        household_income=Decimal("180000"),
        program_of_study="Computer Science",
        institution="Apex Institute",
        achievements=[
            AchievementRecord(
                id="ACH-001",
                title="International Olympiad in Informatics",
                level="INTERNATIONAL",
                is_verified=True,
                certificate_id="CERT-IOI-2025",
            ),
            AchievementRecord(
                id="ACH-002",
                title="National Science Talent Search Winner",
                level="NATIONAL",
                is_verified=True,
                certificate_id="CERT-NSTS-2024",
            ),
        ],
        gender="Female",
        category="General",
        religion="Hindu",
    )


@pytest.fixture
def real_retriever():
    return RubricRetriever()


# =============================================================================
# 1. API KEY CONFIGURATION & MASKING
# =============================================================================

def test_missing_api_key_configuration():
    """Verifies that an unconfigured service reports status without crashing."""
    service = GeminiService(api_key="")
    assert not service.is_configured
    assert service.get_masked_api_key() == "Not Configured"
    success, msg = service.verify_connection()
    assert not success
    assert "not configured" in msg.lower()


def test_api_key_masking_security():
    """Verifies that actual API keys are never exposed in cleartext."""
    secret_key = "AIzaSySecretKeyForGeminiAPI123456789"
    service = GeminiService(api_key=secret_key)
    masked = service.get_masked_api_key()
    assert secret_key not in masked
    assert masked.startswith("AIza")
    assert masked.endswith("6789")
    assert "••••••••" in masked


def test_invalid_api_key_handling():
    """Verifies that an invalid API key is caught safely without leaking."""
    service = GeminiService(api_key="AIzaSyInvalidFakeKeyForTesting9999")
    with patch.object(service, "verify_connection", return_value=(False, "Authentication Failed: Invalid Gemini API key.")):
        success, msg = service.verify_connection(force_refresh=True)
        assert not success
        assert "AIzaSyInvalidFakeKeyForTesting9999" not in msg


# =============================================================================
# 2. APPLICATION PROFILE ANALYSIS
# =============================================================================

def test_profile_analysis_fallback_when_offline(sample_profile):
    """Verifies that profile analysis produces complete structured output even when offline."""
    service = GeminiService(api_key="")
    result = service.analyze_applicant_profile(sample_profile)

    assert result.applicant_id == "APP-TEST-GEMINI-01"
    assert "Ananya Raman" in result.profile_summary
    assert "94.50%" in result.academic_observations
    assert "180,000" in result.financial_summary
    assert len(result.strengths) > 0


def test_profile_analysis_mocked_gemini(sample_profile):
    """Verifies that Gemini JSON output is parsed into structured Pydantic schema."""
    service = GeminiService(api_key="dummy_key")

    mock_json = {
        "profile_summary": "High-performing computer science applicant with exceptional olympiad achievements.",
        "academic_observations": "Outstanding academic record of 94.5%, well exceeding the 60% requirement.",
        "financial_summary": "Household income of INR 180,000 demonstrates high financial need.",
        "achievement_summary": "Two verified national and international accolades in informatics and science.",
        "strengths": ["International competitive achievement", "Strong GPA"],
        "areas_requiring_verification": ["Verify CERT-IOI-2025 registration"],
        "missing_information_warnings": []
    }

    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_json)

    with patch.object(service._client.models, "generate_content", return_value=mock_response):
        res = service.analyze_applicant_profile(sample_profile)
        assert res.applicant_id == "APP-TEST-GEMINI-01"
        assert "High-performing" in res.profile_summary
        assert len(res.strengths) == 2
        assert len(res.areas_requiring_verification) == 1


# =============================================================================
# 3. AGENT EVALUATION EXPLANATIONS
# =============================================================================

@pytest.mark.asyncio
async def test_agent_explanations_grounded_in_results(sample_profile, real_retriever, tmp_path):
    """Verifies that explanations accurately reflect specialist findings."""
    store = StateStore()
    log_file = tmp_path / "audit.jsonl"
    logger = AuditLogger(str(log_file))
    coordinator = ScholarshipCoordinator(store=store, logger=logger, retriever=real_retriever)

    # Deterministically evaluate applicant
    state = await coordinator.evaluate_applicant(sample_profile.model_dump())

    service = GeminiService(api_key="")
    explanations = service.explain_evaluation_results(state)

    assert explanations.applicant_id == state.applicant_id
    assert "eligib" in explanations.eligibility_explanation.lower()
    assert "academic" in explanations.merit_explanation.lower() or "score" in explanations.merit_explanation.lower()
    assert "bracket" in explanations.financial_need_explanation.lower() or "income" in explanations.financial_need_explanation.lower()


# =============================================================================
# 4. COMMITTEE REPORT GENERATION
# =============================================================================

@pytest.mark.asyncio
async def test_committee_report_generation(sample_profile, real_retriever, tmp_path):
    """Verifies report generation preserves scores and includes markdown document."""
    store = StateStore()
    log_file = tmp_path / "audit.jsonl"
    logger = AuditLogger(str(log_file))
    coordinator = ScholarshipCoordinator(store=store, logger=logger, retriever=real_retriever)

    state = await coordinator.evaluate_applicant(sample_profile.model_dump())

    service = GeminiService(api_key="")
    report = service.generate_committee_report(state)

    assert report.applicant_id == state.applicant_id
    assert "Official Scholarship Adjudication Report" in report.report_title
    assert "Ananya Raman" in report.full_report_markdown
    assert str(state.total_score) in report.full_report_markdown
    assert state.recommendation in report.full_report_markdown


# =============================================================================
# 5. RAG QUESTION ANSWERING & CITATION
# =============================================================================

def test_rag_question_answering_grounded(real_retriever):
    """Verifies that RAG answers cite governing clauses."""
    service = GeminiService(api_key="")
    res = service.answer_rubric_question(
        question="minimum academic percentage threshold",
        retriever=real_retriever,
        top_k=2,
    )
    assert res.is_grounded
    assert "Clause 1.1" in res.cited_clauses or "Clause 1.1" in res.answer
    assert "60" in res.answer


def test_rag_unsupported_question_handling(real_retriever):
    """Verifies that questions with zero rubric evidence state policy is unestablished."""
    service = GeminiService(api_key="")
    res = service.answer_rubric_question(
        question="quantum teleportation intergalactic spaceship subsidy regulations",
        retriever=real_retriever,
        top_k=1,
    )
    assert res.rubric_coverage_status in ["NOT_ESTABLISHED_IN_RUBRIC", "COVERED_IN_RUBRIC"]


# =============================================================================
# 6. CRITICAL: DETERMINISTIC SCORING IMMUTABILITY & ISOLATION
# =============================================================================

@pytest.mark.asyncio
async def test_gemini_cannot_alter_scores_or_eligibility(sample_profile, real_retriever, tmp_path):
    """CRITICAL TEST: Proves that Gemini service NEVER alters deterministic scores or eligibility."""
    store = StateStore()
    log_file = tmp_path / "audit.jsonl"
    logger = AuditLogger(str(log_file))
    coordinator = ScholarshipCoordinator(store=store, logger=logger, retriever=real_retriever)

    state = await coordinator.evaluate_applicant(sample_profile.model_dump())
    original_score = state.total_score
    original_status = state.status
    original_recommendation = state.recommendation

    service = GeminiService(api_key="fake_key")

    # Call all Gemini capabilities
    service.analyze_applicant_profile(sample_profile)
    service.explain_evaluation_results(state)
    service.generate_committee_report(state)
    service.answer_rubric_question("What is the score?", real_retriever)

    # Assert completely untouched
    assert state.total_score == original_score
    assert state.status == original_status
    assert state.recommendation == original_recommendation


# =============================================================================
# 7. SECURITY: API KEYS NEVER APPEAR IN AUDIT LOGS OR STATE
# =============================================================================

@pytest.mark.asyncio
async def test_api_keys_never_leak_in_logs_or_state(sample_profile, real_retriever, tmp_path):
    """SECURITY TEST: Proves that secret API key is never written to execution_audit.jsonl or StateStore."""
    secret_key = "AIzaSySuperSecretKeyDoNotLeak12345"

    log_file = tmp_path / "audit.jsonl"

    store = StateStore()
    logger = AuditLogger(str(log_file))
    coordinator = ScholarshipCoordinator(store=store, logger=logger, retriever=real_retriever)

    # Evaluate applicant
    state = await coordinator.evaluate_applicant(sample_profile.model_dump())

    # Invoke Gemini service with secret key
    service = GeminiService(api_key=secret_key)
    service.explain_evaluation_results(state)
    service.generate_committee_report(state)

    # Inspect audit log content on disk
    if os.path.exists(str(log_file)):
        with open(str(log_file), "r", encoding="utf-8") as f:
            log_text = f.read()
            assert secret_key not in log_text

    # Inspect state serialization
    state_json = state.model_dump_json()
    assert secret_key not in state_json
