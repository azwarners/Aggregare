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
    assert "shell: /bin/bash" in tasks
    assert "groups: \"{{ redless_group }}\"" in tasks
    assert "aggregare_primary_users" in tasks
    assert "setfacl" in tasks
    assert "d:g:{{ redless_group }}:rwx" in tasks
    assert "mode: '0644'" in tasks
    assert "mode: '0755'" in tasks
    assert "api_key: llama.cpp-placeholder" in tasks
    assert "runuser, --user, \"{{ redless_user }}\"" in tasks


def test_redless_uses_the_machine_contract_and_report_exposes_it():
    tasks = (ROOT / "ansible/roles/redless/tasks/main.yml").read_text()
    report = (ROOT / "ansible/roles/aggregare_report/defaults/main.yml").read_text()
    assert "/usr/local/bin/redless-machine" in tasks
    assert '"type":"capabilities"' in tasks
    assert '"task_execution"' in tasks
    assert "redless-machine" in report
