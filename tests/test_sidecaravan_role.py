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
