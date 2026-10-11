# Phase 2 verification record

Status: repository checks and live application verification on a clean Ubuntu Server 26.04 test VM are recorded below. Production deployments are outside this product verification scope.

## Local checks

Working tree based on revision `56948e3462e5d80aa2803e60346fac382cdc56fb`; checks below were run against the current working tree.

- `python3 -m unittest discover -s tests` — passed (5 tests).
- `bash -n install.sh` — passed.
- `git diff --check` — passed.
- `ansible-playbook --syntax-check` — passed for `ysparr.yml`, `memos.yml`, `llama-cpp.yml`, and `site.yml`, using `ansible/inventory.ini.example`. After adding `welcome.yml`, syntax checks passed for it and the three live-tested application playbooks, also using the example inventory.
- Case-insensitive scan for the retired product name across active repository files — no matches.
- Confirmed the bootstrap installs/enables OpenSSH and, when UFW is already active, allows SSH from the detected private LAN subnet.

These local checks do not establish live installation behavior.

## Live Ubuntu verification

Target: clean Ubuntu Server 26.04 test VM. Results below were captured during live Phase 2 verification on 2026-10-11; exact command times were not recorded. The VM used the current Aggregare working tree copied into the test environment. The initial bootstrap configured SSH; application playbooks ran locally through the localhost inventory. Ubuntu 26.04's default `sudo-rs` timed out with Ansible become during direct playbook testing, so those runs used `/usr/bin/sudo.ws` via `-e ansible_become_exe=/usr/bin/sudo.ws`.

### Console-only setup and applications

From the VM console, install Git if it is not present, then clone and start the documented Aggregare installer:

```sh
sudo apt update
sudo apt install -y git
cd "$HOME"
git clone https://github.com/azwarners/Aggregare.git
cd "$HOME/Aggregare"
./install.sh
```

When asked about Memos LAN access, answer `n` for a loopback-only verification. The installer adds Ansible Core and OpenSSH Server if missing, creates `ansible/inventory.ini` with `localhost ansible_connection=local`, enables SSH, and applies the Memos and Aggregare welcome playbooks as separate runs on this same VM. Memos configuration changes do not run the welcome role. The initial applies do not need an SSH connection. Use the printed SSH command from your workstation for copy-friendly terminal access after setup, or continue from the VM console. To apply the other candidates, use a terminal on the VM:

```sh
cd "$HOME/Aggregare/ansible"
ansible-playbook -i inventory.ini playbooks/ysparr.yml --ask-become-pass
ansible-playbook -i inventory.ini playbooks/llama-cpp.yml --ask-become-pass
```

Run each of these three commands once more, unchanged, and keep the playbook recaps for idempotency results:

```sh
ansible-playbook -i inventory.ini playbooks/memos.yml --ask-become-pass
ansible-playbook -i inventory.ini playbooks/ysparr.yml --ask-become-pass
ansible-playbook -i inventory.ini playbooks/llama-cpp.yml --ask-become-pass
```

To test a supported Memos port change and restore the default:

```sh
ansible-playbook -i inventory.ini playbooks/memos.yml --ask-become-pass -e application_host_port=5231
ansible-playbook -i inventory.ini playbooks/memos.yml --ask-become-pass
```

Apply the login banner independently when its content or server metadata changes:

```sh
ansible-playbook -i inventory.ini playbooks/welcome.yml --ask-become-pass
```

To test removal while preserving Memos data, check `/var/lib/aggregare/memos`, remove the service, check the directory again, and reinstall:

```sh
sudo ls -ld /var/lib/aggregare/memos
ansible-playbook -i inventory.ini playbooks/memos.yml --ask-become-pass -e application_state=absent
sudo ls -ld /var/lib/aggregare/memos
ansible-playbook -i inventory.ini playbooks/memos.yml --ask-become-pass
```

Check the two service-backed applications and all machine-readable records from the VM console:

```sh
sudo systemctl is-active ysparr.service memos.service
curl --fail --silent --show-error http://127.0.0.1:8000/health
curl --fail --silent --show-error http://127.0.0.1:5230/
sudo cat /var/lib/aggregare/status/ysparr.json
sudo cat /var/lib/aggregare/status/memos.json
sudo cat /var/lib/aggregare/status/llama-cpp.json
```

llama.cpp builds CPU software and remains stopped without a model. Its status record should say `installed` with a passed `llama-server --version` check; that is install verification, not inference readiness. The repeated playbook recaps are the idempotency evidence.

| Application | Category | Revision/version | First apply | Second apply | Config change/reapply | Status/endpoints/data | Removal and persistence | Reinstall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Ysparr | Aggregare-owned | `0.1.0` | Passed (`changed=10`, `failed=0`); service active and `/health` passed | Passed after idempotency guard (`changed=0`, `failed=0`; an earlier repeat exposed `changed=2` from editable pip install and restart) | N/A | Status says `running`; `ysparr.service` active; `/health` returned `status: ok` | N/A | N/A |
| Memos | Third-party productivity | `0.31.0`, image `ghcr.io/usememos/memos:0.31.0` | Installed by bootstrap; recap not captured | Passed after one directory normalization (`changed=0`, `failed=0`) | Port changed to `5231`, then restored to `5230`; applies passed. Memos playbook was separated from welcome role during this test. | `memos.service` active; `http://127.0.0.1:5230/` returned Memos HTML; status says `running`, verification `passed` | Passed: removal (`changed=3`) stopped service; `/var/lib/aggregare/memos` remained `root:root`, mode `0750`; service inactive | Passed: reinstall (`changed=3`); service active and endpoint/status verified |
| llama.cpp | AI runtime | Status version `0.5.0`; binary `0.5.0-dev` (build 11146, commit `7fe450e19`) | Built; first run stopped at missing-model check because `stat.isreg` was undefined. Role now defaults the missing field to false; retry passed (`changed=1`, status written) | Passed (`changed=0`, `failed=0`) | N/A | `llama-server --version` passed; status says `installed` and version check passed; service inactive and disabled without a model | N/A | N/A |

The Aggregare welcome role now has its own `welcome.yml` playbook. It ran independently on the test VM with `changed=1` on the first apply and `changed=0` on the second. Memos runs no longer invoke it. After these changes, the current installer was rerun from a clean pre-Aggregare Ubuntu Server 26.04 snapshot. The bootstrap installed Ansible Core and enabled OpenSSH, installed and verified Memos in its own play (`ok=10`, `changed=5`, `failed=0`), then applied the welcome role as a separate play (`ok=4`, `changed=2`, `failed=0`). The bootstrap completed successfully with Memos bound to loopback.

The live results above are based on captured terminal output from the test VM. Exact command times were not captured. Machine-readable status records are written under `/var/lib/aggregare/status/`. Credentials, tokens, LAN addresses, usernames, hostnames, and other environment-specific values are intentionally excluded from this verification record.

The three applications have different resource needs: llama.cpp builds from source and requires an operator-supplied model to verify its inference endpoint; its install/status check is recorded separately from inference readiness.

## Verification environment

Live application verification was completed on a disposable Ubuntu Server 26.04 test VM. Production deployments were not used for this issue's tests and are not required to establish product-level Phase 2 acceptance.

Future product verification should use a non-production test environment. Keep deployment-specific production decisions and checks separate from this verification record.

## Known limits

The live steps above require access to a clean Ubuntu target. Repository checks alone do not imply successful live installation. Record unsupported behavior and failures rather than marking an application verified.
