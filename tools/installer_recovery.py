Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
#!/usr/bin/env python3
"""Live health checks used before the installer skips a completed application."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable


def _http_is_healthy(url: str, opener: Callable = urllib.request.urlopen) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    try:
        with opener(url, timeout=5) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError, TimeoutError, ValueError):
        return False


def application_is_complete(
    application_id: str,
    expected_version: str,
    *,
    status_dir: Path = Path("/var/lib/aggregare/status"),
    runner: Callable = subprocess.run,
    opener: Callable = urllib.request.urlopen,
    python_root: Path = Path("/opt/aggregare/venvs"),
) -> bool:
    """Return true only when saved metadata and current application health agree."""
    try:
        status = json.loads((status_dir / f"{application_id}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    if not (
        status.get("application_id") == application_id
        and status.get("version") == expected_version
        and status.get("state") in {"running", "installed"}
        and status.get("upstream_onboarding_pending") is not True
        and status.get("verification", {}).get("status") == "passed"
    ):
        return False

    deployment = status.get("deployment", {})
    service = deployment.get("service")
    if service:
        if runner(["systemctl", "is-active", "--quiet", service], check=False).returncode != 0:
            return False
        endpoint = status.get("verification", {}).get("endpoint")
        return bool(endpoint) and _http_is_healthy(endpoint, opener)

    # OpenIPE is an installed Python library, not a daemon. Its status record
    # deliberately has no unit or HTTP endpoint, so check the package itself.
    if application_id != "openipe" or deployment.get("method") != "native-python":
        return False
    check = status.get("verification", {}).get("check", "")
    match = re.fullmatch(r"import ([A-Za-z_][A-Za-z0-9_.]*)", check)
    if not match:
        return False
    executable = python_root / application_id / "bin" / "python"
    return runner([str(executable), "-c", f"import {match.group(1)}"], check=False).returncode == 0


def application_should_be_skipped(
    completed: str,
    saved_signature: str,
    current_signature: str,
    application_id: str,
    expected_version: str,
    **health_options,
) -> bool:
    return (
        completed == "true"
        and saved_signature == current_signature
        and application_is_complete(application_id, expected_version, **health_options)
    )


if __name__ == "__main__":
    if len(sys.argv) == 3:
        healthy = application_is_complete(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 7 and sys.argv[1] == "should-skip":
        _, _, completed, saved_signature, current_signature, application_id, expected_version = sys.argv
        healthy = application_should_be_skipped(
            completed, saved_signature, current_signature, application_id, expected_version
        )
    else:
        raise SystemExit(
            "usage: installer_recovery.py APPLICATION_ID EXPECTED_VERSION | "
            "should-skip COMPLETED SAVED_SIGNATURE CURRENT_SIGNATURE APPLICATION_ID EXPECTED_VERSION"
        )
    raise SystemExit(0 if healthy else 1)
