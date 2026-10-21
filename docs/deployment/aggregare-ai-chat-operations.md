# Aggregare AI chat operations

This note covers service lifecycle, local network boundaries, backup and
restore, diagnostics, and VM checks for the default Open WebUI, Ysparr, and
Apmatia deployment.

## Lifecycle and network

Open WebUI is ordered after and wants `ysparr.service`, so systemd starts the
relay first during boot and restarts. The dependency is soft: Open WebUI can
still start if Ysparr fails. Apmatia is independently managed; its absence does
not prevent Ysparr from serving upstream models. An unavailable Apmatia means
its virtual agents are temporarily missing until the service and published
catalog return.

The default local endpoints are:

| Service | URL | Exposure |
| --- | --- | --- |
| Open WebUI | `http://127.0.0.1:8080/` | User-facing bind follows the installer's loopback/LAN choice |
| Ysparr OpenAI API | `http://127.0.0.1:8000/v1` | Loopback only |
| Apmatia core API | `http://127.0.0.1:8001` | Loopback only |
| llama.cpp upstream | The configured `HOST:PORT` | External endpoint; supplied by you |

Aggregare does not configure router port forwarding. Do not expose Ysparr or
Apmatia control APIs on a public interface. If you choose LAN access, only the
user-facing Open WebUI listener is opened according to the installer and local
firewall configuration. Ansible checks catalogued ports before starting a
service that is not already active. This is a preflight check, not an atomic
reservation, so check manually before changing ports or applying concurrent
deployments:

```sh
sudo ss -ltnp
```

Default user-facing ports for the full productivity bundle are 8080 (Open
WebUI), 5230 (Memos), 6842 (HabitSync), and 3456 (Vikunja). Ysparr and Apmatia
use loopback ports 8000 and 8001. The optional llama.cpp role defaults to port
8080, so do not install it on the same host with its default port while Open
WebUI is using 8080; assign a distinct port and verify it is free.

## Redacted diagnostic

Run this on the Aggregare server from the checkout:

```sh
sudo ./tools/aggregare-ai-chat-diagnose
sudo ./tools/aggregare-ai-chat-diagnose --json
```

It reports configured provider targets, systemd enabled/running state,
reachability, the upstream API authentication result, model counts, published
agents, and the browser end-to-end check as not tested. It never prints
endpoint URLs, API keys, or login credentials. Run it with `sudo` so it can read
the protected upstream configuration. An overall `partial` result is expected if Apmatia is
temporarily unavailable; the report still shows whether upstream models remain
available through Ysparr. An Open WebUI connection saved in its database must
still be checked in **Admin Panel → Settings → Connections**.

## Backup and restore

Service removal and routine reapplication preserve application data. Keep
protected backups of these paths:

- Open WebUI: `/var/lib/aggregare/open-webui/`
- Ysparr model/agent state: `/var/lib/ysparr/`
- Apmatia state: `/var/lib/apmatia/app/`, `/var/lib/apmatia/data/`, and
  `/var/lib/apmatia/config/`
- Protected configuration and credentials: `/etc/aggregare/ysparr-upstream.json`,
  `/etc/aggregare/ysparr.env`, `/etc/aggregare/apmatia-credentials.json`, and
  `/etc/aggregare/apmatia-bootstrap-state.json`
- Open WebUI service definition: `/etc/containers/systemd/open-webui.container`

The config files and archive contain credentials or keys. Store the archive
root-only and copy it to protected backup storage. To make a consistent archive,
stop the three services while copying SQLite and application data; this command
restarts them even if the archive step fails:

```sh
sudo bash <<'ROOT'
set -Eeuo pipefail
services=(ysparr.service apmatia-core.service open-webui.service)
backup_dir=/var/backups/aggregare-ai-chat
archive="$backup_dir/$(date +%Y%m%d-%H%M%S).tar.gz"
install -d -m 0700 "$backup_dir"
restart_services() { systemctl start "${services[@]}"; }
trap restart_services EXIT
systemctl stop "${services[@]}"
umask 077
paths=(var/lib/aggregare/open-webui var/lib/ysparr
  var/lib/apmatia/app var/lib/apmatia/data var/lib/apmatia/config
  etc/aggregare/ysparr-upstream.json etc/aggregare/ysparr.env
  etc/containers/systemd/open-webui.container)
for optional in etc/aggregare/apmatia-credentials.json etc/aggregare/apmatia-bootstrap-state.json; do
  [[ ! -e "/$optional" ]] || paths+=("$optional")
done
tar --xattrs --acls --numeric-owner -czf "$archive" -C / "${paths[@]}"
chmod 0600 "$archive"
printf 'Protected backup created: %s\n' "$archive"
ROOT
```

To restore, use a trusted archive on the intended server. This overwrites the
matching paths with the archived state. Stop the services first, extract as
root so numeric owners and modes are restored, reload systemd, and start the
stack:

```sh
sudo systemctl stop ysparr.service apmatia-core.service open-webui.service
sudo tar --xattrs --acls --numeric-owner --same-owner --same-permissions \
  -xzf /var/backups/aggregare-ai-chat-YYYYMMDD-HHMMSS.tar.gz -C /
sudo systemctl daemon-reload
sudo systemctl start ysparr.service apmatia-core.service open-webui.service
```

## VM smoke checks

After installation and again after a reboot, run the diagnostic report above,
then check the service and API paths:

```sh
sudo systemctl is-active ysparr.service apmatia-core.service open-webui.service
curl --fail --silent --show-error http://127.0.0.1:8000/v1/models
curl --fail --silent --show-error http://127.0.0.1:8001/api/public/agents
curl --fail --silent --show-error http://127.0.0.1:8080/health
```

For an Apmatia outage recovery check, run `sudo systemctl stop apmatia-core.service`,
confirm `/v1/models` still contains at least the upstream model, then run
`sudo systemctl start apmatia-core.service` and confirm the published agents
return. Finish by signing in to Open WebUI, checking its Ysparr connection and
model selector, and sending a browser chat using both an upstream model and a
published starter. Reapply the default bundle from the checkout and confirm
data and chats remain:

```sh
cd "$HOME/Aggregare/ansible"
ansible-playbook -i inventory.ini playbooks/default.yml --become --ask-become-pass
```

Verify removal/reinstallation only on a disposable VM: removing a
service must leave its data paths listed above intact.

If a check fails, inspect:

```sh
sudo journalctl -u ysparr.service -u apmatia-core.service -u open-webui.service -b --no-pager
```

An empty model list usually means the external llama.cpp server is stopped, has
no model loaded, or its `/v1/models` route is not reachable from the Aggregare
host. If upstream models appear but Apmatia agents do not, check Apmatia's
public agent endpoint and its bootstrap credential/state files. If direct
Ysparr requests work but the browser model selector is empty, recheck the saved
connection in Open WebUI and reload the page.
