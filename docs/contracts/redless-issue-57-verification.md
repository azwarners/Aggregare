# Redless issue #57 verification

Verification was run on the disposable `aggregare-dev` VM (`192.168.86.18`)
on 2026-11-15. The checkout was the issue-56 working tree with the issue #57
change copied into `ansible/roles/redless/tasks/main.yml`. No GitHub writes,
purge, queue run, or production host was used.

## Regression and lifecycle evidence

The local focused tests passed:

```text
python3 -m pytest -q tests/test_redless_role.py tests/test_report.py
20 passed in 0.52s
```

The VM lifecycle command used the real role and a local Ansible connection:

```sh
sudo ansible-playbook -i "aggregare," -e ansible_connection=local \
  playbooks/redless.yml \
  -e '{"redless_state":"absent","aggregare_primary_users":[]}'
```

Before removal, a stale `redless.json` status record, a separate
`other-app.json` status record, and `/var/lib/redless/workspaces/issue-57-sentinel/data.txt`
were seeded. The uninstall completed with the new task:

```text
TASK [redless : Remove the Redless deployment status record]
changed: [aggregare]
aggregare : ok=7 changed=0 failed=0
PASS:redless-status-absent
PASS:sentinel-preserved
PASS:other-status-preserved
PASS:persistent-path:/var/lib/redless/workspaces
PASS:persistent-path:/var/lib/redless/runs
PASS:persistent-path:/var/log/redless
```

After uninstall, the deployment report was regenerated with
`playbooks/report.yml`; it contained no Redless section, installed commands,
or live-verification claims.

Reapply used the same real playbook without `redless_state=absent` and passed:

```text
TASK [redless : Verify the deterministic fixture terminal result and clean stderr]
ok: [aggregare] => {"msg": "All assertions passed"}
TASK [redless : Write Redless deployment status]
changed: [aggregare]
aggregare : ok=41 changed=8 failed=0
PASS:redless-status-recreated
PASS:status-after-fixture
PASS:sentinel-still-preserved
PASS:other-status-still-preserved
```

The persisted status after reapply reported `state=installed` and
`fixture=passed`; it was written after the package import, help, and fixture
checks.

## Acceptance matrix

| Check | Result | Evidence |
| --- | --- | --- |
| Normal uninstall removes stale Redless status | Passed | Status file absent after real Ansible removal; report regenerated without Redless claims |
| Normal uninstall preserves user data and other status | Passed | Sentinel content and `other-app.json` unchanged; persistent directories remained |
| Reinstall/reapply recreates status after fixture verification | Passed | Real reapply completed; status contains `fixture=passed` |
| Worker account, locked password, effective worker execution | Passed | `redless` UID/GID observed; `passwd -S` reported `L`; role help/fixture/live commands ran as `redless` |
| Ownership, modes, and default ACLs | Passed | Worker private config `0700`; artifact roots `2750`; entry point `root:root 0755`; `getfacl` showed group/default read-execute ACLs and no other access |
| One bounded live coding task | Passed | Run `aggregare-live-20261115t093822`; JSONL terminal record was `state=succeeded`; trajectory/stdout/stderr artifacts existed; stderr contained model trace and no credentials |
| Primary-user browse and unrelated-user negative ACL checks | Not tested | This VM invocation had `aggregare_primary_users=[]`; no configured human account was in the Redless group |
| Reboot persistence | Not tested | No reboot was performed during this issue run |
| Existing Ysparr/Apmatia/Open WebUI chat no-regression checks | Not tested | Outside the focused uninstall/reinstall run; no chat request was issued |

The live smoke remained a single bounded task with no retry. Its final JSONL
record was recorded on the VM and the persisted status was updated to
`live_model=passed`.

