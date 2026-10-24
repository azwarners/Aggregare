import json
import subprocess
import urllib.error

from tools.installer_recovery import application_is_complete, application_should_be_skipped


class Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def write_status(tmp_path, application_id="open-webui", **overrides):
    status = {
        "application_id": application_id,
        "version": "1.2.3",
        "state": "running",
        "deployment": {"service": f"{application_id}.service"},
        "verification": {"status": "passed", "endpoint": "http://127.0.0.1:8080/health"},
    }
    status.update(overrides)
    (tmp_path / f"{application_id}.json").write_text(json.dumps(status), encoding="utf-8")


def active_runner(*, rc=0, calls=None):
    def run(args, check=False):
        if calls is not None:
            calls.append(args)
        return subprocess.CompletedProcess(args, rc)

    return run


def healthy_endpoint(url, timeout):
    return Response()


def test_fresh_install_without_saved_progress_requires_application_run(tmp_path):
    assert not application_is_complete("open-webui", "1.2.3", status_dir=tmp_path)


def test_unchanged_healthy_application_is_complete_and_probed(tmp_path):
    calls = []
    write_status(tmp_path)
    assert application_is_complete(
        "open-webui", "1.2.3", status_dir=tmp_path, runner=active_runner(calls=calls), opener=healthy_endpoint
    )
    assert calls == [["systemctl", "is-active", "--quiet", "open-webui.service"]]


def test_second_install_skips_unchanged_healthy_application(tmp_path):
    write_status(tmp_path)
    assert application_should_be_skipped(
        "true", "v2:same", "v2:same", "open-webui", "1.2.3",
        status_dir=tmp_path, runner=active_runner(), opener=healthy_endpoint
    )


def test_stopped_service_requires_reapplication(tmp_path):
    write_status(tmp_path)
    assert not application_is_complete("open-webui", "1.2.3", status_dir=tmp_path, runner=active_runner(rc=3))


def test_active_service_with_failed_health_endpoint_requires_reapplication(tmp_path):
    write_status(tmp_path)

    def unavailable(url, timeout):
        raise urllib.error.URLError("connection refused")

    assert not application_is_complete(
        "open-webui", "1.2.3", status_dir=tmp_path, runner=active_runner(), opener=unavailable
    )


def test_completion_marker_cannot_replace_missing_live_service_status(tmp_path):
    # A status record is what the completion marker used to trust; removing it
    # must invalidate the skip even when the caller has a saved signature.
    assert not application_is_complete("open-webui", "1.2.3", status_dir=tmp_path)


def test_saved_completion_with_missing_systemd_service_requires_reapplication(tmp_path):
    write_status(tmp_path)
    assert not application_is_complete("open-webui", "1.2.3", status_dir=tmp_path, runner=active_runner(rc=4))


def test_version_or_source_signature_change_invalidates_saved_completion(tmp_path):
    write_status(tmp_path)
    saved_signature, current_signature = "v2:old-source", "v2:new-source"
    assert not application_should_be_skipped(
        "true", saved_signature, current_signature, "open-webui", "1.2.3",
        status_dir=tmp_path, runner=active_runner(), opener=healthy_endpoint
    )
    assert not application_is_complete("open-webui", "2.0.0", status_dir=tmp_path, runner=active_runner())


def test_interrupted_application_with_no_complete_status_is_retried(tmp_path):
    # An interrupted playbook has not written its successful status record.
    assert not application_is_complete("ysparr", "1.2.3", status_dir=tmp_path)


def test_unhealthy_dependency_does_not_invalidate_independent_healthy_app(tmp_path):
    write_status(tmp_path, "ysparr", deployment={"service": "ysparr.service"})
    write_status(tmp_path, "memos", deployment={"service": "memos.service"})
    assert not application_is_complete("ysparr", "1.2.3", status_dir=tmp_path, runner=active_runner(rc=3))
    assert application_is_complete("memos", "1.2.3", status_dir=tmp_path, runner=active_runner(), opener=healthy_endpoint)

