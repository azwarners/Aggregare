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
        self.assertIn("--identity-domain FQDN", help_result.stdout)
        invalid = subprocess.run([str(ROOT / "install.sh"), "--identity-provider", "unknown"],
                                 capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("choose kanidm, external_oidc, or none", invalid.stderr)

    def test_versioned_config_accepts_all_supported_selections(self):
        schema = json.loads((ROOT / "schemas/v1/identity-config.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        for provider in ("external_oidc", "none"):
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

    def test_version_2_schema_accepts_persisted_kanidm_endpoint(self):
        schema = json.loads((ROOT / "schemas/v1/identity-config.schema.json").read_text())
        Draft202012Validator(schema).validate({
            "schema_version": 2,
            "identity_provider": "kanidm",
            "identity_domain": "id.home.arpa",
            "identity_origin": "https://id.home.arpa",
        })

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
            self.assertIn("Set aggregare_identity_provider", no_selection.stdout + no_selection.stderr)
            invalid_selection = self.run_ansible(missing, provider="invalid")
            self.assertNotEqual(invalid_selection.returncode, 0)
            self.assertFalse(missing.exists())
            corrupt = Path(directory) / "corrupt.json"
            corrupt.write_text(json.dumps({"schema_version": 1, "identity_provider": "mystery"}))
            invalid_saved = self.run_ansible(corrupt)
            self.assertNotEqual(invalid_saved.returncode, 0)
            self.assertIn("is invalid", invalid_saved.stdout + invalid_saved.stderr)

    def test_ansible_identity_selection_requires_explicit_supported_input(self):
        playbook = IDENTITY_PLAYBOOK.read_text()
        installer = (ROOT / "install.sh").read_text()
        self.assertIn("aggregare_identity_provider is defined", playbook)
        self.assertIn("aggregare_identity_provider in ['kanidm', 'external_oidc', 'none']", playbook)
        self.assertIn("Deploy Kanidm service", playbook)
        self.assertIn("aggregare_identity_provider_effective == 'kanidm'", playbook)
        self.assertIn("--dns-only", playbook)
        self.assertLess(playbook.index("--dns-only"), playbook.index("Persist version 2 Kanidm endpoint selection"))
        self.assertLess(playbook.index("Start or safely reapply Kanidm service"),
                        playbook.index("Verify Kanidm status endpoint"))
        self.assertLess(playbook.index("Require a valid certificate, hostname match"),
                        playbook.index("Run shared DNS preflight"))
        self.assertIn("Reuse the persisted Kanidm endpoint", playbook)
        self.assertIn("aggregare_identity_saved_config.identity_domain | default('')", playbook)
        self.assertIn("aggregare_identity_saved_config.identity_origin | default('')", playbook)
        self.assertIn('IDENTITY_CONFIG_FILE="/etc/aggregare/identity.json"', installer)
        self.assertIn("aggregare_identity_config_file: /etc/aggregare/identity.json", playbook)
        self.assertIn("get-field identity_domain", installer)
        self.assertIn("get-field identity_origin", installer)
        self.assertIn('IDENTITY_DOMAIN="${IDENTITY_DOMAIN:-$saved_domain}"', installer)
        self.assertIn('IDENTITY_ORIGIN="${IDENTITY_ORIGIN:-$saved_origin}"', installer)
        self.assertIn("this installer needs an interactive terminal", installer)
        self.assertFalse(any("kanidm" in path.name.lower() for path in (ROOT / "ansible/roles").iterdir()))

    def test_kanidm_preflight_failure_preserves_config_and_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "identity.json"
            config.write_text(json.dumps({
                "schema_version": 2,
                "identity_provider": "kanidm",
                "identity_domain": "id.example.invalid",
                "identity_origin": "https://id.example.invalid",
            }) + "\n")
            original = config.read_bytes()
            data = root / "kanidm-data"
            data.mkdir()
            marker = data / "identity.db"
            marker.write_bytes(b"existing identity data")
            cert, key = self.create_tls_pair(root, "id.example.invalid")
            result = self.run_ansible(
                config, provider="kanidm", domain="id.example.invalid",
                origin="https://id.example.invalid", chain=str(cert), key=str(key),
                data_dir=str(data), update=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("origin_dns", result.stdout + result.stderr)
            self.assertEqual(config.read_bytes(), original)
            self.assertEqual(marker.read_bytes(), b"existing identity data")

    def test_mismatched_tls_key_fails_before_identity_or_data_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "identity.json"
            config.write_text(json.dumps({
                "schema_version": 2,
                "identity_provider": "kanidm",
                "identity_domain": "id.home.arpa",
                "identity_origin": "https://id.home.arpa",
            }) + "\n")
            original = config.read_bytes()
            data = root / "kanidm-data"
            data.mkdir()
            marker = data / "identity.db"
            marker.write_bytes(b"existing identity data")
            cert, _ = self.create_tls_pair(root, "id.home.arpa")
            wrong_key = root / "wrong-key.pem"
            subprocess.run([
                "openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
                "-out", str(wrong_key),
            ], check=True, capture_output=True, text=True)
            result = self.run_ansible(
                config, provider="kanidm", domain="id.home.arpa", origin="https://id.home.arpa",
                chain=str(cert), key=str(wrong_key), data_dir=str(data),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("matching unencrypted PEM private key", result.stdout + result.stderr)
            self.assertEqual(config.read_bytes(), original)
            self.assertEqual(marker.read_bytes(), b"existing identity data")

    def test_established_kanidm_domain_change_is_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "identity.json"
            config.write_text(json.dumps({
                "schema_version": 2,
                "identity_provider": "kanidm",
                "identity_domain": "id.home.arpa",
                "identity_origin": "https://id.home.arpa",
            }) + "\n")
            original = config.read_bytes()
            data = root / "kanidm-data"
            data.mkdir()
            marker = data / "identity.db"
            marker.write_bytes(b"existing identity data")
            cert = root / "chain.pem"
            key = root / "key.pem"
            cert.write_text("test certificate")
            key.write_text("test private key")
            result = self.run_ansible(
                config, provider="kanidm", domain="new-id.home.arpa",
                origin="https://new-id.home.arpa", chain=str(cert), key=str(key),
                data_dir=str(data), update=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cannot be changed in place", result.stdout + result.stderr)
            self.assertEqual(config.read_bytes(), original)
            self.assertEqual(marker.read_bytes(), b"existing identity data")

    def run_ansible(self, config, provider=None, update=False, check=False, **extra):
        if not shutil.which("ansible-playbook"):
            self.skipTest("Ansible Core is not installed")
        variables = {"aggregare_identity_config_file": str(config), "ansible_become": False}
        if provider is not None:
            variables["aggregare_identity_provider"] = provider
        if update:
            variables["aggregare_identity_provider_update"] = True
        variables.update({
            key: value for key, value in {
                "aggregare_identity_domain": extra.get("domain"),
                "aggregare_identity_origin": extra.get("origin"),
                "aggregare_kanidm_tls_chain_source": extra.get("chain"),
                "aggregare_kanidm_tls_key_source": extra.get("key"),
                "aggregare_kanidm_data_dir": extra.get("data_dir"),
            }.items() if value is not None
        })
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

    def create_tls_pair(self, directory, hostname):
        if not shutil.which("openssl"):
            self.skipTest("OpenSSL is required to validate certificate/key inputs")
        cert = directory / "chain.pem"
        key = directory / "key.pem"
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "365",
            "-keyout", str(key), "-out", str(cert), "-subj", f"/CN={hostname}",
            "-addext", f"subjectAltName=DNS:{hostname}",
        ], check=True, capture_output=True, text=True)
        return cert, key


if __name__ == "__main__":
    unittest.main()
