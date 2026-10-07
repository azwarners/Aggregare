# Install Aggregare on Ubuntu Server

Aggregare's Phase 2 foundation is a machine-readable application catalog and
Ansible automation. Aggregare is not one dashboard that replaces the
applications it installs.

This small bootstrap deploys **Memos** as one working example. It is not an
application selector or preset manager; those belong to the Phase 3 client.
Other applications can already be installed directly through their Ansible
playbooks.

## Before you begin

You need:

- A patched Ubuntu Server 26.04 machine with internet access.
- A terminal on the server, or an SSH connection to it.
- A normal Ubuntu user account that can run `sudo` commands.
- A few gigabytes of free disk space for Memos and its container.

Keep your VM backup. Memos data is stored under `/var/lib/aggregare/memos/`
and is preserved when its service is removed.

## Install the example application

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

The script checks for Ubuntu 26.04 and installs Ansible Core if needed. It asks
whether Memos should be reachable by other devices on your private LAN, then
runs the existing Memos Ansible playbook. Type your `sudo` password when
Ansible asks for it. The script does not install Git as a setup step.

The first run installs Podman because the Memos playbook deploys Memos as a
container. Podman is an optional deployment tool for selected applications,
not a requirement of the catalog or Ansible foundation.

When the playbook finishes, check the service and its verification record:

```sh
sudo systemctl status memos.service --no-pager
curl --fail --silent --show-error http://127.0.0.1:5230/api/v1/ping
sudo cat /var/lib/aggregare/status/memos.json
```

The service status should say `active`; the status record should report a
passed verification.

## LAN access

If you answer no, Memos listens only on the server's loopback address. It is
not directly reachable from another computer.

If you answer yes, the script binds Memos to a private IPv4 address on the
server's default network interface. It prints the address to open, for example
`http://192.168.1.25:5230/`. Existing firewall rules are left unchanged. If
UFW blocks LAN connections, the script prints a LAN-scoped rule for port 5230.
The script does not enable a firewall or configure router port forwarding.

For a VM, its network adapter must allow other devices on your LAN to reach
the VM. A NAT-only virtual network may hide it from the LAN; use a bridged
adapter if you want other LAN devices to connect. Do not forward application
ports from your router to the public internet.

## Install another application directly

Each application has a playbook in `ansible/playbooks/`. The bootstrap creates
`ansible/inventory.ini` for this local server and leaves it in place so you can
run additional playbooks. For example, to install Beszel:

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
  -e application_bind_address=192.168.1.25
```

Replace `192.168.1.25` with the server's private address. UFW rules, if needed,
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
- **Apmatia**, **OpenIPE**, and **Redless** are Python packages or command-line
  tools, not web dashboards.
- **TroubleShell** is a desktop application. **Ladcemas** and **Sidecaravan**
  do not yet have installable roles.

The Phase 3 client will build application selection and presets on top of this
catalog and shared automation. It can reuse the playbooks without moving
installation logic into another script.
