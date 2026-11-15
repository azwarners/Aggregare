"""Operator-facing one-shot Redless task command."""

from __future__ import annotations

import argparse
import grp
import json
import os
import pwd
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from tools.redless_task_adapter import RunDescriptor, allocate_run, build_task_request, interpret_records
except ModuleNotFoundError:  # Installed beside the private helper.
    from redless_task_adapter import RunDescriptor, allocate_run, build_task_request, interpret_records


DEFAULT_MACHINE = "/usr/local/bin/redless-machine"
DEFAULT_HOME = "/var/lib/redless"
DEFAULT_TIMEOUT = 900.0
SAFE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


class IdentityError(RuntimeError):
    """The command is not running as the unprivileged Redless account."""


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        task = _read_task(arguments)
        result = run_task(
            task,
            workspace_root=Path(os.environ.get("AGGREGARE_REDLESS_WORKSPACE_ROOT", f"{DEFAULT_HOME}/workspaces")),
            runs_root=Path(os.environ.get("AGGREGARE_REDLESS_RUN_ROOT", f"{DEFAULT_HOME}/runs")),
            logs_root=Path(os.environ.get("AGGREGARE_REDLESS_LOG_ROOT", "/var/log/redless")),
            machine_path=Path(os.environ.get("AGGREGARE_REDLESS_MACHINE", DEFAULT_MACHINE)),
            home=Path(os.environ.get("AGGREGARE_REDLESS_HOME", DEFAULT_HOME)),
            timeout=arguments.timeout,
        )
    except (IdentityError, OSError, ValueError, RuntimeError) as exc:
        print(f"aggregare-redless-task: {exc}", file=sys.stderr)
        return 2

    if arguments.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        _print_human_result(result)
    return 0 if result["exit_code"] == 0 else 1


def run_task(
    task: str,
    *,
    workspace_root: Path,
    runs_root: Path,
    logs_root: Path,
    machine_path: Path,
    home: Path,
    timeout: float = DEFAULT_TIMEOUT,
    expected_uid: int | None = None,
    expected_gid: int | None = None,
) -> dict[str, Any]:
    """Run one task through the installed machine process.

    ``expected_uid`` and ``expected_gid`` are test seams; production callers
    leave them unset so the configured ``redless`` account is required.
    """

    if timeout <= 0:
        raise ValueError("timeout must be positive")
    _check_identity(expected_uid=expected_uid, expected_gid=expected_gid)
    run = allocate_run(workspace_root, runs_root, logs_root)
    request = build_task_request(task, run)
    child_env = _child_environment(home)
    stdout = b""
    stderr = b""
    timed_out = False

    config_path = home / ".config" / "slow_local.yaml"
    if not config_path.is_file():
        stderr = f"Redless profile is missing: {config_path}\n".encode()
        outcome = {"outcome": "protocol_error", "code": "missing_config", "statuses": []}
        return _finish(run, outcome, stdout, stderr, exit_code=2)

    if not machine_path.is_file() or not os.access(machine_path, os.X_OK):
        stderr = f"redless-machine is not executable: {machine_path}\n".encode()
        outcome = {"outcome": "protocol_error", "code": "missing_executable", "statuses": []}
        return _finish(run, outcome, stdout, stderr, exit_code=2)

    try:
        process = subprocess.Popen(
            [str(machine_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=run.workspace_path,
            env=child_env,
            start_new_session=(os.name == "posix"),
        )
        try:
            stdout, stderr = process.communicate(request.encode("utf-8"), timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            _stop_local_process_group(process)
            try:
                remaining_stdout, remaining_stderr = process.communicate(timeout=1.0)
            except subprocess.TimeoutExpired as still_running:
                stdout = _merge_capture(stdout, still_running.stdout)
                stderr = _merge_capture(stderr, still_running.stderr)
                _close_process_pipes(process)
            else:
                stdout = _merge_capture(stdout, remaining_stdout)
                stderr = _merge_capture(stderr, remaining_stderr)
    except OSError as exc:
        stderr = f"could not start redless-machine: {exc}\n".encode()
        outcome = {"outcome": "protocol_error", "code": "start_error", "statuses": []}
        return _finish(run, outcome, stdout, stderr, exit_code=2)

    if timed_out:
        outcome = {
            "outcome": "timeout",
            "code": "ambiguous_timeout",
            "message": "The local machine process was terminated; remote model work is not confirmed stopped.",
            "statuses": [],
        }
        return _finish(run, outcome, stdout, stderr, exit_code=2)

    outcome = interpret_records(stdout.decode("utf-8", errors="replace"), run.run_id)
    if process.returncode != 0 and outcome.get("outcome") == "succeeded":
        outcome = {
            "outcome": "protocol_error",
            "code": "process_exit_after_success",
            "exit_status": process.returncode,
            "statuses": outcome.get("statuses", []),
        }
    exit_code = 0 if outcome.get("outcome") == "succeeded" else 1
    return _finish(run, outcome, stdout, stderr, exit_code=exit_code)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one task through redless-machine.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run one Redless task")
    source = run.add_mutually_exclusive_group(required=True)
    source.add_argument("--task", help="literal task text")
    source.add_argument("--task-file", type=Path, help="UTF-8 file containing the task")
    run.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="local process timeout in seconds")
    run.add_argument("--json", action="store_true", help="print the final outcome as JSON")
    return parser


def _read_task(arguments: argparse.Namespace) -> str:
    if arguments.task_file is not None:
        try:
            task = arguments.task_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"cannot read task file {arguments.task_file}: {exc}") from exc
    else:
        task = arguments.task
    if not isinstance(task, str) or not task.strip():
        raise ValueError("task must be nonempty")
    return task


def _check_identity(*, expected_uid: int | None, expected_gid: int | None) -> None:
    try:
        if expected_uid is None:
            expected_uid = pwd.getpwnam("redless").pw_uid
        if expected_gid is None:
            expected_gid = grp.getgrnam("redless").gr_gid
    except KeyError as exc:
        raise IdentityError("the configured redless user/group does not exist") from exc
    if os.geteuid() != expected_uid or os.getegid() != expected_gid:
        raise IdentityError(
            "must run as the unprivileged redless worker; "
            "use sudo -u redless -- /path/to/tools/aggregare-redless-task run ..."
        )


def _child_environment(home: Path) -> dict[str, str]:
    config_dir = home / ".config"
    return {
        "HOME": str(home),
        "MSWEA_CONFIG_DIR": str(config_dir),
        "PATH": SAFE_PATH,
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
    }


def _stop_local_process_group(process: subprocess.Popen[bytes], *, grace: float = 1.0) -> None:
    """Stop only this local machine process and descendants, bounded in time."""

    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    else:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=grace)
        return
    except (ProcessLookupError, subprocess.TimeoutExpired):
        pass
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=grace)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        pass


def _close_process_pipes(process: subprocess.Popen[bytes]) -> None:
    for stream in (process.stdout, process.stderr, process.stdin):
        if stream is not None:
            stream.close()


def _merge_capture(previous: bytes, current: bytes | None) -> bytes:
    current = current or b""
    if not current:
        return previous
    if current.startswith(previous):
        return current
    if previous.endswith(current):
        return previous
    return previous + current


def _finish(
    run: RunDescriptor,
    outcome: dict[str, Any],
    stdout: bytes,
    stderr: bytes,
    *,
    exit_code: int,
) -> dict[str, Any]:
    run.stdout_path.write_bytes(stdout)
    run.stderr_path.write_bytes(stderr)
    result = dict(outcome)
    result.update(
        {
            "run_id": run.run_id,
            "exit_code": exit_code,
            "result_path": str(run.result_path),
            "trajectory_path": str(run.trajectory_path),
            "stdout_path": str(run.stdout_path),
            "stderr_path": str(run.stderr_path),
        }
    )
    return result


def _print_human_result(result: dict[str, Any]) -> None:
    outcome = result["outcome"]
    print(f"Redless task {outcome}: {result['run_id']}")
    if result.get("result", {}).get("final_answer"):
        print(result["result"]["final_answer"])
    if result.get("message"):
        print(result["message"], file=sys.stderr)
    elif result.get("error"):
        print(result["error"].get("message", result["error"]), file=sys.stderr)
    print(f"Result: {result['result_path']}")
    print(f"Trajectory: {result['trajectory_path']}")
    print(f"Output: {result['stdout_path']}")
    print(f"Error: {result['stderr_path']}")


if __name__ == "__main__":
    raise SystemExit(main())
