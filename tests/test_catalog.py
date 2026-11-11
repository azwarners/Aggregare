import json
from importlib.machinery import SourceFileLoader
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

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

        self.assertEqual(len(app_ids), 19)

    def test_pocket_id_is_not_part_of_a_fresh_install(self):
        app_ids = {ref["id"] for ref in self.catalog["applications"]}
        self.assertNotIn("pocket-id", app_ids)
        site = (ROOT / "ansible/playbooks/site.yml").read_text()
        self.assertNotIn("pocket-id.yml", site)
        self.assertFalse((ROOT / "ansible/playbooks/pocket-id.yml").exists())
        self.assertFalse((ROOT / "ansible/playbooks/phase25-pocket-id-client.yml").exists())
        installer_sources = [ROOT / "install.sh"]
        installer_sources.extend((ROOT / "ansible").rglob("*.yml"))
        installer_sources.extend((ROOT / "catalog").rglob("*.json"))
        for path in installer_sources:
            content = path.read_text()
            with self.subTest(source=path.relative_to(ROOT)):
                self.assertNotIn("STATIC_API_KEY", content)
                self.assertNotIn("pocket-id.yml", content)

    def test_headless_default_does_not_install_troubleshell(self):
        default_playbook = (ROOT / "ansible/playbooks/default.yml").read_text()
        self.assertNotIn("troubleshell.yml", default_playbook)

    def test_open_webui_is_chat_only_by_default(self):
        open_webui = yaml.safe_load((ROOT / "ansible/playbooks/open-webui.yml").read_text())
        environment = open_webui[0]["vars"]["application_environment"]
        self.assertEqual(
            {name: environment[name] for name in (
                "ENABLE_PLUGINS",
                "ENABLE_CODE_EXECUTION",
                "ENABLE_CODE_INTERPRETER",
            )},
            {
                "ENABLE_PLUGINS": "false",
                "ENABLE_CODE_EXECUTION": "false",
                "ENABLE_CODE_INTERPRETER": "false",
            },
        )
        quadlet_template = (ROOT / "ansible/roles/container_app/templates/application.container.j2").read_text()
        self.assertIn("Environment={{ key }}={{ value }}", quadlet_template)

    def test_ysparr_can_follow_the_current_upstream_model(self):
        ysparr_tasks = (ROOT / "ansible/roles/ysparr/tasks/main.yml").read_text()
        self.assertIn("Select the first available chat model when the saved selection is stale", ysparr_tasks)
        self.assertIn("ysparr_upstream_models_probe.json.data[0].id", ysparr_tasks)

    def test_ysparr_routes_extension_model_types_to_the_selected_chat_model(self):
        defaults = (ROOT / "ansible/roles/ysparr/defaults/main.yml").read_text()
        tasks = (ROOT / "ansible/roles/ysparr/tasks/main.yml").read_text()
        template = (ROOT / "ansible/roles/ysparr/templates/ysparr.env.j2").read_text()
        self.assertIn("ysparr_model_type_routes: {}", defaults)
        self.assertIn("'openai_compatible': ysparr_chat_model_effective", tasks)
        self.assertIn("ysparr_model_type_routes_effective", template)

    def test_default_bundle_and_report_metadata_cover_first_party_components(self):
        preset = load_json("catalog/v1/presets/default.json")
        self.assertIn("ladcemas", preset["applications"])
        self.assertIn("sidecaravan", preset["applications"])
        self.assertIn("memkeeper", preset["applications"])
        openipe = load_json("catalog/v1/applications/openipe.json")
        self.assertIn("openipe.service", {service["name"] for service in openipe["services"]})
        apmatia = load_json("catalog/v1/applications/apmatia.json")
        self.assertIn("apmatia", {cli["name"] for cli in apmatia["cli"]})
        sidecaravan = load_json("catalog/v1/applications/sidecaravan.json")
        self.assertEqual({cli["name"] for cli in sidecaravan["cli"]}, {"scv", "scv-mcp", "memkeeper"})
        memkeeper = load_json("catalog/v1/applications/memkeeper.json")
        self.assertEqual(memkeeper["display_name"], "Memkeeper")
        self.assertIn("sidecaravan-mcp.socket", {service["name"] for service in memkeeper["services"]})
        self.assertEqual({cli["name"] for cli in memkeeper["cli"]}, {"memkeeper"})
        installer = (ROOT / "install.sh").read_text()
        self.assertIn('expected.insert(expected.index("sidecaravan") + 1, "memkeeper")', installer)
        ladcemas_playbook = (ROOT / "ansible/playbooks/ladcemas.yml").read_text()
        ladcemas_tasks = (ROOT / "ansible/roles/ladcemas_lite/tasks/main.yml").read_text()
        self.assertIn('"ladcemas_bind_address": sys.argv[1]', installer)
        self.assertIn("ladcemas_host: \"{{ ladcemas_bind_address | default('127.0.0.1') }}\"", ladcemas_playbook)
        self.assertIn("state: \"{{ 'restarted' if ladcemas_service_template.changed else 'started' }}\"", ladcemas_tasks)
        self.assertIn("Verify Ladcemas-Lite is reachable on its configured bind address", ladcemas_tasks)

    def test_catalog_clis_are_exposed_through_system_path(self):
        for ref in self.catalog["applications"]:
            entry = load_json(f"catalog/v1/{ref['path']}")
            for cli in entry.get("cli", []):
                self.assertTrue(cli["path"].startswith("/usr/local/bin/"), f"{entry['id']} CLI is not system-wide: {cli['path']}")
        report_defaults = (ROOT / "ansible/roles/aggregare_report/defaults/main.yml").read_text()
        report_tasks = (ROOT / "ansible/roles/aggregare_report/tasks/main.yml").read_text()
        self.assertIn("Expose installed managed CLI entry points through the system PATH", report_tasks)
        self.assertIn("Remove unavailable optional CLI entry points from the system PATH", report_tasks)
        self.assertIn("scv-mcp", report_defaults)
        for role, marker in (("apmatia", "Expose Apmatia CLI through the system PATH"), ("ysparr", "Expose Ysparr CLI through the system PATH"), ("sidecaravan_memory", "Expose the Sidecaravan MCP CLI through the system PATH"), ("llama_cpp", "Expose llama-server through the system PATH")):
            tasks = (ROOT / "ansible/roles" / role / "tasks/main.yml").read_text()
            self.assertIn(marker, tasks)
        apmatia_wrapper = (ROOT / "ansible/roles/apmatia/templates/apmatia-wrapper.j2").read_text()
        self.assertIn("APMATIA_API_URL:-{{ apmatia_api_url }}", apmatia_wrapper)
        self.assertIn("/bin/apmatia", apmatia_wrapper)

    def test_llama_endpoint_reports_model_ids_for_installer_selection(self):
        module_path = ROOT / "tools/aggregare-llama-endpoint"
        loader = SourceFileLoader("aggregare_llama_endpoint", str(module_path))
        spec = importlib.util.spec_from_file_location("aggregare_llama_endpoint", module_path, loader=loader)
        endpoint = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(endpoint)

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def __iter__(self):
                return iter(())

            def read(self):
                return b'{"data": [{"id": "chat-one"}, {"id": "chat-two"}]}'

        output = io.StringIO()
        with patch.object(endpoint, "urlopen", return_value=Response()), redirect_stdout(output):
            self.assertEqual(endpoint.probe("http://llama"), 0)
        self.assertIn("Model ID: chat-one", output.getvalue())
        self.assertIn("Model ID: chat-two", output.getvalue())

    def test_installer_uses_endpoint_model_selection_for_chat_and_coding(self):
        installer = (ROOT / "install.sh").read_text()
        self.assertIn('select_model_from_endpoint "$LLAMA_CPP_URL" chat', installer)
        self.assertIn('select_model_from_endpoint "$CODING_LLM_URL" coding', installer)
        self.assertNotIn('read -r -p "Coding model ID', installer)

    def test_sidecaravan_status_uses_catalog_application_id(self):
        sidecaravan_tasks = (ROOT / "ansible/roles/sidecaravan_memory/tasks/main.yml").read_text()
        self.assertIn("dest: /var/lib/aggregare/status/sidecaravan.json", sidecaravan_tasks)
        self.assertIn("dest: /var/lib/aggregare/status/memkeeper.json", sidecaravan_tasks)
        self.assertIn("'application_id': 'sidecaravan'", sidecaravan_tasks)

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
