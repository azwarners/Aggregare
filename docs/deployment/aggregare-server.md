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
- A terminal on the server for the first install (for example, the VM console). Aggregare sets up SSH for later remote access.
- A normal Ubuntu user account that can run `sudo` commands.
- A few gigabytes of free disk space for Memos and its container.
- Git to clone the Aggregare repository. If needed, install it from the VM console with `sudo apt update && sudo apt install -y git`.

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

During installation, Aggregare displays the server's local time, UTC time,
timezone, and network time synchronization status. Confirm that they are
correct before application deployment. If the timezone is wrong, enter its
IANA name (for example, `America/Phoenix`); the installer applies it and asks
you to confirm again. Installation stops if the system clock is not synchronized.
On Ubuntu, inspect or enable time synchronization with `timedatectl status` and
`sudo timedatectl set-ntp true`, then rerun the installer. Aggregare's managed
Podman containers use the host timezone.

The script checks for Ubuntu 26.04, installs Ansible Core and OpenSSH Server
if needed, starts SSH, and runs the Memos playbook locally on this same server
using a localhost inventory. A separate control machine or SSH connection is
not needed for this first install. If UFW is already active, the installer
allows SSH only from the server's private LAN subnet; it does not enable UFW.
The script prints an SSH command for later terminal access from another
computer. It asks whether Memos should be reachable by other devices on your
private LAN, then applies the playbook with administrator access. Type your
normal Ubuntu `sudo` password when the installer asks. The script does not
install Git as a setup step.

For later terminal access, run the printed `ssh username@address` command from
a computer that can reach the VM. If the VM uses NAT, a bridged virtual network
adapter may be needed for direct LAN access.

The first run installs Podman because the Memos playbook deploys Memos as a
container. Podman is an optional deployment tool for selected applications,
not a requirement of the catalog or Ansible foundation.

When the playbook finishes, check the service and its verification record:

```sh
sudo systemctl status memos.service --no-pager
curl --fail --silent --show-error http://127.0.0.1:5230/
sudo cat /var/lib/aggregare/status/memos.json
```

The service status should say `active`; the status record should report a
passed verification. If you chose LAN access, use the LAN address printed by
the installer instead of `127.0.0.1` in the `curl` command.

## LAN access

If you answer no, Memos listens only on the server's loopback address. It is
not directly reachable from another computer.

If you answer yes, the script binds Memos to a private IPv4 address on the
server's default network interface. It prints the address to open, for example
`http://192.168.1.25:5230/`. If UFW is active, the installer adds a separate
SSH rule scoped to the server's private LAN subnet; it leaves other rules
unchanged and does not enable a firewall. If UFW blocks Memos connections, the
script prints a LAN-scoped rule for port 5230. It does not configure router
port forwarding.

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
