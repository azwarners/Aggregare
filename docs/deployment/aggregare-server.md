# Install Aggregare on Ubuntu Server

Aggregare's Phase 2 foundation is a machine-readable application catalog and
Ansible automation. Aggregare is not one dashboard that replaces the
applications it installs.

The bootstrap installs the default Aggregare operating-system bundle together:
Open WebUI, Ysparr, Apmatia, Memos, HabitSync, Vikunja, and OpenIPE. The
independent application playbooks remain available for later configuration and
reapplication. Adding an application to the default bundle does not replace or
remove applications already installed.

## Before you begin

You need:

- A patched Ubuntu Server 26.04 machine with internet access.
- A terminal on the server for the first install (for example, the VM console). Aggregare sets up SSH for later remote access.
- A normal Ubuntu user account that can run `sudo` commands.
- A few gigabytes of free disk space for the selected applications and their
  persistent data.
- Git to clone the Aggregare repository. If needed, install it from the VM console with `sudo apt update && sudo apt install -y git`.

Keep your VM backup. Memos data is stored under `/var/lib/aggregare/memos/`
and is preserved when its service is removed. Back up Apmatia's
`/var/lib/apmatia/app`, `/var/lib/apmatia/data`, and `/var/lib/apmatia/config`
along with its root-only credential and bootstrap files; removing the service
does not remove them.

## Install the default system bundle

If you have not already downloaded the Aggregare project, run:

```sh
cd "$HOME"
git clone https://github.com/azwarners/Aggregare.git
```

Start the bootstrap:

```sh
cd "$HOME/Aggregare"
./install.sh
```

The installer always installs the default bundle. It asks you to confirm host
time, identity configuration, and whether the user-facing applications should
be reachable from the private LAN.

During installation, Aggregare displays the server's local time, UTC time,
timezone, and network time synchronization status. Confirm that they are
correct before application deployment. If the timezone is wrong, enter its
IANA name (for example, `America/Phoenix`); the installer applies it and asks
you to confirm again. Installation stops if the system clock is not synchronized.
On Ubuntu, inspect or enable time synchronization with `timedatectl status` and
`sudo timedatectl set-ntp true`, then rerun the installer. Aggregare's managed
Podman containers use the host timezone.

The script checks for Ubuntu 26.04, installs Ansible Core and OpenSSH Server
if needed, starts SSH, and applies the default playbook locally on this same
server using a localhost inventory. A separate control machine or SSH connection is
not needed for this first install. If UFW is already active, the installer
allows SSH only from the server's private LAN subnet; it does not enable UFW.
The script prints an SSH command for later terminal access from another
computer. It asks whether the user-facing applications should be reachable by
other devices on your private LAN, then applies the playbooks with administrator access. Type your
normal Ubuntu `sudo` password when the installer asks. The script does not
install Git as a setup step.

For later terminal access, run the printed `ssh username@address` command from
a computer that can reach the VM. If the VM uses NAT, a bridged virtual network
adapter may be needed for direct LAN access.

The first run installs Podman because the default bundle includes container
applications. Podman is an optional deployment tool for selected applications,
not a requirement of the catalog or Ansible foundation.

When the default playbook finishes, check Memos and its verification record:

```sh
sudo systemctl status memos.service --no-pager
curl --fail --silent --show-error http://127.0.0.1:5230/
sudo cat /var/lib/aggregare/status/memos.json
```

The service status should say `active`; the status record should report a
passed verification. If you chose LAN access, use the LAN address printed by
the installer instead of `127.0.0.1` in the `curl` command.

The default bundle includes AI chat and productivity applications. Open
WebUI listens on port 8080 and Ysparr on port 8000; the catalog records the
pinned upstream versions. Open WebUI keeps its
database and uploaded data in `/var/lib/aggregare/open-webui/`; Ysparr keeps
its SQLite database in `/var/lib/ysparr/`. Apmatia runs as
`apmatia-core.service`, bound to loopback on port 8001, with state in
`/var/lib/apmatia/{app,data,config}`. On a fresh install, Aggregare creates the
first Apmatia account and saves its password at
`/etc/aggregare/apmatia-credentials.json` with root-only permissions. Retrieve
it with `sudo cat /etc/aggregare/apmatia-credentials.json` and keep a protected
backup. Reapply logs in with that account; if an existing database has no saved
credentials, Aggregare leaves its users alone and reports that manual setup is
needed. Apmatia's supported one-time bootstrap publishes its five bundled
prompt-only starters with a backing model from the selected upstream. Ysparr
adds those explicitly published agent names as virtual models alongside real
upstream models. If Apmatia is unavailable, Ysparr continues serving the real
upstream models. Selecting an agent sends its compiled prompt as a system
message and preserves the client's conversation; this integration does not
provide Apmatia tools or memory through Ysparr. OpenIPE is installed from its
pinned Python package revision as part of the default system. Open WebUI uses
Ysparr, which the installer connects to an external llama.cpp endpoint during
setup. Aggregare does not install llama.cpp or download model weights.
HabitSync receives a
generated local login; read it with `sudo cat /etc/aggregare/habitsync-credentials`
and change it after the first sign-in. Back up this credentials file and
`/etc/aggregare/secrets/habitsync-jwt` with the applications' data. If you use
an upstream API key, back up `/etc/aggregare/ysparr-upstream.json` as well.

The same additive default bundle can be applied or reapplied through Ansible.
The bootstrap creates a localhost inventory; use it with:

```sh
cd "$HOME/Aggregare/ansible"
ansible-playbook -i inventory.ini playbooks/default.yml --become --ask-become-pass
```

For unattended runs, provide Ansible privilege credentials through your
inventory's protected secret source and run the same command with `--become`
without `--ask-become-pass`.

The installer prompts for the llama.cpp base URL and checks `GET /v1/models`
from the Aggregare host before installing the bundle. Enter the server address
as `HOST:PORT` (for example `192.168.1.42:8000`) or include `http://` or
`https://`; a missing scheme defaults to `http://`. A URL ending in `/v1` is
also accepted. Ysparr stores a normalized root URL and adds `/v1` to API
requests. The selected URL is saved in
`/etc/aggregare/ysparr-upstream.json` with mode `0640`, owned by root and the
Ysparr service group. Reapplying the playbook without an endpoint override
reuses that saved value. The systemd environment file is also protected and
is the runtime source for Ysparr.

To supply the endpoint without entering it at the installer prompt, use
`./install.sh --llama-cpp-url http://HOST:PORT`; host-time, identity, and LAN
prompts still require a terminal. For direct or unattended
Ansible use, put `ysparr_upstream_base_url` in inventory variables and run
`ansible-playbook -i INVENTORY playbooks/default.yml --become`; the role
checks `/v1/models`, configures Ysparr, and persists the endpoint. To change the
endpoint without reinstalling the stack, reapply
`playbooks/ysparr.yml --become -e ysparr_upstream_base_url=https://HOST:PORT`.

If the upstream requires an API key, set `ysparr_upstream_api_key` in the
encrypted `ansible/group_vars/aggregare/vault.yml` (or the matching protected
inventory secret source). The installer detects an encrypted local
`vault.yml` and prompts for its Vault password. Ansible suppresses task output
for secret-bearing operations; do not place keys in URLs, shell history,
unprotected inventory, or committed files. To clear a saved key, set
`ysparr_upstream_api_key_reset: true` for one reapply.

The connectivity check distinguishes DNS failures, refused or timed-out
connections, authentication failures, and a missing `/v1/models` route. A
loopback address is interpreted from the Aggregare host's network namespace:
if llama.cpp runs in a container, publish its port and use the host's reachable
address rather than the container's `127.0.0.1`. The endpoint remains external;
the installer neither downloads models nor starts a local inference server.

Use the same playbook to upgrade:
review the pinned images and revisions in the application catalog and
`catalog/v1/presets/default.json`, update those pins deliberately, then apply
again. Reapply is idempotent; Apmatia's one-time bootstrap marker preserves
edited or deleted starters and later publication choices. Removing an
application preserves its data directories and generated credentials.

## LAN access

If you answer no, the user-facing applications listen only on the server's loopback address. They are
not directly reachable from another computer.

If you answer yes, the script binds the user-facing applications to a
private IPv4 address on the server's default network interface. It prints the
address to open, for example `http://192.0.2.25:8080/` for Open WebUI,
`http://192.0.2.25:5230/` for Memos, `http://192.0.2.25:6842/` for HabitSync,
and `http://192.0.2.25:3456/` for Vikunja (replace the documentation-only address
with the server's private address). If UFW is active, the installer adds a
separate SSH rule scoped to the server's private LAN subnet; it leaves other
rules unchanged and does not enable a firewall. If UFW blocks application
connections, the script prints LAN-scoped rules for the user-facing app ports.
It does not configure router port forwarding.

For a VM, its network adapter must allow other devices on your LAN to reach
the VM. A NAT-only virtual network may hide it from the LAN; use a bridged
adapter if you want other LAN devices to connect. Do not forward application
ports from your router to the public internet.

## Install another application directly

Each application has a playbook in `ansible/playbooks/`. The bootstrap creates
`ansible/inventory.ini` with `localhost ansible_connection=local` and leaves it
in place so you can run additional playbooks directly on this server. For
example, to install Beszel:

```sh
cd "$HOME/Aggregare/ansible"
ansible-playbook -i inventory.ini playbooks/beszel.yml --ask-become-pass
```

The direct playbooks remain the Phase 2 interface. Container applications
listen on loopback by default. To bind a container application to this
server's LAN address, pass that address explicitly; for example:

```sh
ansible-playbook -i inventory.ini playbooks/beszel.yml \
  --ask-become-pass \
  -e application_bind_address=192.0.2.25
```

Replace the documentation-only address with the server's private address. UFW rules, if needed,
must be limited to the private LAN subnet. Native services use their
application-specific host variable (`ysparr_host`, `comfyui_host`, or
`llama_cpp_host`).

Some applications need extra setup:

- **Ysparr** needs an OpenAI-compatible upstream service address and may need
  an API key.
- **Grafana** and **Semaphore UI** need administrator passwords supplied
  through Ansible Vault. Do not put passwords in playbooks, catalog entries,
  or shell commands.
- **llama.cpp** builds a CPU server and remains stopped until you supply a
  model file under `/var/lib/aggregare/llama.cpp/models`.
- **ComfyUI** uses CPU mode and does not download model files. GPU setup is not
  part of this Phase 2 foundation.
- **Apmatia** runs a loopback-only core API on port 8001. **OpenIPE** and
  **Redless** remain Python packages or command-line tools.
- **TroubleShell** is a desktop application. **Ladcemas** and **Sidecaravan**
  do not yet have installable roles.

The default system bundle and catalog are the source of truth for the
applications Aggregare installs. The bootstrap delegates to the same Ansible
playbooks used directly, and the default application set grows additively.
