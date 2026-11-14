"""Merit / Academic Evaluation Agent: Evaluates academic score against 40-point rubric with RAG citations."""

from decimal import Decimal
import time
from typing import Optional
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function, KernelArguments

from core import ensure_sk_compatibility
from core.schemas import AcademicEvaluationResult
from core.scoring_config import compute_academic_score, ACADEMIC_WEIGHT
from core.shared_state import EvaluationState
from core.audit_logger import AuditLogger
from rag.retriever import RubricRetriever

ensure_sk_compatibility()


class MeritPlugin:
    """Semantic Kernel plugin for academic merit scoring and rubric retrieval."""

    def __init__(self, retriever: Optional[RubricRetriever] = None) -> None:
        self.retriever = retriever or RubricRetriever()

    @kernel_function(
        name="calculate_academic_score",
        description="Calculates proportional academic merit score out of 40 based on percentage.",
    )
    def calculate_academic_score(self, applicant_id: str, percentage_str: str) -> str:
        """Plain Python tool to compute academic score."""
        percentage = Decimal(percentage_str) if percentage_str and percentage_str != "None" else None

        if percentage is None:
            res = AcademicEvaluationResult(
                applicant_id=applicant_id,
                percentage=None,
                score=None,
                max_score=ACADEMIC_WEIGHT,
                status="MISSING_DATA",
                justification="Academic percentage missing; cannot award academic points.",
            )
            return res.model_dump_json()

        score = compute_academic_score(percentage)
        res = AcademicEvaluationResult(
            applicant_id=applicant_id,
            percentage=percentage,
            score=score,
            max_score=ACADEMIC_WEIGHT,
            status="SUCCESS",
            justification=f"Academic percentage {percentage}% awards {score:.2f} out of {ACADEMIC_WEIGHT} points (scaled linearly: ({percentage}/100) * {ACADEMIC_WEIGHT}).",
        )
        return res.model_dump_json()

    @kernel_function(
        name="retrieve_academic_rubric_citation",
        description="Retrieves official rubric clause governing academic merit calculation.",
    )
    def retrieve_academic_rubric_citation(self, query: str) -> str:
        """Plain Python tool to fetch grounded academic clause via RAG."""
        clause = self.retriever.get_clause_by_id("Clause 2.1")
        if clause:
            return f"{clause.clause_id}: {clause.title} — {clause.text}"
        clauses = self.retriever.retrieve_relevant_clauses("academic merit performance weight 40", top_k=1)
        return clauses[0].text if clauses else "Section 2.1 - Academic Performance (Max 40)"


class MeritAgent:
    """Specialist agent responsible for evaluating academic records."""

    def __init__(self, retriever: Optional[RubricRetriever] = None, logger: Optional[AuditLogger] = None) -> None:
        self.kernel = Kernel()
        self.retriever = retriever or RubricRetriever()
        self.logger = logger or AuditLogger()
        self.plugin = self.kernel.add_plugin(
            MeritPlugin(retriever=self.retriever), plugin_name="MeritPlugin"
        )

    async def evaluate_applicant(self, state: EvaluationState) -> EvaluationState:
        """Executes academic merit evaluation using Semantic Kernel tools and updates state."""
        app_id = state.applicant_id
        profile = state.profile
        pct_str = str(profile.academic_percentage) if profile.academic_percentage is not None else "None"

        # Tool 1: Calculate score
        t1_start = time.perf_counter()
        score_func = self.plugin["calculate_academic_score"]
        score_res = await self.kernel.invoke(
            score_func,
            KernelArguments(applicant_id=app_id, percentage_str=pct_str),
        )
        acad_result = AcademicEvaluationResult.model_validate_json(str(score_res.value))
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="MeritAgent",
            tool_name="calculate_academic_score",
            input_summary=f"percentage={pct_str}",
            output_summary=f"score={acad_result.score}, status={acad_result.status}",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t1_start,
        )

        # Tool 2: Retrieve RAG citation
        t2_start = time.perf_counter()
        rag_func = self.plugin["retrieve_academic_rubric_citation"]
        rag_res = await self.kernel.invoke(rag_func, KernelArguments(query="academic performance"))
        citation = str(rag_res.value)
        acad_result.rubric_reference = citation
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="MeritAgent",
            tool_name="retrieve_academic_rubric_citation",
            input_summary="Querying Clause 2.1 for academic weighting",
            output_summary=f"Cited: {citation[:80]}...",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t2_start,
        )

        state.academic_result = acad_result
        state.record_trace(
            sender="MeritAgent",
            receiver="EvaluationState",
            event_type="ACADEMIC_EVALUATED",
            payload_summary=f"Academic Score: {acad_result.score}/40. Justification: {acad_result.justification}",
        )
        state.take_snapshot(f"Academic Evaluated: {acad_result.score}/40")
        return state

