import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_redless_is_a_pinned_default_bundle_component():
    playbook = (ROOT / "ansible/playbooks/redless.yml").read_text()
    preset = json.loads((ROOT / "catalog/v1/presets/default.json").read_text())
    assert "- redless" in playbook
    assert "redless" in preset["applications"]
    assert "16bb8dd2d68582a55394075dfb7fbf5bb2924385" in playbook


def test_redless_role_enforces_account_and_filesystem_isolation():
    tasks = (ROOT / "ansible/roles/redless/tasks/main.yml").read_text()
    assert "name: redless" in tasks
    assert "home: \"{{ redless_home }}\"" in tasks
    assert "path: /bin/bash" in tasks
    assert "else '/bin/sh'" in tasks
    assert "groups: \"{{ redless_group }}\"" in tasks
    assert "aggregare_primary_users" in tasks
    assert "setfacl" in tasks
    assert "password_lock: true" in tasks
    assert "append: false" in tasks
    assert "d:g:{{ redless_group }}:r-x" in tasks
    assert "mode: '0600'" in tasks
    assert "mode: '0710'" in tasks
    assert "api_key: llama.cpp-placeholder" in tasks
    assert "gcc" in tasks
    assert "mode: '4755'" in tasks
    launcher = (ROOT / "ansible/roles/redless/files/redless-machine-launcher.c").read_text()
    assert "initgroups" in launcher
    assert "setuid(account->pw_uid)" in launcher
    assert "clearenv" in launcher


def test_redless_uses_the_machine_contract_and_report_exposes_it():
    tasks = (ROOT / "ansible/roles/redless/tasks/main.yml").read_text()
    report = (ROOT / "ansible/roles/aggregare_report/defaults/main.yml").read_text()
    assert "/usr/local/bin/redless-machine" in tasks
    assert '"type":"capabilities"' in tasks
    assert '"task_execution"' in tasks
    assert "redless-machine" in report


def test_redless_catalog_declares_cli_and_no_human_credentials():
    entry = json.loads((ROOT / "catalog/v1/applications/redless.json").read_text())
    assert entry["cli"][0]["path"] == "/usr/local/bin/redless-machine"
    assert entry["authentication"]["bootstrap"]["mode"] == "none"
    assert "password" not in entry["configuration"]
