#!/usr/bin/env bash

# Phase 2 bootstrap: install one fixed example through the shared Ansible role.
# Application selection, presets, and previews belong to the Phase 3 client.
set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ANSIBLE_DIR="$PROJECT_ROOT/ansible"
INVENTORY_FILE="$ANSIBLE_DIR/inventory.ini"
VERSION_FILE="$PROJECT_ROOT/VERSION"

fail() {
  printf 'Installer stopped: %s\n' "$*" >&2
  exit 1
}

ask_yes_no() {
  local answer
  while true; do
    read -r -p 'Should Memos be reachable by other devices on your private LAN? [y/N] ' answer
    case "${answer,,}" in
      y|yes) return 0 ;;
      ''|n|no) return 1 ;;
      *) printf 'Please type y or n.\n' ;;
    esac
  done
}

detect_lan_address() {
  local interface cidr details
  interface="$(ip -4 route show default 2>/dev/null | awk 'NR == 1 { for (i = 1; i <= NF; i++) if ($i == "dev") { print $(i + 1); exit } }')"
  [[ -n "$interface" ]] || return 1
  cidr="$(ip -o -4 addr show dev "$interface" scope global 2>/dev/null | awk 'NR == 1 { print $4 }')"
  [[ -n "$cidr" ]] || return 1

  details="$(python3 - "$cidr" <<'PY'
import ipaddress
import sys

interface = ipaddress.ip_interface(sys.argv[1])
address = interface.ip
rfc1918 = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)
if not any(address in network for network in rfc1918):
    raise SystemExit(1)
print(address)
print(interface.network)
PY
)" || return 1

  LAN_ADDRESS="${details%%$'\n'*}"
  LAN_SUBNET="${details#*$'\n'}"
}

[[ "$EUID" -ne 0 ]] || fail "run this script as your normal Ubuntu user, without sudo. It will ask when elevated access is needed."
[[ -t 0 && -t 1 ]] || fail "this installer needs an interactive terminal."
[[ -d "$ANSIBLE_DIR/playbooks" ]] || fail "run install.sh from a complete Aggregare project checkout."
[[ -r "$VERSION_FILE" ]] || fail "the Aggregare VERSION file is missing."
AGGREGARE_VERSION="$(<"$VERSION_FILE")"
[[ "$AGGREGARE_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "VERSION must contain a semantic version such as 0.0.1."

if [[ ! -r /etc/os-release ]]; then
  fail "cannot identify this operating system."
fi
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == ubuntu && "${VERSION_ID:-}" == 26.04 ]] || fail "this bootstrap currently supports Ubuntu Server 26.04."
command -v python3 >/dev/null 2>&1 || fail "Python 3 is required by Ubuntu and was not found."
command -v ip >/dev/null 2>&1 || fail "the ip command is missing; install Ubuntu's iproute2 package first."

printf '\nAggregare Server v%s bootstrap\n' "$AGGREGARE_VERSION"
printf 'This installs Memos as one example application through its Ansible playbook.\n'
printf 'Other applications remain available through their direct Ansible playbooks.\n\n'

if ! command -v ansible-playbook >/dev/null 2>&1; then
  printf 'Ansible Core is missing. I will install it now.\n'
  sudo apt update
  sudo apt install -y ansible-core
fi
command -v ansible-playbook >/dev/null 2>&1 || fail "Ansible Core could not be installed."

LAN_ACCESS=false
LAN_ADDRESS=127.0.0.1
LAN_SUBNET=""
if ask_yes_no; then
  detect_lan_address || fail "I could not find a private IPv4 address on the default network interface. Configure the server's private LAN network and try again, or choose no."
  LAN_ACCESS=true
  printf 'Memos will bind to %s (network %s).\n' "$LAN_ADDRESS" "$LAN_SUBNET"
else
  printf 'Memos will listen only on this server.\n'
fi

if [[ -e "$INVENTORY_FILE" ]]; then
  expected_inventory="$(printf '[aggregare]\nlocalhost ansible_connection=local\n')"
  existing_inventory="$(cat "$INVENTORY_FILE")"
  [[ "$existing_inventory" == "$expected_inventory" ]] || fail "ansible/inventory.ini already contains custom settings. I left it untouched; run the Memos playbook directly with your inventory."
else
  cat > "$INVENTORY_FILE" <<'EOF'
[aggregare]
localhost ansible_connection=local
EOF
fi

EXTRA_VARS="$(python3 - "$LAN_ADDRESS" "$AGGREGARE_VERSION" "$PROJECT_ROOT/docs/deployment/aggregare-server.md" <<'PY'
import json
import sys

print(json.dumps({
    "application_bind_address": sys.argv[1],
    "ansible_become": False,
    "aggregare_version": sys.argv[2],
    "aggregare_docs_path": sys.argv[3],
}))
PY
)"

cd "$ANSIBLE_DIR"
sudo "$(command -v ansible-playbook)" -i inventory.ini playbooks/memos.yml \
  --extra-vars "$EXTRA_VARS"

printf '\nMemos installation finished. Its status record is /var/lib/aggregare/status/memos.json.\n'
printf 'The Aggregare login banner is installed; log out and back in to see it.\n'
if [[ "$LAN_ACCESS" == true ]]; then
  printf 'Open Memos on the LAN at http://%s:5230/\n' "$LAN_ADDRESS"
  printf 'If UFW blocks LAN connections, add this LAN-scoped rule:\n'
  printf 'sudo ufw allow from %s to %s port 5230 proto tcp\n' "$LAN_SUBNET" "$LAN_ADDRESS"
  printf 'Do not configure router port forwarding for this application.\n'
else
  printf 'Memos is local-only at http://127.0.0.1:5230/.\n'
fi
