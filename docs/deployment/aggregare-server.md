# Install Aggregare on Ubuntu Server

Aggregare's Phase 2 foundation is a machine-readable application catalog and
Ansible automation. Aggregare is not one dashboard that replaces the
applications it installs.

The bootstrap installs the default Aggregare operating-system bundle together:
Open WebUI, Ysparr, Apmatia, Memos, HabitSync, Vikunja, OpenIPE, Sidecaravan
shared team memory, and Ladcemas-Lite. The
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

Before deployment, Aggregare checks the host's network time synchronization.
If the clock is not synchronized, it enables Chrony, waits for a synchronized
time source, and steps the clock when the remaining correction exceeds one
second and is under 24 hours. Review the selected Chrony source if the
correction is larger; the installer stops rather than making that change.
Aggregare then displays the server's local time, UTC time, timezone, and
synchronization status for confirmation. If the timezone is wrong, enter its
IANA name (for example, `America/Phoenix`); the installer applies it and asks
you to confirm again. If time synchronization cannot be established, inspect
`timedatectl status`, `chronyc tracking`, and `chronyc sources -v`, then rerun
the installer. Aggregare's managed Podman containers use the host timezone.

When you select `kanidm`, the installer collects a stable identity FQDN and
HTTPS origin. The production default asks for a certificate-chain and matching
private-key path on the Ansible controller. For an explicitly opted-in
disposable/private development install, pass `--kanidm-development-certificate`
or select Kanidm's self-signed evaluation certificate when prompted. The
generated certificate and key stay in persistent Kanidm storage and are reused
on reapplication; generation refuses a nonempty data directory. Reapplications
use the saved endpoint and TLS mode and reject ordinary attempts to change
them. `external_oidc` and `none` do not ask for Kanidm-specific settings.

Before selecting Kanidm, an administrator must configure the chosen DNS name
to resolve from the server and intended clients and route HTTPS from the
selected origin to the host's local Kanidm listener at `127.0.0.1:8443`. For
production, the administrator also supplies a trusted certificate for the
hostname. For private LANs, a name beneath
`home.arpa` can use local DNS and a private CA; install that CA's public root in
the host/browser/client trust stores and provide its path with
`--identity-ca-file` when running the installer. For a name under a registered
domain, a publicly trusted certificate can be used without exposing the
service publicly. The development certificate is self-signed and is not
trusted on other devices until its public certificate is explicitly imported
into each device's trust store. The installer prints its SHA-256 fingerprint,
public certificate path, and Linux import steps. Never distribute the private
key. DNS, production certificate issuance/renewal, proxy/router/firewall rules,
and development trust-store distribution remain administrator-managed.
Validate the selected origin from the host and each required client network
before enrolling accounts.

The script checks for Ubuntu 26.04, installs Ansible Core and OpenSSH Server
if needed, synchronizes and confirms host time, starts SSH, and applies the
default playbook locally on this same server using a localhost inventory. A
separate control machine or SSH connection is not needed for this first
install. If UFW is already active, the installer
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

The default bundle installs Sidecaravan's `scv` command and the pinned
Memkeeper v0.5.3 release binary automatically; no separate Memkeeper install
is required. The memory store is local and does not require an LLM.
The checked-in development bundle pins Sidecaravan, Ysparr, and Apmatia to the
coordinated test branches, so a fresh Aggregare install pulls matching
application versions automatically. After those branches are promoted, change
the pins back to `main` in the role defaults. For any other reviewed branch
or commit, override the corresponding source-ref variables in protected
inventory.
For changes that have not been pushed upstream, set
`sidecaravan_source_path` to a controller-local checkout; this is useful for
development and preserves the same automated installation path.

The role creates a random root-only team token on first initialization unless
`sidecaravan_team_token` is supplied through Ansible Vault. Retrieve or
distribute the generated token through an administrator-controlled channel,
then use it for authorized callers:

```sh
sudo cat /var/lib/aggregare/sidecaravan/team.token
export SCV_TOKEN='team-token'
scv save 'A durable team decision' --source session-1 --author nick
scv search 'team decision' --limit 5
sudo cat /var/lib/aggregare/status/sidecaravan-memory.json
```

The store is at `/var/lib/aggregare/sidecaravan/team.sqlite`. Back it up with
`scv backup /secure/backup/team.sqlite`, and restore only after stopping active
writers; `scv restore` requires `--force` before replacing an existing store.
Concurrent writers have not been certified by this milestone.

Removing Sidecaravan with `sidecaravan_state: absent` removes the wrapper,
source checkout, virtual environment, Memkeeper binary, and status record but
preserves the store and team token. Reapplying the role therefore reuses the
existing memories and access configuration. A destructive data purge is not
part of the normal uninstall path; back up and remove the data explicitly if
that is ever required.

The service status should say `active`; the status record should report a
passed verification. If you chose LAN access, use the LAN address printed by
the installer instead of `127.0.0.1` in the `curl` command.

Sidecaravan exposes its local MCP boundary through the administrator-protected
`sidecaravan-mcp.socket` Unix socket and provides the `scv` and `memkeeper`
commands. OpenIPE runs its REST API as `openipe.service` on loopback port 8002.
Ladcemas-Lite runs as `ladcemas-lite.service` on the same loopback or private
LAN bind address selected for the other user-facing applications, on port 5000,
and reads the generated deployment report.

The default bundle includes AI chat and productivity applications. Open
WebUI listens on port 8080 and Ysparr on port 8000; first-party Python
applications are installed from their upstream `main` branches. Open WebUI keeps its
database and uploaded data in `/var/lib/aggregare/open-webui/`; Ysparr keeps
its SQLite database in `/var/lib/ysparr/`. Apmatia runs as
`apmatia-core.service`, bound to loopback on port 8001, with state in
`/var/lib/apmatia/{app,data,config}`. On a fresh install, Aggregare creates the
first Apmatia account and saves its password at
`/etc/aggregare/apmatia-credentials.json` with root-only permissions. The
deployment report includes the generated username and password and is readable
only by the installing administrator. Retrieve the credential file with
`sudo cat /etc/aggregare/apmatia-credentials.json` if needed, and keep protected
backups of both. Reapply logs in with that account; if an existing database has no saved
credentials, Aggregare leaves its users alone and reports that manual setup is
needed. Apmatia's supported one-time bootstrap publishes its five bundled
prompt-only starters with a backing model from the selected upstream. Ysparr
adds those explicitly published agent names as virtual models alongside real
upstream models. If Apmatia is unavailable, Ysparr continues serving the real
upstream models. Selecting an agent sends its compiled prompt as a system
message and preserves the client's conversation; this integration does not
provide Apmatia tools or memory through Ysparr. OpenIPE is installed from its
`main` branch as part of the default system. Open WebUI uses
Ysparr, which the installer connects to an external llama.cpp endpoint during
setup. Aggregare does not install llama.cpp or download model weights.

### Open WebUI first use

Open WebUI is an independent, boot-enabled `open-webui.service`. Its data and
chats persist in `/var/lib/aggregare/open-webui/`. The installer prints the
address selected by the loopback/LAN access prompt. The Open WebUI process
shares the host network so it can reach Ysparr at
`http://127.0.0.1:8000/v1`; its own web listener still follows the selected
bind address. Aggregare configures this as the only model provider and disables
Open WebUI's Ollama and direct-provider connections. It does not point Open
WebUI at llama.cpp.

On a fresh Open WebUI database, open the printed URL and create the first
account in the browser. Open WebUI makes the first account an administrator.
Sign-up is temporarily enabled for that initial setup; disable new sign-ups in
**Admin Panel → Settings** after creating the account. If you keep sign-ups
enabled, new accounts default to the pending role and require administrator
approval. Until sign-up is disabled, keep access limited to trusted clients.
Aggregare does not create an Open WebUI account or password on your behalf.

After signing in, start a new chat and open the model selector. Ysparr exposes
the upstream llama.cpp model IDs plus the published Apmatia starter names
**Mira, Luna, Rowan, Belle, and Ivy**. If the list is empty or stale, verify
Ysparr independently with:

```sh
curl --fail --silent --show-error http://127.0.0.1:8000/v1/models
```

For a direct streaming smoke check, replace `MODEL_ID_FROM_LIST` with one of
the IDs returned above (for example, a published agent ID):

```sh
curl --no-buffer --fail --silent --show-error \
  http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"MODEL_ID_FROM_LIST","messages":[{"role":"user","content":"Reply briefly."}],"stream":true}'
```

Then open **Admin Panel → Settings → Connections**, save or recheck the
preconfigured Ysparr connection, and reload the model selector. Selecting an
Apmatia virtual model sends its compiled system prompt through Ysparr; leave
the model's Open WebUI system-prompt override empty if you want to preserve the
Apmatia prompt as published. Complete a chat from the Open WebUI interface as a
separate check; the command above tests Ysparr directly, not the browser path.

Aggregare disables Open WebUI's Ollama, direct provider, web search, code
execution, code interpreter, memory, subagents, and plugins. The plugin master
switch also disables Open WebUI's built-in Tools, Functions, OpenAPI/MCP tool
servers, and Open Terminal integrations. Open WebUI is intentionally a
chat-only frontend in Aggregare; optional upstream capabilities remain off
unless a future configuration explicitly enables them. These environment
settings are applied to the generated service definition and require an Open
WebUI service restart to take effect. Reapplying Aggregare or recreating the
service preserves the settings and the existing Open WebUI database, accounts,
chats, and Ysparr connection. Aggregare does not configure Open WebUI
Knowledge/RAG or install plugin, pipeline, RAG, or custom agent content.

HabitSync receives a generated local login using the account that ran the
installer as its username; the initial login appears in the deployment report.
To choose a personal password or change it later, run
`cd ~/Aggregare && ./tools/aggregare-habitsync-password` from your home directory.
It prompts without echoing the password, applies it to the service, removes the
superseded initial login handoff, and refreshes the deployment report without
recording the new password. Back up `/etc/aggregare/secrets/habitsync-jwt`
with the applications' data. If you use
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

The installer prompts for the chat endpoint and checks `GET /v1/models`
from the Aggregare host before installing the bundle. If that endpoint returns
one model, the installer selects it automatically for chat. If it returns
multiple models, the installer displays them as a numbered list for selection.
The same automatic selection or numbered list is used for the coding endpoint.
The installer also collects the coding endpoint URL. The chat endpoint
continues to serve Open WebUI chats and Apmatia agents. Ysparr lists the
configured coding model as a separate selectable model; requests using that
ID go to the coding endpoint. Apmatia agents declare their backend type as
`openai_compatible`; Aggregare automatically maps that type to the selected
Ysparr chat model. Operators can override or add `ysparr_model_type_routes`
when an extension requires a different upstream model ID. Enter endpoint
addresses as `HOST:PORT` (for
example `192.168.1.42:8000`) or include `http://` or `https://`; a missing
scheme defaults to `http://`. URLs ending in `/v1` are accepted. Ysparr stores
normalized root URLs and adds `/v1` to API requests. These values are saved in
`/etc/aggregare/ysparr-upstream.json` with mode `0640`, owned by root and the
Ysparr service group. Reapplying without overrides reuses saved values and
preserves the existing API key. Older saved configurations without coding
targets continue using their single endpoint. The systemd environment file is
also protected and is the runtime source for Ysparr.

To supply the endpoint without entering it at the installer prompt, use
`./install.sh --llama-cpp-url http://HOST:PORT --chat-model CHAT_ID --coding-llm-url http://CODE_HOST:PORT --coding-model CODE_ID`; host-time, identity, and LAN
prompts still require a terminal. For direct or unattended
Ansible use, set `ysparr_upstream_base_url`, `ysparr_chat_model`,
`ysparr_coding_base_url`, `ysparr_coding_model`, and optionally
`ysparr_model_type_routes` in inventory variables and run
`ansible-playbook -i INVENTORY playbooks/default.yml --become`; the role
checks both `/v1/models` endpoints and verifies the configured model IDs,
configures Ysparr, and persists the settings. To change an endpoint or model
without reinstalling the stack, reapply `playbooks/ysparr.yml --become` with
`-e ysparr_upstream_base_url=https://CHAT_HOST:PORT -e ysparr_chat_model=CHAT_ID
-e ysparr_coding_base_url=https://CODE_HOST:PORT -e ysparr_coding_model=CODE_ID`.

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
For service lifecycle, network boundaries, diagnostic output, backup/restore,
and the VM smoke-check sequence, see
[AI chat operations](aggregare-ai-chat-operations.md).

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
- **Apmatia** runs a loopback-only core API on port 8001 and installs the
  `apmatia` CLI in its isolated virtual environment. **OpenIPE** runs its
  REST API as `openipe.service`; it does not yet ship an `openipe` CLI.
- **TroubleShell** is a desktop application. **Ladcemas-Lite** is installed as
  a local launcher service. **Sidecaravan** installs the `scv` and `memkeeper`
  CLIs plus its MCP socket service.

The default system bundle and catalog are the source of truth for the
applications Aggregare installs. The bootstrap delegates to the same Ansible
playbooks used directly, and the default application set grows additively.
