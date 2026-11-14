"""Unit tests for append-only JSONL execution logger."""

import json
import os
import pytest

from core.audit_logger import AuditLogger
from core.scoring_config import RUBRIC_VERSION, get_configuration_hash


def test_audit_logger_sync_append_only(tmp_path):
    log_file = str(tmp_path / "test_audit.jsonl")
    logger1 = AuditLogger(log_file)

    logger1.log_sync(
        applicant_id="APP-001",
        agent_name="EligibilityAgent",
        tool_name="verify_income_and_academic_thresholds",
        input_summary="income=150000, percentage=85",
        output_summary="eligible=True",
        execution_status="SUCCESS",
        duration=0.0125,
    )

    # Instantiate a second logger pointing to same file to verify append-only (no overwrite)
    logger2 = AuditLogger(log_file)
    logger2.log_sync(
        applicant_id="APP-002",
        agent_name="MeritAgent",
        tool_name="calculate_merit_score",
        input_summary="percentage=72",
        output_summary="score=28.8",
        execution_status="SUCCESS",
        duration=0.0210,
    )

    records = logger2.read_all_logs()
    assert len(records) == 2

    r1 = records[0]
    assert r1["applicant_id"] == "APP-001"
    assert r1["agent_name"] == "EligibilityAgent"
    assert r1["execution_status"] == "SUCCESS"
    assert r1["rubric_version"] == RUBRIC_VERSION
    assert r1["config_hash"] == get_configuration_hash()
    assert r1["duration_seconds"] == 0.0125

    r2 = records[1]
    assert r2["applicant_id"] == "APP-002"
    assert r2["agent_name"] == "MeritAgent"


@pytest.mark.asyncio
async def test_audit_logger_async_logging(tmp_path):
    log_file = str(tmp_path / "async_audit.jsonl")
    logger = AuditLogger(log_file)

    await logger.log_async(
        applicant_id="APP-003",
        agent_name="FinancialAgent",
        tool_name="lookup_income_band",
        input_summary="income=200000",
        output_summary="band=₹150,001–₹250,000, score=28.0",
        execution_status="SUCCESS",
        duration=0.008,
    )

    logs = logger.read_all_logs()
    assert len(logs) == 1
    assert logs[0]["applicant_id"] == "APP-003"
    assert logs[0]["tool_name"] == "lookup_income_band"


def test_audit_logger_filter_by_applicant(tmp_path):
    log_file = str(tmp_path / "filter_audit.jsonl")
    logger = AuditLogger(log_file)

    logger.log_sync("APP-001", "AgentA", "Tool1", "in1", "out1", "SUCCESS", 0.01)
    logger.log_sync("APP-002", "AgentB", "Tool2", "in2", "out2", "SUCCESS", 0.01)
    logger.log_sync("APP-001", "AgentC", "Tool3", "in3", "out3", "SUCCESS", 0.01)

    app1_logs = logger.get_applicant_logs("APP-001")
    assert len(app1_logs) == 2
    assert all(l["applicant_id"] == "APP-001" for l in app1_logs)

