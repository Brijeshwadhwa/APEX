"""Financial Need Agent: Evaluates economic need against progressive income bands with RAG citations."""

from decimal import Decimal
import time
from typing import Optional
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function, KernelArguments

from core import ensure_sk_compatibility
from core.schemas import FinancialEvaluationResult
from core.scoring_config import compute_financial_need_score, FINANCIAL_NEED_WEIGHT
from core.shared_state import EvaluationState
from core.audit_logger import AuditLogger
from rag.retriever import RubricRetriever

ensure_sk_compatibility()


class FinancialNeedPlugin:
    """Semantic Kernel plugin for financial need assessment and rubric retrieval."""

    def __init__(self, retriever: Optional[RubricRetriever] = None) -> None:
        self.retriever = retriever or RubricRetriever()

    @kernel_function(
        name="assess_financial_need",
        description="Maps annual household income to progressive scoring bands out of 35 points.",
    )
    def assess_financial_need(self, applicant_id: str, income_str: str) -> str:
        """Plain Python tool to evaluate financial need score."""
        income = Decimal(income_str) if income_str and income_str != "None" else None

        if income is None:
            res = FinancialEvaluationResult(
                applicant_id=applicant_id,
                annual_income=None,
                score=None,
                max_score=FINANCIAL_NEED_WEIGHT,
                income_band=None,
                status="MISSING_DATA",
                justification="Annual household income missing; cannot award financial need points.",
            )
            return res.model_dump_json()

        score, band = compute_financial_need_score(income)
        res = FinancialEvaluationResult(
            applicant_id=applicant_id,
            annual_income=income,
            score=score,
            max_score=FINANCIAL_NEED_WEIGHT,
            income_band=band,
            status="SUCCESS",
            justification=f"Household income of ₹{income:,.2f} falls into Band '{band}', awarding {score:.1f} out of {FINANCIAL_NEED_WEIGHT} need points.",
        )
        return res.model_dump_json()

    @kernel_function(
        name="retrieve_financial_rubric_citation",
        description="Retrieves official rubric clause governing financial need income brackets.",
    )
    def retrieve_financial_rubric_citation(self, query: str) -> str:
        """Plain Python tool to fetch grounded financial clause via RAG."""
        clause = self.retriever.get_clause_by_id("Clause 2.2")
        if clause:
            return f"{clause.clause_id}: {clause.title} — {clause.text}"
        clauses = self.retriever.retrieve_relevant_clauses("financial need income brackets weight 35", top_k=1)
        return clauses[0].text if clauses else "Section 2.2 - Financial Need Assessment (Max 35)"


class FinancialAgent:
    """Specialist agent responsible for evaluating household economic need."""

    def __init__(self, retriever: Optional[RubricRetriever] = None, logger: Optional[AuditLogger] = None) -> None:
        self.kernel = Kernel()
        self.retriever = retriever or RubricRetriever()
        self.logger = logger or AuditLogger()
        self.plugin = self.kernel.add_plugin(
            FinancialNeedPlugin(retriever=self.retriever), plugin_name="FinancialNeedPlugin"
        )

    async def evaluate_applicant(self, state: EvaluationState) -> EvaluationState:
        """Executes financial need evaluation using Semantic Kernel tools and updates state."""
        app_id = state.applicant_id
        profile = state.profile
        inc_str = str(profile.household_income) if profile.household_income is not None else "None"

        # Tool 1: Assess need
        t1_start = time.perf_counter()
        assess_func = self.plugin["assess_financial_need"]
        assess_res = await self.kernel.invoke(
            assess_func,
            KernelArguments(applicant_id=app_id, income_str=inc_str),
        )
        fin_result = FinancialEvaluationResult.model_validate_json(str(assess_res.value))
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="FinancialAgent",
            tool_name="assess_financial_need",
            input_summary=f"income={inc_str}",
            output_summary=f"score={fin_result.score}, band={fin_result.income_band}",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t1_start,
        )

        # Tool 2: Retrieve RAG citation
        t2_start = time.perf_counter()
        rag_func = self.plugin["retrieve_financial_rubric_citation"]
        rag_res = await self.kernel.invoke(rag_func, KernelArguments(query="financial need brackets"))
        citation = str(rag_res.value)
        fin_result.rubric_reference = citation
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="FinancialAgent",
            tool_name="retrieve_financial_rubric_citation",
            input_summary="Querying Clause 2.2 for financial need brackets",
            output_summary=f"Cited: {citation[:80]}...",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t2_start,
        )

        state.financial_result = fin_result
        state.record_trace(
            sender="FinancialAgent",
            receiver="EvaluationState",
            event_type="FINANCIAL_EVALUATED",
            payload_summary=f"Financial Score: {fin_result.score}/35. Band: {fin_result.income_band}",
        )
        state.take_snapshot(f"Financial Evaluated: {fin_result.score}/35")
        return state

