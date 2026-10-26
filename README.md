# Aggregare

## Implemented features and boundaries

**Available today:** Ubuntu Server/Ansible-oriented installation scaffolding; a default bundle with Open WebUI, Ysparr, Apmatia, Memos, HabitSync, Vikunja, and OpenIPE; published Apmatia starter-agent discovery through Ysparr; documented application and composition contracts; a selectable identity-provider *configuration value* (`kanidm`, `external_oidc`, or `none`), saved for repeatable reapplication; identity requirement inspection via `./tools/aggregare-auth`; and tests covering configuration and contracts.

**Not installed by selecting an option:** Kanidm, an external OpenID Connect provider, certificates, private DNS, or a fully configured SSO flow. The current identity-provider selector records a choice; it does not provision identity infrastructure. The guided Phase 3 client remains future work.

For a current checkout, review [the Ubuntu Server deployment guide](docs/deployment/aggregare-server.md), then run `./install.sh` on a suitable Ubuntu Server test host. It installs the default applications together; later additions to that baseline are additive. The installer asks for a reachable external OpenAI-compatible llama.cpp endpoint; Aggregare does not download models or install an inference server. Apmatia runs locally with persistent state and publishes its five prompt-only starter agents through Ysparr. Prefer a disposable VM for initial evaluation; review the playbooks and inventory before applying changes.

After installation, read the persistent deployment report from any directory with `aggregare report`. The authoritative Markdown report is `/var/lib/aggregare/deployment-report.md`; interactive installs also create `~/Aggregare-Report.md` when available. See the [deployment report guide](docs/deployment/deployment-report.md).

Change the HabitSync local password from your home directory with `cd ~/Aggregare && ./tools/aggregare-habitsync-password`. It prompts without echoing the password, preserves the installer's LAN setting, updates the service and protected credential file, and refreshes the deployment report.


Aggregare composes independently useful applications and infrastructure tools into one coherent platform.

Ubuntu is the initial reference host platform, and Ansible is the initial/default configuration engine for that implementation. Aggregare is not defined as an operating system, Linux distribution, custom kernel, or custom ISO. Its application and composition contracts should avoid unnecessary platform coupling so additional host platforms or deployment backends can be added later when there is a concrete need.

Aggregare owns the application catalog, presets, installation/configuration composition, and stack-level integration conventions. It does not replace the applications or execution systems it composes.

## Install Aggregare on Ubuntu Server

Ready to set up a server? From an Ubuntu Server 26.04 checkout, run `./install.sh` to install the Aggregare default system bundle: AI chat, Memos, HabitSync, Vikunja, and OpenIPE. The installer always requires a TTY for host-time, identity, and LAN prompts. It asks for a reachable external llama.cpp URL; pass `--llama-cpp-url http://HOST:PORT` to supply that value without the endpoint prompt. Choose the identity provider at its prompt, or pass `--identity-provider kanidm`, `--identity-provider external_oidc`, or `--identity-provider none` to make that choice noninteractive. The endpoint is checked with `GET /v1/models`, saved under `/etc/aggregare/`, and reused on reapply. Apmatia's first-user password is generated once and stored root-only in `/etc/aggregare/apmatia-credentials.json`. For unattended Ansible runs, set `ysparr_upstream_base_url` in protected inventory variables. The durable identity selection is `/etc/aggregare/identity.json`, managed by the identity configuration playbook. A conflicting identity selection fails unless an explicit update is requested. See the [step-by-step installation guide](docs/deployment/aggregare-server.md) for details.

The shared contracts and end-to-end examples are in
[`docs/contracts/phase-1.md`](docs/contracts/phase-1.md). The Phase 2 catalog
and direct Ansible usage are documented in
[`docs/contracts/phase-2.md`](docs/contracts/phase-2.md).
Phase 2.5 login requirements and secure credential setup are in
[`docs/contracts/phase-2.5.md`](docs/contracts/phase-2.5.md); the current live
results are in [`docs/contracts/phase-2.5-verification.md`](docs/contracts/phase-2.5-verification.md).
Inspect app login requirements with `./tools/aggregare-auth`. The
[Phase 2.5 HTTPS and OIDC guide](docs/deployment/phase-2.5-https-oidc.md)
covers temporary HTTPS and the separate dev and prod inventory model.

Validate the contracts, catalog, and Ansible YAML with
`python3 -m unittest discover -s tests` after installing `requirements-dev.txt`.
