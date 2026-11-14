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
        bias_patterns = [
            "due to {attr}", "because of {attr}", "penalty for {attr}",
            "based on {attr}", "bonus for {attr}", "weighted by {attr}",
            "applicant's {attr}", "candidate's {attr}", "{attr} factor",
            "{attr} preference", "considering {attr}", "favoring {attr}",
            "discounting {attr}", "adjusted for {attr}", "points for {attr}",
            "{attr}: female", "{attr}: male", "{attr}: hindu", "{attr}: muslim",
            "{attr}: christian", "{attr}: sikh", "caste factor", "caste penalty"
        ]

        for attr in PROHIBITED_SCORING_ATTRIBUTES:
            for pat in bias_patterns:
                check_str = pat.format(attr=attr)
                if check_str in combined_text and attr not in flagged_attributes:
                    flagged_attributes.append(attr)

        bias_detected = len(flagged_attributes) > 0
        evidence_verified = not bias_detected
        notes = (
            f"BIAS DETECTED: Disallowed demographic attribute(s) {flagged_attributes} referenced in evaluation rationales. Violates Clause 4.1."
            if bias_detected
            else "Heuristic Non-Discrimination Scan Passed: No overt prohibited demographic attribute references detected in rationales (Clause 4.1 compliant). [Limitation Note: Syntactic pattern scanning checks explicit terms; latent proxy bias requires human committee review]."
        )

        return json.dumps({
            "bias_detected": bias_detected,
            "flagged_attributes": flagged_attributes,
            "evidence_verified": evidence_verified,
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
        """Plain Python tool to verify mathematical summation, component maximums, and recommendation consistency."""
        if total_score_str == "None":
            # Ineligible or incomplete candidates have None total score
            return json.dumps({
                "math_consistent": True,
                "limits_consistent": True,
                "notes": "Verified exclusion consistency: non-eligible applicant has no confirmed total score.",
            })

        acad = Decimal(academic_score_str)
        fin = Decimal(financial_score_str)
        ach = Decimal(achievement_score_str)
        reported_total = Decimal(total_score_str)

        # 1. Verify component score maximums per Clause 2.1, 2.2, 2.3
        acad_ok = Decimal("0.0") <= acad <= Decimal("40.0")
        fin_ok = Decimal("0.0") <= fin <= Decimal("35.0")
        ach_ok = Decimal("0.0") <= ach <= Decimal("25.0")
        tot_ok = Decimal("0.0") <= reported_total <= Decimal("100.0")
        limits_ok = acad_ok and fin_ok and ach_ok and tot_ok

        limit_violations = []
        if not acad_ok:
            limit_violations.append(f"Academic score {acad} exceeds permitted ceiling [0, 40.0]")
        if not fin_ok:
            limit_violations.append(f"Financial score {fin} exceeds permitted ceiling [0, 35.0]")
        if not ach_ok:
            limit_violations.append(f"Achievement score {ach} exceeds permitted ceiling [0, 25.0]")
        if not tot_ok:
            limit_violations.append(f"Total score {reported_total} exceeds permitted ceiling [0, 100.0]")

        # 2. Verify mathematical summation consistency
        computed_sum = acad + fin + ach
        sum_matches = computed_sum == reported_total
        expected_rec = resolve_recommendation(computed_sum)
        rec_matches = expected_rec == recommendation

        consistent = sum_matches and rec_matches and limits_ok
        notes_parts = []
        if not limits_ok:
            notes_parts.append(f"SCORE MAXIMUM VIOLATION: {'; '.join(limit_violations)}")
        if not sum_matches:
            notes_parts.append(f"MATHEMATICAL SUM DISCREPANCY: {acad} + {fin} + {ach} = {computed_sum} != reported {reported_total}")
        if not rec_matches:
            notes_parts.append(f"RECOMMENDATION MISMATCH: Reported '{recommendation}' != expected '{expected_rec}'")
        if consistent:
            notes_parts.append(f"Mathematical check verified: {acad} + {fin} + {ach} = {computed_sum} matches {reported_total}. All component limits respected. Threshold category '{recommendation}' confirmed.")

        return json.dumps({
            "math_consistent": sum_matches and rec_matches,
            "limits_consistent": limits_ok,
            "consistent": consistent,
            "notes": " | ".join(notes_parts),
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

        limits_consistent = math_data.get("limits_consistent", True)
        math_consistent = math_data.get("math_consistent", True)
        evidence_verified = bias_data.get("evidence_verified", True)
        bias_detected = bias_data.get("bias_detected", False)

        passed = (not bias_detected) and math_consistent and limits_consistent and evidence_verified
        audit_status = "PASS" if passed else "FAIL"
        combined_notes = f"{bias_data['notes']} | {math_data['notes']}"

        audit_result = AuditResult(
            applicant_id=app_id,
            passed=passed,
            audit_status=audit_status,
            bias_detected=bias_detected,
            flagged_attributes=bias_data["flagged_attributes"],
            score_consistency_verified=math_consistent,
            component_limits_verified=limits_consistent,
            evidence_based_verified=evidence_verified,
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

