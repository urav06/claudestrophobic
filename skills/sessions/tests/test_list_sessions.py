"""Tests for list_sessions.py — selector resolution behavior.

The SKILL.md and README claim that `delete` supports prefix-UUID matching and
fuzzy-name matching. These tests verify that contract.

Run from the repo root:
    python3 -m unittest discover -s skills/sessions/tests
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


# Load the script as a module so we can call its functions directly.
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "list_sessions.py"
_spec = importlib.util.spec_from_file_location("list_sessions", _SCRIPT)
list_sessions = importlib.util.module_from_spec(_spec)
sys.modules["list_sessions"] = list_sessions
_spec.loader.exec_module(list_sessions)


def _write_session(
    project_root: Path,
    uuid: str,
    custom_title: str | None = None,
) -> Path:
    """Create a fake session JSONL plus its sidecar directories."""
    project_root.mkdir(parents=True, exist_ok=True)
    jsonl = project_root / f"{uuid}.jsonl"

    lines = []
    if custom_title:
        lines.append(json.dumps({
            "type": "custom-title",
            "customTitle": custom_title,
        }))
    else:
        lines.append(json.dumps({"type": "user", "content": "hello"}))

    jsonl.write_text("\n".join(lines) + "\n")
    return jsonl


class SelectorResolutionTests(unittest.TestCase):
    """Verify delete() honors the selector contract documented in SKILL.md."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.claude_dir = Path(self.tmp.name) / ".claude"
        self.claude_dir.mkdir()
        (self.claude_dir / "projects").mkdir()

        self.project = "/imaginary/project/path"
        # Mirrors list_sessions.project_dir() encoding.
        encoded = "-imaginary-project-path"
        self.project_root = self.claude_dir / "projects" / encoded
        self.project_root.mkdir()

        # Point the module at our temp tree.
        self._claude_patch = patch.object(
            list_sessions, "CLAUDE_DIR", self.claude_dir,
        )
        self._claude_patch.start()
        self.addCleanup(self._claude_patch.stop)

        # Force _remove()'s shutil fallback by making the trash subprocess
        # "fail." This keeps tests hermetic — no real Trash interaction.
        self._sp_patch = patch.object(
            subprocess, "run",
            return_value=subprocess.CompletedProcess(args=[], returncode=1),
        )
        self._sp_patch.start()
        self.addCleanup(self._sp_patch.stop)

    def _delete(self, selector: str) -> str:
        """Run delete() and capture stdout."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            list_sessions.delete(selector, self.project)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # The headline regression test — proves the SKILL.md claim.
    # ------------------------------------------------------------------

    def test_delete_by_uuid_prefix(self):
        """SKILL.md: 'fuzzy name or prefix match'. README: 'delete by partial UUID'."""
        full_uuid = "42f15ca9-2d23-4ee5-9ad8-17fc6c3637f2"
        jsonl = _write_session(self.project_root, full_uuid)

        self._delete("42f15ca9")

        self.assertFalse(
            jsonl.exists(),
            "delete() with UUID prefix should remove the session",
        )


if __name__ == "__main__":
    unittest.main()
