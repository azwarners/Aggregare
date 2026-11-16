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
output, missing configuration, and local timeouts exit nonzero. Use
`--help` for options. The command prints the run ID and saved paths. Results
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
