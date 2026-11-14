"""Shared State and Evaluation State Store for Scholarship Evaluation.

Guarantees thread-safe and asyncio-safe state operations, complete isolation between
applicants (no shared mutable state leakage), deep-copy protections, historical
snapshots, and JSON persistence.
"""

import asyncio
import copy
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
import threading
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from core.schemas import (
    ApplicantProfile,
    AcademicEvaluationResult,
    FinancialEvaluationResult,
    AchievementEvaluationResult,
    EligibilityResult,
    AuditResult,
    ErrorRecord,
    TraceEvent,
)
from core.scoring_config import (
    RUBRIC_VERSION,
    get_configuration_hash,
    resolve_recommendation,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvaluationState(BaseModel):
    """Encapsulates the complete, isolated lifecycle state of an applicant's evaluation."""
    applicant_id: str
    profile: ApplicantProfile
    
    # Specialist agent results
    eligibility: Optional[EligibilityResult] = None
    academic_result: Optional[AcademicEvaluationResult] = None
    financial_result: Optional[FinancialEvaluationResult] = None
    achievement_result: Optional[AchievementEvaluationResult] = None
    audit_result: Optional[AuditResult] = None

    # Aggregated adjudication
    total_score: Optional[Decimal] = None
    recommendation: Optional[str] = None
    status: str = Field(default="PENDING")  # PENDING, EVALUATING, ELIGIBLE_CONFIRMED, INELIGIBLE, NEEDS_REVIEW, FAILED

    # Execution telemetry and snapshots
    errors: List[ErrorRecord] = Field(default_factory=list)
    trace_events: List[TraceEvent] = Field(default_factory=list)
    history: List[Dict[str, Any]] = Field(default_factory=list)

    rubric_version: str = Field(default=RUBRIC_VERSION)
    config_hash: str = Field(default_factory=get_configuration_hash)
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)

    def record_trace(self, sender: str, receiver: str, event_type: str, payload_summary: str) -> TraceEvent:
        """Record an inter-agent trace event."""
        event = TraceEvent(
            event_id=f"evt_{len(self.trace_events) + 1}_{datetime.now(timezone.utc).strftime('%H%M%S%f')}",
            timestamp=_utc_now_iso(),
            applicant_id=self.applicant_id,
            sender=sender,
            receiver=receiver,
            event_type=event_type,
            payload_summary=payload_summary,
        )
        self.trace_events.append(event)
        self.updated_at = _utc_now_iso()
        return event

    def record_error(self, agent_name: str, error_type: str, message: str, context: Optional[Dict[str, Any]] = None) -> ErrorRecord:
        """Log an execution error in the state."""
        error = ErrorRecord(
            applicant_id=self.applicant_id,
            agent_name=agent_name,
            error_type=error_type,
            message=message,
            timestamp=_utc_now_iso(),
            context=context or {},
        )
        self.errors.append(error)
        self.status = "FAILED"
        self.updated_at = _utc_now_iso()
        return error

    def take_snapshot(self, label: str) -> Dict[str, Any]:
        """Capture an immutable state snapshot into history."""
        snapshot = {
            "snapshot_label": label,
            "timestamp": _utc_now_iso(),
            "status": self.status,
            "is_eligible": self.eligibility.is_eligible if self.eligibility else None,
            "eligibility_decision": self.eligibility.decision if self.eligibility else None,
            "academic_score": str(self.academic_result.score) if self.academic_result and self.academic_result.score is not None else None,
            "financial_score": str(self.financial_result.score) if self.financial_result and self.financial_result.score is not None else None,
            "achievement_score": str(self.achievement_result.score) if self.achievement_result and self.achievement_result.score is not None else None,
            "total_score": str(self.total_score) if self.total_score is not None else None,
            "recommendation": self.recommendation,
        }
        self.history.append(snapshot)
        self.updated_at = _utc_now_iso()
        return snapshot

    def compute_total_if_eligible(self) -> Optional[Decimal]:
        """Compute the final score out of 100 if all specialist scores are present and applicant is eligible.

        Sets total_score and recommendation.
        Returns total_score or None if missing data/ineligible.
        """
        if self.eligibility and self.eligibility.is_eligible is False:
            self.total_score = None
            self.recommendation = "Ineligible - Disqualified"
            self.status = "INELIGIBLE"
            self.updated_at = _utc_now_iso()
            return None

        if self.eligibility and self.eligibility.decision == "NEEDS_REVIEW":
            self.total_score = None
            self.recommendation = "Under Review - Incomplete Data"
            self.status = "NEEDS_REVIEW"
            self.updated_at = _utc_now_iso()
            return None

        acad_score = self.academic_result.score if self.academic_result else None
        fin_score = self.financial_result.score if self.financial_result else None
        ach_score = self.achievement_result.score if self.achievement_result else None

        if acad_score is None or fin_score is None or ach_score is None:
            self.total_score = None
            self.recommendation = "Pending Specialist Scores"
            self.updated_at = _utc_now_iso()
            return None

        total = acad_score + fin_score + ach_score
        self.total_score = total
        self.recommendation = resolve_recommendation(total)
        self.status = "ELIGIBLE_CONFIRMED"
        self.updated_at = _utc_now_iso()
        return total


class StateStore:
    """Thread-safe, asyncio-safe, and disk-persisted repository for managing isolated applicant evaluation states."""

    def __init__(self, persistence_file_path: Optional[str] = None) -> None:
        self._states: Dict[str, EvaluationState] = {}
        self._lock: Optional[asyncio.Lock] = None
        self._lock_loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread_lock = threading.Lock()
        self.persistence_file_path = os.path.abspath(persistence_file_path) if persistence_file_path else None

        if self.persistence_file_path and os.path.exists(self.persistence_file_path):
            try:
                self.load_from_json(self.persistence_file_path)
            except Exception:
                # Safe recovery on corrupt or partial file
                pass

    def _auto_save_to_disk(self) -> None:
        """Internal helper to automatically sync memory states to JSON disk storage."""
        if self.persistence_file_path:
            try:
                self.save_to_json(self.persistence_file_path)
            except Exception:
                pass

    def _get_lock(self) -> asyncio.Lock:
        """Lazily initialize asyncio.Lock inside active event loop, rebinding if loop changes."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if self._lock is None or self._lock_loop != current_loop:
            self._lock = asyncio.Lock()
            self._lock_loop = current_loop
        return self._lock

    def is_applicant_registered(self, applicant_id: str) -> bool:
        """Check whether an applicant ID already exists in the store to prevent duplicate submissions."""
        with self._thread_lock:
            return applicant_id in self._states

    async def get_state(self, applicant_id: str) -> Optional[EvaluationState]:
        """Retrieve a deep-copied evaluation state for a given applicant ID."""
        async with self._get_lock():
            state = self._states.get(applicant_id)
            if state is None:
                return None
            return copy.deepcopy(state)

    async def save_state(self, state: EvaluationState) -> None:
        """Store a deep-copied evaluation state isolated by applicant ID and persist to disk."""
        async with self._get_lock():
            cloned = copy.deepcopy(state)
            cloned.updated_at = _utc_now_iso()
            self._states[cloned.applicant_id] = cloned
        self._auto_save_to_disk()

    async def update_state(
        self, applicant_id: str, updater: Callable[[EvaluationState], None]
    ) -> EvaluationState:
        """Safely mutate an applicant state under the store lock with deep-copy isolation and persist."""
        async with self._get_lock():
            if applicant_id not in self._states:
                raise KeyError(f"Applicant ID '{applicant_id}' not found in state store.")
            current_state = copy.deepcopy(self._states[applicant_id])
            updater(current_state)
            current_state.updated_at = _utc_now_iso()
            self._states[applicant_id] = copy.deepcopy(current_state)
            cloned_result = copy.deepcopy(current_state)
        self._auto_save_to_disk()
        return cloned_result

    async def list_all(self) -> List[EvaluationState]:
        """Return deep-copied list of all currently tracked applicant states."""
        async with self._get_lock():
            return [copy.deepcopy(st) for st in self._states.values()]

    async def create_snapshot(self, applicant_id: str, label: str) -> Dict[str, Any]:
        """Create and persist a state snapshot for a specific applicant."""
        async with self._get_lock():
            if applicant_id not in self._states:
                raise KeyError(f"Applicant ID '{applicant_id}' not found in state store.")
            state = self._states[applicant_id]
            snap = state.take_snapshot(label)
            cloned_snap = copy.deepcopy(snap)
        self._auto_save_to_disk()
        return cloned_snap

    async def clear(self) -> None:
        """Clear all applicant states in the store and update disk storage."""
        async with self._get_lock():
            self._states.clear()
        self._auto_save_to_disk()

    def save_to_json(self, file_path: str) -> None:
        """Synchronously persist all stored evaluation states to a JSON file."""
        with self._thread_lock:
            target_path = os.path.abspath(file_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            data = {
                "rubric_version": RUBRIC_VERSION,
                "config_hash": get_configuration_hash(),
                "exported_at": _utc_now_iso(),
                "applicants": {
                    app_id: json.loads(state.model_dump_json())
                    for app_id, state in self._states.items()
                },
            }
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def load_from_json(self, file_path: str) -> None:
        """Load evaluation states from a JSON file with resilient corruption handling."""
        target_path = os.path.abspath(file_path)
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"State file '{target_path}' does not exist.")
        with self._thread_lock:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            applicants = data.get("applicants", {})
            loaded_states: Dict[str, EvaluationState] = {}
            for app_id, state_dict in applicants.items():
                try:
                    loaded_states[app_id] = EvaluationState.model_validate(state_dict)
                except Exception:
                    # Safely skip unparseable records to prevent whole application crash
                    continue

            self._states = loaded_states

