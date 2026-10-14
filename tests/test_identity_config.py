import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONFIG_TOOL = ROOT / "tools/aggregare-identity-config"


class IdentityConfigTests(unittest.TestCase):
    def test_installer_documents_and_rejects_invalid_cli_selection(self):
        help_result = subprocess.run([str(ROOT / "install.sh"), "--help"],
                                     capture_output=True, text=True)
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("kanidm|external_oidc|none", help_result.stdout)
        invalid = subprocess.run([str(ROOT / "install.sh"), "--identity-provider", "unknown"],
                                 capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("choose kanidm, external_oidc, or none", invalid.stderr)

    def test_versioned_config_accepts_all_supported_selections(self):
        schema = json.loads((ROOT / "schemas/v1/identity-config.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        for provider in ("kanidm", "external_oidc", "none"):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as directory:
                config = Path(directory) / "identity.json"
                subprocess.run([str(CONFIG_TOOL), "write", provider, str(config)], check=True)
                value = json.loads(config.read_text())
                Draft202012Validator(schema).validate(value)
                self.assertEqual(value, {"schema_version": 1, "identity_provider": provider})
                result = subprocess.run([str(CONFIG_TOOL), "get-provider", str(config)], check=True,
                                        capture_output=True, text=True)
                self.assertEqual(result.stdout.strip(), provider)

    def test_invalid_or_missing_saved_selection_fails_visibly(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "identity.json"
            config.write_text(json.dumps({"schema_version": 1, "identity_provider": "mystery"}))
            result = subprocess.run([str(CONFIG_TOOL), "get-provider", str(config)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("expected schema_version 1", result.stderr)

    def test_ansible_identity_selection_requires_explicit_supported_input(self):
        playbook = (ROOT / "ansible/playbooks/phase25-identity-config.yml").read_text()
        self.assertIn("aggregare_identity_provider is defined", playbook)
        self.assertIn("aggregare_identity_provider in ['kanidm', 'external_oidc', 'none']", playbook)
        self.assertIn("provider installation is not part", playbook)
        self.assertFalse(any("kanidm" in path.name.lower() for path in (ROOT / "ansible/roles").iterdir()))


if __name__ == "__main__":
    unittest.main()
