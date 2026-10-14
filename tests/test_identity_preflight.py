import importlib.util
from importlib.machinery import SourceFileLoader
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout


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

    def test_urls_with_credentials_or_non_https_are_rejected(self):
        for value in ("http://id.example.test", "https://user:secret@id.example.test"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                preflight.validate_url(value, "issuer")

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
