#!/usr/bin/env bash

# Install the Aggregare default operating-system bundle through shared Ansible roles.
set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ANSIBLE_DIR="$PROJECT_ROOT/ansible"
INVENTORY_FILE="$ANSIBLE_DIR/inventory.ini"
VERSION_FILE="$PROJECT_ROOT/VERSION"
IDENTITY_CONFIG_FILE="/etc/aggregare/identity.json"
IDENTITY_PROVIDER=""
IDENTITY_PROVIDER_UPDATE=false
LLAMA_CPP_URL=""

while (($#)); do
  case "$1" in
    --identity-provider)
      (($# >= 2)) || { printf 'Installer stopped: --identity-provider needs kanidm, external_oidc, or none.\n' >&2; exit 2; }
      IDENTITY_PROVIDER="$2"
      IDENTITY_PROVIDER_UPDATE=true
      shift 2
      ;;
    --llama-cpp-url)
      (($# >= 2)) || { printf 'Installer stopped: --llama-cpp-url needs an http:// or https:// OpenAI-compatible server base URL.\n' >&2; exit 2; }
      LLAMA_CPP_URL="$2"
      shift 2
      ;;
    --help|-h)
      printf 'Usage: ./install.sh [--identity-provider kanidm|external_oidc|none] [--llama-cpp-url URL]\n'
      exit 0
      ;;
    *) printf 'Installer stopped: unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

fail() {
  printf 'Installer stopped: %s\n' "$*" >&2
  exit 1
}

case "$IDENTITY_PROVIDER" in
  ""|kanidm|external_oidc|none) ;;
  *) printf 'Installer stopped: invalid identity provider "%s"; choose kanidm, external_oidc, or none.\n' "$IDENTITY_PROVIDER" >&2; exit 2 ;;
esac

ask_yes_no() {
  local answer
  while true; do
    read -r -p "${1:-Should the user-facing applications be reachable by other devices on your private LAN? [y/N] }" answer
    case "${answer,,}" in
      y|yes) return 0 ;;
      ''|n|no) return 1 ;;
      *) printf 'Please type y or n.\n' ;;
    esac
  done
}

select_identity_provider() {
  local saved_provider=""
  if [[ -r "$IDENTITY_CONFIG_FILE" ]]; then
    saved_provider="$(python3 "$PROJECT_ROOT/tools/aggregare-identity-config" get-provider "$IDENTITY_CONFIG_FILE")" || fail "saved identity configuration is invalid; review $IDENTITY_CONFIG_FILE."
  fi
  if [[ -z "$IDENTITY_PROVIDER" && -n "$saved_provider" ]]; then
    IDENTITY_PROVIDER="$saved_provider"
    printf 'Using saved identity provider selection: %s\n' "$IDENTITY_PROVIDER"
  elif [[ -z "$IDENTITY_PROVIDER" ]]; then
    [[ -t 0 ]] || fail "identity provider selection is required in noninteractive mode; use --identity-provider kanidm, external_oidc, or none."
    printf 'Select the identity provider configuration (this does not install an identity service):\n'
    printf '  1) kanidm\n  2) external_oidc\n  3) none\n'
    local choice
    read -r -p 'Selection [3]: ' choice
    case "${choice:-3}" in
      1|kanidm) IDENTITY_PROVIDER=kanidm ;;
      2|external_oidc) IDENTITY_PROVIDER=external_oidc ;;
      3|none) IDENTITY_PROVIDER=none ;;
      *) fail "invalid identity provider selection '$choice'; choose kanidm, external_oidc, or none." ;;
    esac
  fi
  case "$IDENTITY_PROVIDER" in kanidm|external_oidc|none) ;; *) fail "invalid identity provider '$IDENTITY_PROVIDER'; choose kanidm, external_oidc, or none." ;; esac
}

select_llama_cpp_endpoint() {
  local saved_url="" candidate="" probe_output="" probe_status=0 normalized_url=""
  local config_file=/etc/aggregare/ysparr-upstream.json

  if sudo test -r "$config_file"; then
    saved_url="$(sudo python3 - "$config_file" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as config_file:
        print(json.load(config_file).get("ysparr_upstream_base_url", ""))
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)
PY
    )" || fail "the saved Ysparr upstream configuration is invalid; review $config_file."
  fi

  if [[ -n "$LLAMA_CPP_URL" ]]; then
    candidate="$LLAMA_CPP_URL"
  else
    [[ -t 0 ]] || {
      [[ -n "$saved_url" ]] && { LLAMA_CPP_URL="$saved_url"; return 0; }
      fail "a reachable external llama.cpp endpoint is required in noninteractive mode; pass --llama-cpp-url URL or set ysparr_upstream_base_url in inventory."
    }
    printf '\nConnect AI chat to an OpenAI-compatible llama.cpp server.\n'
    printf 'Enter its base URL as seen from this Aggregare server (for example http://192.168.1.20:8080). A trailing /v1 is accepted.\n'
    while true; do
      read -r -p "llama.cpp server URL${saved_url:+ [$saved_url]}: " candidate
      candidate="${candidate:-$saved_url}"
      [[ -n "$candidate" ]] || { printf 'Enter the reachable server URL.\n'; continue; }
      probe_output="$("$PROJECT_ROOT/tools/aggregare-llama-endpoint" "$candidate" 2>&1)" || probe_status=$?
      if ((probe_status == 0 || probe_status == 3)); then
        printf '%s\n' "$probe_output"
        normalized_url="$(awk '/^Using Ysparr upstream base URL:/ { sub(/^Using Ysparr upstream base URL: /, ""); print; exit }' <<<"$probe_output")"
        [[ -n "$normalized_url" ]] || fail "could not normalize the selected llama.cpp endpoint."
        LLAMA_CPP_URL="$normalized_url"
        return 0
      fi
      printf '%s\n' "$probe_output" >&2
      probe_status=0
    done
  fi

  probe_status=0
  probe_output="$("$PROJECT_ROOT/tools/aggregare-llama-endpoint" "$candidate" 2>&1)" || probe_status=$?
  if ((probe_status != 0 && probe_status != 3)); then
    printf '%s\n' "$probe_output" >&2
    fail "the provided llama.cpp endpoint did not pass validation."
  fi
  printf '%s\n' "$probe_output"
  LLAMA_CPP_URL="$(awk '/^Using Ysparr upstream base URL:/ { sub(/^Using Ysparr upstream base URL: /, ""); print; exit }' <<<"$probe_output")"
  [[ -n "$LLAMA_CPP_URL" ]] || fail "could not normalize the selected llama.cpp endpoint."
}

confirm_host_time() {
  local timezone current_timezone ntp_synchronized

  command -v timedatectl >/dev/null 2>&1 || fail "timedatectl is required to confirm the host timezone and network time synchronization."
  current_timezone="$(timedatectl show --property=Timezone --value)" || fail "could not read the host timezone."

  while true; do
    printf '\nHost time settings:\n'
    date '+  Local: %Y-%m-%d %H:%M:%S %Z (%z)'
    date -u '+  UTC:   %Y-%m-%d %H:%M:%S UTC'
    printf '  Timezone: %s\n' "$current_timezone"
    timedatectl status | sed -n '/System clock synchronized:/p; /NTP service:/p'

    if ask_yes_no 'Is the host date, time, and timezone correct? [y/N] '; then
      ntp_synchronized="$(timedatectl show --property=NTPSynchronized --value)" || fail "could not read the host clock synchronization status."
      [[ "$ntp_synchronized" == yes ]] || fail "the system clock is not synchronized. Enable and verify network time synchronization, then rerun install.sh. Check with: timedatectl status"
      return 0
    fi

    read -r -p "Enter the correct IANA timezone [$current_timezone]: " timezone
    timezone="${timezone:-$current_timezone}"
    if ! timedatectl list-timezones | grep -Fxq -- "$timezone"; then
      printf 'Unknown timezone: %s. Enter a name such as America/Phoenix.\n' "$timezone" >&2
      continue
    fi
    if [[ "$timezone" != "$current_timezone" ]]; then
      sudo timedatectl set-timezone "$timezone" || fail "could not set the host timezone to $timezone."
      current_timezone="$timezone"
    fi
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
confirm_host_time
select_identity_provider
select_llama_cpp_endpoint

printf '\nAggregare Server v%s bootstrap\n' "$AGGREGARE_VERSION"
printf 'The default operating-system bundle includes AI chat, Memos, HabitSync, Vikunja, and OpenIPE.\n\n'

PACKAGES_TO_INSTALL=()
if ! command -v ansible-playbook >/dev/null 2>&1; then
  PACKAGES_TO_INSTALL+=(ansible-core)
fi
if ! dpkg-query -W -f='${Status}' openssh-server 2>/dev/null | grep -q 'install ok installed'; then
  PACKAGES_TO_INSTALL+=(openssh-server)
fi

if ((${#PACKAGES_TO_INSTALL[@]} > 0)); then
  printf 'I will install the server packages: %s\n' "${PACKAGES_TO_INSTALL[*]}"
  sudo apt update
  sudo apt install -y "${PACKAGES_TO_INSTALL[@]}"
fi
command -v ansible-playbook >/dev/null 2>&1 || fail "Ansible Core could not be installed."
sudo systemctl enable --now ssh

SSH_LAN_ADDRESS=""
SSH_LAN_SUBNET=""
if detect_lan_address; then
  SSH_LAN_ADDRESS="$LAN_ADDRESS"
  SSH_LAN_SUBNET="$LAN_SUBNET"
  if command -v ufw >/dev/null 2>&1 && sudo ufw status 2>/dev/null | grep -q '^Status: active$'; then
    sudo ufw allow from "$SSH_LAN_SUBNET" to "$SSH_LAN_ADDRESS" port 22 proto tcp comment 'Aggregare SSH from private LAN'
  fi
fi

printf '\nOpenSSH is installed and running. Connect from another computer with:\n'
if [[ -n "$SSH_LAN_ADDRESS" ]]; then
  printf 'ssh %s@%s\n' "$(id -un)" "$SSH_LAN_ADDRESS"
else
  printf 'I could not detect a private LAN address; check the server network before connecting.\n'
fi

LAN_ACCESS=false
LAN_ADDRESS=127.0.0.1
LAN_SUBNET=""
if ask_yes_no 'Should the user-facing applications be reachable by other devices on your private LAN? [y/N] '; then
  detect_lan_address || fail "I could not find a private IPv4 address on the default network interface. Configure the server's private LAN network and try again, or choose no."
  LAN_ACCESS=true
  printf 'User-facing applications will bind to %s (network %s).\n' "$LAN_ADDRESS" "$LAN_SUBNET"
else
  printf 'User-facing applications will listen only on this server.\n'
fi

if [[ -e "$INVENTORY_FILE" ]]; then
  expected_inventory="$(printf '[aggregare]\nlocalhost ansible_connection=local\n')"
  existing_inventory="$(cat "$INVENTORY_FILE")"
  [[ "$existing_inventory" == "$expected_inventory" ]] || fail "ansible/inventory.ini already contains custom settings. I left it untouched; run the default playbook directly with your inventory."
else
  cat > "$INVENTORY_FILE" <<'EOF'
[aggregare]
localhost ansible_connection=local
EOF
fi

BOOTSTRAP_EXTRA_VARS="$(python3 - "$LAN_ADDRESS" "$IDENTITY_PROVIDER" "$LLAMA_CPP_URL" <<'PY'
import json
import sys

print(json.dumps({
    "application_bind_address": sys.argv[1],
    "habitsync_bind_address": sys.argv[1],
    "memos_base_url": f"http://{sys.argv[1]}:5230",
    "habitsync_base_url": f"http://{sys.argv[1]}:6842",
    "vikunja_base_url": f"http://{sys.argv[1]}:3456",
    "aggregare_identity_provider": sys.argv[2],
    "ysparr_upstream_base_url": sys.argv[3],
    "ansible_become": False,
}))
PY
)"

WELCOME_EXTRA_VARS="$(python3 - "$AGGREGARE_VERSION" "$PROJECT_ROOT/docs/deployment/aggregare-server.md" <<'PY'
import json
import sys

print(json.dumps({
    "ansible_become": False,
    "aggregare_version": sys.argv[1],
    "aggregare_docs_path": sys.argv[2],
}))
PY
)"

ANSIBLE_VAULT_ARGS=()
VAULT_VARS_FILE="$ANSIBLE_DIR/group_vars/aggregare/vault.yml"
if [[ -f "$VAULT_VARS_FILE" ]] && grep -q '^\$ANSIBLE_VAULT;' "$VAULT_VARS_FILE"; then
  ANSIBLE_VAULT_ARGS+=(--ask-vault-pass)
fi

cd "$ANSIBLE_DIR"
sudo "$(command -v ansible-playbook)" -i inventory.ini playbooks/phase25-identity-config.yml \
  --extra-vars "{\"aggregare_identity_provider\":\"$IDENTITY_PROVIDER\",\"aggregare_identity_provider_update\":$IDENTITY_PROVIDER_UPDATE}"
sudo "$(command -v ansible-playbook)" -i inventory.ini playbooks/default.yml \
  --extra-vars "$BOOTSTRAP_EXTRA_VARS" "${ANSIBLE_VAULT_ARGS[@]}"
sudo "$(command -v ansible-playbook)" -i inventory.ini playbooks/welcome.yml \
  --extra-vars "$WELCOME_EXTRA_VARS"

printf '\nAggregare default application bundle installation finished.\n'
printf 'The Aggregare login banner is installed; log out and back in to see it.\n'
if [[ "$LAN_ACCESS" == true ]]; then
  printf 'User-facing applications on the LAN:\n'
  printf '  Open WebUI: http://%s:8080/\n  Memos:      http://%s:5230/\n  HabitSync:  http://%s:6842/\n  Vikunja:    http://%s:3456/\n' "$LAN_ADDRESS" "$LAN_ADDRESS" "$LAN_ADDRESS" "$LAN_ADDRESS"
  printf 'If UFW blocks LAN connections, add this LAN-scoped rule:\n'
  for port in 8080 5230 6842 3456; do
    printf 'sudo ufw allow from %s to %s port %s proto tcp\n' "$LAN_SUBNET" "$LAN_ADDRESS" "$port"
  done
  printf 'Do not configure router port forwarding for this application.\n'
else
  printf 'User-facing applications on this server:\n'
  printf '  Open WebUI: http://127.0.0.1:8080/\n  Memos:      http://127.0.0.1:5230/\n  HabitSync:  http://127.0.0.1:6842/\n  Vikunja:    http://127.0.0.1:3456/\n'
fi
printf 'Ysparr API: http://127.0.0.1:8000/v1. Apmatia core API: http://127.0.0.1:8001 (loopback only).\n'
printf 'Open WebUI sign-up remains enabled for first use: create the first administrator account in the browser, then immediately disable sign-up in Admin Panel > Settings. Until then, allow access only from trusted clients.\n'
printf 'Open WebUI is preconfigured to use Ysparr only. If models do not appear immediately, reopen the model selector or save the Ysparr connection in Admin Panel > Settings > Connections, then refresh the page.\n'
printf 'On a fresh install, Apmatia first-user credentials are stored root-only at /etc/aggregare/apmatia-credentials.json; retrieve with sudo cat and keep a protected backup.\n'
printf 'Apmatia publishes its five starter agents to Ysparr during fresh first-user setup. Ysparr continues to serve real upstream models if Apmatia is temporarily unavailable.\n'
printf 'For a redacted AI-chat status report, run: sudo ./tools/aggregare-ai-chat-diagnose\n'
printf 'Lifecycle, network, backup/restore, and VM smoke-check steps: docs/deployment/aggregare-ai-chat-operations.md\n'
printf 'HabitSync local login is stored root-only at /etc/aggregare/habitsync-credentials; retrieve it with sudo cat and rotate it after first sign-in.\n'
printf 'AI chat upstream: %s (checked at /v1/models). Reapply the default playbook to update it; the value is saved in /etc/aggregare/ysparr-upstream.json.\n' "$LLAMA_CPP_URL"
