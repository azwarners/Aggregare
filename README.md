# Aggregare

## Implemented features and boundaries

**Available today:** Ubuntu Server/Ansible-oriented installation scaffolding; a Phase 2 application catalog and Memos deployment path; documented application and composition contracts; a selectable identity-provider *configuration value* (`kanidm`, `external_oidc`, or `none`), saved for repeatable reapplication; identity requirement inspection via `./tools/aggregare-auth`; and tests covering configuration and contracts.

**Not installed by selecting an option:** Kanidm, an external OpenID Connect provider, certificates, private DNS, or a fully configured SSO flow. The current identity-provider selector records a choice; it does not provision identity infrastructure. Application presets and a guided Phase 3 client remain future work.

For a current checkout, review [the Ubuntu Server deployment guide](docs/deployment/aggregare-server.md), then run `./install.sh` on a suitable Ubuntu Server test host. Prefer a disposable VM for initial evaluation; review the playbooks and inventory before applying changes.


Aggregare composes independently useful applications and infrastructure tools into one coherent platform.

Ubuntu is the initial reference host platform, and Ansible is the initial/default configuration engine for that implementation. Aggregare is not defined as an operating system, Linux distribution, custom kernel, or custom ISO. Its application and composition contracts should avoid unnecessary platform coupling so additional host platforms or deployment backends can be added later when there is a concrete need.

Aggregare owns the application catalog, presets, installation/configuration composition, and stack-level integration conventions. It does not replace the applications or execution systems it composes.

## Install Aggregare on Ubuntu Server

Ready to set up a server? From an Ubuntu Server 26.04 checkout, run `./install.sh` to deploy Memos as a Phase 2 example. It asks whether Memos should be reachable over your private LAN and which identity provider configuration to select. Pass `--identity-provider kanidm`, `--identity-provider external_oidc`, or `--identity-provider none` to set the choice directly. The non-secret choice is saved in `/etc/aggregare/identity.json` and reused on reapply unless overridden. For a noninteractive configuration-only run, set `aggregare_identity_provider` in the protected inventory and run `ansible-playbook -i INVENTORY playbooks/phase25-identity-config.yml`. This selection does not install or provision an identity provider. See the [step-by-step installation guide](docs/deployment/aggregare-server.md) for details. Application selection and presets are planned for the Phase 3 client.

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
