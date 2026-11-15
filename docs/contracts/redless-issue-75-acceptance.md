# Redless issue #75 acceptance record

Date: 2026-11-15

This records the verification completed for the local task-process lifetime
work in issue #75. No live Redless/model task was submitted; the operator can
perform that acceptance step after deployment.

## Result matrix

| Check | Result | Evidence |
| --- | --- | --- |
| SIGTERM-resistant descendant cleanup | Passed | Focused test and the VM smoke both observed the descendant disappear from `/proc`. |
| Bounded timeout and pipe handling | Passed | Local run completed in the bounded test window; VM smoke completed in 0.208 seconds. |
| Ambiguous timeout contract and no retry | Passed | Returned `outcome=timeout`, `code=ambiguous_timeout`; the fake machine was invoked once. |
| Raw partial stdout/stderr/artifacts retained | Passed | Existing focused artifact assertions remain green; the VM smoke retained the running status JSONL. |
| Full offline regression suite | Passed | `97 passed, 203 subtests passed in 40.42s`. |
| Redless playbook syntax | Passed | `ANSIBLE_CONFIG=ansible/ansible.cfg ANSIBLE_LOCAL_TEMP=/tmp/aggregare-ansible-tmp ansible-playbook --syntax-check -i inventory-examples/dev/hosts.ini playbooks/redless.yml`. |
| Standard CLI installed on aggregare-dev | Not tested | The VM currently has `redless` but no `/usr/local/bin/aggregare-redless-task` or `/usr/local/lib/aggregare` deployment. |
| Real report command, live model route, and target contact | Not tested | Requires the deployed service/profile and operator acceptance; no inference was started automatically. |
| Reapply, reboot persistence, uninstall/reinstall retention | Not tested | Requires performing the deployment lifecycle on the VM. |

## Exact local invocations

```sh
PYTHONPATH=. pytest -q tests/test_aggregare_redless_task.py
# 10 passed in 1.05s

PYTHONPATH=. pytest -q
# 97 passed, 203 subtests passed in 40.42s

ANSIBLE_CONFIG=ansible/ansible.cfg \
ANSIBLE_LOCAL_TEMP=/tmp/aggregare-ansible-tmp \
ansible-playbook --syntax-check \
  -i inventory-examples/dev/hosts.ini playbooks/redless.yml
# playbook: playbooks/redless.yml
```

## VM evidence

The authorized host `aggregare-dev` was checked with:

```sh
ssh -F /dev/null nick@192.168.86.18 \
  'getent passwd redless; ls -l /usr/local/bin/aggregare-redless-task /usr/local/lib/aggregare/*'
```

It reported `redless:x:1001:1002` and no installed CLI or library directory.
A disposable copy of the two CLI modules was used under `/tmp`, with a fake
machine that spawned a child ignoring SIGTERM. The direct smoke returned:

```text
{"outcome": "timeout", "code": "ambiguous_timeout", "elapsed": 0.208,
 "descendant_state": "missing", "stdout": "...state...running..."}
```

The temporary VM files were confined to `/tmp/aggregare-75-smoke` and were not
part of the system installation.
