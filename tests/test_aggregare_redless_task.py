import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.aggregare_redless_task import (
    IdentityError,
    _build_parser,
    _check_identity,
    _read_task,
    run_task,
)


FAKE_MACHINE = """\
#!/usr/bin/env python3
import json
import os
import sys
request = json.loads(sys.stdin.readline())
run_id = request["payload"]["run_id"]
task = request["payload"]["task"]
if task == "timeout":
    import time
    time.sleep(2)
elif task == "descendant":
    import subprocess
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    print(json.dumps({"type": "status", "payload": {"run_id": run_id, "state": "running"}}), flush=True)
    time.sleep(2)
elif task == "malformed":
    print("not json")
elif task == "missing":
    print(json.dumps({"type": "status", "payload": {"run_id": run_id, "state": "running"}}))
else:
    print(json.dumps({"type": "status", "payload": {"run_id": run_id, "state": "running"}}))
    state = "failed" if task == "failed" else "succeeded"
    result = {"type": "result", "payload": {"run_id": run_id, "state": state}}
    if state == "succeeded":
        result["payload"]["final_answer"] = "fake answer"
    print(json.dumps(result))
print("HOME=" + os.environ.get("HOME", ""), file=sys.stderr)
print("SECRET=" + os.environ.get("ADMIN_SECRET", ""), file=sys.stderr)
"""


def fake_machine(tmp_path):
    machine = tmp_path / "fake-redless-machine"
    machine.write_text(FAKE_MACHINE)
    machine.chmod(0o755)
    return machine


def run_fake(tmp_path, task, *, timeout=5):
    roots = [tmp_path / name for name in ("workspaces", "runs", "logs")]
    home = tmp_path / "redless-home"
    (home / ".config").mkdir(parents=True)
    (home / ".config" / "slow_local.yaml").write_text("profile")
    return run_task(
        task,
        workspace_root=roots[0],
        runs_root=roots[1],
        logs_root=roots[2],
        machine_path=fake_machine(tmp_path),
        home=home,
        timeout=timeout,
        expected_uid=os.geteuid(),
        expected_gid=os.getegid(),
    )


def test_fake_machine_success_preserves_input_environment_and_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "must-not-leak")
    result = run_fake(tmp_path, "quotes \" ' $HOME\nΔ")

    assert result["outcome"] == "succeeded"
    assert result["exit_code"] == 0
    assert Path(result["stdout_path"]).read_text().count('"type": "result"') == 1
    assert f"HOME={tmp_path / 'redless-home'}" in Path(result["stderr_path"]).read_text()
    assert "SECRET=must-not-leak" not in Path(result["stderr_path"]).read_text()
    assert result["trajectory_path"].endswith(".trajectory.json")


@pytest.mark.parametrize(
    ("task", "outcome"),
    [("failed", "failed"), ("malformed", "protocol_error"), ("missing", "missing_terminal")],
)
def test_fake_machine_outcomes_return_nonzero_and_keep_raw_stream(tmp_path, task, outcome):
    result = run_fake(tmp_path, task)

    assert result["outcome"] == outcome
    assert result["exit_code"] != 0
    assert Path(result["stdout_path"]).exists()
    assert Path(result["stderr_path"]).exists()


def test_timeout_is_explicitly_ambiguous_and_artifacts_remain(tmp_path):
    result = run_fake(tmp_path, "timeout", timeout=0.05)

    assert result["outcome"] == "timeout"
    assert result["code"] == "ambiguous_timeout"
    assert "not confirmed stopped" in result["message"]
    assert Path(result["stdout_path"]).exists()


def test_timeout_kills_descendant_process_group_without_indefinite_pipe_wait(tmp_path):
    started = time.monotonic()
    result = run_fake(tmp_path, "descendant", timeout=0.2)
    elapsed = time.monotonic() - started

    assert elapsed < 3
    assert result["outcome"] == "timeout"
    assert "running" in Path(result["stdout_path"]).read_text()


def test_missing_config_fails_before_machine_invocation(tmp_path):
    result = run_task(
        "hello",
        workspace_root=tmp_path / "workspaces",
        runs_root=tmp_path / "runs",
        logs_root=tmp_path / "logs",
        machine_path=fake_machine(tmp_path),
        home=tmp_path / "missing-home",
        expected_uid=os.geteuid(),
        expected_gid=os.getegid(),
    )

    assert result["outcome"] == "protocol_error"
    assert result["code"] == "missing_config"
    assert result["exit_code"] == 2


def test_missing_machine_fails_without_invocation(tmp_path):
    home = tmp_path / "redless-home"
    (home / ".config").mkdir(parents=True)
    (home / ".config" / "slow_local.yaml").write_text("profile")
    result = run_task(
        "hello",
        workspace_root=tmp_path / "workspaces",
        runs_root=tmp_path / "runs",
        logs_root=tmp_path / "logs",
        machine_path=tmp_path / "missing-machine",
        home=home,
        expected_uid=os.geteuid(),
        expected_gid=os.getegid(),
    )

    assert result["outcome"] == "protocol_error"
    assert result["code"] == "missing_executable"
    assert result["exit_code"] == 2


def test_task_file_preserves_multiline_unicode_and_parser_rejects_conflicts(tmp_path):
    task_file = tmp_path / "task.txt"
    task = "line one\nline two — Δ"
    task_file.write_text(task, encoding="utf-8")
    parser = _build_parser()

    arguments = parser.parse_args(["run", "--task-file", str(task_file)])
    assert _read_task(arguments) == task
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--task", "one", "--task-file", str(task_file)])


def test_identity_guard_rejects_unexpected_uid_and_gid():
    with pytest.raises(IdentityError, match="sudo -u redless"):
        _check_identity(expected_uid=os.geteuid() + 1, expected_gid=os.getegid())
