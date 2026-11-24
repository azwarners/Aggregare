#!/usr/bin/env python3
"""Controlled GitHub App reads for Redless.

This program intentionally never writes an installation token to disk or stdout.
It is installed root-owned and invoked through a narrowly scoped sudo rule.
"""
from __future__ import annotations

import base64
import json
import os
import re
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = Path("/etc/aggregare/redless-github-app.json")
KEY = Path("/etc/aggregare/secrets/redless-github-app.pem")
API = "https://api.github.com"
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class AppError(RuntimeError):
    pass


def private_file(path: Path) -> None:
    try:
        details = path.stat()
    except FileNotFoundError as error:
        raise AppError(f"GitHub App is not configured: missing {path}") from error
    if details.st_uid != 0 or stat.S_IMODE(details.st_mode) & 0o077:
        raise AppError(f"refusing insecure GitHub App file: {path}")


def config() -> dict:
    private_file(CONFIG)
    private_file(KEY)
    try:
        value = json.loads(CONFIG.read_text())
        app_id = int(value["app_id"])
        installation_id = int(value["installation_id"])
        allowed = value["allowed_repositories"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise AppError("invalid GitHub App configuration") from error
    if app_id <= 0 or installation_id <= 0 or not isinstance(allowed, list) or not allowed:
        raise AppError("GitHub App configuration requires IDs and a non-empty allowlist")
    if any(not isinstance(repo, str) or not REPOSITORY.fullmatch(repo) for repo in allowed):
        raise AppError("GitHub App allowlist contains an invalid repository")
    return {"app_id": app_id, "installation_id": installation_id, "allowed": sorted(set(allowed))}


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def app_jwt(app_id: int) -> str:
    now = int(time.time())
    signing_input = ".".join((
        b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode()),
        b64(json.dumps({"iat": now - 30, "exp": now + 540, "iss": str(app_id)}, separators=(",", ":")).encode()),
    ))
    try:
        signature = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(KEY)], input=signing_input.encode(),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise AppError("unable to sign GitHub App JWT") from error
    return f"{signing_input}.{b64(signature)}"


def request(path: str, token: str, method: str = "GET") -> dict:
    request_obj = urllib.request.Request(
        f"{API}{path}", method=method,
        headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        if error.code in (401, 403, 404):
            raise AppError(f"GitHub access denied or unavailable ({error.code})") from error
        raise AppError(f"GitHub API request failed ({error.code})") from error
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise AppError("GitHub API request failed") from error


def installation_token(settings: dict) -> str:
    body = request(f"/app/installations/{settings['installation_id']}/access_tokens", app_jwt(settings["app_id"]), "POST")
    token = body.get("token")
    if not isinstance(token, str) or not token:
        raise AppError("GitHub did not return an installation token")
    return token


def allowed(settings: dict, repo: str) -> None:
    if not REPOSITORY.fullmatch(repo) or repo not in settings["allowed"]:
        raise AppError("repository is not allowlisted")


def emit(value: object) -> None:
    print(json.dumps(value, separators=(",", ":"), sort_keys=True))


def doctor(settings: dict, token: str) -> None:
    result = request("/installation/repositories?per_page=100", token)
    installed = {entry.get("full_name") for entry in result.get("repositories", [])}
    emit({"configured": True, "allowlisted_repositories": settings["allowed"],
          "installed_repositories": sorted(repo for repo in settings["allowed"] if repo in installed),
          "unavailable_repositories": sorted(repo for repo in settings["allowed"] if repo not in installed),
          "operations": ["read repository metadata", "read issues"],
          "publication": "not enabled by this helper"})


def repositories(settings: dict, token: str, owner: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9-]+", owner):
        raise AppError("invalid owner")
    result = request("/installation/repositories?per_page=100", token)
    repos = [{"full_name": item["full_name"], "default_branch": item["default_branch"]}
             for item in result.get("repositories", [])
             if item.get("full_name") in settings["allowed"] and item.get("owner", {}).get("login") == owner]
    emit(sorted(repos, key=lambda item: item["full_name"]))


def issues(settings: dict, token: str, repo: str) -> None:
    allowed(settings, repo)
    result = request(f"/repos/{repo}/issues?state=open&per_page=100", token)
    emit([item for item in result if "pull_request" not in item])


def main(arguments: list[str]) -> int:
    if os.geteuid() != 0:
        raise AppError("must run through the controlled root wrapper")
    settings = config()
    token = installation_token(settings)  # A new short-lived token is minted for every operation.
    if arguments == ["doctor"]:
        doctor(settings, token)
    elif len(arguments) == 2 and arguments[0] == "repos":
        repositories(settings, token, arguments[1])
    elif len(arguments) == 2 and arguments[0] == "issues":
        issues(settings, token, arguments[1])
    else:
        raise AppError("usage: redless-github-app {doctor|repos OWNER|issues OWNER/REPOSITORY}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except AppError as error:
        print(f"redless-github-app: {error}", file=sys.stderr)
        raise SystemExit(1)
