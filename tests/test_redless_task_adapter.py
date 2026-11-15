import json
import json
import grp
import os
import stat
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.redless_task_adapter import allocate_run, build_task_request, interpret_records


def test_request_round_trip_preserves_literal_task_and_contract_shape(tmp_path):
    run = allocate_run(tmp_path / "workspaces", tmp_path / "runs", tmp_path / "logs")
    task = "  quote \"double\" 'single' $HOME; echo nope\nΔ  "

    record = json.loads(build_task_request(task, run))

    assert record["type"] == "task"
    payload = record["payload"]
    assert payload["contract_version"] == "1"
    assert payload["task"] == task
    assert payload["workspace"] == {
        "contract_version": "1",
        "mode": "existing",
        "path": str(run.workspace_path),
        "cleanup_policy": "preserve",
    }
    assert payload["model"] == {"contract_version": "1", "profile": "slow_local.yaml"}
    assert payload["destinations"]["result_path"] == str(run.result_path)


def test_allocation_is_unique_contained_private_and_non_overwriting(tmp_path):
    roots = [tmp_path / name for name in ("workspaces", "runs", "logs")]
    for root in roots:
        root.mkdir()
        root.chmod(0o2750)
    first = allocate_run(*roots)
    second = allocate_run(*roots)

    assert first.run_id != second.run_id
    assert all(stat.S_IMODE(root.stat().st_mode) == 0o2750 for root in roots)
    assert first.workspace_path.is_dir()
    assert stat.S_IMODE(first.workspace_path.stat().st_mode) & 0o007 == 0
    assert first.trajectory_path.suffix == ".json"
    assert first.stdout_path.suffix == ".jsonl"
    for path, root in (
        (first.workspace_path, roots[0]),
        (first.result_path, roots[1]),
        (first.trajectory_path, roots[1]),
        (first.stdout_path, roots[2]),
        (first.stderr_path, roots[2]),
    ):
        assert os.path.commonpath((path, root)) == str(root.resolve())

    (first.workspace_path / "preserved.txt").write_text("failed run artifact")
    assert (first.workspace_path / "preserved.txt").read_text() == "failed run artifact"


def test_allocation_preserves_default_acl_and_inherits_group_traverse(tmp_path):
    if not shutil.which("setfacl") or not shutil.which("getfacl"):
        pytest.skip("ACL tools are unavailable")
    group = grp.getgrgid(os.getgid()).gr_name
    root = tmp_path / "workspaces"
    root.mkdir(mode=0o2750)
    acl = [
        f"g:{group}:r-x",
        "m::r-x",
        "d:u::rwx",
        "d:g::---",
        f"d:g:{group}:r-x",
        "d:m::r-x",
        "d:o::---",
    ]
    subprocess.run(["setfacl", "-m", ",".join(acl), str(root)], check=True)
    before = subprocess.check_output(["getfacl", "-p", str(root)], text=True)

    run = allocate_run(root, tmp_path / "runs", tmp_path / "logs")

    after = subprocess.check_output(["getfacl", "-p", str(root)], text=True)
    workspace_acl = subprocess.check_output(["getfacl", "-p", str(run.workspace_path)], text=True)
    assert after == before
    assert f"group:{group}:r-x" in workspace_acl
    assert "other::---" in workspace_acl
    assert "mask::r-x" in workspace_acl


@pytest.mark.parametrize(
    ("records", "outcome"),
    [
        ('{"type":"status","payload":{"run_id":"r","state":"accepted"}}\n'
         '{"type":"status","payload":{"run_id":"r","state":"running"}}\n'
         '{"type":"result","payload":{"run_id":"r","state":"succeeded"}}\n', "succeeded"),
        ('{"type":"result","payload":{"run_id":"r","state":"failed"}}\n', "failed"),
        ('{"type":"result","payload":{"run_id":"r","state":"cancelled"}}\n', "cancelled"),
    ],
)
def test_interpret_records_accepts_actual_terminal_result_shapes(records, outcome):
    assert interpret_records(records, "r")["outcome"] == outcome


def test_interpret_records_accepts_complete_upstream_machine_fixture():
    fixture = [
        {
            "type": "status",
            "payload": {
                "contract_version": "1",
                "run_id": "run-1",
                "state": "accepted",
                "started_at": None,
                "updated_at": "2026-11-15T12:00:00Z",
                "message": None,
                "cancellation_requested": False,
            },
        },
        {
            "type": "status",
            "payload": {
                "contract_version": "1",
                "run_id": "run-1",
                "state": "running",
                "started_at": "2026-11-15T12:00:00Z",
                "updated_at": "2026-11-15T12:00:01Z",
                "message": None,
                "cancellation_requested": False,
            },
        },
        {
            "type": "result",
            "payload": {
                "contract_version": "1",
                "run_id": "run-1",
                "state": "succeeded",
                "started_at": "2026-11-15T12:00:00Z",
                "finished_at": "2026-11-15T12:01:00Z",
                "final_answer": "done",
                "artifacts": [],
                "trajectory": {
                    "contract_version": "1",
                    "kind": "trajectory",
                    "path": "/var/lib/redless/runs/run-1.trajectory.json",
                    "media_type": "application/json",
                    "description": None,
                },
                "error": None,
                "cancellation_requested": False,
            },
        },
    ]
    records = "\n".join(json.dumps(record) for record in fixture) + "\n"

    outcome = interpret_records(records, "run-1")

    assert outcome["outcome"] == "succeeded"
    assert len(outcome["statuses"]) == 2
    assert outcome["result"]["trajectory"]["media_type"] == "application/json"


def test_interpret_records_rejects_transport_and_protocol_failures():
    transport_error = '{"type":"error","payload":{"code":"executor_error"}}\n'
    assert interpret_records(transport_error, "r")["outcome"] == "protocol_error"
    assert interpret_records("not json\n", "r")["code"] == "malformed_json"
    wrong_id = '{"type":"result","payload":{"run_id":"other","state":"succeeded"}}\n'
    assert interpret_records(wrong_id, "r")["code"] == "wrong_run_id"
    duplicate = ('{"type":"result","payload":{"run_id":"r","state":"succeeded"}}\n'
                 '{"type":"result","payload":{"run_id":"r","state":"failed"}}\n')
    assert interpret_records(duplicate, "r")["code"] == "duplicate_terminal"
    running = '{"type":"status","payload":{"run_id":"r","state":"running"}}\n'
    assert interpret_records(running, "r")["outcome"] == "missing_terminal"
