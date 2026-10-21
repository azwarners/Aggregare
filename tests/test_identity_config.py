import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONFIG_TOOL = ROOT / "tools/aggregare-identity-config"
IDENTITY_PLAYBOOK = ROOT / "ansible/playbooks/phase25-identity-config.yml"


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
                result = self.run_ansible(config, provider=provider)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                value = json.loads(config.read_text())
                Draft202012Validator(schema).validate(value)
                self.assertEqual(value, {"schema_version": 1, "identity_provider": provider})
                result = subprocess.run([str(CONFIG_TOOL), "get-provider", str(config)], check=True,
                                        capture_output=True, text=True)
                self.assertEqual(result.stdout.strip(), provider)

    @unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible Core is not installed")
    def test_reapply_uses_persisted_selection_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "identity.json"
            first = self.run_ansible(config, provider="external_oidc")
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            original = config.read_bytes()
            reapply = self.run_ansible(config)
            self.assertEqual(reapply.returncode, 0, reapply.stdout + reapply.stderr)
            self.assertEqual(config.read_bytes(), original)

    @unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible Core is not installed")
    def test_conflicting_selection_fails_until_explicit_update(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "identity.json"
            self.run_ansible(config, provider="external_oidc", check=True)
            original = config.read_bytes()
            conflict = self.run_ansible(config, provider="none")
            self.assertNotEqual(conflict.returncode, 0)
            self.assertIn("conflicts with", conflict.stdout + conflict.stderr)
            self.assertEqual(config.read_bytes(), original)
            update = self.run_ansible(config, provider="none", update=True)
            self.assertEqual(update.returncode, 0, update.stdout + update.stderr)
            self.assertEqual(json.loads(config.read_text())["identity_provider"], "none")

    @unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible Core is not installed")
    def test_invalid_missing_and_corrupt_config_fail_visibly(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            no_selection = self.run_ansible(missing)
            self.assertNotEqual(no_selection.returncode, 0)
            self.assertIn("no persistent identity selection exists", no_selection.stdout + no_selection.stderr)
            invalid_selection = self.run_ansible(missing, provider="invalid")
            self.assertNotEqual(invalid_selection.returncode, 0)
            self.assertFalse(missing.exists())
            corrupt = Path(directory) / "corrupt.json"
            corrupt.write_text(json.dumps({"schema_version": 1, "identity_provider": "mystery"}))
            invalid_saved = self.run_ansible(corrupt)
            self.assertNotEqual(invalid_saved.returncode, 0)
            self.assertIn("must be version 1", invalid_saved.stdout + invalid_saved.stderr)

    def test_ansible_identity_selection_requires_explicit_supported_input(self):
        playbook = IDENTITY_PLAYBOOK.read_text()
        installer = (ROOT / "install.sh").read_text()
        self.assertIn("aggregare_identity_provider is defined", playbook)
        self.assertIn("aggregare_identity_provider in ['kanidm', 'external_oidc', 'none']", playbook)
        self.assertIn("provider installation is not part", playbook)
        self.assertIn('IDENTITY_CONFIG_FILE="/etc/aggregare/identity.json"', installer)
        self.assertIn("aggregare_identity_config_file: /etc/aggregare/identity.json", playbook)
        self.assertIn("this installer needs an interactive terminal", installer)
        self.assertFalse(any("kanidm" in path.name.lower() for path in (ROOT / "ansible/roles").iterdir()))

    def run_ansible(self, config, provider=None, update=False, check=False):
        if not shutil.which("ansible-playbook"):
            self.skipTest("Ansible Core is not installed")
        variables = {"aggregare_identity_config_file": str(config), "ansible_become": False}
        if provider is not None:
            variables["aggregare_identity_provider"] = provider
        if update:
            variables["aggregare_identity_provider_update"] = True
        with tempfile.TemporaryDirectory() as tmp:
            environment = dict(os.environ)
            environment["ANSIBLE_LOCAL_TEMP"] = tmp
            environment["ANSIBLE_REMOTE_TEMP"] = tmp
            inventory = Path(tmp) / "hosts.ini"
            inventory.write_text("[aggregare]\nlocalhost ansible_connection=local\n")
            result = subprocess.run(
                [shutil.which("ansible-playbook"), "-i", str(inventory),
                 str(IDENTITY_PLAYBOOK), "--extra-vars", json.dumps(variables)],
                cwd=ROOT / "ansible", env=environment, capture_output=True, text=True,
            )
        if check and result.returncode != 0:
            self.fail(result.stdout + result.stderr)
        return result


if __name__ == "__main__":
    unittest.main()
