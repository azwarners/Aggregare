"""Show a task ordinal and the planned task total in Ansible task banners."""

from __future__ import annotations

import os
import re

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

    def _print_task_banner(self, task):
        task_label = self._last_task_name
        if task_label is None:
            task_label = task.get_name().strip()

        role_name, separator, task_title = task_label.rpartition(" : ")
        scope = f"{role_name}{separator}" if separator else ""
        if not separator:
            task_title = task_label

        match = re.match(r"(?P<ordinal>\d+/\d+) (?P<title>.*)$", task_title)
        if match is None:
            return super()._print_task_banner(task)

        task_uuid = task._uuid
        original_name = self._last_task_name
        original_prefix = self._task_type_cache.get(task_uuid, "TASK")
        self._last_task_name = f"{scope}{match.group('title')}"
        self._task_type_cache[task_uuid] = f"{match.group('ordinal')} {original_prefix}"
        try:
            super()._print_task_banner(task)
        finally:
            self._last_task_name = original_name
            self._task_type_cache[task_uuid] = original_prefix
