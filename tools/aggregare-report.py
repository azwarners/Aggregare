#!/usr/bin/env python3
"""Build and display the Aggregare deployment handoff report."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit

REPORT_PATH = Path(os.environ.get("AGGREGARE_REPORT_PATH", "/var/lib/aggregare/deployment-report.md"))
STATUS_PATH = Path("/var/lib/aggregare/status")
CATALOG_PATH = Path("/usr/local/share/aggregare/catalog/v1")
HABITSYNC_PASSWORD_ROTATED_MARKER = Path("/etc/aggregare/habitsync-password-rotated")
LOCAL_CREDENTIAL_FORMATS = {
    "/etc/aggregare/apmatia-credentials.json": "json",
    "/etc/aggregare/habitsync-credentials": "key_value",
}


def safe_url(value: str) -> str:
    """Strip URL userinfo and query/fragment data before rendering."""
    if not isinstance(value, str):
        return ""
    try:
        parts = urlsplit(value)
        if not parts.scheme or not parts.hostname:
            return ""
        host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
        if parts.port:
            host += f":{parts.port}"
        path = parts.path or "/"
        if re.search(r"password|token|secret|api[-_]?key|credential", path, re.I):
            path = "/"
        return urlunsplit((parts.scheme, host, path, "", ""))
    except ValueError:
        return ""


def service_state(unit: str) -> str:
    try:
        result = subprocess.run(
            ["systemctl", "show", unit, "--property=LoadState", "--property=ActiveState", "--value"],
            capture_output=True, text=True, check=False, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    values = result.stdout.splitlines()
    if result.returncode != 0 or len(values) < 2 or values[0] == "not-found":
        return "not installed"
    return values[1] or "unknown"


def load_json(path: Path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def load_initial_credentials(reference: str) -> dict[str, str] | None:
    """Read only Aggregare's known, root-only generated login files."""
    file_format = LOCAL_CREDENTIAL_FORMATS.get(reference)
    if not file_format:
        return None
    path = Path(reference)
    try:
        metadata = path.stat()
        if path.is_symlink() or not path.is_file() or metadata.st_uid != 0 or metadata.st_mode & 0o077:
            return None
        if file_format == "json":
            values = json.loads(path.read_text(encoding="utf-8"))
        else:
            values = {}
            for line in path.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                if separator and key in {"username", "password"}:
                    values[key] = value
        if not isinstance(values, dict):
            return None
        credentials = {key: values[key] for key in ("username", "password") if isinstance(values.get(key), str) and values[key]}
        return credentials if set(credentials) == {"username", "password"} else None
    except (OSError, json.JSONDecodeError):
        return None


def render_report(catalog_dir: Path, status_dir: Path, *, hostname: str,
                  addresses: list[str], version: str, bind_address: str = "",
                  loopback_apps: set[str] | None = None,
                  expected_apps: set[str] | None = None,
                  failed_apps: set[str] | None = None, observed_services: dict[str, str] | None = None,
                  generated_at: datetime | None = None) -> str:
    expected_apps = expected_apps or set()
    loopback_apps = loopback_apps or {"ysparr", "apmatia"}
    failed_apps = failed_apps or set()
    observed_services = observed_services or {}
    index = load_json(catalog_dir / "index.json") or {}
    apps = []
    units = set()
    refs = index.get("applications", []) if isinstance(index, dict) else []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        entry = load_json(catalog_dir / ref.get("path", ""))
        if not entry:
            continue
        status = load_json(status_dir / f"{entry.get('id', '')}.json")
        services = entry.get("services", [])
        if not isinstance(services, list):
            services = []
        app_units = [service.get("name") for service in services if service.get("name")]
        states = {unit: observed_services[unit] if unit in observed_services else service_state(unit) for unit in app_units}
        has_unit = any(value != "not installed" for value in states.values())
        app_id = entry.get("id", "")
        app_bind_address = "127.0.0.1" if app_id in loopback_apps else bind_address
        if not status and not has_unit and app_id not in failed_apps and app_id not in expected_apps:
            continue
        units.update(unit for unit, state in states.items() if state != "not installed")
        apps.append((entry, status, states))

    now = generated_at or datetime.now(timezone.utc)
    lines = [
        "# Aggregare deployment report", "",
        f"- Host: {hostname or 'unknown'}",
        f"- Host addresses: {', '.join(addresses) if addresses else 'unknown'}",
        f"- Generated: {now.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"- Aggregare version: {version or 'unknown'}", "",
        "## Applications", "",
    ]
    if not apps:
        lines.append("No installed Aggregare applications could be verified.")
    for entry, status, states in sorted(apps, key=lambda item: item[0].get("display_name", item[0].get("id", "" )).casefold()):
        app_id = entry.get("id", "unknown")
        name = entry.get("display_name", app_id)
        state = status.get("state", "unknown") if status else "unknown"
        verification_data = status.get("verification") if status and isinstance(status.get("verification"), dict) else {}
        verification = verification_data.get("status", "unknown")
        if app_id in failed_apps:
            state_label = "Failed during this installer run; current install state is unverified"
        elif status:
            state_label = f"Recorded state: {state}; last recorded check: {verification}"
        elif has_unit:
            state_label = "Installed service detected; application status is unverified"
        elif app_id in expected_apps:
            state_label = "Not detected; the application may be disabled, skipped, or not installed"
        else:
            state_label = "Installed service detected; application status is unverified"
        lines.extend([f"### {name}", "", f"- Status: {state_label}"])
        ports = [port for service in entry.get("services", []) for port in service.get("ports", [])]
        endpoint = ""
        if app_id not in failed_apps and has_unit and ports and app_bind_address:
            endpoint = f"http://{app_bind_address}:{ports[0]}/"
        elif app_id not in failed_apps and status:
            endpoint = safe_url(verification_data.get("endpoint", ""))
        if endpoint:
            source = "Configured endpoint" if ports and app_bind_address else "Endpoint recorded by last application check"
            if ports and app_bind_address:
                exposure = "local-only binding" if app_bind_address in {"127.0.0.1", "::1", "localhost"} else "remote reachability not verified"
            else:
                exposure = "current reachability not verified"
            lines.append(f"- {source}: {endpoint} ({exposure})")
        else:
            lines.append("- Configured endpoint: unknown or unavailable")
        for unit, unit_state in sorted(states.items()):
            lines.append(f"- Service: `{unit}` ({unit_state})")
        if not services:
            lines.append("- Service metadata is unavailable for this application")
        auth = entry.get("authentication", {})
        bootstrap = auth.get("bootstrap", {}) if isinstance(auth, dict) else {}
        if isinstance(bootstrap, dict):
            notes = bootstrap.get("notes")
            if isinstance(notes, str) and notes:
                lines.append(f"- Access setup: {notes}")
            credential_reference = bootstrap.get("credential_reference", "")
            if isinstance(credential_reference, str) and credential_reference:
                if credential_reference.startswith("ansible-vault:"):
                    variable = credential_reference.removeprefix("ansible-vault:")
                    lines.append(f"- Admin password source: Ansible Vault variable `{variable}` in `ansible/group_vars/aggregare/vault.yml`.")
                else:
                    credentials = None if (
                        credential_reference == "/etc/aggregare/habitsync-credentials"
                        and HABITSYNC_PASSWORD_ROTATED_MARKER.exists()
                    ) else load_initial_credentials(credential_reference)
                    if credentials:
                        lines.append(f"- Initial login username: `{credentials['username']}`")
                        lines.append(f"- Initial login password: `{credentials['password']}`")
                    else:
                        lines.append("- Initial login details: unavailable in this report; use the application's password recovery or change process.")
        for step in auth.get("manual_steps", []):
            if isinstance(step, str) and step:
                lines.append(f"- First-run / manual step: {step}")
        lines.append("")

    lines.extend(["## Aggregare-managed systemd services", ""])
    if units:
        for unit in sorted(units):
            lines.extend([f"- `{unit}`", f"  - `sudo systemctl status {unit}`", f"  - `sudo journalctl -u {unit} -n 100 --no-pager`"])
    else:
        lines.append("No Aggregare-managed services were detected.")
    lines.extend([
        "", "## Management and logs", "",
        "- Reapply from an Aggregare checkout with `./install.sh`.",
        "- Aggregare configuration directory: `/etc/aggregare` (may contain secrets; keep protected).",
        "- Application status records: `/var/lib/aggregare/status`.",
        "- Service logs: use the `journalctl` examples above.",
        "- This report may contain initial application credentials and is restricted to its designated administrator; keep copies and backups protected.",
        "", "This report lists configured endpoints and observed local service state. It does not establish remote reachability.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("report", help="print the current deployment report")
    sub.add_parser("summary", help="print a concise application summary")
    generate = sub.add_parser("generate", help="generate the persistent deployment report")
    generate.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    generate.add_argument("--status-dir", type=Path, default=STATUS_PATH)
    generate.add_argument("--output", type=Path, default=REPORT_PATH)
    generate.add_argument("--hostname", default="")
    generate.add_argument("--addresses", default="")
    generate.add_argument("--version", default="")
    generate.add_argument("--bind-address", default="")
    generate.add_argument("--loopback-apps", default="ysparr,apmatia")
    generate.add_argument("--expected-apps", default="")
    generate.add_argument("--failed-apps", default="")
    args = parser.parse_args()
    if args.command in {"report", "summary"}:
        try:
            content = REPORT_PATH.read_text(encoding="utf-8")
        except OSError as error:
            print(f"Could not read {REPORT_PATH}: {error}", file=sys.stderr)
            return 1
        if args.command == "report":
            sys.stdout.write(content)
        else:
            print("Applications:")
            in_apps = False
            current_name = None
            current_status = "status unknown"
            current_endpoint = "endpoint unknown"
            for line in content.splitlines():
                if line == "## Applications":
                    in_apps = True
                    continue
                if in_apps and line.startswith("## "):
                    break
                if not in_apps:
                    continue
                if line.startswith("### "):
                    if current_name is not None:
                        print(f"- {current_name}: {current_status}; {current_endpoint}")
                    current_name = line[4:]
                    current_status = "status unknown"
                    current_endpoint = "endpoint unknown"
                elif line.startswith("- Status: "):
                    current_status = line.removeprefix("- Status: ")
                elif line.startswith("- Configured endpoint: ") or line.startswith("- Endpoint recorded by last application check: "):
                    current_endpoint = line.removeprefix("- ")
            if current_name is not None:
                print(f"- {current_name}: {current_status}; {current_endpoint}")
        return 0
    content = render_report(
        args.catalog, args.status_dir, hostname=args.hostname, addresses=[x for x in args.addresses.split(",") if x],
        version=args.version, bind_address=args.bind_address,
        loopback_apps={x for x in args.loopback_apps.split(",") if x},
        expected_apps={x for x in args.expected_apps.split(",") if x},
        failed_apps={x for x in args.failed_apps.split(",") if x},
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=args.output.parent,
            prefix=f".{args.output.name}.", delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
        temporary_path.replace(args.output)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    print(f"Generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
