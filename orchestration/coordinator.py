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
    """Coordinates multi-agent scholarship evaluation across the seven specialized agents."""

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

        # Gate Check: Enforce hard cutoffs before specialist fan-out
        if state.status == "INELIGIBLE":
            failed = state.eligibility.failed_rules if state.eligibility else []
            state.record_trace(
                sender="Coordinator",
                receiver="SpecialistAgents",
                event_type="SPECIALIST_SCORING_SKIPPED",
                payload_summary=f"Applicant is INELIGIBLE ({'; '.join(failed)}). Specialist scoring agents (Merit, Financial, Achievement) skipped per Clause 1.1/1.2.",
            )
            state.take_snapshot("Evaluation Terminated: Ineligible Disqualified")
            await self.store.save_state(state)
            duration = time.perf_counter() - start_time
            self.logger.log_sync(
                applicant_id=app_id,
                agent_name="Coordinator",
                tool_name="eligibility_gate_stop",
                input_summary=f"Hard eligibility cutoff stopped evaluation for {app_id}",
                output_summary=f"Status: INELIGIBLE, Failed Rules: {failed}",
                execution_status="SUCCESS",
                duration=duration,
            )
            return state

        if state.status == "NEEDS_REVIEW":
            missing = state.eligibility.missing_fields if state.eligibility else []
            state.record_trace(
                sender="Coordinator",
                receiver="SpecialistAgents",
                event_type="SPECIALIST_SCORING_SKIPPED",
                payload_summary=f"Applicant requires manual review (NEEDS_REVIEW) due to missing mandatory data: {missing}. Specialist scoring skipped per Clause 1.3.",
            )
            state.take_snapshot("Evaluation Terminated: Incomplete Needs Review")
            await self.store.save_state(state)
            duration = time.perf_counter() - start_time
            self.logger.log_sync(
                applicant_id=app_id,
                agent_name="Coordinator",
                tool_name="eligibility_gate_hold",
                input_summary=f"Missing documentation stopped automatic evaluation for {app_id}",
                output_summary=f"Status: NEEDS_REVIEW, Missing Fields: {missing}",
                execution_status="SUCCESS",
                duration=duration,
            )
            return state

        # Step 3: Fan-Out to Specialist Evaluation Agents in parallel (ONLY FOR ELIGIBLE CANDIDATES)
        state.record_trace(
            sender="Coordinator",
            receiver="SpecialistAgents",
            event_type="FAN_OUT_DISPATCH",
            payload_summary="Fanning out eligible applicant profile to Merit, Financial Need, and Achievement agents.",
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
        # Preserve all relevant specialist trace events without dropping events or introducing duplicates
        existing_event_ids = {evt.event_id for evt in state.trace_events}
        for spec_state in (merit_state, fin_state, ach_state):
            for evt in spec_state.trace_events:
                if evt.event_id not in existing_event_ids:
                    state.trace_events.append(evt)
                    existing_event_ids.add(evt.event_id)

        # Step 4: Fan-In through Panel Manager (Synthesizes composite score & recommendation)
        state.record_trace(
            sender="SpecialistAgents",
            receiver="PanelManagerAgent",
            event_type="FAN_IN_AGGREGATION",
            payload_summary="Fanning in specialist scores to Panel Manager for final adjudication.",
        )
        state = await self.panel_manager.adjudicate_applicant(state)
        await self.store.save_state(state)

        # Step 5: Fairness Auditor (Ethical review, bias check, score consistency, and limit verification)
        state = await self.fairness_auditor.audit_applicant(state)

        # Enforcement: A failed fairness audit prevents confirmed ranking until human review
        if state.audit_result and not state.audit_result.passed:
            state.status = "FLAGGED_FAIRNESS"
            state.recommendation = "Under Review - Fairness Audit Flagged"
            state.record_trace(
                sender="Coordinator",
                receiver="EvaluationState",
                event_type="FAIRNESS_AUDIT_INTERVENTION",
                payload_summary=f"Fairness audit failed ({state.audit_result.audit_notes}). Confirmed ranking blocked pending human review.",
            )
            state.take_snapshot("Status Overridden: Fairness Audit Failed")

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
        """Categorizes and sorts all evaluated applicants into formal committee pools with deterministic tie-breaking."""
        all_states = await self.store.list_all()

        confirmed_awardees: List[Dict[str, Any]] = []
        high_priority_pool: List[Dict[str, Any]] = []
        recommended_pool: List[Dict[str, Any]] = []
        consider_waitlist: List[Dict[str, Any]] = []
        low_priority_pool: List[Dict[str, Any]] = []
        fairness_quarantine_pool: List[Dict[str, Any]] = []
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
                "audit_notes": st.audit_result.audit_notes if st.audit_result else None,
            }

            # 1. Ineligible / Disqualified: strictly barred from awards
            if st.status == "INELIGIBLE":
                summary["disqualification_reasons"] = st.eligibility.failed_rules if st.eligibility else []
                ineligible_pool.append(summary)

            # 2. Incomplete / Needs Review: pending documentation
            elif st.status == "NEEDS_REVIEW":
                summary["missing_fields"] = st.eligibility.missing_fields if st.eligibility else []
                needs_review_pool.append(summary)

            # 3. Quarantined due to Failed Fairness / Consistency Audit
            elif st.status == "FLAGGED_FAIRNESS" or (st.audit_result and not st.audit_result.passed):
                summary["quarantine_reason"] = st.audit_result.audit_notes if st.audit_result else "Fairness or calculation consistency check failed"
                fairness_quarantine_pool.append(summary)

            # 4. Confirmed Awardees: High Priority
            elif st.recommendation == "High Priority":
                high_priority_pool.append(summary)
                confirmed_awardees.append(summary)

            # 5. Confirmed Awardees: Recommended
            elif st.recommendation == "Recommended":
                recommended_pool.append(summary)
                confirmed_awardees.append(summary)

            # 6. Consider / Secondary Allocation Waitlist (50.0 - 64.9)
            elif st.recommendation == "Consider":
                consider_waitlist.append(summary)

            # 7. Low Priority / Non-Competitive (< 50.0) - kept in waitlist pool & tracked in low_priority_pool
            elif st.recommendation == "Low Priority":
                low_priority_pool.append(summary)
                consider_waitlist.append(summary)

            else:
                # Pending evaluation or unclassified
                needs_review_pool.append(summary)

        # Deterministic multi-tier tie-breaking:
        # 1. Total score (descending)
        # 2. Academic percentage (descending)
        # 3. Household income (ascending — lower income receives priority)
        # 4. Achievement score (descending)
        # 5. Applicant ID (lexicographical ascending for stable deterministic sorting)
        def _tie_break_key(x: Dict[str, Any]):
            tot = x.get("total_score") if x.get("total_score") is not None else -1.0
            acad = x.get("academic_percentage") if x.get("academic_percentage") is not None else -1.0
            inc = x.get("household_income") if x.get("household_income") is not None else 999999999.0
            ach = x.get("achievement_score") if x.get("achievement_score") is not None else -1.0
            app_id = x.get("applicant_id") or ""
            # Reverse-sort helper: we want tot desc, acad desc, inc ASC, ach desc, app_id ASC
            # In Python, we can sort ascending by (-tot, -acad, inc, -ach, app_id)
            return (-tot, -acad, inc, -ach, app_id)

        confirmed_awardees.sort(key=_tie_break_key)
        high_priority_pool.sort(key=_tie_break_key)
        recommended_pool.sort(key=_tie_break_key)
        consider_waitlist.sort(key=_tie_break_key)
        low_priority_pool.sort(key=_tie_break_key)
        fairness_quarantine_pool.sort(key=_tie_break_key)

        return {
            "confirmed_awardees": confirmed_awardees,
            "high_priority_pool": high_priority_pool,
            "recommended_pool": recommended_pool,
            "consider_waitlist": consider_waitlist,
            "low_priority_pool": low_priority_pool,
            "fairness_quarantine_pool": fairness_quarantine_pool,
            "ineligible_disqualified": ineligible_pool,
            "needs_review": needs_review_pool,
        }

