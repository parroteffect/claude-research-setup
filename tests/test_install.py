"""Installer behaviour on a Claude-only project."""
from __future__ import annotations

import json
from pathlib import Path
import unittest
import unittest.mock

from _common import ROOT, MANIFEST, ProjectCase, installer


class InstallerTests(ProjectCase):
    def test_dry_run_writes_nothing(self):
        changes, _ = installer.make_plan(self.target, "test")
        self.assertGreater(len(changes), 5)
        self.assertEqual(self.snapshot(), {})

    def test_fresh_install_passes_static_check_and_never_creates_codex_files(self):
        self.install()
        self.assertEqual(installer.check(self.target), 0)
        self.assertFalse((self.target / ".codex").exists())
        self.assertFalse((self.target / "AGENTS.md").exists())
        self.assertFalse((self.target / ".claude/settings.json").exists())
        self.assertFalse((self.target / ".claude/settings.local.json").exists())

    def test_reinstall_is_idempotent(self):
        self.install()
        before = self.snapshot()
        changes, _ = installer.make_plan(self.target, "test-revision")
        self.assertEqual(changes, [])
        installer.apply_plan(self.target, changes)
        self.assertEqual(before, self.snapshot())

    def test_existing_claude_md_text_and_settings_preserved(self):
        old = "# Project instructions\nUse existing style and preserve data.\n"
        settings = '{"model": "chosen-model", "permissions": {"deny": ["Bash(rm:*)"]}}\n'
        self.write("CLAUDE.md", old)
        self.write(".claude/settings.json", settings)
        self.install()
        text = self.read("CLAUDE.md")
        self.assertTrue(text.startswith(old))
        self.assertEqual(text.count(installer.BEGIN), 1)
        self.assertEqual(self.read(".claude/settings.json"), settings)

    def test_state_code_results_and_readme_preserved(self):
        paths = ("research/STATE.claude.md", "research/GOAL_CONFIG.claude.md", "research/notes-claude/topic.md",
                 "research/goals-claude/g1/SETUP.md", "research/STATE.codex.md", "research/GOAL_CONFIG.codex.md",
                 "research/notes-codex/topic.md", "research/goals-codex/g1/SETUP.md", "research/STATE.md",
                 "research/GOAL_CONFIG.md", "research/notes/topic.md", "research/goals/g1/SETUP.md", "train.py",
                 "experiments/existing/raw.txt", "README.md", "START.txt")
        for rel in paths:
            self.write(rel, "user-owned " + rel)
        self.install()
        for rel in paths:
            self.assertEqual(self.read(rel), "user-owned " + rel)

    def test_fresh_install_creates_only_claude_named_research_state(self):
        changed = [rel for rel, _, _ in self.install()]
        self.assertIn("research/STATE.claude.md", changed)
        self.assertIn("research/GOAL_CONFIG.claude.md", changed)
        for rel in ("research/STATE.md", "research/GOAL_CONFIG.md", "research/goals", "research/notes",
                    "research/STATE.codex.md", "research/GOAL_CONFIG.codex.md", "research/goals-codex",
                    "research/notes-codex"):
            self.assertFalse((self.target / rel).exists(), rel)
        self.assertIn("research/notes-claude/", self.read("research/STATE.claude.md"))
        self.assertIn("research/goals-claude/", self.read("research/GOAL_CONFIG.claude.md"))
        self.assertFalse(any(note.startswith("ATTENTION") for note in self.notes), self.notes)

    def earlier_release(self, version="5.4.0+claude.1"):
        """An install of the release that kept Claude's records in the unsuffixed files: no *.claude.md yet."""
        self.install()
        (self.target / "research/STATE.claude.md").unlink()
        (self.target / "research/GOAL_CONFIG.claude.md").unlink()
        meta = self.target / installer.META
        data = json.loads(meta.read_text(encoding="utf-8"))
        data["version"] = version
        meta.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_upgrade_from_shared_state_reports_and_never_copies_or_edits_it(self):
        pristine = (ROOT / "payload/research/GOAL_CONFIG.claude.md").read_text(encoding="utf-8")
        # The shared file is still unsuffixed, or the Codex installer has already carried it to its own name.
        for state, goal, goal_dir in (("research/STATE.md", "research/GOAL_CONFIG.md", "research/goals/"),
                                      ("research/STATE.codex.md", "research/GOAL_CONFIG.codex.md", "research/goals-codex/")):
            with self.subTest(shared=state):
                self.earlier_release()
                self.write(state, "# Research state\nearlier decisions\n")
                self.write(goal, pristine.replace("research/goals-claude/", goal_dir))
                changed = [rel for rel, _, _ in self.install()]
                self.assertEqual(self.read(state), "# Research state\nearlier decisions\n")
                self.assertNotIn("earlier decisions", self.read("research/STATE.claude.md"))
                self.assertNotIn(state, changed)
                moved = [note for note in self.notes if "starts empty" in note]
                # The untouched template of the earlier goal form carries nothing to move.
                self.assertEqual(len(moved), 1, self.notes)
                self.assertIn("research/STATE.claude.md", moved[0])
                self.assertIn(state, moved[0])
                self.assertTrue(moved[0].startswith("ATTENTION"))
                # Once Claude's own state exists the reminder is not repeated.
                self.install()
                self.assertFalse(any("starts empty" in note for note in self.notes), self.notes)
                (self.target / state).unlink()
                (self.target / goal).unlink()

    def test_unsuffixed_state_of_unknown_origin_is_reported_once_and_left_alone(self):
        self.write("research/STATE.md", "someone's earlier record\n")
        self.install()
        self.assertEqual(sum("starts empty" in note for note in self.notes), 1, self.notes)
        self.assertEqual(self.read("research/STATE.md"), "someone's earlier record\n")
        # A current install that merely lost its state file is not an upgrade from the shared layout.
        (self.target / "research/STATE.claude.md").unlink()
        self.install()
        self.assertFalse(any("starts empty" in note for note in self.notes), self.notes)

    def test_custom_engineer_conflict_prevents_all_writes(self):
        self.write(".claude/agents/engineer.md", "---\nname: engineer\ndescription: custom\n---\nkeep\n")
        before = self.snapshot()
        with self.assertRaises(installer.Conflict):
            installer.make_plan(self.target, "test")
        self.assertEqual(before, self.snapshot())

    def test_custom_guide_conflict_prevents_all_writes(self):
        self.write(".claude/research-workflow/guides/research.md", "custom research rules")
        before = self.snapshot()
        with self.assertRaises(installer.Conflict):
            installer.make_plan(self.target, "test")
        self.assertEqual(before, self.snapshot())

    def test_modified_managed_block_not_overwritten(self):
        self.install()
        p = self.target / "CLAUDE.md"
        p.write_text(p.read_text(encoding="utf-8").replace("# Research workflow", "# Local changes"), encoding="utf-8")
        before = self.snapshot()
        with self.assertRaises(installer.Conflict):
            installer.make_plan(self.target, "new-version")
        self.assertEqual(before, self.snapshot())

    def test_unknown_block_without_metadata_is_not_trusted(self):
        self.install()
        p = self.target / "CLAUDE.md"
        p.write_text(p.read_text(encoding="utf-8").replace("# Research workflow", "# Research workflow\nLocal rule"),
                     encoding="utf-8")
        (self.target / installer.META).unlink()
        with self.assertRaises(installer.Conflict):
            installer.make_plan(self.target, "test")

    def test_edits_outside_managed_block_preserved_without_metadata_churn(self):
        self.install()
        p = self.target / "CLAUDE.md"
        p.write_text("# New project rule\n" + p.read_text(encoding="utf-8") + "\nTrailing rule\n", encoding="utf-8")
        self.assertEqual(installer.make_plan(self.target, "test-revision")[0], [])
        self.assertTrue(self.read("CLAUDE.md").startswith("# New project rule"))

    def test_recorded_clean_block_and_tracked_file_upgrade(self):
        manifest, legacy, payload = installer.read_package()
        old = dict(payload, **{"CLAUDE.md": b"# Earlier workflow\n",
                               ".claude/research-workflow/guides/monk.md": b"earlier guide\n"})
        with unittest.mock.patch.object(installer, "read_package", return_value=(manifest, legacy, old)):
            self.install()
        self.assertIn("# Earlier workflow", self.read("CLAUDE.md"))
        self.install()
        self.assertIn("# Research workflow", self.read("CLAUDE.md"))
        self.assertNotIn("# Earlier workflow", self.read("CLAUDE.md"))
        self.assertNotEqual(self.read(".claude/research-workflow/guides/monk.md"), "earlier guide\n")
        self.assertEqual(installer.check(self.target), 0)

    def test_backups_preserve_exact_prior_bytes(self):
        old = b"# User rules\nDo not delete results.\n"
        self.write("CLAUDE.md", old.decode())
        self.install()
        backups = list((self.target / installer.BACKUPS).iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "CLAUDE.md").read_bytes(), old)
        records = json.loads((backups[0] / "RESTORE.json").read_text(encoding="utf-8"))
        self.assertTrue(any(r["path"] == "CLAUDE.md" and r["existed"] for r in records))

    def test_gitignore_preserves_existing_and_is_idempotent(self):
        self.write(".gitignore", "data/\n# keep\n")
        self.install()
        self.install()
        text = self.read(".gitignore")
        self.assertTrue(text.startswith("data/\n# keep\n"))
        self.assertEqual(text.count(installer.IGNORE_BEGIN), 1)
        self.assertIn("/.claude/research-workflow/backups/", text)

    def test_role_pins_and_nested_spawn_are_detected(self):
        self.install()
        p = self.target / ".claude/agents/engineer.md"
        original = p.read_text(encoding="utf-8")
        for bad in (original.replace("effort: high", "effort: max"),
                    original.replace("effort: high\n", ""),
                    original.replace("effort: high", "effort: high\nmodel: opus"),
                    original.replace("disallowedTools: Agent\n", ""),
                    original.replace("disallowedTools: Agent", "tools: Read, Agent, Bash"),
                    original.replace("name: engineer", "name: builder"),
                    "no frontmatter\n"):
            p.write_text(bad, encoding="utf-8")
            with self.subTest(bad=bad[:80]):
                self.assertEqual(installer.check(self.target), 2)
        p.write_text(original.replace("disallowedTools: Agent", "tools: Read, Grep, Bash"), encoding="utf-8")
        self.assertEqual(installer.check(self.target), 0)

    def test_duplicate_role_fails_before_writes(self):
        self.write(".claude/agents/another.md", "---\nname: qa\ndescription: duplicate\n---\nkeep\n")
        before = self.snapshot()
        with self.assertRaises(installer.Conflict):
            installer.make_plan(self.target, "test")
        self.assertEqual(self.snapshot(), before)

    def test_duplicate_block_in_nested_claude_md_fails(self):
        self.write(".claude/CLAUDE.md", installer.BEGIN + "\ncopy\n" + installer.END + "\n")
        with self.assertRaises(installer.Conflict):
            installer.make_plan(self.target, "test")

    def test_symlinks_are_not_followed(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        try:
            (self.target / ".claude").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink creation unavailable")
        with self.assertRaises(installer.Conflict):
            installer.make_plan(self.target, "test")
        self.assertEqual(list(outside.iterdir()), [])

    def test_home_source_root_and_escape_rejected(self):
        for value in (str(Path.home()), str(Path.home() / ".claude"), str(ROOT), str(ROOT / "payload"),
                      str(Path(self.tmp.name).anchor)):
            with self.assertRaises(installer.Conflict):
                installer.target_root(value)
        for rel in ("../outside", ".git/config", ".codex/config.toml", "research/STATE.md", "research/STATE.codex.md"):
            with self.assertRaises(installer.Conflict):
                installer.safe_path(self.target, rel)

    def test_provenance_has_no_absolute_target_path(self):
        self.install()
        meta = self.read(installer.META)
        self.assertNotIn(str(self.target), meta)
        data = json.loads(meta)
        self.assertEqual(data["runtime_status"], "NOT_VERIFIED")
        self.assertEqual(data["upstream"], MANIFEST["upstream"])

    def test_concurrent_change_detected_before_write(self):
        self.write("CLAUDE.md", "# Before\n")
        changes, _ = installer.make_plan(self.target, "test")
        self.write("CLAUDE.md", "# Changed concurrently\n")
        before = self.snapshot()
        with self.assertRaises(installer.Conflict):
            installer.apply_plan(self.target, changes)
        self.assertEqual(before, self.snapshot())

    def test_malformed_markers_fail_closed(self):
        self.write("CLAUDE.md", installer.BEGIN + "\nmissing end\n")
        with self.assertRaises(installer.Conflict):
            installer.make_plan(self.target, "test")

    def test_claude_only_shared_template_update_rules(self):
        rel = "research/_templates/CANDIDATE.md"
        self.install()
        current = self.read(rel)
        meta_path = self.target / installer.META
        # An unmodified earlier copy that this package created is updated...
        self.write(rel, "earlier release\n")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["shared_hashes"][rel] = installer.digest(b"earlier release\n")
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.install()
        self.assertEqual(self.read(rel), current)
        # ...but a locally edited one is preserved and reported, never overwritten.
        self.write(rel, "my own template\n")
        self.install()
        self.assertEqual(self.read(rel), "my own template\n")
        self.assertTrue(any("PRESERVED shared " + rel in note for note in self.notes))
        self.assertEqual(installer.check(self.target), 0)

    def test_effort_override_in_project_settings_is_reported(self):
        self.install()
        self.write(".claude/settings.json", '{"env": {"CLAUDE_CODE_EFFORT_LEVEL": "max"}}\n')
        self.output.truncate(0)
        self.assertEqual(installer.check(self.target), 0)
        self.assertIn("REVIEW CLAUDE_CODE_EFFORT_LEVEL is set in .claude/settings.json", self.output.getvalue())


if __name__ == "__main__":
    unittest.main()
