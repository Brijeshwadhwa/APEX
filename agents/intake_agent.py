"""Intake Agent: Parses raw applicant submissions and initializes evaluation state."""

from decimal import Decimal
import time
from typing import Any, Dict, Optional
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function, KernelArguments

from core import ensure_sk_compatibility
from core.schemas import ApplicantProfile, AchievementRecord
from core.shared_state import EvaluationState
from core.audit_logger import AuditLogger

ensure_sk_compatibility()


class IntakePlugin:
    """Semantic Kernel plugin for application intake and validation."""

    def __init__(self, logger: Optional[AuditLogger] = None) -> None:
        self.logger = logger or AuditLogger()

    @kernel_function(
        name="parse_applicant_profile",
        description="Parses raw dictionary data into a validated ApplicantProfile domain model.",
    )
    def parse_applicant_profile(self, raw_data_json: str) -> str:
        """Plain Python tool to parse and validate applicant data."""
        import json
        data = json.loads(raw_data_json)
        profile = ApplicantProfile.model_validate(data)
        return profile.model_dump_json()

    @kernel_function(
        name="initialize_applicant_state",
        description="Creates an initial EvaluationState for an applicant with tracking and snapshots.",
    )
    def initialize_applicant_state(self, profile_json: str) -> str:
        """Plain Python tool to initialize evaluation state."""
        profile = ApplicantProfile.model_validate_json(profile_json)
        state = EvaluationState(
            applicant_id=profile.applicant_id,
            profile=profile,
            status="PENDING",
        )
        state.record_trace(
            sender="IntakeAgent",
            receiver="StateStore",
            event_type="INTAKE_INITIALIZED",
            payload_summary=f"Initialized state for applicant {profile.applicant_id} ({profile.full_name})",
        )
        state.take_snapshot("Intake Profile Validated")
        return state.model_dump_json()


class IntakeAgent:
    """Agent responsible for ingesting, validating, and initializing applicant dossiers."""

    def __init__(self, logger: Optional[AuditLogger] = None) -> None:
        self.kernel = Kernel()
        self.logger = logger or AuditLogger()
        self.plugin = self.kernel.add_plugin(
            IntakePlugin(logger=self.logger), plugin_name="IntakePlugin"
        )

    async def process_applicant(self, raw_data: Dict[str, Any]) -> EvaluationState:
        """Executes the intake workflow using Semantic Kernel tools."""
        import json
        start_time = time.perf_counter()
        raw_json = json.dumps(raw_data, default=str)
        app_id = raw_data.get("applicant_id", "UNKNOWN")

        # Tool 1: Parse and validate profile
        t1_start = time.perf_counter()
        parse_func = self.plugin["parse_applicant_profile"]
        parsed_res = await self.kernel.invoke(parse_func, KernelArguments(raw_data_json=raw_json))
        profile_json = str(parsed_res.value)
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="IntakeAgent",
            tool_name="parse_applicant_profile",
            input_summary=f"Parsing raw record for {app_id}",
            output_summary="ApplicantProfile validated successfully",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t1_start,
        )

        # Tool 2: Initialize evaluation state
        t2_start = time.perf_counter()
        init_func = self.plugin["initialize_applicant_state"]
        init_res = await self.kernel.invoke(init_func, KernelArguments(profile_json=profile_json))
        state = EvaluationState.model_validate_json(str(init_res.value))
        self.logger.log_sync(
            applicant_id=app_id,
            agent_name="IntakeAgent",
            tool_name="initialize_applicant_state",
            input_summary=f"Initializing EvaluationState for {app_id}",
            output_summary=f"State created with status {state.status}",
            execution_status="SUCCESS",
            duration=time.perf_counter() - t2_start,
        )

        return state

