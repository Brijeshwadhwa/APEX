"""Fairness Auditor / Consistency Reviewer Agent: Audits decisions for bias and mathematical accuracy."""

from decimal import Decimal
import json
import time
from typing import Optional
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function, KernelArguments

from core import ensure_sk_compatibility
from core.schemas import AuditResult
from core.scoring_config import PROHIBITED_SCORING_ATTRIBUTES, resolve_recommendation
from core.shared_state import EvaluationState
from core.audit_logger import AuditLogger
from rag.retriever import RubricRetriever

ensure_sk_compatibility()


class FairnessAuditPlugin:
    """Semantic Kernel plugin for bias auditing and mathematical consistency verification."""

    def __init__(self, retriever: Optional[RubricRetriever] = None) -> None:
        self.retriever = retriever or RubricRetriever()

    @kernel_function(
        name="audit_demographic_bias",
        description="Inspects evaluation justification texts to verify prohibited attributes did not influence scores.",
    )
    def audit_demographic_bias(self, applicant_id: str, justification_texts_json: str) -> str:
        """Plain Python tool to detect prohibited bias keywords in evaluation rationales."""
        texts = json.loads(justification_texts_json)
        combined_text = " ".join(texts).lower()

        flagged_attributes = []
        for attr in PROHIBITED_SCORING_ATTRIBUTES:
            # Check for direct mentions in rationale
            if f"due to {attr}" in combined_text or f"because of {attr}" in combined_text or f"penalty for {attr}" in combined_text:
                flagged_attributes.append(attr)

        bias_detected = len(flagged_attributes) > 0
        notes = (
            f"BIAS DETECTED: Disallowed attribute(s) {flagged_attributes} referenced in score rationales."
            if bias_detected
            else "Bias Audit Passed: Evaluation strictly blind to prohibited demographic attributes."
        )

        return json.dumps({
            "bias_detected": bias_detected,
            "flagged_attributes": flagged_attributes,
            "notes": notes,
        })

    @kernel_function(
        name="verify_mathematical_consistency",
        description="Verifies that individual component scores correctly sum to the reported total and match thresholds.",
    )
    def verify_mathematical_consistency(
        self,
        applicant_id: str,
        academic_score_str: str,
        financial_score_str: str,
        achievement_score_str: str,
        total_score_str: str,
        recommendation: str,
    ) -> str:
        """Plain Python tool to verify mathematical summation and recommendation consistency."""
        if total_score_str == "None":
            # Ineligible or incomplete candidates have None total score
            return json.dumps({
                "math_consistent": True,
                "notes": "Verified exclusion consistency: non-eligible applicant has no confirmed total score.",
            })

        acad = Decimal(academic_score_str)
        fin = Decimal(financial_score_str)
        ach = Decimal(achievement_score_str)
        reported_total = Decimal(total_score_str)

        computed_sum = acad + fin + ach
        sum_matches = computed_sum == reported_total
        expected_rec = resolve_recommendation(computed_sum)
        rec_matches = expected_rec == recommendation

        consistent = sum_matches and rec_matches
        notes = (
            f"Mathematical check verified: {acad} + {fin} + {ach} = {computed_sum} exactly matches total {reported_total}. Threshold category '{recommendation}' confirmed."
            if consistent
            else f"MATHEMATICAL DISCREPANCY: Sum is {computed_sum} vs reported {reported_total}, or rec '{recommendation}' != expected '{expected_rec}'."
        )

        return json.dumps({
            "math_consistent": consistent,
            "notes": notes,
        })


class FairnessAuditorAgent:
    """Specialist auditor ensuring ethical fairness, non-discrimination, and calculation soundness."""

    def __init__(self, retriever: Optional[RubricRetriever] = None, logger: Optional[AuditLogger] = None) -> None:
        self.kernel = Kernel()
        self.retriever = retriever or RubricRetriever()
        self.logger = logger or AuditLogger()
        self.plugin = self.kernel.add_plugin(
            FairnessAuditPlugin(retriever=self.retriever), plugin_name="FairnessAuditPlugin"
        )

    async def audit_applicant(self, state: EvaluationState) -> EvaluationState:
        """Runs the fairness and consistency audit on an applicant's evaluated state."""
        app_id = state.applicant_id

        # Collect justifications from all modules
        justifications = []
        if state.eligibility:
            justifications.append(state.eligibility.justification)
        if state.academic_result:
            justifications.append(state.academic_result.justification)
        if state.financial_result:
            justifications.append(state.financial_result.justification)
        if state.achievement_result:
            justifications.append(state.achievement_result.justification)

        # Tool 1: Audit demographic bias
        t1_start = time.perf_counter()
        bias_func = self.plugin["audit_demographic_bias"]
        bias_res = await self.kernel.invoke(
            bias_func,
            KernelArguments(applicant_id=app_id, justification_texts_json=json.dumps(justifications)),
        )
        bias_data = json.loads(str(bias_res.value))
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="FairnessAuditorAgent",
            tool_name="audit_demographic_bias",
            input_summary="Auditing justification texts for bias",
            output_summary=f"bias_detected={bias_data['bias_detected']}",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t1_start,
        )

        # Tool 2: Verify mathematical consistency
        t2_start = time.perf_counter()
        math_func = self.plugin["verify_mathematical_consistency"]
        acad_str = str(state.academic_result.score) if state.academic_result and state.academic_result.score is not None else "None"
        fin_str = str(state.financial_result.score) if state.financial_result and state.financial_result.score is not None else "None"
        ach_str = str(state.achievement_result.score) if state.achievement_result and state.achievement_result.score is not None else "None"
        total_str = str(state.total_score) if state.total_score is not None else "None"
        rec_str = state.recommendation or "None"

        math_res = await self.kernel.invoke(
            math_func,
            KernelArguments(
                applicant_id=app_id,
                academic_score_str=acad_str,
                financial_score_str=fin_str,
                achievement_score_str=ach_str,
                total_score_str=total_str,
                recommendation=rec_str,
            ),
        )
        math_data = json.loads(str(math_res.value))
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="FairnessAuditorAgent",
            tool_name="verify_mathematical_consistency",
            input_summary=f"Checking sum for total={total_str}",
            output_summary=f"math_consistent={math_data['math_consistent']}",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t2_start,
        )

        passed = (not bias_data["bias_detected"]) and math_data["math_consistent"]
        combined_notes = f"{bias_data['notes']} | {math_data['notes']}"

        audit_result = AuditResult(
            applicant_id=app_id,
            passed=passed,
            bias_detected=bias_data["bias_detected"],
            flagged_attributes=bias_data["flagged_attributes"],
            score_consistency_verified=math_data["math_consistent"],
            audit_notes=combined_notes,
        )

        state.audit_result = audit_result
        state.record_trace(
            sender="FairnessAuditorAgent",
            receiver="EvaluationState",
            event_type="AUDIT_COMPLETED",
            payload_summary=f"Audit Passed={passed}. Notes: {combined_notes}",
        )
        state.take_snapshot(f"Fairness Audit: {'PASSED' if passed else 'FLAGGED'}")
        return state

