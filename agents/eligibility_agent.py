"""Eligibility Verification Agent: Checks hard criteria boundaries and RAG citations."""

from decimal import Decimal
import json
import time
from typing import Optional
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function, KernelArguments

from core import ensure_sk_compatibility
from core.schemas import EligibilityResult
from core.scoring_config import MIN_ACADEMIC_PERCENTAGE, MAX_HOUSEHOLD_INCOME
from core.shared_state import EvaluationState
from core.audit_logger import AuditLogger
from rag.retriever import RubricRetriever

ensure_sk_compatibility()


class EligibilityPlugin:
    """Semantic Kernel plugin for eligibility verification and rubric retrieval."""

    def __init__(self, retriever: Optional[RubricRetriever] = None) -> None:
        self.retriever = retriever or RubricRetriever()

    @kernel_function(
        name="verify_eligibility_criteria",
        description="Evaluates applicant academic percentage and household income against hard eligibility rules.",
    )
    def verify_eligibility_criteria(
        self, applicant_id: str, percentage_str: str, income_str: str
    ) -> str:
        """Plain Python tool to evaluate hard eligibility constraints."""
        percentage = Decimal(percentage_str) if percentage_str and percentage_str != "None" else None
        income = Decimal(income_str) if income_str and income_str != "None" else None

        failed_rules = []
        missing_fields = []

        if percentage is None:
            missing_fields.append("Academic Percentage")
        elif percentage < MIN_ACADEMIC_PERCENTAGE:
            failed_rules.append(
                f"Academic percentage ({percentage}%) is below minimum threshold of {MIN_ACADEMIC_PERCENTAGE}%"
            )

        if income is None:
            missing_fields.append("Household Income")
        elif income > MAX_HOUSEHOLD_INCOME:
            failed_rules.append(
                f"Household income (₹{income:,.2f}) exceeds ceiling of ₹{MAX_HOUSEHOLD_INCOME:,.2f}"
            )

        # Decision resolution logic:
        # If any hard rule failed -> INELIGIBLE outright
        # Else if any mandatory field is missing -> NEEDS_REVIEW
        # Else -> ELIGIBLE
        if failed_rules:
            is_eligible = False
            decision = "INELIGIBLE"
            justification = "Disqualified: " + "; ".join(failed_rules)
        elif missing_fields:
            is_eligible = None
            decision = "NEEDS_REVIEW"
            justification = "Incomplete Submission: Missing " + ", ".join(missing_fields) + ". Pending manual verification."
        else:
            is_eligible = True
            decision = "ELIGIBLE"
            justification = f"Passed all eligibility criteria: Academic >= {MIN_ACADEMIC_PERCENTAGE}% and Income <= ₹{MAX_HOUSEHOLD_INCOME:,.2f}."

        result = EligibilityResult(
            applicant_id=applicant_id,
            is_eligible=is_eligible,
            decision=decision,
            failed_rules=failed_rules,
            missing_fields=missing_fields,
            justification=justification,
            rubric_references=[],
        )
        return result.model_dump_json()

    @kernel_function(
        name="retrieve_eligibility_rubric_citations",
        description="Retrieves governing eligibility clauses from the official scholarship rubric knowledge base.",
    )
    def retrieve_eligibility_rubric_citations(self, query: str) -> str:
        """Plain Python tool to fetch grounded eligibility clauses via RAG."""
        clauses = self.retriever.retrieve_relevant_clauses(query=query, top_k=2)
        citations = [f"{c.clause_id}: {c.title} — {c.text}" for c in clauses]
        return json.dumps(citations)


class EligibilityAgent:
    """Specialist agent responsible for verifying hard eligibility and enforcing exclusion gates."""

    def __init__(self, retriever: Optional[RubricRetriever] = None, logger: Optional[AuditLogger] = None) -> None:
        self.kernel = Kernel()
        self.retriever = retriever or RubricRetriever()
        self.logger = logger or AuditLogger()
        self.plugin = self.kernel.add_plugin(
            EligibilityPlugin(retriever=self.retriever), plugin_name="EligibilityPlugin"
        )

    async def evaluate_applicant(self, state: EvaluationState) -> EvaluationState:
        """Executes the eligibility evaluation using Semantic Kernel tools and updates state."""
        app_id = state.applicant_id
        profile = state.profile
        pct_str = str(profile.academic_percentage) if profile.academic_percentage is not None else "None"
        inc_str = str(profile.household_income) if profile.household_income is not None else "None"

        # Tool 1: Verify criteria
        t1_start = time.perf_counter()
        verify_func = self.plugin["verify_eligibility_criteria"]
        verify_res = await self.kernel.invoke(
            verify_func,
            KernelArguments(applicant_id=app_id, percentage_str=pct_str, income_str=inc_str),
        )
        eligibility = EligibilityResult.model_validate_json(str(verify_res.value))
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="EligibilityAgent",
            tool_name="verify_eligibility_criteria",
            input_summary=f"percentage={pct_str}, income={inc_str}",
            output_summary=f"decision={eligibility.decision}, is_eligible={eligibility.is_eligible}",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t1_start,
        )

        # Tool 2: Retrieve RAG citations
        t2_start = time.perf_counter()
        rag_func = self.plugin["retrieve_eligibility_rubric_citations"]
        rag_res = await self.kernel.invoke(
            rag_func,
            KernelArguments(query=f"eligibility minimum academic percentage {pct_str} income ceiling {inc_str}"),
        )
        citations = json.loads(str(rag_res.value))
        eligibility.rubric_references = citations
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="EligibilityAgent",
            tool_name="retrieve_eligibility_rubric_citations",
            input_summary="Querying eligibility clauses from rubric",
            output_summary=f"Retrieved {len(citations)} governing clauses",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t2_start,
        )

        # Update state
        state.eligibility = eligibility
        if eligibility.is_eligible is False:
            state.status = "INELIGIBLE"
            state.recommendation = "Ineligible - Disqualified"
        elif eligibility.decision == "NEEDS_REVIEW":
            state.status = "NEEDS_REVIEW"
            state.recommendation = "Under Review - Incomplete Data"

        state.record_trace(
            sender="EligibilityAgent",
            receiver="EvaluationState",
            event_type="ELIGIBILITY_EVALUATED",
            payload_summary=f"Decision: {eligibility.decision}. Reason: {eligibility.justification}",
        )
        state.take_snapshot(f"Eligibility Evaluated: {eligibility.decision}")
        return state

