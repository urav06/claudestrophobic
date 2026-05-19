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

    # ------------------------------------------------------------------
    # Baseline: full-UUID match still works (regression guard).
    # ------------------------------------------------------------------

    def test_delete_by_full_uuid(self):
        full = "abc12345-1111-2222-3333-444444444444"
        jsonl = _write_session(self.project_root, full)
        self._delete(full)
        self.assertFalse(jsonl.exists())

    # ------------------------------------------------------------------
    # Name matching.
    # ------------------------------------------------------------------

    def test_delete_by_name_substring(self):
        """README example: '/sessions delete fix auth middleware'."""
        uuid = "11111111-aaaa-bbbb-cccc-000000000001"
        jsonl = _write_session(
            self.project_root, uuid, custom_title="Fix auth middleware",
        )
        self._delete("fix auth")
        self.assertFalse(jsonl.exists())

    def test_delete_by_name_tokens_out_of_order(self):
        """All tokens must match, but order is irrelevant."""
        uuid = "11111111-aaaa-bbbb-cccc-000000000002"
        jsonl = _write_session(
            self.project_root, uuid, custom_title="Authentication middleware fix",
        )
        self._delete("fix auth")
        self.assertFalse(jsonl.exists())

    def test_name_match_case_insensitive(self):
        uuid = "11111111-aaaa-bbbb-cccc-000000000003"
        jsonl = _write_session(
            self.project_root, uuid, custom_title="Authenticate User",
        )
        self._delete("AUTH")
        self.assertFalse(jsonl.exists())

    # ------------------------------------------------------------------
    # Ambiguity: refuse, don't pick.
    # ------------------------------------------------------------------

    def test_ambiguous_prefix_refuses(self):
        a = _write_session(
            self.project_root, "42f15ca9-aaaa-1111-2222-333333333333",
        )
        b = _write_session(
            self.project_root, "42f15ca9-bbbb-4444-5555-666666666666",
        )
        out = self._delete("42f15ca9")
        self.assertTrue(a.exists(), "ambiguous prefix must not delete")
        self.assertTrue(b.exists(), "ambiguous prefix must not delete")
        self.assertIn("Ambiguous", out)

    def test_ambiguous_name_refuses(self):
        a = _write_session(
            self.project_root,
            "aaaaaaaa-1111-1111-1111-111111111111",
            custom_title="Fix auth bug",
        )
        b = _write_session(
            self.project_root,
            "bbbbbbbb-2222-2222-2222-222222222222",
            custom_title="Investigate auth",
        )
        out = self._delete("auth")
        self.assertTrue(a.exists(), "ambiguous name must not delete")
        self.assertTrue(b.exists(), "ambiguous name must not delete")
        self.assertIn("Ambiguous", out)

    # ------------------------------------------------------------------
    # Safety: active sessions, no-match.
    # ------------------------------------------------------------------

    def test_active_session_protected_via_prefix(self):
        """Active-session protection survives prefix resolution."""
        full = "deadbeef-1111-2222-3333-444444444444"
        jsonl = _write_session(self.project_root, full)

        sessions_dir = self.claude_dir / "sessions"
        sessions_dir.mkdir()
        (sessions_dir / "lock.json").write_text(
            json.dumps({"sessionId": full}),
        )

        out = self._delete("deadbeef")
        self.assertTrue(jsonl.exists())
        self.assertIn("currently active", out)

    def test_no_match(self):
        _write_session(
            self.project_root, "abc12345-1111-2222-3333-444444444444",
        )
        out = self._delete("xyzzy")
        self.assertIn("No session found", out)

    # ------------------------------------------------------------------
    # Priority: UUID-prefix wins over name substring.
    # ------------------------------------------------------------------

    def test_uuid_prefix_priority_over_name(self):
        """If selector is a valid UUID prefix, name match does not fire."""
        # Session 1: UUID starts with "abc"
        uuid_with_prefix = "abcdef00-1111-2222-3333-444444444444"
        j1 = _write_session(self.project_root, uuid_with_prefix)
        # Session 2: name contains "abc", UUID does not
        uuid_with_name = "00000000-1111-2222-3333-555555555555"
        j2 = _write_session(
            self.project_root, uuid_with_name, custom_title="abc title",
        )

        self._delete("abc")

        self.assertFalse(j1.exists(), "UUID-prefix match should win priority")
        self.assertTrue(j2.exists(), "name match must not fire when UUID prefix matches")


class PrunePerformanceTests(unittest.TestCase):
    """Guard against O(N²) regressions in prune().

    prune() must call discover() exactly once and rewrite history.jsonl
    exactly once, regardless of how many sessions are pruned. Calling
    delete() per iteration (which itself calls discover() and rewrites
    history) would explode both costs.
    """

    def setUp(self):
        import os
        import time
        self._os = os
        self._time = time

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.claude_dir = Path(self.tmp.name) / ".claude"
        self.claude_dir.mkdir()
        (self.claude_dir / "projects").mkdir()

        self.project = "/imaginary/project/path"
        encoded = "-imaginary-project-path"
        self.project_root = self.claude_dir / "projects" / encoded
        self.project_root.mkdir()

        self._claude_patch = patch.object(
            list_sessions, "CLAUDE_DIR", self.claude_dir,
        )
        self._claude_patch.start()
        self.addCleanup(self._claude_patch.stop)

        # Force the shutil fallback in _remove(); no real Trash interaction.
        self._sp_patch = patch.object(
            subprocess, "run",
            return_value=subprocess.CompletedProcess(args=[], returncode=1),
        )
        self._sp_patch.start()
        self.addCleanup(self._sp_patch.stop)

        # Three sessions, all 30 days old (well past any prune threshold).
        old_time = self._time.time() - 30 * 86400
        self.uuids = [
            "aaaaaaaa-1111-1111-1111-111111111111",
            "bbbbbbbb-2222-2222-2222-222222222222",
            "cccccccc-3333-3333-3333-333333333333",
        ]
        for u in self.uuids:
            j = _write_session(self.project_root, u)
            self._os.utime(j, (old_time, old_time))

        # Pre-populate history so the rewrite path actually runs.
        history = self.claude_dir / "history.jsonl"
        history.write_text("\n".join(
            json.dumps({"project": self.project, "sessionId": u, "display": "x"})
            for u in self.uuids
        ) + "\n")

    def _prune(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            list_sessions.prune(self.project, "1d", confirm=True)

    def test_prune_calls_discover_only_once(self):
        with patch.object(
            list_sessions, "discover", wraps=list_sessions.discover,
        ) as spy:
            self._prune()
            self.assertEqual(
                spy.call_count, 1,
                "prune() must call discover() exactly once, not per session",
            )

    def test_prune_rewrites_history_only_once(self):
        with patch.object(
            list_sessions, "_rewrite_history",
            wraps=list_sessions._rewrite_history,
        ) as spy:
            self._prune()
            self.assertEqual(
                spy.call_count, 1,
                "prune() must batch history rewrite into one call",
            )


class SafetyTests(unittest.TestCase):
    """Defensive properties: atomic history rewrite + tight path guard in _remove."""

    def setUp(self):
        import os
        self._os = os

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.claude_dir = Path(self.tmp.name) / ".claude"
        self.claude_dir.mkdir()
        (self.claude_dir / "projects").mkdir()

        self.project = "/imaginary/project/path"
        encoded = "-imaginary-project-path"
        self.project_root = self.claude_dir / "projects" / encoded
        self.project_root.mkdir()

        self._claude_patch = patch.object(
            list_sessions, "CLAUDE_DIR", self.claude_dir,
        )
        self._claude_patch.start()
        self.addCleanup(self._claude_patch.stop)

        # Force the shutil fallback in _remove(); no real Trash interaction.
        self._sp_patch = patch.object(
            subprocess, "run",
            return_value=subprocess.CompletedProcess(args=[], returncode=1),
        )
        self._sp_patch.start()
        self.addCleanup(self._sp_patch.stop)

    # ------------------------------------------------------------------
    # Atomic history.jsonl rewrite.
    # ------------------------------------------------------------------

    def test_history_rewrite_uses_os_replace(self):
        """Rewriting history.jsonl must go through os.replace, not direct write."""
        uuid = "abc12345-1111-2222-3333-444444444444"
        _write_session(self.project_root, uuid)

        history = self.claude_dir / "history.jsonl"
        history.write_text(json.dumps({
            "project": self.project, "sessionId": uuid, "display": "x",
        }) + "\n")

        with patch.object(self._os, "replace", wraps=self._os.replace) as spy:
            buf = io.StringIO()
            with redirect_stdout(buf):
                list_sessions.delete(uuid, self.project)
            self.assertEqual(
                spy.call_count, 1,
                "history rewrite must call os.replace exactly once",
            )

    def test_history_rewrite_leaves_no_tmp_file(self):
        """The .tmp file used during atomic rewrite must be renamed away."""
        uuid = "abc12345-1111-2222-3333-444444444444"
        _write_session(self.project_root, uuid)

        history = self.claude_dir / "history.jsonl"
        history.write_text(json.dumps({
            "project": self.project, "sessionId": uuid, "display": "x",
        }) + "\n")

        buf = io.StringIO()
        with redirect_stdout(buf):
            list_sessions.delete(uuid, self.project)

        tmp = history.parent / (history.name + ".tmp")
        self.assertFalse(tmp.exists(), "history.jsonl.tmp must not survive the rewrite")
        self.assertTrue(history.exists(), "history.jsonl must exist after the rewrite")

    def test_history_rewrite_actually_filters(self):
        """End-to-end: the deleted UUID's history line is gone after delete."""
        kept_uuid    = "00000000-0000-0000-0000-000000000001"
        deleted_uuid = "00000000-0000-0000-0000-000000000002"
        _write_session(self.project_root, deleted_uuid)

        history = self.claude_dir / "history.jsonl"
        history.write_text("\n".join([
            json.dumps({"project": self.project, "sessionId": kept_uuid,    "display": "keep"}),
            json.dumps({"project": self.project, "sessionId": deleted_uuid, "display": "drop"}),
        ]) + "\n")

        buf = io.StringIO()
        with redirect_stdout(buf):
            list_sessions.delete(deleted_uuid, self.project)

        remaining = history.read_text()
        self.assertIn(kept_uuid,    remaining)
        self.assertNotIn(deleted_uuid, remaining)

if __name__ == "__main__":
    unittest.main()
