# Aggregare

## Implemented features and boundaries

**Available today:** Ubuntu Server/Ansible-oriented installation scaffolding; a default bundle with Open WebUI, Ysparr, Apmatia, Memos, HabitSync, Vikunja, and OpenIPE; published Apmatia starter-agent discovery through Ysparr; documented application and composition contracts; a selectable identity provider (`kanidm`, `external_oidc`, or `none`), with pinned Kanidm service deployment and persisted endpoint settings; identity requirement inspection via `./tools/aggregare-auth`; and tests covering configuration and contracts.

**Administrator supplied:** DNS records, trusted TLS certificates and private keys, and any reverse-proxy/router/firewall configuration needed to reach the selected Kanidm endpoint. Selecting `external_oidc` records the provider choice without installing an external provider. Application OIDC clients and the guided Phase 3 client remain future work.

For a current checkout, review [the Ubuntu Server deployment guide](docs/deployment/aggregare-server.md), then run `./install.sh` on a suitable Ubuntu Server test host. It installs the default applications together; later additions to that baseline are additive. The installer asks for a reachable external OpenAI-compatible llama.cpp endpoint; Aggregare does not download models or install an inference server. Apmatia runs locally with persistent state and publishes its five prompt-only starter agents through Ysparr. Prefer a disposable VM for initial evaluation; review the playbooks and inventory before applying changes.


Aggregare composes independently useful applications and infrastructure tools into one coherent platform.

Ubuntu is the initial reference host platform, and Ansible is the initial/default configuration engine for that implementation. Aggregare is not defined as an operating system, Linux distribution, custom kernel, or custom ISO. Its application and composition contracts should avoid unnecessary platform coupling so additional host platforms or deployment backends can be added later when there is a concrete need.

Aggregare owns the application catalog, presets, installation/configuration composition, and stack-level integration conventions. It does not replace the applications or execution systems it composes.

## Install Aggregare on Ubuntu Server

Ready to set up a server? From an Ubuntu Server 26.04 checkout, run `./install.sh` to install the Aggregare default system bundle: AI chat, Memos, HabitSync, Vikunja, and OpenIPE. The installer always requires a TTY for host-time, identity, and LAN prompts. It asks for a reachable external llama.cpp URL; pass `--llama-cpp-url http://HOST:PORT` to supply that value without the endpoint prompt. Choose `kanidm`, `external_oidc`, or `none` at the identity prompt. For Kanidm, also provide an administrator-selected identity FQDN, HTTPS origin, and matching certificate chain/private key; the installer checks DNS and TLS before deployment. The endpoint is saved under `/etc/aggregare/identity.json` and reused on reapply. Apmatia's first-user password is generated once and stored root-only in `/etc/aggregare/apmatia-credentials.json`. For unattended Ansible runs, set `ysparr_upstream_base_url` in protected inventory variables. See the [step-by-step installation guide](docs/deployment/aggregare-server.md) for details.

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
