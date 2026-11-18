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
        paths = ("research/STATE.claude0.md", "research/GOAL_CONFIG.claude0.md", "research/notes-claude0/topic.md",
                 "research/goals-claude0/g1/SETUP.md", "research/STATE.codex0.md", "research/GOAL_CONFIG.codex0.md",
                 "research/notes-codex0/topic.md", "research/goals-codex0/g1/SETUP.md", "research/STATE.md",
                 "research/GOAL_CONFIG.md", "research/notes/topic.md", "research/goals/g1/SETUP.md", "train.py",
                 "experiments/existing/raw.txt", "README.md", "START.txt")
        for rel in paths:
            self.write(rel, "user-owned " + rel)
        self.install()
        for rel in paths:
            self.assertEqual(self.read(rel), "user-owned " + rel)

    def test_fresh_install_creates_only_claude_named_research_state(self):
        changed = [rel for rel, _, _ in self.install()]
        self.assertIn("research/STATE.claude0.md", changed)
        self.assertIn("research/GOAL_CONFIG.claude0.md", changed)
        for rel in ("research/STATE.md", "research/GOAL_CONFIG.md", "research/goals", "research/notes",
                    "research/STATE.codex0.md", "research/GOAL_CONFIG.codex0.md", "research/goals-codex0",
                    "research/notes-codex0"):
            self.assertFalse((self.target / rel).exists(), rel)
        self.assertIn("research/notes-<slot>/", self.read("research/STATE.claude0.md"))
        self.assertIn("research/goals-<slot>/", self.read("research/GOAL_CONFIG.claude0.md"))
        self.assertIn("| slot | session id | status |", self.read("research/SESSIONS.claude.md"))
        self.assertFalse(any(note.startswith("ATTENTION") for note in self.notes), self.notes)
        # Only slot 0 exists after an install; it equals the forms sessions use for later slots.
        self.assertEqual(sorted(p.name for p in (self.target / "research").iterdir()),
                         ["GOAL_CONFIG.claude0.md", "SESSIONS.claude.md", "STATE.claude0.md", "_templates"])
        for slot_file, form in (("STATE.claude0.md", "STATE.md"), ("GOAL_CONFIG.claude0.md", "GOAL_CONFIG.md"),
                                ("SESSIONS.claude.md", "SESSIONS.md")):
            self.assertEqual((self.target / "research" / slot_file).read_bytes(),
                             (self.target / "research/_templates" / form).read_bytes())

    def test_other_slots_and_the_session_map_survive_reinstalls(self):
        self.install()
        owned = {"research/SESSIONS.claude.md": "# Session slots\n| 0 | id-a | active |\n| 1 | id-b | active |\n",
                 "research/STATE.claude0.md": "slot 0 decisions\n", "research/STATE.claude1.md": "slot 1 decisions\n",
                 "research/GOAL_CONFIG.claude1.md": "slot 1 goal\n", "research/notes-claude1/topic.md": "note\n",
                 "research/goals-claude2/g1/run-state/ledger.jsonl": "{}\n"}
        for rel, text in owned.items():
            self.write(rel, text)
        self.assertEqual(self.install(), [])
        for rel, text in owned.items():
            self.assertEqual(self.read(rel), text)
        self.assertEqual(installer.check(self.target), 0)

    def test_upgrade_from_the_unnumbered_claude_names_of_5_5_0(self):
        self.earlier_release("5.5.0+claude.1")
        owned = {"research/STATE.claude.md": "decisions; see research/notes-claude/topic.md\n"}
        kept = {"research/notes-claude/topic.md": "derivation\n", "research/goals-claude/g1/run-state/ledger.jsonl": "{}\n"}
        _, legacy, payload = installer.read_package()
        untouched = payload["research/GOAL_CONFIG.claude0.md"].replace(b"research/goals-<slot>/", b"research/goals-claude/")
        self.assertIn(installer.digest(untouched), legacy["research/GOAL_CONFIG.claude.md"])
        (self.target / "research/GOAL_CONFIG.claude.md").write_bytes(untouched)
        for rel, text in (owned | kept).items():
            self.write(rel, text)
        plan, _ = installer.make_plan(self.target, "test-revision")
        self.assertEqual(sorted(rel for rel, _, new in plan if new is None),
                         ["research/GOAL_CONFIG.claude.md", "research/STATE.claude.md"])
        before = self.snapshot()
        self.write("research/STATE.claude.md", "edited by a running session after planning\n")
        with self.assertRaises(installer.Conflict):
            installer.apply_plan(self.target, plan)
        self.write("research/STATE.claude.md", owned["research/STATE.claude.md"])
        self.assertEqual(self.snapshot(), before)
        self.install()
        self.assertEqual(self.read("research/STATE.claude0.md"), owned["research/STATE.claude.md"])
        self.assertEqual((self.target / "research/GOAL_CONFIG.claude0.md").read_bytes(), payload["research/GOAL_CONFIG.claude0.md"])
        for rel in ("research/STATE.claude.md", "research/GOAL_CONFIG.claude.md"):
            self.assertFalse((self.target / rel).exists(), rel)
        for rel, text in kept.items():
            self.assertEqual(self.read(rel), text)
        self.assertEqual(sum(note.startswith("MIGRATED") for note in self.notes), 2, self.notes)
        self.assertTrue(any(note.startswith("KEPT research/notes-claude/, research/goals-claude/") for note in self.notes))
        backup = max((self.target / installer.BACKUPS).iterdir(), key=lambda p: (p / "research/STATE.claude.md").exists())
        self.assertEqual((backup / "research/STATE.claude.md").read_text(encoding="utf-8"), owned["research/STATE.claude.md"])
        self.assertEqual(installer.check(self.target), 0)
        self.assertEqual(installer.make_plan(self.target, "test-revision")[0], [])

    def earlier_release(self, version="5.4.0+claude.1"):
        """An install of an earlier release: no slot 0 files yet (by default the one that shared Codex's STATE)."""
        self.install()
        (self.target / "research/STATE.claude0.md").unlink()
        (self.target / "research/GOAL_CONFIG.claude0.md").unlink()
        meta = self.target / installer.META
        data = json.loads(meta.read_text(encoding="utf-8"))
        data["version"] = version
        meta.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_upgrade_from_shared_state_reports_and_never_copies_or_edits_it(self):
        pristine = (ROOT / "payload/shared/research/_templates/GOAL_CONFIG.md").read_text(encoding="utf-8")
        # The shared file is still unsuffixed, or the Codex installer has already carried it to its own name.
        for state, goal, goal_dir in (("research/STATE.md", "research/GOAL_CONFIG.md", "research/goals/"),
                                      ("research/STATE.codex.md", "research/GOAL_CONFIG.codex.md", "research/goals-codex/"),
                                      ("research/STATE.codex0.md", "research/GOAL_CONFIG.codex0.md", "research/goals-<slot>/")):
            with self.subTest(shared=state):
                self.earlier_release()
                self.write(state, "# Research state\nearlier decisions\n")
                self.write(goal, pristine.replace("research/goals-<slot>/", goal_dir))
                changed = [rel for rel, _, _ in self.install()]
                self.assertEqual(self.read(state), "# Research state\nearlier decisions\n")
                self.assertNotIn("earlier decisions", self.read("research/STATE.claude0.md"))
                self.assertNotIn(state, changed)
                moved = [note for note in self.notes if "starts empty" in note]
                # The untouched template of the earlier goal form carries nothing to move.
                self.assertEqual(len(moved), 1, self.notes)
                self.assertIn("research/STATE.claude0.md", moved[0])
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
        (self.target / "research/STATE.claude0.md").unlink()
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
        for rel in ("../outside", ".git/config", ".codex/config.toml", "research/STATE.md", "research/STATE.codex0.md"):
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
