"""Both workflows in one project: namespaces, shared files, and real cross-installer runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from _common import ROOT, MANIFEST, COMPAT, ProjectCase, installer, load, codex_checkout

CODEX = codex_checkout()
codex_installer = load("codex_installer", CODEX / "scripts/install.py") if CODEX else None
PROJECT_RULE = "# Project instructions\nKeep raw data read-only.\n"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LayoutTests(ProjectCase):
    """Static guarantees that need no Codex checkout."""

    def test_manifest_stays_out_of_codex_namespace(self):
        for item in MANIFEST["files"]:
            dest = Path(item["destination"])
            self.assertNotEqual(dest.parts[0], ".codex", item)
            if item["mode"] == "codex-note":
                self.assertEqual(item["destination"], "AGENTS.md")
            else:
                self.assertFalse(dest.name.startswith("AGENTS"), item)
            if item["mode"] in ("managed-file", "claude-block"):
                self.assertTrue(dest.parts[0] in (".claude", "CLAUDE.md"), item)
        self.assertTrue(installer.META.startswith(".claude/research-workflow/"))
        self.assertTrue(installer.BACKUPS.startswith(".claude/research-workflow/"))

    def test_markers_cannot_be_confused_with_codex_markers(self):
        ours = (installer.BEGIN, installer.END, installer.NOTE_BEGIN, installer.NOTE_END,
                installer.IGNORE_BEGIN, installer.IGNORE_END)
        theirs = (installer.CODEX_BEGIN, installer.CODEX_END,
                  "# BEGIN CODEX RESEARCH WORKFLOW", "# END CODEX RESEARCH WORKFLOW")
        for a in ours:
            for b in theirs + tuple(x for x in ours if x != a):
                self.assertNotIn(a, b)
                self.assertNotIn(b, a)

    def test_shared_and_identical_files_match_recorded_codex_release(self):
        by_source = {item["source"]: item for item in MANIFEST["files"]}
        shared = {item["destination"] for item in MANIFEST["files"] if item["mode"] in ("create-only", "shared-file")}
        recorded = {entry["destination"] for entry in COMPAT["identical"] if entry["shared_destination"]}
        self.assertEqual(shared, recorded)
        for entry in COMPAT["identical"]:
            data = (ROOT / entry["claude_source"]).read_bytes()
            self.assertEqual(sha(data), entry["sha256"], entry["claude_source"])
            self.assertEqual(by_source[entry["claude_source"]]["sha256"], entry["sha256"])
        self.assertEqual(COMPAT["upstream"], MANIFEST["upstream"])

    def test_installer_refuses_any_codex_write(self):
        for rel in (".codex/config.toml", ".codex/agents/engineer.toml", ".codex/research-workflow-install.json"):
            with self.assertRaises(installer.Conflict):
                installer.safe_path(self.target, rel)
        self.assertEqual(installer.safe_path(self.target, ".codex/tools/goal_guard.py", write=False),
                         self.target / ".codex/tools/goal_guard.py")

    def test_project_agents_fallback_loss_is_reported(self):
        self.write("AGENTS.md", PROJECT_RULE)
        _, notes = installer.make_plan(self.target, "test")
        self.assertTrue(any("only while no CLAUDE.md exists" in note for note in notes))
        # No Codex workflow here, so AGENTS.md itself is left alone.
        self.install()
        self.assertEqual(self.read("AGENTS.md"), PROJECT_RULE)
        # Once the project already has its own CLAUDE.md the fallback was not in use.
        self.assertFalse(any("only while no CLAUDE.md exists" in note
                             for note in installer.make_plan(self.target, "test")[1]))

    def test_claude_md_symlink_to_agents_is_blocked_without_writes(self):
        self.write("AGENTS.md", PROJECT_RULE)
        try:
            (self.target / "CLAUDE.md").symlink_to("AGENTS.md")
        except OSError:
            self.skipTest("Symlink creation unavailable")
        with self.assertRaises(installer.Conflict) as caught:
            installer.make_plan(self.target, "test")
        self.assertIn("symlink", str(caught.exception))
        self.assertEqual(self.read("AGENTS.md"), PROJECT_RULE)

    def test_import_of_agents_md_is_noted(self):
        self.write("CLAUDE.md", "# Mine\n@AGENTS.md\n")
        _, notes = installer.make_plan(self.target, "test")
        self.assertTrue(any("imports AGENTS.md" in note for note in notes))


@unittest.skipUnless(CODEX, "no codex-research-setup checkout of the recorded upstream version next to this repo")
class CrossInstallerTests(ProjectCase):
    """Run the real Codex installer and this one against the same temporary project."""

    def codex_install(self):
        changes, _ = codex_installer.make_plan(self.target, "codex-test")
        codex_installer.apply_plan(self.target, changes)
        return [rel for rel, _, _ in changes]

    def codex_block(self):
        text = self.read("AGENTS.md")
        return text[text.index(installer.CODEX_BEGIN):text.index(installer.CODEX_END) + len(installer.CODEX_END)]

    def claude_owned(self):
        files = self.snapshot(".claude/")
        files["CLAUDE.md"] = (self.target / "CLAUDE.md").read_bytes()
        files.pop(installer.META, None)
        return {k: v for k, v in files.items() if not k.startswith(installer.BACKUPS)}

    def assert_both_pass(self):
        self.assertEqual(codex_installer.check(self.target), 0, self.output.getvalue())
        self.assertEqual(installer.check(self.target), 0, self.output.getvalue())

    def test_codex_first_then_claude(self):
        self.write("AGENTS.md", PROJECT_RULE)
        self.write(".codex/config.toml", 'model = "chosen-model"\nmodel_reasoning_effort = "max"\n')
        self.codex_install()
        codex_files, block = self.snapshot(".codex/"), self.codex_block()
        templates = self.snapshot("experiments/") | self.snapshot("research/")
        changed = [rel for rel, _, _ in self.install()]
        self.assertEqual(self.snapshot(".codex/"), codex_files)
        self.assertEqual(self.codex_block(), block)
        self.assertEqual(self.snapshot("experiments/") | self.snapshot("research/"), templates)
        self.assertFalse(any(rel.startswith(("research/", "experiments/", ".codex")) for rel in changed))
        agents = self.read("AGENTS.md")
        self.assertTrue(agents.startswith(PROJECT_RULE))
        self.assertEqual(agents.count(installer.NOTE_BEGIN), 1)
        self.assertGreater(agents.index(installer.NOTE_BEGIN), agents.index(installer.CODEX_END))
        self.assertTrue(any(note.startswith("CODEX_DETECTED") for note in self.notes))
        self.assertTrue(any("only while no CLAUDE.md exists" in note for note in self.notes))
        self.assert_both_pass()

    def test_claude_first_then_codex(self):
        self.install()
        self.assertFalse((self.target / "AGENTS.md").exists())
        owned = self.claude_owned()
        self.codex_install()
        self.assertEqual(self.claude_owned(), owned)
        for entry in COMPAT["identical"]:
            if entry["shared_destination"] and entry["destination"] not in ("research/STATE.md", "research/GOAL_CONFIG.md"):
                self.assertEqual(sha((self.target / entry["destination"]).read_bytes()), entry["sha256"])
        # Re-running this installer now tells Codex about the Claude workflow, and nothing else.
        changed = sorted(rel for rel, _, _ in self.install())
        self.assertEqual(changed, sorted(["AGENTS.md", installer.META]))
        self.assertEqual(self.claude_owned(), owned)
        self.assert_both_pass()

    def test_alternating_reinstalls_converge_without_conflicts(self):
        self.codex_install()
        self.install()
        block, owned = self.codex_block(), self.claude_owned()
        for _ in range(2):
            # Codex only refreshes its own metadata hash of AGENTS.md after the appended note.
            self.assertLessEqual(set(self.codex_install()), {codex_installer.META})
            self.install()
        self.assertEqual(codex_installer.make_plan(self.target, "codex-test")[0], [])
        self.assertEqual(installer.make_plan(self.target, "test-revision")[0], [])
        self.assertEqual(self.codex_block(), block)
        self.assertEqual(self.claude_owned(), owned)
        ignore = self.read(".gitignore")
        self.assertEqual(ignore.count("# BEGIN CODEX RESEARCH WORKFLOW"), 1)
        self.assertEqual(ignore.count(installer.IGNORE_BEGIN), 1)
        self.assert_both_pass()

    def test_installed_copies_share_one_guard_and_state_vocabulary(self):
        self.codex_install()
        self.install()
        self.assertEqual((self.target / installer.CODEX_GUARD).read_bytes(), (self.target / installer.GUARD).read_bytes())
        self.assertEqual(json.loads(self.read(installer.CODEX_META))["version"], MANIFEST["upstream"]["version"])
        self.assertFalse(any(note.startswith("ATTENTION") for note in self.notes), self.notes)

    def test_no_codex_note_flag_leaves_agents_md_untouched(self):
        self.codex_install()
        before = self.read("AGENTS.md")
        self.install(codex_note=False)
        self.assertEqual(self.read("AGENTS.md"), before)
        self.assertTrue(any(note.startswith("SKIPPED") for note in self.notes))
        self.output.truncate(0)
        self.assertEqual(installer.check(self.target), 0)
        self.assertIn("REVIEW Codex is installed but AGENTS.md has no coexistence note", self.output.getvalue())

    def test_edited_coexistence_note_is_not_overwritten(self):
        self.codex_install()
        self.install()
        agents = self.target / "AGENTS.md"
        agents.write_text(agents.read_text(encoding="utf-8").replace(
            installer.NOTE_END, "- local addition\n" + installer.NOTE_END), encoding="utf-8")
        before = self.snapshot()
        with self.assertRaises(installer.Conflict):
            installer.make_plan(self.target, "test")
        self.assertEqual(self.snapshot(), before)

    def test_codex_owned_templates_are_never_overwritten(self):
        self.codex_install()
        rel = "research/_templates/CANDIDATE.md"
        self.write(rel, "a newer Codex release\n")
        self.install()
        self.assertEqual(self.read(rel), "a newer Codex release\n")
        self.assertTrue(any("owned by the Codex workflow" in note for note in self.notes))

    def test_version_and_guard_drift_are_reported_not_repaired(self):
        self.codex_install()
        guard = self.target / installer.CODEX_GUARD
        meta = self.target / installer.CODEX_META
        guard_before = guard.read_bytes()
        data = json.loads(meta.read_text(encoding="utf-8"))
        data["version"] = "9.9.9"
        meta.write_text(json.dumps(data), encoding="utf-8")
        guard.write_bytes(guard_before + b"\n# newer upstream\n")
        codex_files = self.snapshot(".codex/")
        self.install()
        self.assertTrue(any("policy revisions differ" in note for note in self.notes))
        self.assertTrue(any("goal guard copies differ" in note for note in self.notes))
        self.assertEqual(self.snapshot(".codex/"), codex_files)
        self.output.truncate(0)
        self.assertEqual(installer.check(self.target), 0)
        self.assertIn("REVIEW goal guard copies differ", self.output.getvalue())

    def test_agents_md_size_budget_warning(self):
        self.write("AGENTS.md", "# Project\n" + "x" * 6000 + "\n")
        self.codex_install()
        _, notes = installer.make_plan(self.target, "test")
        self.assertTrue(any("32 KiB" in note for note in notes))


@unittest.skipUnless(CODEX, "no codex-research-setup checkout of the recorded upstream version next to this repo")
class UpstreamParityTests(unittest.TestCase):
    """The port keeps the upstream policy structure and the byte-identical shared files."""

    def test_recorded_hashes_match_the_actual_codex_payload(self):
        for entry in COMPAT["identical"]:
            self.assertEqual(sha((CODEX / entry["codex_source"]).read_bytes()), entry["sha256"], entry["codex_source"])
        codex_manifest = json.loads((CODEX / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(codex_manifest["version"], COMPAT["upstream"]["version"])
        codex_modes = {item["destination"]: item["mode"] for item in codex_manifest["files"]}
        for item in MANIFEST["files"]:
            if item["mode"] == "create-only":
                self.assertEqual(codex_modes[item["destination"]], "create-only")
            if item["mode"] == "shared-file":
                self.assertEqual(codex_modes[item["destination"]], "managed-file")

    def test_every_upstream_policy_and_guide_heading_survives(self):
        def headings(path):
            return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("#")]
        pairs = [(CODEX / "payload/AGENTS.md", ROOT / "payload/CLAUDE.block.md")]
        for guide in sorted((CODEX / "payload/.codex/guides").glob("*.md")):
            pairs.append((guide, ROOT / "payload/.claude/research-workflow/guides" / guide.name))
        for upstream, ported in pairs:
            ours = set(headings(ported))
            for heading in headings(upstream):
                self.assertIn(heading, ours, f"{ported.name} lost upstream heading {heading!r}")
        self.assertEqual(sorted(p.stem for p in (CODEX / "payload/.codex/agents").glob("*.toml")),
                         sorted(p.stem for p in (ROOT / "payload/.claude/agents").glob("*.md")))


if __name__ == "__main__":
    unittest.main()
