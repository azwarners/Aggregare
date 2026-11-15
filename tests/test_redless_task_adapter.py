import json
import os
import stat
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
    first = allocate_run(*roots)
    second = allocate_run(*roots)

    assert first.run_id != second.run_id
    assert first.workspace_path.is_dir()
    assert stat.S_IMODE(first.workspace_path.stat().st_mode) & 0o007 == 0
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
