from pathlib import Path


ROLE_TASKS = Path(__file__).parents[1] / "ansible/roles/sidecaravan_memory/tasks/main.yml"


def test_sidecaravan_uninstall_preserves_store_and_token() -> None:
    text = ROLE_TASKS.read_text(encoding="utf-8")
    uninstall = text.split("- name: Install and initialize Sidecaravan memory", 1)[0]
    assert '"{{ sidecaravan_data_dir }}"' not in uninstall
    assert '"{{ sidecaravan_token_file }}"' not in uninstall
    assert "preserves the store and token" in uninstall


def test_sidecaravan_uses_verified_release_binary_by_default() -> None:
    defaults = ROLE_TASKS.parents[1] / "defaults/main.yml"
    text = defaults.read_text(encoding="utf-8")
    assert "memkeeper_build_lexical_only: false" in text
    assert "x86_64-unknown-linux-gnu" in ROLE_TASKS.read_text(encoding="utf-8")


def test_sidecaravan_default_tracks_the_tested_integration_ref() -> None:
    defaults = ROLE_TASKS.parents[1] / "defaults/main.yml"
    text = defaults.read_text(encoding="utf-8")
    assert "sidecaravan_source_ref: feat/issue-5-shared-memory-interface" in text


def test_default_bundle_tracks_coordinated_apmatia_ysparr_ref() -> None:
    root = ROLE_TASKS.parents[2]
    ysparr_defaults = (root / "ysparr/defaults/main.yml").read_text(encoding="utf-8")
    apmatia_defaults = (root / "apmatia/defaults/main.yml").read_text(encoding="utf-8")
    expected = "feat/apmatia-13-authenticated-ysparr-agents"
    assert f"ysparr_source_ref: {expected}" in ysparr_defaults
    assert f"apmatia_source_ref: {expected}" in apmatia_defaults


def test_apmatia_is_wired_to_the_ansible_managed_sidecaravan_boundary() -> None:
    role = ROLE_TASKS.parents[1].parent / "apmatia"
    defaults = (role / "defaults/main.yml").read_text(encoding="utf-8")
    service = (role / "templates/apmatia-core.service.j2").read_text(encoding="utf-8")
    assert "apmatia_sidecaravan_enabled: true" in defaults
    assert "Environment=APMATIA_SIDECARAVAN_ENABLED=" in service
    assert "Environment=SCV_TOKEN_FILE=" in service
    assert "Environment=SCV_STORE=" in service


def test_aggregate_playbooks_install_sidecaravan_before_apmatia() -> None:
    playbooks = ROLE_TASKS.parents[3] / "playbooks"
    for playbook in (playbooks / "site.yml", playbooks / "default.yml"):
        lines = playbook.read_text(encoding="utf-8").splitlines()
        assert lines.index("- import_playbook: sidecaravan.yml") < lines.index("- import_playbook: apmatia.yml")
