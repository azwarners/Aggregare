import importlib.util
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("aggregare_report", ROOT / "tools/aggregare-report.py")
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


class DeploymentReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.catalog = self.root / "catalog"
        self.apps = self.catalog / "applications"
        self.statuses = self.root / "status"
        self.apps.mkdir(parents=True)
        self.statuses.mkdir()
        (self.catalog / "index.json").write_text(json.dumps({"applications": [
            {"id": "enabled", "path": "applications/enabled.json"},
            {"id": "disabled", "path": "applications/disabled.json"},
            {"id": "missing-meta", "path": "applications/missing-meta.json"},
        ]}))
        entries = [
            {"id": "enabled", "display_name": "Enabled App", "services": [{"name": "enabled.service", "ports": [8765]}],
             "authentication": {"manual_steps": ["Create the first user in the browser."]}},
            {"id": "disabled", "display_name": "Disabled App", "services": [{"name": "disabled.service", "ports": [8766]}]},
            {"id": "missing-meta", "display_name": "Missing Metadata App", "services": []},
        ]
        for entry in entries:
            (self.apps / f"{entry['id']}.json").write_text(json.dumps(entry))
        (self.statuses / "enabled.json").write_text(json.dumps({
            "application_id": "enabled", "state": "running",
            "verification": {"status": "passed", "endpoint": "https://admin:password@example.test:8765/health?token=secret"},
            "deployment": {"credential": "never-render-this"},
        }))
        (self.statuses / "missing-meta.json").write_text(json.dumps({"application_id": "missing-meta", "state": "installed"}))

    def tearDown(self):
        self.temporary.cleanup()

    def render(self, **kwargs):
        return report.render_report(
            self.catalog, self.statuses, hostname="test-host", addresses=["192.168.50.10"],
            version="1.2.3", generated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            observed_services={"enabled.service": "active", "disabled.service": "not installed"}, **kwargs,
        )

    def test_disabled_application_is_not_reported(self):
        content = self.render()
        self.assertIn("Enabled App", content)
        self.assertNotIn("Disabled App", content)

    def test_missing_endpoint_and_service_metadata_are_marked_unknown(self):
        content = self.render()
        self.assertIn("Missing Metadata App", content)
        self.assertIn("Configured endpoint: unknown or unavailable", content)
        self.assertIn("Service metadata is unavailable", content)

    def test_report_redacts_credentials_and_credential_bearing_urls(self):
        content = self.render()
        for secret in ("token=secret", "never-render-this", "admin:"):
            self.assertNotIn(secret, content)
        self.assertIn("https://example.test:8765/health", content)

    def test_failed_and_skipped_applications_are_distinguished(self):
        content = self.render(failed_apps={"disabled"}, expected_apps={"disabled"})
        self.assertIn("Failed during this installer run", content)
        self.assertIn("Disabled App", content)
        self.assertIn("Missing Metadata App", content)

    def test_expected_but_uninstalled_application_is_marked_as_skipped_or_disabled(self):
        content = self.render(expected_apps={"disabled"})
        self.assertIn("Disabled App", content)
        self.assertIn("Not detected; the application may be disabled, skipped, or not installed", content)

    def test_reapplication_content_is_stable_except_explicit_timestamp(self):
        self.assertEqual(self.render(), self.render())

    def test_report_command_works_from_any_current_directory(self):
        report_path = self.root / "deployment-report.md"
        report_path.write_text("# Current report\n")
        environment = os.environ.copy()
        environment["AGGREGARE_REPORT_PATH"] = str(report_path)
        command = ROOT / "tools/aggregare"
        result = subprocess.run([str(command), "report"], cwd=self.root, env=environment,
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, "# Current report\n")

    def test_summary_command_uses_the_current_report(self):
        report_path = self.root / "deployment-report.md"
        report_path.write_text("# Report\n\n## Applications\n\n### Example\n\n- Status: Recorded state: running\n- Configured endpoint: http://127.0.0.1:8080/\n\n## Services\n")
        environment = os.environ.copy()
        environment["AGGREGARE_REPORT_PATH"] = str(report_path)
        result = subprocess.run([str(ROOT / "tools/aggregare"), "summary"], cwd=self.root, env=environment,
                                capture_output=True, text=True, check=True)
        self.assertIn("Example: Recorded state: running", result.stdout)
        self.assertIn("http://127.0.0.1:8080/", result.stdout)


if __name__ == "__main__":
    unittest.main()
