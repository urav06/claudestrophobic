#!/usr/bin/env python3
"""Regression check: sessions_delete must not traverse outside the project's own dir."""

from __future__ import annotations

import io
import contextlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import cc
import store


def test_sessions_delete_rejects_path_traversal():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        proj_a, proj_b = root / "proj-a", root / "proj-b"
        proj_a.mkdir()
        proj_b.mkdir()
        victim = proj_b / "deadbeef-1111-uuid.jsonl"
        victim.write_text('{"type":"user"}\n')

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), \
             patch.object(store, "project_dir", return_value=proj_a), \
             patch.object(store, "active_ids", return_value=set()):
            cc.sessions_delete("unused", "../proj-b/deadbeef")

        assert victim.exists(), f"path traversal deleted a file outside the target project: {buf.getvalue()}"
        assert "No session matches" in buf.getvalue()


if __name__ == "__main__":
    test_sessions_delete_rejects_path_traversal()
    print("ok")
