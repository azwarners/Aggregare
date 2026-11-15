# Run a Redless task

Redless is Aggregare's bounded coding and task-execution component. Aggregare
installs its machine-callable JSONL interface as `redless-machine` at
`/usr/local/bin/redless-machine`.

The root-owned launcher automatically drops privileges to the unprivileged
`redless` account before starting the worker. Configured primary users do not
need—and are not given—a Redless password.

## Check the installed interface

Send a capabilities request directly through the installed command:

```sh
printf '%s\n' '{"type":"capabilities"}' | redless-machine
```

The command emits JSONL status and result records on standard output. Redless
owns the task loop; Aggregare provides the installed launcher and host-level
account and filesystem isolation.

## Persistent artifacts

Task workspaces, run artifacts, and logs persist under:

- `/var/lib/redless/workspaces`
- `/var/lib/redless/runs`
- `/var/log/redless`

Configured primary users receive read access to completed and newly created
results through the `redless` group. They do not receive write access to those
artifacts, and the worker's private model profile is not group-readable.

For the account, launcher, and deployment details, see the [Redless section of
the Ubuntu Server deployment guide](aggregare-server.md#redless).
