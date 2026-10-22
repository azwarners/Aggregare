"""Show a task ordinal and the planned task total in Ansible task banners."""

from __future__ import annotations

import os

from ansible.plugins.callback.default import CallbackModule as DefaultCallbackModule


DOCUMENTATION = """
    name: aggregare_progress
    type: stdout
    short_description: default Ansible output with task progress numbers
    version_added: "1.0"
    description:
      - Prefixes each task banner with its ordinal and the planned task count.
    extends_documentation_fragment:
      - default_callback
      - result_format_callback
    requirements:
      - set as stdout in configuration
"""


class CallbackModule(DefaultCallbackModule):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "aggregare_progress"
    CALLBACK_NEEDS_WHITELIST = False

    def __init__(self):
        super().__init__()
        self._aggregare_task_index = 0
        try:
            self._aggregare_task_offset = max(0, int(os.environ.get("AGGREGARE_TASK_OFFSET", "0")))
        except ValueError:
            self._aggregare_task_offset = 0
        try:
            self._aggregare_task_total = max(0, int(os.environ.get("AGGREGARE_TASK_TOTAL", "0")))
        except ValueError:
            self._aggregare_task_total = 0

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._aggregare_task_index += 1
        original_name = task.name
        total = str(self._aggregare_task_total) if self._aggregare_task_total else "?"
        ordinal = self._aggregare_task_offset + self._aggregare_task_index
        task.name = f"{ordinal}/{total} {original_name or task.get_name().strip()}"
        try:
            super().v2_playbook_on_task_start(task, is_conditional)
        finally:
            task.name = original_name
