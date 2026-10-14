import json
from pathlib import Path
import subprocess
import sys
import unittest

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path):
    return json.loads((ROOT / relative_path).read_text())


class CatalogContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_json("catalog/v1/index.json")
        cls.application_schema = load_json("schemas/v1/application.schema.json")
        cls.status_schema = load_json("schemas/v1/application-status.schema.json")

    def test_catalog_index_and_entries_match_schema(self):
        Draft202012Validator.check_schema(self.application_schema)
        validator = Draft202012Validator(self.application_schema)
        app_ids = set()

        for ref in self.catalog["applications"]:
            with self.subTest(application=ref["id"]):
                self.assertNotIn(ref["id"], app_ids)
                app_ids.add(ref["id"])
                entry = load_json(f"catalog/v1/{ref['path']}")
                self.assertEqual(entry["id"], ref["id"])
                validator.validate(entry)

                if entry["capabilities"]["install"]:
                    self.assertTrue(entry["install_methods"])
                    self.assertTrue(entry.get("entry_point"))
                    self.assertTrue((ROOT / entry["entry_point"]).is_file())
                    self.assertTrue(entry.get("platforms"))
                    self.assertTrue(entry.get("deployments"))
                else:
                    self.assertEqual(entry["status"], "blocked")
                    self.assertEqual(entry["install_methods"], [])

        self.assertEqual(len(app_ids), 17)

    def test_pocket_id_is_not_part_of_a_fresh_install(self):
        app_ids = {ref["id"] for ref in self.catalog["applications"]}
        self.assertNotIn("pocket-id", app_ids)
        site = (ROOT / "ansible/playbooks/site.yml").read_text()
        self.assertNotIn("pocket-id.yml", site)
        self.assertFalse((ROOT / "ansible/playbooks/pocket-id.yml").exists())
        self.assertFalse((ROOT / "ansible/playbooks/phase25-pocket-id-client.yml").exists())

    def test_application_status_contract_accepts_catalog_verification_shape(self):
        Draft202012Validator.check_schema(self.status_schema)
        validator = Draft202012Validator(self.status_schema)
        for ref in self.catalog["applications"]:
            entry = load_json(f"catalog/v1/{ref['path']}")
            if not entry["capabilities"]["install"]:
                continue
            deployment = entry["deployments"][0]
            status = {
                "schema_version": "v1",
                "application_id": entry["id"],
                "state": "installed",
                "version": entry["version"],
                "deployment": {
                    "backend": deployment["backend"],
                    "method": deployment["method"],
                },
                "verification": {"status": "passed", "check": "catalog contract fixture"},
            }
            if entry.get("services"):
                status["deployment"]["service"] = entry["services"][0]["name"]
            if deployment.get("image"):
                status["deployment"]["image"] = deployment["image"]
            with self.subTest(application=entry["id"]):
                validator.validate(status)

    def test_ansible_yaml_parses(self):
        paths = sorted((ROOT / "ansible").rglob("*.yml"))
        self.assertGreater(len(paths), 0)
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIsNotNone(yaml.safe_load(path.read_text()))

    def test_catalog_references_only_named_secret_handles(self):
        for ref in self.catalog["applications"]:
            entry = load_json(f"catalog/v1/{ref['path']}")
            for secret in entry.get("secret_references", []):
                self.assertNotIn("=", secret)
                self.assertNotIn(" ", secret)

    def test_initial_productivity_apps_declare_authentication_state(self):
        expected = {"habitsync", "memos", "vikunja"}
        entries = {
            ref["id"]: load_json(f"catalog/v1/{ref['path']}")
            for ref in self.catalog["applications"]
            if ref["id"] in expected
        }
        self.assertEqual(set(entries), expected)
        for app_id, entry in entries.items():
            with self.subTest(application=app_id):
                self.assertIn("authentication", entry)
                self.assertTrue(entry["authentication"]["methods"])
                self.assertTrue(entry["authentication"]["manual_steps"])

    def test_auth_cli_json_report_includes_productivity_apps_without_secrets(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/aggregare-auth"),
                "habitsync",
                "memos",
                "vikunja",
                "--format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(result.stdout)
        self.assertEqual(
            [app["application_id"] for app in report["applications"]],
            ["habitsync", "memos", "vikunja"],
        )
        self.assertTrue(all("password" not in app for app in report["applications"]))


if __name__ == "__main__":
    unittest.main()
