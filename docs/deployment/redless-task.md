# Run a Redless task

Redless is Aggregare's bounded coding and task-execution component. Aggregare
installs its machine-callable JSONL interface as `redless-machine` in the
`/opt/aggregare/venvs/redless` virtual environment.

The package entry point runs as the unprivileged `redless` account through the
normal administrator mechanism. Configured primary users do not need—and are
not given—a Redless password.

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
