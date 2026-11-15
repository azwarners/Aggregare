"""Small, side-effect-limited helpers for submitting one Redless task.

This module deliberately stops at the Redless machine boundary.  It does not
start a process, interpret shell syntax, or implement any Redless contract
validation.  The installed ``redless-machine`` remains the owner of execution
and contract validation.
"""

from __future__ import annotations

import json
import os
import secrets
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "1"
_TERMINAL_STATES = frozenset(("succeeded", "failed", "cancelled"))
_STATUS_STATES = frozenset(("accepted", "running", "cancellation_requested"))


@dataclass(frozen=True)
class RunDescriptor:
    """Paths reserved for one Redless run."""

    run_id: str
    workspace_path: Path
    result_path: Path
    trajectory_path: Path
    stdout_path: Path
    stderr_path: Path


def allocate_run(
    workspace_root: str | os.PathLike[str],
    runs_root: str | os.PathLike[str],
    logs_root: str | os.PathLike[str],
    *,
    attempts: int = 12,
) -> RunDescriptor:
    """Reserve a private workspace and artifact paths for a new run.

    The roots are deployment-owned configuration, not request data.  A fresh
    UUID is used for the run name and the workspace directory is created with
    ``exist_ok=False``; a collision therefore cannot overwrite an old run.
    """

    if attempts < 1:
        raise ValueError("attempts must be positive")

    workspace_base = _prepare_root(workspace_root)
    runs_base = _prepare_root(runs_root)
    logs_base = _prepare_root(logs_root)

    for _ in range(attempts):
        run_id = f"aggregare-{uuid.uuid4().hex}-{secrets.token_hex(4)}"
        workspace = workspace_base / run_id
        try:
            # The Redless roots carry default ACLs.  0750 prevents unrelated
            # users from entering the workspace while leaving the inherited ACL
            # mask free to grant configured group read/traverse access.
            workspace.mkdir(mode=0o750)
        except FileExistsError:
            continue
        descriptor = RunDescriptor(
            run_id=run_id,
            workspace_path=workspace,
            result_path=runs_base / f"{run_id}.result.json",
            trajectory_path=runs_base / f"{run_id}.trajectory.json",
            stdout_path=logs_base / f"{run_id}.stdout.jsonl",
            stderr_path=logs_base / f"{run_id}.stderr.log",
        )
        if any(path.exists() or path.is_symlink() for path in (
            descriptor.result_path,
            descriptor.trajectory_path,
            descriptor.stdout_path,
            descriptor.stderr_path,
        )):
            workspace.rmdir()
            continue
        for path, root in (
            (descriptor.workspace_path, workspace_base),
            (descriptor.result_path, runs_base),
            (descriptor.trajectory_path, runs_base),
            (descriptor.stdout_path, logs_base),
            (descriptor.stderr_path, logs_base),
        ):
            _require_contained(path, root)
        return descriptor
    raise RuntimeError("could not allocate a collision-free Redless run")


def build_task_request(task: str, run: RunDescriptor) -> str:
    """Return exactly one JSONL task request for an allocated run."""

    if not isinstance(task, str) or not task:
        raise ValueError("task must be a nonempty string")
    if not isinstance(run, RunDescriptor):
        raise TypeError("run must be a RunDescriptor")

    payload = {
        "contract_version": CONTRACT_VERSION,
        "run_id": run.run_id,
        "task": task,
        "workspace": {
            "contract_version": CONTRACT_VERSION,
            "mode": "existing",
            "path": str(run.workspace_path),
            "cleanup_policy": "preserve",
        },
        "model": {
            "contract_version": CONTRACT_VERSION,
            "profile": "slow_local.yaml",
        },
        "destinations": {
            "contract_version": CONTRACT_VERSION,
            "result_path": str(run.result_path),
            "trajectory_path": str(run.trajectory_path),
        },
    }
    return json.dumps(
        {"type": "task", "payload": payload},
        ensure_ascii=False,
        separators=(",", ":"),
    ) + "\n"


def interpret_records(records: Iterable[str] | str, expected_run_id: str) -> dict[str, Any]:
    """Interpret Redless JSONL and return one terminal outcome.

    The returned ``outcome`` is one of ``succeeded``, ``failed``,
    ``cancelled``, ``protocol_error``, or ``missing_terminal``.  Status
    records are retained for callers that want progress reporting.
    """

    if not isinstance(expected_run_id, str) or not expected_run_id:
        raise ValueError("expected_run_id must be nonempty")
    lines = records.splitlines() if isinstance(records, str) else records
    statuses: list[dict[str, Any]] = []
    terminal: dict[str, Any] | None = None

    for line_number, line in enumerate(lines, start=1):
        if not isinstance(line, str):
            return _protocol_error("malformed_record", line_number=line_number)
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            return _protocol_error("malformed_json", line_number=line_number)
        if not isinstance(record, dict) or not isinstance(record.get("type"), str):
            return _protocol_error("malformed_record", line_number=line_number)

        record_type = record["type"]
        payload = record.get("payload")
        if record_type == "status":
            if not isinstance(payload, dict) or payload.get("run_id") != expected_run_id:
                return _protocol_error("wrong_run_id", line_number=line_number)
            if payload.get("state") not in _STATUS_STATES:
                return _protocol_error("malformed_status", line_number=line_number)
            statuses.append(payload)
            continue

        if record_type == "result":
            if not isinstance(payload, dict) or payload.get("run_id") != expected_run_id:
                return _protocol_error("wrong_run_id", line_number=line_number)
            if payload.get("state") not in _TERMINAL_STATES:
                return _protocol_error("malformed_result", line_number=line_number)
            if terminal is not None:
                return _protocol_error("duplicate_terminal", line_number=line_number)
            terminal = {"result": payload}
            continue

        if record_type == "error":
            if not isinstance(payload, dict):
                return _protocol_error("malformed_error", line_number=line_number)
            if "run_id" in payload and payload["run_id"] != expected_run_id:
                return _protocol_error("wrong_run_id", line_number=line_number)
            if terminal is not None:
                return _protocol_error("duplicate_terminal", line_number=line_number)
            terminal = {"error": payload}
            continue

        # Capabilities and unknown records are not task outcomes.  A
        # capabilities response is harmless, but an unknown record is not.
        if record_type != "capabilities":
            return _protocol_error("unsupported_record_type", line_number=line_number)

    if terminal is None:
        return {"outcome": "missing_terminal", "statuses": statuses}
    if "error" in terminal:
        return {"outcome": "protocol_error", "error": terminal["error"], "statuses": statuses}
    result = terminal["result"]
    return {"outcome": result["state"], "result": result, "statuses": statuses}


def _prepare_root(value: str | os.PathLike[str]) -> Path:
    root = Path(value).expanduser()
    if root.exists() and root.is_symlink():
        raise ValueError(f"Redless root must not be a symlink: {root}")
    root.mkdir(mode=0o750, parents=True, exist_ok=True)
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"Redless root is not a directory: {root}")
    return root.resolve()


def _require_contained(path: Path, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"allocated path escapes Redless root: {path}") from exc


def _protocol_error(code: str, *, line_number: int) -> dict[str, Any]:
    return {"outcome": "protocol_error", "code": code, "line": line_number, "statuses": []}
