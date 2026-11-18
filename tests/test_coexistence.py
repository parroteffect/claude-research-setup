"""Both workflows in one project: separate namespaces and research state, shared templates, real cross-installer runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from _common import ROOT, MANIFEST, COMPAT, ProjectCase, installer, load, codex_checkout

CODEX = codex_checkout()
codex_installer = load("codex_installer", CODEX / "scripts/install.py") if CODEX else None
PROJECT_RULE = "# Project instructions\nKeep raw data read-only.\n"
CLAUDE_STATE = ("research/STATE.claude.md", "research/GOAL_CONFIG.claude.md")
CODEX_STATE = ("research/STATE.codex.md", "research/GOAL_CONFIG.codex.md")
UNSUFFIXED_STATE = ("research/STATE.md", "research/GOAL_CONFIG.md")  # the layout before Codex 5.5.0


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
            if item["mode"] != "codex-note":
                self.assertFalse(installer.codex_owned(item["destination"]), item)
        created = {item["destination"] for item in MANIFEST["files"] if item["mode"] == "create-only"}
        self.assertEqual(created, set(CLAUDE_STATE))
        self.assertEqual([installer.SPLIT_FROM[rel] for rel in CLAUDE_STATE], list(zip(UNSUFFIXED_STATE, CODEX_STATE)))
        # Every research-state name carries its harness; this package installs none without one.
        for item in MANIFEST["files"]:
            dest = Path(item["destination"])
            if dest.parts[0] == "research" and "_templates" not in dest.parts:
                self.assertTrue(dest.name.endswith(".claude.md"), item)
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
        shared = {item["destination"] for item in MANIFEST["files"] if item["mode"] == "shared-file"}
        recorded = {entry["destination"] for entry in COMPAT["identical"] if entry["shared_destination"]}
        self.assertEqual(shared, recorded)
        # Only read-only form templates are shared; no research state lives at a shared path.
        for rel in shared:
            self.assertIn("_templates", Path(rel).parts, rel)
        for entry in COMPAT["identical"]:
            data = (ROOT / entry["claude_source"]).read_bytes()
            self.assertEqual(sha(data), entry["sha256"], entry["claude_source"])
            self.assertEqual(by_source[entry["claude_source"]]["sha256"], entry["sha256"])
        self.assertEqual(COMPAT["upstream"], MANIFEST["upstream"])

    def test_derived_files_differ_from_the_codex_release_only_by_their_paths(self):
        by_source = {item["source"]: item for item in MANIFEST["files"]}
        self.assertLessEqual(set(CLAUDE_STATE), {entry["destination"] for entry in COMPAT["derived"]})
        for entry in COMPAT["derived"]:
            data = (ROOT / entry["claude_source"]).read_bytes()
            self.assertEqual(by_source[entry["claude_source"]]["destination"], entry["destination"])
            self.assertNotEqual(entry["destination"], entry["codex_destination"])
            for ours, theirs in entry["claude_to_codex"]:
                self.assertIn(ours.encode(), data, entry["claude_source"])
                data = data.replace(ours.encode(), theirs.encode())
            self.assertEqual(sha(data), entry["codex_sha256"], entry["claude_source"])

    def test_installer_refuses_any_codex_write(self):
        for rel in (".codex/config.toml", ".codex/agents/engineer.toml", ".codex/research-workflow-install.json",
                    "research/STATE.codex.md", "research/GOAL_CONFIG.codex.md",
                    "research/goals-codex/g1/run-state/ledger.jsonl", "research/notes-codex/topic.md",
                    "research/goals-codex", "research/notes-codex",
                    "research/STATE.md", "research/GOAL_CONFIG.md", "research/goals/g1/run-state/ledger.jsonl",
                    "research/notes/topic.md", "research/goals", "research/notes"):
            with self.assertRaises(installer.Conflict):
                installer.safe_path(self.target, rel)
        for rel in CLAUDE_STATE + ("research/goals-claude/g1/SETUP.md", "research/notes-claude/topic.md",
                                   "research/_templates/CANDIDATE.md"):
            self.assertEqual(installer.safe_path(self.target, rel), self.target / rel)
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
        for rel in CLAUDE_STATE:
            files[rel] = (self.target / rel).read_bytes()
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
        # Everything Codex installed is untouched; Claude only adds its own two state files.
        after = self.snapshot("experiments/") | self.snapshot("research/")
        self.assertEqual({rel: data for rel, data in after.items() if rel not in CLAUDE_STATE}, templates)
        self.assertEqual(sorted(rel for rel in changed if rel.startswith(("research/", "experiments/", ".codex"))),
                         sorted(CLAUDE_STATE))
        self.assertFalse(any("starts empty" in note for note in self.notes), self.notes)
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
        for rel in CODEX_STATE:
            self.assertFalse((self.target / rel).exists(), rel)
        created = self.codex_install()
        self.assertEqual(self.claude_owned(), owned)
        # Codex creates its own state next to Claude's instead of adopting it.
        for rel in CODEX_STATE:
            self.assertIn(rel, created)
        for entry in COMPAT["identical"]:
            if entry["shared_destination"]:
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
        # Separate files, same form: either harness can read the other's state when the user asks.
        for ours, theirs in zip(CLAUDE_STATE, CODEX_STATE):
            self.assertNotEqual(self.read(ours), self.read(theirs))
            self.assertEqual([line for line in self.read(ours).splitlines() if line.startswith("#")],
                             [line for line in self.read(theirs).splitlines() if line.startswith("#")])

    def test_each_harness_keeps_its_own_research_state_across_reinstalls(self):
        self.codex_install()
        self.install()
        records = {"research/STATE.codex.md": "# Codex state\ncodex decision\n",
                   "research/GOAL_CONFIG.codex.md": "# Codex goal\n",
                   "research/goals-codex/g1/run-state/ledger.jsonl": "{}\n",
                   "research/notes-codex/topic.md": "codex note\n",
                   "research/goals/g0/run-state/ledger.jsonl": "{}\n",
                   "research/notes/earlier.md": "note of the earlier layout\n",
                   "research/STATE.claude.md": "# Claude state\nclaude decision\n",
                   "research/GOAL_CONFIG.claude.md": "# Claude goal\n",
                   "research/goals-claude/g1/run-state/ledger.jsonl": "{}\n",
                   "research/notes-claude/topic.md": "claude note\n",
                   "experiments/exp-a/SPEC.md": "spec\n"}
        for rel, text in records.items():
            self.write(rel, text)
        for _ in range(2):
            self.install()
            self.codex_install()
        for rel, text in records.items():
            self.assertEqual(self.read(rel), text, rel)
        self.assertFalse(any("starts empty" in note for note in self.notes), self.notes)
        self.assert_both_pass()

    def test_note_tells_codex_which_research_state_is_whose(self):
        self.codex_install()
        self.install()
        agents = self.read("AGENTS.md")
        note = agents[agents.index(installer.NOTE_BEGIN):agents.index(installer.NOTE_END)]
        for needle in CLAUDE_STATE + CODEX_STATE + ("research/goals-claude/", "research/notes-claude/",
                                                    "research/goals-codex/", "research/notes-codex/",
                                                    "자동으로 읽지 않는다", "사용자가 지시하면", "~/.claude/projects/"):
            self.assertIn(needle, note)
        self.assertLess(len(agents.encode()), installer.CODEX_DOC_LIMIT)
        # The Codex block itself names only Codex's paths.
        for rel in CLAUDE_STATE:
            self.assertNotIn(rel, self.codex_block())

    def shared_layout_project(self):
        """Codex 5.4.0 and Claude 5.4.0+claude.1 in one project: both wrote research/STATE.md."""
        self.codex_install()
        self.install()
        shared = {"research/STATE.md": "# Research state\ncodex and claude decisions\n",
                  "research/GOAL_CONFIG.md": "User objective and finite budget\n"}
        for rel in CLAUDE_STATE + CODEX_STATE:
            (self.target / rel).unlink()
        for rel, text in shared.items():
            self.write(rel, text)
        meta = self.target / installer.META
        data = json.loads(meta.read_text(encoding="utf-8"))
        data["version"] = "5.4.0+claude.1"
        meta.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return shared

    def assert_split(self, shared):
        _, _, payload = installer.read_package()
        for ours, theirs, earlier in zip(CLAUDE_STATE, CODEX_STATE, UNSUFFIXED_STATE):
            self.assertEqual(self.read(theirs), shared[earlier])
            self.assertEqual((self.target / ours).read_bytes(), payload[ours])
            self.assertFalse((self.target / earlier).exists(), earlier)
        self.assert_both_pass()
        self.assertEqual(codex_installer.make_plan(self.target, "codex-test")[0], [])
        self.assertEqual(installer.make_plan(self.target, "test-revision")[0], [])

    def test_shared_layout_upgrade_codex_first(self):
        shared = self.shared_layout_project()
        self.assertTrue(any(new is None for _, _, new in codex_installer.make_plan(self.target, "codex-test")[0]))
        self.codex_install()
        self.install()
        # Codex already carried the shared file to its own name; Claude points there and copies nothing.
        told = [note for note in self.notes if "starts empty" in note]
        self.assertEqual(len(told), 2, self.notes)
        self.assertTrue(all(rel in " ".join(told) for rel in CODEX_STATE), told)
        self.codex_install()
        self.assert_split(shared)

    def test_shared_layout_upgrade_claude_first(self):
        shared = self.shared_layout_project()
        self.install()
        told = [note for note in self.notes if "starts empty" in note]
        self.assertEqual(len(told), 2, self.notes)
        for rel, text in shared.items():
            self.assertEqual(self.read(rel), text)  # Claude never moves or edits the shared file
        self.codex_install()
        self.install()
        self.codex_install()
        self.assert_split(shared)

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
                # Claude's state is never a path the Codex package installs; its counterpart is create-only there.
                self.assertNotIn(item["destination"], codex_modes)
                self.assertEqual(codex_modes[installer.SPLIT_FROM[item["destination"]][1]], "create-only")
            if item["mode"] == "shared-file":
                self.assertEqual(codex_modes[item["destination"]], "managed-file")
        for entry in COMPAT["derived"]:
            self.assertEqual(sha((CODEX / entry["codex_source"]).read_bytes()), entry["codex_sha256"],
                             entry["codex_source"])
        for rel in CODEX_STATE:
            self.assertIn(rel, codex_modes)
            self.assertTrue(installer.codex_owned(rel))
        # What Codex carries over on upgrade is exactly what this package treats as the earlier layout.
        carried = {item["destination"]: item["migrate_from"] for item in codex_manifest["files"] if "migrate_from" in item}
        self.assertEqual(carried, dict(zip(CODEX_STATE, UNSUFFIXED_STATE)))
        for rel in UNSUFFIXED_STATE + tuple(codex_installer.EARLIER_DIRS) + tuple(codex_installer.EARLIER_DIRS.values()):
            self.assertTrue(installer.codex_owned(rel), rel)

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
