import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_redless_is_a_pinned_default_bundle_component():
    playbook = (ROOT / "ansible/playbooks/redless.yml").read_text()
    preset = json.loads((ROOT / "catalog/v1/presets/default.json").read_text())
    assert "- redless" in playbook
    assert "redless" in preset["applications"]
    assert "16bb8dd2d68582a55394075dfb7fbf5bb2924385" in playbook
    assert "redless_live_smoke: true" not in playbook


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
    assert "redless_purge_data" in tasks
    assert "follow: false" in tasks
    assert "legacy setuid Redless regular executable" in tasks
    assert "redless_coding_models_probe" in tasks
    assert "does not substitute the chat model" in tasks
    assert "Restore ownership of preserved Redless artifacts" in tasks
    assert "mode: '4755'" not in tasks
    assert "redless-machine, --fixture" in tasks
    assert "/opt/aggregare/venvs/redless/bin/redless-machine" in tasks


def test_redless_uses_the_machine_contract_and_report_exposes_it():
    tasks = (ROOT / "ansible/roles/redless/tasks/main.yml").read_text()
    report = (ROOT / "ansible/roles/aggregare_report/defaults/main.yml").read_text()
    assert "/opt/aggregare/venvs/redless/bin/redless-machine" in tasks
    assert '"type":"task"' in tasks
    assert "redless_fixture_records" in tasks
    assert "redless_live_records" in tasks
    assert "trajectory_path" in tasks
    assert "max_retries: 0" in tasks
    assert "redless-machine" in report
    assert "redless_live_verification" in tasks
    assert "redless_fixture_verification" in tasks
    assert "redless_smoke.yaml" in tasks
    assert "execution_policy" in tasks
    assert "step_limit: 0" in tasks
    assert "model_timeout_seconds: 0" in tasks


def test_redless_live_smoke_is_disabled_by_default():
    defaults = (ROOT / "ansible/roles/redless/defaults/main.yml").read_text()
    assert "redless_live_smoke: false" in defaults
    assert "redless_live_model_timeout: 240" in defaults


def test_redless_catalog_declares_cli_and_no_human_credentials():
    entry = json.loads((ROOT / "catalog/v1/applications/redless.json").read_text())
    assert entry["cli"][0]["path"] == "/opt/aggregare/venvs/redless/bin/redless-machine"
    assert entry["authentication"]["bootstrap"]["mode"] == "none"
    assert "password" not in entry["configuration"]


def test_redless_uninstall_preserves_data_by_default():
    tasks = (ROOT / "ansible/roles/redless/tasks/main.yml").read_text()
    absent_block = tasks.split("- name: Remove Redless", 1)[1].split("- name: Install and configure Redless", 1)[0]
    normal_remove = absent_block.split("- name: Purge", 1)[0]
    assert "name: Remove the Redless deployment status record" in normal_remove
    assert "path: /var/lib/aggregare/status/redless.json" in normal_remove
    assert "redless_home" not in normal_remove
    assert "redless_log_path" not in normal_remove
    assert "when: redless_purge_data | bool" in absent_block
