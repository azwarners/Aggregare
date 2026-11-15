# Redless one-shot task CLI

`tools/aggregare-redless-task` is a directly invokable, one-task operator
command. It is intentionally kept in the checkout until the deployment work
in issue #74 packages it.

```sh
sudo -u redless -- ./tools/aggregare-redless-task run --task 'inspect this bounded task'
sudo -u redless -- ./tools/aggregare-redless-task run --task-file ./task.txt
```

The command requires the effective `redless` UID and primary GID. It passes
the request to the installed `/usr/local/bin/redless-machine` with an argument
vector, a clean environment containing only `HOME`, `MSWEA_CONFIG_DIR`, safe
`PATH`, and locale settings, and no shell evaluation. It captures raw stdout
JSONL and stderr in the allocated persistent paths, then uses the issue #72
interpreter for the terminal outcome. A failed Redless result remains failed
even when the process exits zero.

Timeouts return an explicit ambiguous outcome: the local process is
terminated, but the command does not claim that any remote model work stopped.
Results, trajectories, and captured streams are never removed after failure.

Focused verification uses fake machine processes for success, failed result,
malformed output, missing terminal output, timeout, task-file Unicode and
multiline preservation, identity rejection, and environment-secret isolation.
