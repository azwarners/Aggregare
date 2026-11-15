# Redless task adapter

Issue #72 adds the private `tools.redless_task_adapter` module used by the
future operator CLI. It exposes three callables:

* `allocate_run(workspace_root, runs_root, logs_root)` reserves a collision-free
  run ID, private existing-workspace directory, and contained result,
  trajectory, stdout, and stderr paths.
* `build_task_request(task, run)` returns one JSONL `task` record using the
  pinned Redless contract v1, `slow_local.yaml`, and the allocated paths.
* `interpret_records(records, expected_run_id)` separates status events from a
  single terminal result and reports success, failure, cancellation, protocol
  errors, or missing terminal output.

The adapter does not launch `redless-machine`, execute shell input, validate a
second copy of the Redless Pydantic contract, or infer success from a process
exit code. Allocation preserves deployment setgid/ACL inheritance and never
reuses an existing workspace or artifact path.

Verification:

* `PYTHONPATH=. pytest -q`: 85 tests and 203 subtests passed.
* Focused adapter and role tests: 12 passed.
* The same adapter smoke checks passed on `aggregare-dev` using Python 3.14.
