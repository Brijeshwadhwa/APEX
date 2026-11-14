"""Core foundation package for Grant and Scholarship Application Evaluator.

Provides scoring configuration, Pydantic v2 schemas, shared state store,
append-only audit logger, and Semantic Kernel forward-reference compatibility.
"""

from core.scoring_config import (
    RUBRIC_VERSION,
    ACADEMIC_WEIGHT,
    FINANCIAL_NEED_WEIGHT,
    ACHIEVEMENT_WEIGHT,
    MIN_ACADEMIC_PERCENTAGE,
    MAX_HOUSEHOLD_INCOME,
    INCOME_BANDS,
    ACHIEVEMENT_LEVEL_POINTS,
    MAX_ACHIEVEMENT_SCORE,
    RECOMMENDATION_HIGH_PRIORITY,
    RECOMMENDATION_RECOMMENDED,
    RECOMMENDATION_CONSIDER,
    RECOMMENDATION_LOW_PRIORITY,
    PROHIBITED_SCORING_ATTRIBUTES,
    compute_academic_score,
    compute_financial_need_score,
    compute_achievement_score,
    resolve_recommendation,
    get_configuration_dict,
    get_configuration_hash,
)
from core.schemas import (
    AchievementRecord,
    ApplicantProfile,
    AcademicEvaluationResult,
    FinancialEvaluationResult,
    AchievementEvaluationResult,
    EligibilityResult,
    AuditResult,
    ErrorRecord,
    TraceEvent,
    GeminiAnalysisResult,
    GeminiExplanationResult,
    GeminiReportResult,
    GeminiRAGResult,
)
from core.shared_state import EvaluationState, StateStore
from core.audit_logger import AuditLogger
from core.gemini_service import GeminiService


_sk_compat_applied = False


def ensure_sk_compatibility() -> bool:
    """Safely apply Pydantic 2.13+ model_rebuild patch for Semantic Kernel 1.47.0 if installed.

    Resolves TYPE_CHECKING forward references in FilterContextBase and FunctionInvocationContext.
    """
    global _sk_compat_applied
    if _sk_compat_applied:
        return True
    try:
        from semantic_kernel.kernel import Kernel
        from semantic_kernel.functions.kernel_function import KernelFunction
        from semantic_kernel.functions.kernel_arguments import KernelArguments
        from semantic_kernel.functions.function_result import FunctionResult
        from semantic_kernel.filters.filter_context_base import FilterContextBase
        from semantic_kernel.filters.functions.function_invocation_context import FunctionInvocationContext

        ns = {
            "Kernel": Kernel,
            "KernelFunction": KernelFunction,
            "KernelArguments": KernelArguments,
            "FunctionResult": FunctionResult,
        }
        FilterContextBase.model_rebuild(_types_namespace=ns)
        FunctionInvocationContext.model_rebuild(_types_namespace=ns)
        _sk_compat_applied = True
        return True
    except (ImportError, AttributeError):
        return False


__all__ = [
    "RUBRIC_VERSION",
    "ACADEMIC_WEIGHT",
    "FINANCIAL_NEED_WEIGHT",
    "ACHIEVEMENT_WEIGHT",
    "MIN_ACADEMIC_PERCENTAGE",
    "MAX_HOUSEHOLD_INCOME",
    "INCOME_BANDS",
    "ACHIEVEMENT_LEVEL_POINTS",
    "MAX_ACHIEVEMENT_SCORE",
    "RECOMMENDATION_HIGH_PRIORITY",
    "RECOMMENDATION_RECOMMENDED",
    "RECOMMENDATION_CONSIDER",
    "RECOMMENDATION_LOW_PRIORITY",
    "PROHIBITED_SCORING_ATTRIBUTES",
    "compute_academic_score",
    "compute_financial_need_score",
    "compute_achievement_score",
    "resolve_recommendation",
    "get_configuration_dict",
    "get_configuration_hash",
    "AchievementRecord",
    "ApplicantProfile",
    "AcademicEvaluationResult",
    "FinancialEvaluationResult",
    "AchievementEvaluationResult",
    "EligibilityResult",
    "AuditResult",
    "ErrorRecord",
    "TraceEvent",
    "GeminiAnalysisResult",
    "GeminiExplanationResult",
    "GeminiReportResult",
    "GeminiRAGResult",
    "GeminiService",
    "EvaluationState",
    "StateStore",
    "AuditLogger",
    "ensure_sk_compatibility",
]

