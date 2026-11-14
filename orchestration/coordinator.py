"""Pipeline Coordinator: Orchestrates Fan-Out / Fan-In multi-agent scholarship evaluation."""

import asyncio
from decimal import Decimal
import time
from typing import Any, Dict, List, Optional

from core.shared_state import EvaluationState, StateStore
from core.audit_logger import AuditLogger
from rag.retriever import RubricRetriever
from agents.intake_agent import IntakeAgent
from agents.eligibility_agent import EligibilityAgent
from agents.merit_agent import MeritAgent
from agents.financial_agent import FinancialAgent
from agents.achievement_agent import AchievementAgent
from agents.panel_manager import PanelManagerAgent
from agents.fairness_auditor import FairnessAuditorAgent


class ScholarshipCoordinator:
    """Coordinates multi-agent scholarship evaluation across the 6 specialist agents."""

    def __init__(
        self,
        store: Optional[StateStore] = None,
        logger: Optional[AuditLogger] = None,
        retriever: Optional[RubricRetriever] = None,
    ) -> None:
        self.store = store or StateStore()
        self.logger = logger or AuditLogger()
        self.retriever = retriever or RubricRetriever()

        # Initialize specialist agents
        self.intake_agent = IntakeAgent(logger=self.logger)
        self.eligibility_agent = EligibilityAgent(retriever=self.retriever, logger=self.logger)
        self.merit_agent = MeritAgent(retriever=self.retriever, logger=self.logger)
        self.financial_agent = FinancialAgent(retriever=self.retriever, logger=self.logger)
        self.achievement_agent = AchievementAgent(retriever=self.retriever, logger=self.logger)
        self.panel_manager = PanelManagerAgent(retriever=self.retriever, logger=self.logger)
        self.fairness_auditor = FairnessAuditorAgent(retriever=self.retriever, logger=self.logger)

    async def evaluate_applicant(self, raw_data: Dict[str, Any]) -> EvaluationState:
        """Executes the complete multi-agent lifecycle for a single applicant."""
        app_id = raw_data.get("applicant_id", "UNKNOWN")
        start_time = time.perf_counter()

        # Step 1: Intake Agent (Validates and initializes state)
        state = await self.intake_agent.process_applicant(raw_data)
        await self.store.save_state(state)

        # Step 2: Eligibility Verification Agent (Checks hard gates)
        state = await self.eligibility_agent.evaluate_applicant(state)
        await self.store.save_state(state)

        # Step 3: Fan-Out to Specialist Evaluation Agents in parallel
        state.record_trace(
            sender="Coordinator",
            receiver="SpecialistAgents",
            event_type="FAN_OUT_DISPATCH",
            payload_summary="Fanning out applicant profile to Merit, Financial Need, and Achievement agents.",
        )

        merit_task = self.merit_agent.evaluate_applicant(state)
        fin_task = self.financial_agent.evaluate_applicant(state)
        ach_task = self.achievement_agent.evaluate_applicant(state)

        # Run parallel evaluations
        merit_state, fin_state, ach_state = await asyncio.gather(merit_task, fin_task, ach_task)

        # Merge specialist results into common state
        state.academic_result = merit_state.academic_result
        state.financial_result = fin_state.financial_result
        state.achievement_result = ach_state.achievement_result
        state.trace_events.extend(merit_state.trace_events[-1:])
        state.trace_events.extend(fin_state.trace_events[-1:])
        state.trace_events.extend(ach_state.trace_events[-1:])

        # Step 4: Fan-In through Panel Manager (Synthesizes composite score & recommendation)
        state.record_trace(
            sender="SpecialistAgents",
            receiver="PanelManagerAgent",
            event_type="FAN_IN_AGGREGATION",
            payload_summary="Fanning in specialist scores to Panel Manager for final adjudication.",
        )
        state = await self.panel_manager.adjudicate_applicant(state)
        await self.store.save_state(state)

        # Step 5: Fairness Auditor (Ethical review and calculation verification)
        state = await self.fairness_auditor.audit_applicant(state)
        await self.store.save_state(state)

        duration = time.perf_counter() - start_time
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="Coordinator",
            tool_name="pipeline_complete",
            input_summary=f"End-to-end evaluation for {app_id}",
            output_summary=f"Final Status: {state.status}, Recommendation: {state.recommendation}, Score: {state.total_score}",
            execution_status="SUCCESS",
            duration=duration,
        )

        return state

    async def evaluate_batch(self, applicants_data: List[Dict[str, Any]]) -> List[EvaluationState]:
        """Evaluates a batch of applicant records concurrently under store lock protection."""
        tasks = [self.evaluate_applicant(app) for app in applicants_data]
        results = await asyncio.gather(*tasks)
        return results

    async def get_ranked_leaderboard(self) -> Dict[str, List[Dict[str, Any]]]:
        """Categorizes and sorts all evaluated applicants into formal committee pools."""
        all_states = await self.store.list_all()

        confirmed_awardees: List[Dict[str, Any]] = []
        consider_waitlist: List[Dict[str, Any]] = []
        ineligible_pool: List[Dict[str, Any]] = []
        needs_review_pool: List[Dict[str, Any]] = []

        for st in all_states:
            summary = {
                "applicant_id": st.applicant_id,
                "full_name": st.profile.full_name,
                "academic_percentage": float(st.profile.academic_percentage) if st.profile.academic_percentage is not None else None,
                "household_income": float(st.profile.household_income) if st.profile.household_income is not None else None,
                "academic_score": float(st.academic_result.score) if st.academic_result and st.academic_result.score is not None else None,
                "financial_score": float(st.financial_result.score) if st.financial_result and st.financial_result.score is not None else None,
                "achievement_score": float(st.achievement_result.score) if st.achievement_result and st.achievement_result.score is not None else None,
                "total_score": float(st.total_score) if st.total_score is not None else None,
                "recommendation": st.recommendation,
                "status": st.status,
                "audit_passed": st.audit_result.passed if st.audit_result else None,
            }

            if st.status == "INELIGIBLE":
                summary["disqualification_reasons"] = st.eligibility.failed_rules if st.eligibility else []
                ineligible_pool.append(summary)
            elif st.status == "NEEDS_REVIEW":
                summary["missing_fields"] = st.eligibility.missing_fields if st.eligibility else []
                needs_review_pool.append(summary)
            elif st.recommendation in ("High Priority", "Recommended"):
                confirmed_awardees.append(summary)
            else:
                consider_waitlist.append(summary)

        # Sort confirmed pools by descending total score
        confirmed_awardees.sort(key=lambda x: x["total_score"] or 0, reverse=True)
        consider_waitlist.sort(key=lambda x: x["total_score"] or 0, reverse=True)

        return {
            "confirmed_awardees": confirmed_awardees,
            "consider_waitlist": consider_waitlist,
            "ineligible_disqualified": ineligible_pool,
            "needs_review": needs_review_pool,
        }

