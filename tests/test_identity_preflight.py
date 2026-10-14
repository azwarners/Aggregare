import importlib.util
from importlib.machinery import SourceFileLoader
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr, redirect_stdout


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_loader(
    "identity_preflight", SourceFileLoader("identity_preflight", str(ROOT / "tools/aggregare-identity-preflight"))
)
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class IdentityPreflightTests(unittest.TestCase):
    def test_success_checks_dns_tls_and_exact_discovery_issuer(self):
        issuer = "https://id.example.test/oauth2"
        discovery = {"issuer": issuer, "authorization_endpoint": "https://id.example.test/authorize",
                     "token_endpoint": "https://id.example.test/token"}
        with (patch.object(preflight, "resolve", return_value=["192.0.2.10"]),
              patch.object(preflight, "check_tls", return_value="TLSv1.3"),
              patch.object(preflight, "fetch_discovery", return_value=(issuer + "/.well-known/openid-configuration",
                                                                         ["authorization_endpoint", "token_endpoint"]))):
            checks = preflight.run_checks("https://id.example.test", issuer, None)
        self.assertEqual([check["name"] for check in checks],
                         ["origin_dns", "origin_tls", "issuer_dns", "issuer_tls", "issuer_discovery"])
        self.assertTrue(all(check["status"] == "passed" for check in checks))

    def test_dns_failure_is_reported_and_skips_tls_for_that_host(self):
        with (patch.object(preflight, "resolve", side_effect=[OSError("no such host"), ["192.0.2.20"]]),
              patch.object(preflight, "check_tls", return_value="TLSv1.3"),
              patch.object(preflight, "fetch_discovery", side_effect=OSError("unreachable"))):
            checks = preflight.run_checks("https://app.example.test", "https://id.example.test", None)
        self.assertEqual(checks[0]["status"], "failed")
        self.assertEqual(checks[0]["name"], "origin_dns")
        self.assertEqual(checks[-1]["name"], "issuer_discovery")
        self.assertEqual(checks[-1]["status"], "failed")

    def test_discovery_rejects_http_endpoints(self):
        issuer = "https://id.example.test"
        document = {"issuer": issuer, "authorization_endpoint": "http://id.example.test/authorize"}
        with patch.object(preflight.urllib.request, "urlopen") as open_url:
            class Response:
                status = 200
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return False
                def geturl(self):
                    return issuer + "/.well-known/openid-configuration"
                def read(self):
                    import json
                    return json.dumps(document).encode()
            open_url.return_value = Response()
            with self.assertRaisesRegex(ValueError, "non-HTTPS"):
                preflight.fetch_discovery(issuer, None)

    def test_discovery_checks_advertised_scheme_without_contacting_endpoints(self):
        issuer = "https://id.example.test"
        document = {"issuer": issuer,
                    "authorization_endpoint": "https://id.example.test/authorize",
                    "token_endpoint": "https://id.example.test/token"}
        with patch.object(preflight.urllib.request, "urlopen") as open_url:
            class Response:
                status = 200
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return False
                def geturl(self):
                    return issuer + "/.well-known/openid-configuration"
                def read(self):
                    return json.dumps(document).encode()
            open_url.return_value = Response()
            url, endpoint_fields = preflight.fetch_discovery(issuer, None)
        self.assertEqual(url, issuer + "/.well-known/openid-configuration")
        self.assertEqual(endpoint_fields, ["authorization_endpoint", "token_endpoint"])
        self.assertEqual(open_url.call_count, 1)

    def test_urls_with_credentials_or_non_https_are_rejected(self):
        for value in ("http://id.example.test", "https://user:secret@id.example.test"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                preflight.validate_url(value, "issuer")

    def test_malformed_urls_and_invalid_ports_raise_actionable_validation_errors(self):
        cases = (
            ("https://[broken", "malformed"),
            ("https://id.example.test:abc", "malformed"),
            ("https://id.example.test:70000", "malformed"),
            ("https://id.example.test:0", "port must be between 1 and 65535"),
            ("https://id.example.test/a path", "without whitespace"),
        )
        for value, message in cases:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, message):
                preflight.validate_url(value, "issuer")

    def test_cli_reports_malformed_url_without_traceback(self):
        error = io.StringIO()
        with redirect_stderr(error), self.assertRaises(SystemExit) as raised:
            preflight.main(["--origin", "https://id.example.test:bad", "--issuer", "https://id.example.test"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("origin is malformed", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())

    def test_container_execution_parses_successful_podman_output(self):
        checks = [{"name": "issuer_tls", "status": "passed", "protocol": "TLSv1.3"}]
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(checks), stderr=""
        )
        with patch.object(preflight.subprocess, "run", return_value=completed) as run:
            result = preflight.check_context(
                "habitsync", "https://app.example.test", "https://id.example.test", None
            )
        self.assertEqual(result, checks)
        self.assertEqual(run.call_args.args[0][:4], ["podman", "exec", "habitsync", "python3"])

    def test_container_execution_reports_missing_python(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=127, stdout="",
            stderr='Error: exec: "python3": executable file not found in $PATH',
        )
        with patch.object(preflight.subprocess, "run", return_value=completed):
            result = preflight.check_context(
                "habitsync", "https://app.example.test", "https://id.example.test", None
            )
        self.assertEqual(result[0]["name"], "container_python")
        self.assertIn("Python 3 is required", result[0]["detail"])

    def test_container_execution_reports_podman_failures(self):
        cases = (
            ("return", subprocess.CompletedProcess(
                args=[], returncode=125, stdout="", stderr="container not found"
            ), "Podman could not complete"),
            ("raise", FileNotFoundError("podman"), "Podman is unavailable"),
            ("raise", subprocess.TimeoutExpired(cmd="podman exec", timeout=1), "timed out"),
        )
        for mode, outcome, message in cases:
            with self.subTest(outcome=outcome):
                patcher = patch.object(
                    preflight.subprocess, "run",
                    return_value=outcome if mode == "return" else None,
                    side_effect=outcome if mode == "raise" else None,
                )
                with patcher:
                    result = preflight.check_context(
                        "habitsync", "https://app.example.test", "https://id.example.test", None
                    )
                self.assertEqual(result[0]["status"], "failed")
                self.assertIn(message, result[0]["detail"])

    def test_cli_renders_json_and_human_output(self):
        report = {"schema_version": "v1", "status": "failed", "origin": "https://app.example.test",
                  "issuer": "https://id.example.test", "contexts": [{"name": "host", "checks": [
                      {"name": "origin_dns", "status": "failed", "detail": "no such host"}]}]}
        for args, expected in ((["--format", "json"], "schema_version"), ([], "Identity preflight: failed")):
            output = io.StringIO()
            with patch.object(preflight, "make_report", return_value=report), redirect_stdout(output):
                status = preflight.main(["--origin", report["origin"], "--issuer", report["issuer"], *args])
            self.assertEqual(status, 1)
            self.assertIn(expected, output.getvalue())
            if "json" in args:
                self.assertEqual(json.loads(output.getvalue()), report)


if __name__ == "__main__":
    unittest.main()
