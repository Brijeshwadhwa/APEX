"""Achievement Portfolio Agent: Evaluates extracurricular and co-curricular achievements up to 25 points."""

from decimal import Decimal
import json
import time
from typing import Optional
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function, KernelArguments

from core import ensure_sk_compatibility
from core.schemas import AchievementEvaluationResult
from core.scoring_config import compute_achievement_score, MAX_ACHIEVEMENT_SCORE
from core.shared_state import EvaluationState
from core.audit_logger import AuditLogger
from rag.retriever import RubricRetriever

ensure_sk_compatibility()


class AchievementPlugin:
    """Semantic Kernel plugin for achievement portfolio scoring and rubric retrieval."""

    def __init__(self, retriever: Optional[RubricRetriever] = None) -> None:
        self.retriever = retriever or RubricRetriever()

    @kernel_function(
        name="evaluate_achievement_portfolio",
        description="Filters verified achievements, removes duplicates, sums tier points, and caps at 25.0.",
    )
    def evaluate_achievement_portfolio(self, applicant_id: str, achievements_json: str) -> str:
        """Plain Python tool to aggregate verified, distinct achievement points."""
        achievements_list = json.loads(achievements_json)

        if not achievements_list:
            res = AchievementEvaluationResult(
                applicant_id=applicant_id,
                verified_count=0,
                rejected_or_duplicate_count=0,
                raw_score=Decimal("0.0"),
                score=Decimal("0.0"),
                max_score=MAX_ACHIEVEMENT_SCORE,
                evaluated_achievements=[],
                status="NO_ACHIEVEMENTS",
                justification="No extracurricular achievements claimed or provided.",
            )
            return res.model_dump_json()

        capped_score, raw_score, verified_cnt, rej_cnt, titles = compute_achievement_score(achievements_list)
        justification = (
            f"Validated {verified_cnt} verified achievement(s) totalling {raw_score:.1f} raw points. "
            f"Capped at {capped_score:.1f} out of {MAX_ACHIEVEMENT_SCORE} maximum allowable points. "
            f"Excluded {rej_cnt} unverified or duplicate submission(s)."
        )

        res = AchievementEvaluationResult(
            applicant_id=applicant_id,
            verified_count=verified_cnt,
            rejected_or_duplicate_count=rej_cnt,
            raw_score=raw_score,
            score=capped_score,
            max_score=MAX_ACHIEVEMENT_SCORE,
            evaluated_achievements=titles,
            status="SUCCESS",
            justification=justification,
        )
        return res.model_dump_json()

    @kernel_function(
        name="retrieve_achievement_rubric_citation",
        description="Retrieves official rubric clause governing achievement tier points and ceilings.",
    )
    def retrieve_achievement_rubric_citation(self, query: str) -> str:
        """Plain Python tool to fetch grounded achievement clause via RAG."""
        clause = self.retriever.get_clause_by_id("Clause 2.3")
        if clause:
            return f"{clause.clause_id}: {clause.title} — {clause.text}"
        clauses = self.retriever.retrieve_relevant_clauses("achievement portfolio recognition points cap 25", top_k=1)
        return clauses[0].text if clauses else "Section 2.3 - Achievement Portfolio Valuation (Max 25)"


class AchievementAgent:
    """Specialist agent responsible for evaluating co-curricular achievement portfolios."""

    def __init__(self, retriever: Optional[RubricRetriever] = None, logger: Optional[AuditLogger] = None) -> None:
        self.kernel = Kernel()
        self.retriever = retriever or RubricRetriever()
        self.logger = logger or AuditLogger()
        self.plugin = self.kernel.add_plugin(
            AchievementPlugin(retriever=self.retriever), plugin_name="AchievementPlugin"
        )

    async def evaluate_applicant(self, state: EvaluationState) -> EvaluationState:
        """Executes achievement evaluation using Semantic Kernel tools and updates state."""
        app_id = state.applicant_id
        profile = state.profile
        ach_json = json.dumps([ach.model_dump() for ach in profile.achievements])

        # Tool 1: Evaluate portfolio
        t1_start = time.perf_counter()
        eval_func = self.plugin["evaluate_achievement_portfolio"]
        eval_res = await self.kernel.invoke(
            eval_func,
            KernelArguments(applicant_id=app_id, achievements_json=ach_json),
        )
        ach_result = AchievementEvaluationResult.model_validate_json(str(eval_res.value))
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="AchievementAgent",
            tool_name="evaluate_achievement_portfolio",
            input_summary=f"Count={len(profile.achievements)} achievements",
            output_summary=f"score={ach_result.score}, verified={ach_result.verified_count}",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t1_start,
        )

        # Tool 2: Retrieve RAG citation
        t2_start = time.perf_counter()
        rag_func = self.plugin["retrieve_achievement_rubric_citation"]
        rag_res = await self.kernel.invoke(rag_func, KernelArguments(query="achievement tiers points"))
        citation = str(rag_res.value)
        ach_result.rubric_reference = citation
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="AchievementAgent",
            tool_name="retrieve_achievement_rubric_citation",
            input_summary="Querying Clause 2.3 for achievement tier points",
            output_summary=f"Cited: {citation[:80]}...",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t2_start,
        )

        state.achievement_result = ach_result
        state.record_trace(
            sender="AchievementAgent",
            receiver="EvaluationState",
            event_type="ACHIEVEMENT_EVALUATED",
            payload_summary=f"Achievement Score: {ach_result.score}/25. Verified: {ach_result.verified_count}",
        )
        state.take_snapshot(f"Achievement Evaluated: {ach_result.score}/25")
        return state

