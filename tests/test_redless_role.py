import json
from pathlib import Path
import importlib.util
from importlib.machinery import SourceFileLoader
import io
import sys
import types
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_redless_is_a_pinned_default_bundle_component():
    playbook = (ROOT / "ansible/playbooks/redless.yml").read_text()
    default_playbook = (ROOT / "ansible/playbooks/default.yml").read_text()
    preset = json.loads((ROOT / "catalog/v1/presets/default.json").read_text())
    assert "- redless" in playbook
    assert "- import_playbook: redless.yml" in default_playbook
    assert "redless" in preset["applications"]
    assert "173171cc5018d1b2c3648780cc0f87ebce4bd588" in playbook
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
    assert "aggregare-redless-task" in tasks
    assert "aggregare_redless_task.py" in tasks
    assert "redless_task_adapter.py" in tasks
    assert "operator_cli" in tasks
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
    assert any(cli["path"] == "/usr/local/bin/aggregare-redless-task" for cli in entry["cli"])
    assert any(cli["path"] == "/usr/local/bin/aggRedless" for cli in entry["cli"])
    assert entry["authentication"]["bootstrap"]["mode"] == "none"
    assert "password" not in entry["configuration"]


def test_redless_issue_queue_is_installed_and_root_owned():
    tasks = (ROOT / "ansible/roles/redless/tasks/main.yml").read_text()
    script = ROOT / "tools/redless-issue-queue.sh"
    assert script.is_file()
    assert "src: \"{{ role_path }}/../../../tools/redless-issue-queue.sh\"" in tasks
    assert "dest: /usr/local/bin/redless-issue-queue" in tasks
    assert "mode: '0755'" in tasks
    assert "/usr/local/bin/redless-issue-queue" in tasks.split("- name: Remove Redless", 1)[1].split("- name: Install and configure Redless", 1)[0]
    content = script.read_text()
    assert "--endpoint" in content
    assert "--plan" in content
    assert "Authorization:' --header 'PRIVATE-TOKEN:'" in content
    assert "redless-machine" in content


def test_redless_github_app_helper_is_root_owned_and_constrained():
    tasks = (ROOT / "ansible/roles/redless/tasks/main.yml").read_text()
    helper = (ROOT / "tools/redless_github_app.py").read_text()
    sudoers = (ROOT / "ansible/roles/redless/templates/redless-github-app.sudoers.j2").read_text()
    assert "redless_github_app.py" in tasks
    assert "redless-github-app" in tasks
    assert "mode: '0440'" in tasks
    assert "visudo -cf %s" in tasks
    assert "allowed_repositories" in helper
    assert "installation_token" in helper
    assert "Authorization" in helper
    assert "git-credential" not in helper
    assert "print(token" not in helper
    assert "NOPASSWD" in sudoers
    assert " doctor" in sudoers and " repos *" in sudoers and " issues *" in sudoers
    assert "/etc/aggregare/secrets/redless-github-app.pem" in helper
    git_helper = (ROOT / "tools/redless-github-app-git").read_text()
    assert "isatty" in git_helper
    assert "os.geteuid() != 0" in git_helper
    assert 'sys.argv[1] != "get"' in git_helper
    assert "repository_accessible" in git_helper
    assert "password={token}" in git_helper
    assert "redless-github-app-git" in tasks


def test_redless_issue_queue_keeps_anonymous_preview_and_adds_opt_in_app_reads():
    content = (ROOT / "tools/redless-issue-queue.sh").read_text()
    assert "--github-app" in content
    assert "Authorization:' --header 'PRIVATE-TOKEN:'" in content
    assert 'github_app repos "$OWNER"' in content
    assert 'github_app issues "$repo"' in content
    assert "refusing anonymous fallback" in content


def test_github_app_doctor_never_serializes_its_installation_token(capsys, monkeypatch):
    spec = importlib.util.spec_from_file_location("redless_github_app", ROOT / "tools/redless_github_app.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    responses = iter([
        {"token": "sensitive-installation-token"},
        {"repositories": [{"full_name": "OWNER/REPOSITORY"}]},
    ])
    monkeypatch.setattr(helper, "config", lambda: {
        "app_id": 1, "installation_id": 2, "repository_policy": "explicit", "allowed": ["OWNER/REPOSITORY"],
    })
    monkeypatch.setattr(helper, "app_jwt", lambda _: "signed-jwt")
    monkeypatch.setattr(helper, "request", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0)
    assert helper.main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert "sensitive-installation-token" not in output
    assert "signed-jwt" not in output
    assert "OWNER/REPOSITORY" in output


def load_github_helper():
    spec = importlib.util.spec_from_file_location("redless_github_app_test", ROOT / "tools/redless_github_app.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


def test_github_app_paginates_repositories_and_preserves_later_allowlisted_result(capsys, monkeypatch):
    helper = load_github_helper()
    first = [{"full_name": f"OWNER/ignored-{index}", "default_branch": "main", "owner": {"login": "OWNER"}}
             for index in range(100)]
    second = [{"full_name": "OWNER/REPOSITORY", "default_branch": "main", "owner": {"login": "OWNER"}}]
    calls = []

    def fake_request(path, token, method="GET"):
        calls.append(path)
        return {"repositories": first if path.endswith("page=1") else second}

    monkeypatch.setattr(helper, "request", fake_request)
    helper.repositories({"repository_policy": "explicit", "allowed": ["OWNER/REPOSITORY"]}, "opaque", "OWNER")
    assert json.loads(capsys.readouterr().out) == [{"default_branch": "main", "full_name": "OWNER/REPOSITORY"}]
    assert calls == ["/installation/repositories?per_page=100&page=1", "/installation/repositories?per_page=100&page=2"]


def test_github_app_paginates_issues_beyond_the_first_hundred(capsys, monkeypatch):
    helper = load_github_helper()
    first = [{"number": index, "title": f"issue {index}"} for index in range(1, 101)]
    later = [{"number": 101, "title": "later issue"}]
    calls = []

    def fake_request(path, token, method="GET"):
        calls.append(path)
        return first if path.endswith("page=1") else later

    monkeypatch.setattr(helper, "request", fake_request)
    helper.issues({"repository_policy": "explicit", "allowed": ["OWNER/REPOSITORY"]}, "opaque", "OWNER/REPOSITORY")
    issues = json.loads(capsys.readouterr().out)
    assert [issue["number"] for issue in issues] == list(range(1, 102))
    assert calls == ["/repos/OWNER/REPOSITORY/issues?state=open&per_page=100&page=1", "/repos/OWNER/REPOSITORY/issues?state=open&per_page=100&page=2"]


def test_github_app_issue_read_fails_closed_for_a_repository_outside_the_allowlist(monkeypatch):
    helper = load_github_helper()
    monkeypatch.setattr(helper, "request", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("request must not run")))
    try:
        helper.issues({"repository_policy": "explicit", "allowed": ["OWNER/REPOSITORY"]}, "opaque", "OWNER/OTHER")
    except helper.AppError as error:
        assert "allowlisted" in str(error)
    else:
        raise AssertionError("non-allowlisted issue request was accepted")


def test_github_app_installation_policy_discovers_new_installation_repositories_and_rejects_other_owners(capsys, monkeypatch):
    helper = load_github_helper()
    settings = {"repository_policy": "installation", "allowed_owner": "OWNER", "allowed": []}
    monkeypatch.setattr(helper, "request", lambda *args, **kwargs: {"repositories": [
        {"full_name": "OWNER/existing", "default_branch": "main", "owner": {"login": "OWNER"}},
        {"full_name": "OWNER/newly-created", "default_branch": "main", "owner": {"login": "OWNER"}},
        {"full_name": "OTHER/not-ours", "default_branch": "main", "owner": {"login": "OTHER"}},
    ]})
    helper.repositories(settings, "opaque", "OWNER")
    assert [item["full_name"] for item in json.loads(capsys.readouterr().out)] == ["OWNER/existing", "OWNER/newly-created"]
    helper.doctor(settings, "opaque")
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["repository_policy"] == "installation"
    assert doctor["allowed_owner"] == "OWNER"
    assert doctor["installed_repositories"] == ["OWNER/existing", "OWNER/newly-created"]
    try:
        helper.issues(settings, "opaque", "OTHER/not-ours")
    except helper.AppError as error:
        assert "owner" in str(error)
    else:
        raise AssertionError("installation policy allowed a cross-owner repository")


def test_github_app_installation_policy_config_and_revoked_access_fail_closed(tmp_path, monkeypatch):
    helper = load_github_helper()
    config = tmp_path / "github-app.json"
    key = tmp_path / "github-app.pem"
    config.write_text(json.dumps({
        "app_id": 1, "installation_id": 2,
        "repository_policy": "installation", "allowed_owner": "OWNER",
    }))
    key.write_text("fixture")
    monkeypatch.setattr(helper, "CONFIG", config)
    monkeypatch.setattr(helper, "KEY", key)
    monkeypatch.setattr(helper, "private_file", lambda _: None)
    assert helper.config() == {
        "app_id": 1, "installation_id": 2, "repository_policy": "installation",
        "allowed_owner": "OWNER", "allowed": [],
    }
    config.write_text(json.dumps({"app_id": 1, "installation_id": 2, "repository_policy": "installation", "allowed_owner": "OWNER", "allowed_repositories": ["OWNER/repo"]}))
    try:
        helper.config()
    except helper.AppError as error:
        assert "does not accept" in str(error)
    else:
        raise AssertionError("mixed policy configuration was accepted")
    config.write_text(json.dumps({"app_id": 1, "installation_id": 2, "repository_policy": "all"}))
    try:
        helper.config()
    except helper.AppError as error:
        assert "repository_policy" in str(error)
    else:
        raise AssertionError("unknown repository policy was accepted")
    explicit = {"repository_policy": "explicit", "allowed": ["OWNER/repo"]}
    helper.allowed(explicit, "OWNER/repo")
    monkeypatch.setattr(helper, "request", lambda *args, **kwargs: (_ for _ in ()).throw(helper.AppError("GitHub access denied or unavailable (404)")))
    try:
        helper.repositories({"repository_policy": "installation", "allowed_owner": "OWNER", "allowed": []}, "opaque", "OWNER")
    except helper.AppError as error:
        assert "denied" in str(error)
    else:
        raise AssertionError("revoked installation access was accepted")


def test_git_credential_helper_requires_a_noninteractive_allowlisted_https_path(monkeypatch):
    module = types.ModuleType("redless_github_app")
    module.AppError = RuntimeError
    module.config = lambda: {"repository_policy": "explicit", "allowed": ["OWNER/REPOSITORY"]}
    module.repository_accessible = lambda settings, token, repo: repo == "OWNER/REPOSITORY" or (_ for _ in ()).throw(RuntimeError("repository is not allowlisted"))
    module.installation_token = lambda settings: "opaque-token"
    monkeypatch.setitem(sys.modules, "redless_github_app", module)
    spec = importlib.util.spec_from_loader(
        "redless_github_app_git_test", SourceFileLoader("redless_github_app_git_test", str(ROOT / "tools/redless-github-app-git"))
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0)
    monkeypatch.setattr(helper.os, "isatty", lambda _: False)
    monkeypatch.setattr(helper.os, "fstat", lambda _: types.SimpleNamespace(st_mode=helper.stat.S_IFIFO))
    monkeypatch.setattr(helper.sys, "argv", ["redless-github-app-git", "get"])
    monkeypatch.setattr(helper.sys, "stdin", io.StringIO("protocol=https\nhost=github.com\npath=OWNER/REPOSITORY.git\n\n"))
    output = io.StringIO()
    monkeypatch.setattr(helper.sys, "stdout", output)
    assert helper.main() == 0
    assert output.getvalue().startswith("username=x-access-token\npassword=")
    monkeypatch.setattr(helper.sys, "stdin", io.StringIO("protocol=https\nhost=github.com\npath=OWNER/OTHER.git\n\n"))
    monkeypatch.setattr(helper.sys, "stdout", io.StringIO())
    try:
        helper.main()
    except RuntimeError as error:
        assert "allowlisted" in str(error)
    else:
        raise AssertionError("credential request outside the allowlist was accepted")
    monkeypatch.setattr(helper.os, "isatty", lambda _: True)
    monkeypatch.setattr(helper.sys, "stdout", io.StringIO())
    try:
        helper.main()
    except RuntimeError as error:
        assert "noninteractive" in str(error)
    else:
        raise AssertionError("interactive credential request was accepted")
    guide = (ROOT / "docs/deployment/redless-github-app.md").read_text()
    assert "credential.useHttpPath=true" in guide


def test_git_credential_use_http_path_passes_repository_path_without_a_token(tmp_path):
    received = tmp_path / "received"
    helper = tmp_path / "credential-helper"
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        f"pathlib.Path({str(received)!r}).write_text(sys.stdin.read())\n"
        "sys.stdout.write('username=x-access-token\\npassword=fixture-only\\n\\n')\n"
    )
    helper.chmod(0o700)
    result = subprocess.run(
        ["git", "-c", "credential.useHttpPath=true", "-c", f"credential.helper=!{helper}", "credential", "fill"],
        input="protocol=https\nhost=github.com\npath=OWNER/REPOSITORY.git\n\n", text=True,
        capture_output=True, check=True,
    )
    assert "password=fixture-only" in result.stdout
    assert "path=OWNER/REPOSITORY.git" in received.read_text()


def test_redless_issue_queue_supports_read_only_assessments():
    content = (ROOT / "tools/redless-issue-queue.sh").read_text()
    assert "--assess-only" in content
    assert "--retry-assessment" in content
    assert "assessment.plan.json" in content
    assert "assessment.md" in content
    assert "source_revision" in content
    assert "Model JSON did not satisfy the assessment schema" in content
    assert "Do not edit files" in content
    assert "write GitHub state" in content


def test_redless_issue_queue_bounds_assessment_requests_and_fails_closed():
    content = (ROOT / "tools/redless-issue-queue.sh").read_text()
    assert 'ASSESSMENT_MAX_CALLS="${ASSESSMENT_MAX_CALLS:-12}"' in content
    assert "--assessment-max-calls" in content
    assert "max_model_calls" in content
    assert "synthesis_begins_at" in content
    assert "finalization_begins_at" in content
    assert "disable_tools_on_final_call" in content
    assert "completion cannot be verified" in content
    assert "completion is invalid" in content


def test_redless_uninstall_preserves_data_by_default():
    tasks = (ROOT / "ansible/roles/redless/tasks/main.yml").read_text()
    absent_block = tasks.split("- name: Remove Redless", 1)[1].split("- name: Install and configure Redless", 1)[0]
    normal_remove = absent_block.split("- name: Purge", 1)[0]
    assert "name: Remove the Redless deployment status record" in normal_remove
    assert "path: /var/lib/aggregare/status/redless.json" in normal_remove
    assert "/usr/local/bin/aggregare-redless-task" in normal_remove
    assert "/usr/local/lib/aggregare/aggregare_redless_task.py" in normal_remove
    assert "/usr/local/lib/aggregare/redless_task_adapter.py" in normal_remove
    assert "redless_home" not in normal_remove
    assert "redless_log_path" not in normal_remove
    assert "when: redless_purge_data | bool" in absent_block
