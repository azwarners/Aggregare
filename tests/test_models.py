import importlib.util
import io
import json
from contextlib import redirect_stdout, redirect_stderr
from importlib.machinery import SourceFileLoader
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/aggregare-models"
SPEC = importlib.util.spec_from_file_location("aggregare_models", MODULE_PATH, loader=SourceFileLoader("aggregare_models", str(MODULE_PATH)))
models = importlib.util.module_from_spec(SPEC)
sys.modules["aggregare_models"] = models
SPEC.loader.exec_module(models)


class ModelCliTests(unittest.TestCase):
    url = "http://127.0.0.1:8765"

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "ysparr-upstream.json"
        self.path.write_text(json.dumps({
            "ysparr_upstream_base_url": self.url,
            "ysparr_chat_model": "chat-model",
            "ysparr_coding_base_url": self.url,
            "ysparr_coding_model": "coding-model",
            "ysparr_upstream_api_key": "secret-not-output",
            "unrelated": {"keep": True},
        }))

    def tearDown(self):
        self.temporary.cleanup()

    def test_status_separates_roles_and_never_prints_secret(self):
        output = io.StringIO()
        with patch.object(models, "config_path", return_value=self.path), patch.object(models, "probe", return_value=models.Probe(True, 200, ("chat-model", "coding-model"))), redirect_stdout(output):
            self.assertEqual(models.main(["status"]), 0)
        text = output.getvalue()
        self.assertIn("Chat:", text)
        self.assertIn("Coding:", text)
        self.assertIn("model advertised: yes", text)
        self.assertNotIn("secret-not-output", text)

    def test_set_coding_preserves_chat_secret_and_unrelated_keys(self):
        with patch.object(models, "config_path", return_value=self.path), patch.object(models, "probe", return_value=models.Probe(True, 200, ("chat-model", "coding-model"))), patch.object(models, "restart_service", return_value=(True, "service active")):
            self.assertEqual(models.main(["set", "coding", "--url", self.url, "--model", "chat-model"]), 0)
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["ysparr_upstream_base_url"], self.url)
        self.assertEqual(saved["ysparr_chat_model"], "chat-model")
        self.assertEqual(saved["ysparr_coding_model"], "chat-model")
        self.assertEqual(saved["ysparr_upstream_api_key"], "secret-not-output")
        self.assertEqual(saved["unrelated"], {"keep": True})

    def test_failed_reload_restores_previous_file(self):
        original = self.path.read_text()
        with patch.object(models, "config_path", return_value=self.path), patch.object(models, "probe", return_value=models.Probe(True, 200, ("chat-model", "coding-model"))), patch.object(models, "restart_service", return_value=(False, "service reload failed")):
            self.assertNotEqual(models.main(["set", "chat", "--url", self.url, "--model", "coding-model"]), 0)
        self.assertEqual(self.path.read_text(), original)

    def test_unadvertised_model_does_not_change_file(self):
        original = self.path.read_text()
        errors = io.StringIO()
        with patch.object(models, "config_path", return_value=self.path), patch.object(models, "probe", return_value=models.Probe(True, 200, ("chat-model", "coding-model"))), redirect_stderr(errors):
            self.assertNotEqual(models.main(["set", "chat", "--url", self.url, "--model", "missing"]), 0)
        self.assertEqual(self.path.read_text(), original)
        self.assertIn("not advertised", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
