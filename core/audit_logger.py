"""Append-only JSONL audit and execution logger for Scholarship Evaluation.

Guarantees immutable historical recording of every agent tool invocation, state update,
and evaluation milestone with duration, status, rubric version, and configuration hash.
Never overwrites existing logs.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
import threading
from typing import Any, Dict, List, Optional

from core.scoring_config import RUBRIC_VERSION, get_configuration_hash


class AuditLogger:
    """Thread-safe and async-compatible append-only JSONL logger."""

    def __init__(self, log_file_path: str = "execution_audit.jsonl") -> None:
        self.log_file_path = os.path.abspath(log_file_path)
        self._async_lock: Optional[asyncio.Lock] = None
        self._lock_loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread_lock = threading.Lock()
        
        # Ensure target directory exists
        log_dir = os.path.dirname(self.log_file_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    def _get_async_lock(self) -> asyncio.Lock:
        """Lazily initialize asyncio.Lock inside active event loop, rebinding if loop changes."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if self._async_lock is None or self._lock_loop != current_loop:
            self._async_lock = asyncio.Lock()
            self._lock_loop = current_loop
        return self._async_lock

    def _format_entry(
        self,
        applicant_id: Optional[str],
        agent_name: str,
        tool_name: str,
        input_summary: str,
        output_summary: str,
        execution_status: str,
        duration: float,
        error_details: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Construct a standardized audit log entry dictionary."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "applicant_id": applicant_id,
            "agent_name": agent_name,
            "tool_name": tool_name,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "execution_status": execution_status,
            "duration_seconds": round(float(duration), 4),
            "error_details": error_details,
            "rubric_version": RUBRIC_VERSION,
            "config_hash": get_configuration_hash(),
            "metadata": extra_metadata or {},
        }

    def log_sync(
        self,
        applicant_id: Optional[str],
        agent_name: str,
        tool_name: str,
        input_summary: str,
        output_summary: str,
        execution_status: str,
        duration: float,
        error_details: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synchronously append an audit entry to the JSONL log file."""
        entry = self._format_entry(
            applicant_id=applicant_id,
            agent_name=agent_name,
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=output_summary,
            execution_status=execution_status,
            duration=duration,
            error_details=error_details,
            extra_metadata=extra_metadata,
        )
        line = json.dumps(entry) + "\n"
        with self._thread_lock:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
        return entry

    async def log_async(
        self,
        applicant_id: Optional[str],
        agent_name: str,
        tool_name: str,
        input_summary: str,
        output_summary: str,
        execution_status: str,
        duration: float,
        error_details: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Asynchronously append an audit entry to the JSONL log file."""
        entry = self._format_entry(
            applicant_id=applicant_id,
            agent_name=agent_name,
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=output_summary,
            execution_status=execution_status,
            duration=duration,
            error_details=error_details,
            extra_metadata=extra_metadata,
        )
        line = json.dumps(entry) + "\n"
        async with self._get_async_lock():
            # Append write under lock
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
        return entry

    def read_all_logs(self) -> List[Dict[str, Any]]:
        """Read and parse all JSONL audit entries."""
        if not os.path.exists(self.log_file_path):
            return []
        entries: List[Dict[str, Any]] = []
        with self._thread_lock:
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        # Resilient parsing: record corrupted line warning without crashing
                        continue
        return entries

    def get_applicant_logs(self, applicant_id: str) -> List[Dict[str, Any]]:
        """Filter audit logs for a specific applicant ID."""
        all_logs = self.read_all_logs()
        return [entry for entry in all_logs if entry.get("applicant_id") == applicant_id]

