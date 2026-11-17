"""Shared helpers for small, offline tests. Never import target-project code or start a model."""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    # Never leave bytecode next to a module, especially inside a neighbouring Codex checkout.
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = previous


installer = load("claude_installer", ROOT / "scripts/install.py")
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
COMPAT = json.loads((ROOT / "codex-compat.json").read_text(encoding="utf-8"))


def codex_checkout() -> Path | None:
    """A read-only neighbouring codex-research-setup checkout of the recorded upstream version."""
    path = Path(os.environ.get("CODEX_RESEARCH_SETUP", str(ROOT.parent / "codex-research-setup")))
    if not (path / "scripts/install.py").is_file() or not (path / "VERSION").is_file():
        return None
    if (path / "VERSION").read_text(encoding="utf-8").strip() != COMPAT["upstream"]["version"]:
        return None
    return path


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "project"
        self.target.mkdir()
        self.output = io.StringIO()
        self.redirect = redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def write(self, relative, text):
        p = self.target / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def read(self, relative):
        return (self.target / relative).read_text(encoding="utf-8")

    def install(self, **kwargs):
        changes, notes = installer.make_plan(self.target, "test-revision", **kwargs)
        installer.apply_plan(self.target, changes)
        self.notes = notes
        return changes

    def snapshot(self, prefix=""):
        return {str(p.relative_to(self.target)): p.read_bytes()
                for p in self.target.rglob("*") if p.is_file() and not p.is_symlink()
                and str(p.relative_to(self.target)).startswith(prefix)}
