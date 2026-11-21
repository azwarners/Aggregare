# Run a Redless task

Redless is Aggregare's bounded coding and task-execution component. Aggregare
installs its machine-callable JSONL interface as `redless-machine` in the
`/opt/aggregare/venvs/redless` virtual environment.

The package entry point runs as the unprivileged `redless` account through the
normal administrator mechanism. Configured primary users do not need—and are
not given—a Redless password.

## Submit one ordinary task

After installation, submit a bounded task through Aggregare's one-shot
operator command:

```sh
sudo -u redless -- /usr/local/bin/aggregare-redless-task run \
  --task "Say hello and explain what Redless does"
```

The shorter `aggRedless` command is installed in the same system `PATH` as an
alias for this command:

```sh
sudo -u redless -- aggRedless run \
  --task "Say hello and explain what Redless does"
```

The command must run as the unprivileged `redless` worker. A successful Redless
result exits 0; failed or cancelled results, malformed or missing terminal
output, and missing configuration exit nonzero. The command waits indefinitely
by default because model inference may be very slow. Use the optional
`--timeout SECONDS` flag only when a local deadline is deliberately wanted;
that produces an explicitly ambiguous timeout result. Use `--help` for options.
The command streams the machine's stdout JSONL and stderr to the terminal while
also preserving both streams in the saved paths. The command prints the run ID
and saved paths after completion. Results
and trajectories are under `/var/lib/redless/runs`; captured stdout JSONL and
stderr are under `/var/log/redless`. A trajectory is a single `.json` document,
while the machine status/result stream is preserved as `.stdout.jsonl`.

For a long or multiline UTF-8 task, the file must be traversable and readable
by `redless`; a file in an administrator's private home or checkout may not
be readable after switching users. Prepare a harmless prompt in the Redless
home with root-authorized ownership and restricted mode, then remove it after
use:

```sh
sudo install -o redless -g redless -m 0640 ./task.txt \
  /var/lib/redless/task-input.txt
sudo -u redless -- /usr/local/bin/aggregare-redless-task run \
  --task-file /var/lib/redless/task-input.txt
sudo rm /var/lib/redless/task-input.txt
```

Do not weaken administrator-home permissions, add account membership, change
sudoers, or use `chmod 777`. If `--task-file` reports a permission error,
inspect every directory component and the file as the worker:

```sh
namei -l /var/lib/redless/task-input.txt
sudo -u redless -- test -r /var/lib/redless/task-input.txt && echo readable
```

For automation, consume the exit status and saved JSONL rather than model
prose:

```sh
if sudo -u redless -- /usr/local/bin/aggregare-redless-task run \
    --task "perform the bounded check"; then
  echo succeeded
else
  echo failed >&2
  exit 1
fi
```

## Run the Redless issue queue

The installed `redless-issue-queue` command is the single operator script for
discovering ready public issues, previewing a frozen plan, and processing a
small batch sequentially. It makes anonymous GitHub reads and never pushes,
commits, opens pull requests, or merges changes.

Preview the first ready issue:

```sh
sudo -u redless -- redless-issue-queue
```

Run one issue against an explicitly selected OpenAI-compatible coding endpoint:

```sh
sudo -u redless -- redless-issue-queue --run --once \
  --endpoint http://MODEL_HOST:8080/v1 \
  --model MODEL_ID
```

Use `--all` for the selected queue, or `--plan FILE` to execute a previously
saved plan without more GitHub discovery. The endpoint and model can also be
provided through `REDLESS_ENDPOINT` and `REDLESS_MODEL`. The default readiness
rule accepts the `ready` label or a `Readiness` heading beginning with `Ready`;
set `READY_MODE=label` to require only the label.

Run a bounded, read-only assessment for a small selected batch:

```sh
sudo -u redless -- redless-issue-queue --assess-only --once \
  --endpoint http://MODEL_HOST:8080/v1 --model MODEL_ID
```

Assessment requests use a configurable 12-request budget by default. Calls 1–6
investigate, calls 7–9 synthesize, calls 10–11 finalize, and call 12 is the
final-response-only request. Override the budget with
`--assessment-max-calls N`; phase thresholds remain configurable through the
`ASSESSMENT_SYNTHESIS_CALL` and `ASSESSMENT_FINALIZATION_CALL` environment
variables. The request envelope carries call-count and phase instructions so a
compatible Redless worker can inject them into every model message and disable
tools for the final request. Retries are part of the same budget.

The queue verifies the persisted trajectory request count before marking an
assessment complete. Missing or excessive counts, invalid finalization, worker
errors, and prohibited tool requests remain partial. Partial artifacts retain
result/event paths, the last model output when available, and the existing
trajectory/evidence for diagnosis; they are never used to publish child issues.

Assessment mode reuses issue discovery and writes `*.assessment.json`,
`*.assessment.plan.json`, and `*.assessment.md` under the run directory. The
JSON records the issue, source revision, evidence, classification, bounded
tasks, dependency order, verification requirements, complexity, recommended
role, and a future Zoapaww prompt. A run starts as `running` and becomes
`complete` only after schema validation; crashes, timeouts, and malformed model
output remain `partial`. Existing assessment artifacts are skipped unless
`--retry-assessment` is supplied. Assessment mode does not modify GitHub,
repository files, the index, staging, commits, or deployment.

Queue plans are saved under `/var/lib/redless/redless-queue/plans`, workspaces
under `/var/lib/redless/redless-queue/workspaces`, run results under
`/var/lib/redless/redless-queue/runs`, and stderr logs beside each run result.
Existing workspaces or run records are skipped so a human can inspect or
retry them deliberately.

Timeout output is explicitly ambiguous: the command stops its local process
group, but does not claim that any remote coding-model work has stopped. The
ordinary command is separate from the opt-in Ansible live smoke below.

## Check the installed interface

Send a capabilities request directly through the installed command:

```sh
printf '%s\n' '{"type":"capabilities"}' | sudo -u redless -- /opt/aggregare/venvs/redless/bin/redless-machine
```

The command emits JSONL status and result records on standard output. Redless
owns the task loop; Aggregare provides the installed package and host-level
account and filesystem isolation.

The coding profile uses the explicit `ysparr_coding_base_url` target directly
as an OpenAI-compatible `/v1` endpoint. Ysparr stores and validates that target,
but Redless does not route requests through the Ysparr chat service or silently
fall back to the chat model. Installation probes `/v1/models` and requires the
configured coding model ID before a live smoke task is attempted.

## Persistent artifacts

Task workspaces, run artifacts, and logs persist under:

- `/var/lib/redless/workspaces`
- `/var/lib/redless/runs`
- `/var/log/redless`

Configured primary users receive read access to completed and newly created
results through the `redless` group. They do not receive write access to those
artifacts, and the worker's private model profile is not group-readable.

Removing Redless with `redless_state: absent` removes the application source,
virtual environment, command, and Redless deployment status record. It
preserves these persistent paths and the private profile. A destructive purge
requires the explicit operator override `redless_purge_data: true` in the
removal invocation; back up the data first.

For the account and deployment details, see the [Redless section of
the Ubuntu Server deployment guide](aggregare-server.md#redless).
