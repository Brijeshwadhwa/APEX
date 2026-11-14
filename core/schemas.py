"""Pydantic v2 domain schemas and data transfer models for Scholarship Evaluation.

All schemas strictly enforce types, maintain missing fields as None (no silent coercion
to zero), and utilize Decimal for monetary and score values.
"""

from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class AchievementRecord(BaseModel):
    """Represents a single achievement claimed by an applicant."""
    id: str = Field(..., description="Unique achievement identifier")
    title: str = Field(..., description="Name or title of achievement")
    level: Literal["INTERNATIONAL", "NATIONAL", "STATE", "DISTRICT", "INSTITUTIONAL"] = Field(
        ..., description="Standardized recognition tier"
    )
    description: Optional[str] = Field(default=None, description="Detailed description")
    is_verified: bool = Field(default=False, description="Whether supporting documentation was validated")
    year: Optional[int] = Field(default=None, description="Year achieved")
    certificate_id: Optional[str] = Field(default=None, description="Certificate registration number")

    @field_validator("level", mode="before")
    @classmethod
    def normalize_level(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip().upper()
        return v


class ApplicantProfile(BaseModel):
    """Complete applicant dossier submitted for grant/scholarship evaluation."""
    applicant_id: str = Field(..., description="Unique applicant identifier")
    full_name: str = Field(..., description="Legal name of applicant")
    email: Optional[str] = Field(default=None, description="Contact email")
    
    # Mandatory criteria fields: remain None if not supplied, NEVER silently replaced with 0
    academic_percentage: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0.0"),
        le=Decimal("100.0"),
        description="Aggregate academic percentage. None indicates missing record.",
    )
    household_income: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0.0"),
        description="Gross annual family income in INR. None indicates missing record.",
    )
    
    program_of_study: Optional[str] = Field(default=None, description="Degree or course program")
    institution: Optional[str] = Field(default=None, description="Current institution")
    achievements: List[AchievementRecord] = Field(
        default_factory=list, description="List of claimed achievements"
    )

    # Demographics fields: Tracked for audit and fairness verification only, prohibited in scoring
    gender: Optional[str] = Field(default=None, description="Demographic attribute (prohibited from scoring)")
    category: Optional[str] = Field(default=None, description="Social category (prohibited from scoring)")
    religion: Optional[str] = Field(default=None, description="Religious background (prohibited from scoring)")
    notes: Optional[str] = Field(default=None, description="Additional intake notes")


class AcademicEvaluationResult(BaseModel):
    """Output produced by Academic Evaluation / Merit specialist."""
    applicant_id: str = Field(..., description="Associated applicant ID")
    percentage: Optional[Decimal] = Field(default=None, description="Input academic percentage")
    score: Optional[Decimal] = Field(default=None, description="Awarded academic score out of 40")
    max_score: Decimal = Field(default=Decimal("40.0"), description="Maximum possible academic score")
    status: Literal["SUCCESS", "MISSING_DATA", "FAILED"] = Field(..., description="Evaluation outcome status")
    rubric_reference: str = Field(
        default="Section 2.1 - Academic Performance Evaluation (Max 40)",
        description="Cited rubric rule",
    )
    justification: str = Field(..., description="Written explanation justifying awarded score")


class FinancialEvaluationResult(BaseModel):
    """Output produced by Financial Need Evaluation specialist."""
    applicant_id: str = Field(..., description="Associated applicant ID")
    annual_income: Optional[Decimal] = Field(default=None, description="Verified household annual income")
    score: Optional[Decimal] = Field(default=None, description="Awarded need score out of 35")
    max_score: Decimal = Field(default=Decimal("35.0"), description="Maximum possible financial score")
    income_band: Optional[str] = Field(default=None, description="Matched income bracket")
    status: Literal["SUCCESS", "MISSING_DATA", "FAILED"] = Field(..., description="Evaluation outcome status")
    rubric_reference: str = Field(
        default="Section 2.2 - Financial Need Assessment (Max 35)",
        description="Cited rubric rule",
    )
    justification: str = Field(..., description="Written explanation justifying need points")


class AchievementEvaluationResult(BaseModel):
    """Output produced by Achievement Portfolio Evaluation specialist."""
    applicant_id: str = Field(..., description="Associated applicant ID")
    verified_count: int = Field(default=0, description="Number of verified achievements accepted")
    rejected_or_duplicate_count: int = Field(default=0, description="Number of unverified or duplicate items dropped")
    raw_score: Decimal = Field(default=Decimal("0.0"), description="Sum of raw achievement points")
    score: Decimal = Field(default=Decimal("0.0"), description="Capped score awarded out of 25")
    max_score: Decimal = Field(default=Decimal("25.0"), description="Maximum possible achievement score")
    evaluated_achievements: List[str] = Field(default_factory=list, description="Titles of recognized achievements")
    status: Literal["SUCCESS", "NO_ACHIEVEMENTS", "FAILED"] = Field(..., description="Evaluation outcome status")
    rubric_reference: str = Field(
        default="Section 2.3 - Achievement Portfolio Valuation (Max 25)",
        description="Cited rubric rule",
    )
    justification: str = Field(..., description="Written explanation of portfolio valuation")


class EligibilityResult(BaseModel):
    """Output produced by Eligibility Verification specialist."""
    applicant_id: str = Field(..., description="Associated applicant ID")
    is_eligible: Optional[bool] = Field(
        default=None,
        description="True if eligible, False if confirmed ineligible, None if data missing (needs review)",
    )
    decision: Literal["ELIGIBLE", "INELIGIBLE", "NEEDS_REVIEW"] = Field(
        ..., description="Categorical eligibility status"
    )
    failed_rules: List[str] = Field(default_factory=list, description="Rules failed by applicant")
    missing_fields: List[str] = Field(default_factory=list, description="Mandatory fields missing")
    justification: str = Field(..., description="Policy-grounded explanation")
    rubric_references: List[str] = Field(default_factory=list, description="Governing clause citations")


class AuditResult(BaseModel):
    """Output produced by Fairness Auditor / Consistency Reviewer."""
    applicant_id: str = Field(..., description="Associated applicant ID")
    passed: bool = Field(..., description="Whether decision passes bias and consistency checks")
    audit_status: str = Field(default="PASS", description="Audit outcome: PASS, FAIL, or NEEDS_REVIEW")
    bias_detected: bool = Field(default=False, description="Flag indicating reliance on prohibited demographics")
    flagged_attributes: List[str] = Field(default_factory=list, description="Prohibited attributes referenced")
    score_consistency_verified: bool = Field(default=True, description="Mathematical sum consistency check")
    component_limits_verified: bool = Field(default=True, description="Whether all component scores respect maximum ceilings (40, 35, 25)")
    evidence_based_verified: bool = Field(default=True, description="Whether decisions are grounded exclusively in authorized evaluation evidence")
    audit_notes: str = Field(..., description="Detailed audit narrative")


class ErrorRecord(BaseModel):
    """Structured failure record logged during agent execution."""
    applicant_id: Optional[str] = Field(default=None, description="Applicant being evaluated when error occurred")
    agent_name: str = Field(..., description="Module/agent where error was triggered")
    error_type: str = Field(..., description="Classification or exception type")
    message: str = Field(..., description="Descriptive error explanation")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional debugging context")


class TraceEvent(BaseModel):
    """Event representing inter-agent communication and state progression."""
    event_id: str = Field(..., description="Unique event identifier")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    applicant_id: Optional[str] = Field(default=None, description="Applicant associated with event")
    sender: str = Field(..., description="Originating agent")
    receiver: str = Field(..., description="Recipient or target state")
    event_type: str = Field(..., description="Classification e.g. FAN_OUT, AGENT_RESULT, FAN_IN")
    payload_summary: str = Field(..., description="Concise human-readable event summary")


class GeminiAnalysisResult(BaseModel):
    """Output produced by Gemini Application Analysis."""
    applicant_id: str = Field(..., description="Associated applicant ID")
    profile_summary: str = Field(..., description="Concise overview of applicant dossier")
    academic_observations: str = Field(..., description="Observations on academic performance")
    financial_summary: str = Field(..., description="Summary of financial circumstances")
    achievement_summary: str = Field(..., description="Summary of extracurricular portfolio")
    strengths: List[str] = Field(default_factory=list, description="Key candidate strengths identified")
    areas_requiring_verification: List[str] = Field(default_factory=list, description="Fields/records needing manual verification")
    missing_information_warnings: List[str] = Field(default_factory=list, description="Warnings for missing mandatory data")


class GeminiExplanationResult(BaseModel):
    """Output produced by Gemini explaining specialist agent findings."""
    applicant_id: str = Field(..., description="Associated applicant ID")
    eligibility_explanation: str = Field(..., description="Explanation of eligibility gate decision")
    merit_explanation: str = Field(..., description="Explanation of academic merit score calculation")
    financial_need_explanation: str = Field(..., description="Explanation of financial bracket and need score")
    achievement_explanation: str = Field(..., description="Explanation of verified achievements and points")
    panel_recommendation_explanation: str = Field(..., description="Explanation of composite score and recommendation tier")
    fairness_audit_explanation: str = Field(..., description="Explanation of non-discrimination and consistency audit")


class GeminiReportResult(BaseModel):
    """Comprehensive committee evaluation report produced by Gemini."""
    applicant_id: str = Field(..., description="Associated applicant ID")
    report_title: str = Field(..., description="Title of evaluation report")
    executive_summary: str = Field(..., description="Executive summary for the committee")
    evaluation_breakdown: str = Field(..., description="Deconstructed evaluation summary")
    main_strengths: List[str] = Field(default_factory=list, description="Main positive candidate attributes")
    concerns_and_missing_info: List[str] = Field(default_factory=list, description="Concerns, holds, or documentation deficiencies")
    recommendation_explanation: str = Field(..., description="In-depth rationale for final recommendation")
    rubric_references: List[str] = Field(default_factory=list, description="Governing rubric clauses cited")
    full_report_markdown: str = Field(..., description="Complete publication-ready markdown report")


class GeminiRAGResult(BaseModel):
    """Output produced by Gemini RAG question answering."""
    question: str = Field(..., description="Original user query")
    answer: str = Field(..., description="Grounded answer synthesized from rubric clauses")
    cited_clauses: List[str] = Field(default_factory=list, description="Clause IDs cited in response")
    rejected_citations: List[str] = Field(default_factory=list, description="Citations returned by model that were not in retrieved passages")
    retrieved_passages: List[Dict[str, Any]] = Field(default_factory=list, description="Passages retrieved prior to generation")
    source_document: str = Field(default="scholarship_rubric.md", description="Source rubric file")
    is_grounded: bool = Field(default=True, description="Whether the answer is substantiated by retrieved text")
    rubric_coverage_status: str = Field(..., description="Status e.g. COVERED_IN_RUBRIC or NOT_ESTABLISHED_IN_RUBRIC")


