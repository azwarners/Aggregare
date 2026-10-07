# Aggregare

Aggregare composes independently useful applications and infrastructure tools into one coherent platform.

Ubuntu is the initial reference host platform, and Ansible is the initial/default configuration engine for that implementation. Aggregare is not defined as an operating system, Linux distribution, custom kernel, or custom ISO. Its application and composition contracts should avoid unnecessary platform coupling so additional host platforms or deployment backends can be added later when there is a concrete need.

Aggregare owns the application catalog, presets, installation/configuration composition, and stack-level integration conventions. It does not replace the applications or execution systems it composes.

## Install Aggregare on Ubuntu Server

Ready to set up a server? From an Ubuntu Server 26.04 checkout, run `./install.sh` to deploy Memos as a Phase 2 example. It asks whether Memos should be reachable over your private LAN. See the [step-by-step installation guide](docs/deployment/aggregare-server.md) for details. Application selection and presets are planned for the Phase 3 client.

The shared contracts and end-to-end examples are in
[`docs/contracts/phase-1.md`](docs/contracts/phase-1.md). The Phase 2 catalog
and direct Ansible usage are documented in
[`docs/contracts/phase-2.md`](docs/contracts/phase-2.md).

Validate the contracts, catalog, and Ansible YAML with
`python3 -m unittest discover -s tests` after installing `requirements-dev.txt`.
