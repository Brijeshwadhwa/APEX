"""Panel Manager Agent: Fans in specialist results, enforces eligibility gates, and issues grounded recommendations."""

from decimal import Decimal
import json
import time
from typing import Optional
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function, KernelArguments

from core import ensure_sk_compatibility
from core.shared_state import EvaluationState
from core.scoring_config import resolve_recommendation
from core.audit_logger import AuditLogger
from rag.retriever import RubricRetriever

ensure_sk_compatibility()


class PanelManagerPlugin:
    """Semantic Kernel plugin for composite adjudication and recommendation assignment."""

    def __init__(self, retriever: Optional[RubricRetriever] = None) -> None:
        self.retriever = retriever or RubricRetriever()

    @kernel_function(
        name="adjudicate_scholarship_decision",
        description="Fans in scores from specialist agents, applies eligibility gates, and assigns final recommendation.",
    )
    def adjudicate_scholarship_decision(
        self,
        applicant_id: str,
        is_eligible_str: str,
        eligibility_decision: str,
        academic_score_str: str,
        financial_score_str: str,
        achievement_score_str: str,
    ) -> str:
        """Plain Python tool to synthesize composite score and enforce eligibility exclusion."""
        if is_eligible_str == "False" or eligibility_decision == "INELIGIBLE":
            return json.dumps({
                "status": "INELIGIBLE",
                "total_score": None,
                "recommendation": "Ineligible - Disqualified",
                "summary": "Candidate disqualified under Clause 1.1/1.2; excluded from confirmed ranking.",
            })

        if eligibility_decision == "NEEDS_REVIEW" or is_eligible_str == "None":
            return json.dumps({
                "status": "NEEDS_REVIEW",
                "total_score": None,
                "recommendation": "Under Review - Incomplete Data",
                "summary": "Candidate dossier missing mandatory documentation; pending administrative review under Clause 1.3.",
            })

        acad = Decimal(academic_score_str) if academic_score_str != "None" else None
        fin = Decimal(financial_score_str) if financial_score_str != "None" else None
        ach = Decimal(achievement_score_str) if achievement_score_str != "None" else None

        if acad is None or fin is None or ach is None:
            return json.dumps({
                "status": "NEEDS_REVIEW",
                "total_score": None,
                "recommendation": "Under Review - Missing Specialist Evaluation",
                "summary": "Specialist evaluations incomplete.",
            })

        total = acad + fin + ach
        recommendation = resolve_recommendation(total)
        summary = (
            f"Adjudicated composite score {total:.2f}/100.0 "
            f"(Academic: {acad:.2f}, Need: {fin:.1f}, Achievements: {ach:.1f}). "
            f"Award Classification: '{recommendation}'."
        )

        return json.dumps({
            "status": "ELIGIBLE_CONFIRMED",
            "total_score": str(total),
            "recommendation": recommendation,
            "summary": summary,
        })

    @kernel_function(
        name="retrieve_panel_rubric_citations",
        description="Retrieves official rubric clauses governing recommendation tiers and disqualified exclusions.",
    )
    def retrieve_panel_rubric_citations(self, query: str) -> str:
        """Plain Python tool to fetch grounded panel decision clauses via RAG."""
        c1 = self.retriever.get_clause_by_id("Clause 3.1")
        c2 = self.retriever.get_clause_by_id("Clause 3.2")
        citations = []
        if c1:
            citations.append(f"{c1.clause_id}: {c1.title} — {c1.text}")
        if c2:
            citations.append(f"{c2.clause_id}: {c2.title} — {c2.text}")
        return json.dumps(citations)


class PanelManagerAgent:
    """Coordinator agent responsible for fan-in aggregation, exclusion enforcement, and recommendation."""

    def __init__(self, retriever: Optional[RubricRetriever] = None, logger: Optional[AuditLogger] = None) -> None:
        self.kernel = Kernel()
        self.retriever = retriever or RubricRetriever()
        self.logger = logger or AuditLogger()
        self.plugin = self.kernel.add_plugin(
            PanelManagerPlugin(retriever=self.retriever), plugin_name="PanelManagerPlugin"
        )

    async def adjudicate_applicant(self, state: EvaluationState) -> EvaluationState:
        """Synthesizes all specialist evaluations and updates final state."""
        app_id = state.applicant_id
        elig = state.eligibility
        is_elig_str = str(elig.is_eligible) if elig else "None"
        elig_dec_str = elig.decision if elig else "NEEDS_REVIEW"

        acad_str = str(state.academic_result.score) if state.academic_result and state.academic_result.score is not None else "None"
        fin_str = str(state.financial_result.score) if state.financial_result and state.financial_result.score is not None else "None"
        ach_str = str(state.achievement_result.score) if state.achievement_result and state.achievement_result.score is not None else "None"

        # Tool 1: Adjudicate decision
        t1_start = time.perf_counter()
        adj_func = self.plugin["adjudicate_scholarship_decision"]
        adj_res = await self.kernel.invoke(
            adj_func,
            KernelArguments(
                applicant_id=app_id,
                is_eligible_str=is_elig_str,
                eligibility_decision=elig_dec_str,
                academic_score_str=acad_str,
                financial_score_str=fin_str,
                achievement_score_str=ach_str,
            ),
        )
        decision_data = json.loads(str(adj_res.value))
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="PanelManagerAgent",
            tool_name="adjudicate_scholarship_decision",
            input_summary=f"Eligible={is_elig_str}, Acad={acad_str}, Need={fin_str}, Ach={ach_str}",
            output_summary=f"Status={decision_data['status']}, Rec={decision_data['recommendation']}",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t1_start,
        )

        # Tool 2: Retrieve RAG citation
        t2_start = time.perf_counter()
        rag_func = self.plugin["retrieve_panel_rubric_citations"]
        rag_res = await self.kernel.invoke(rag_func, KernelArguments(query="panel recommendation quota exclusion"))
        citations = json.loads(str(rag_res.value))
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="PanelManagerAgent",
            tool_name="retrieve_panel_rubric_citations",
            input_summary="Querying Section 3 clauses for recommendation thresholds",
            output_summary=f"Retrieved {len(citations)} panel governing clauses",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t2_start,
        )

        # Apply results to state
        state.status = decision_data["status"]
        state.total_score = Decimal(decision_data["total_score"]) if decision_data["total_score"] is not None else None
        state.recommendation = decision_data["recommendation"]

        state.record_trace(
            sender="PanelManagerAgent",
            receiver="EvaluationState",
            event_type="DECISION_ADJUDICATED",
            payload_summary=decision_data["summary"],
        )
        state.take_snapshot(f"Panel Adjudication: {state.recommendation}")
        return state

