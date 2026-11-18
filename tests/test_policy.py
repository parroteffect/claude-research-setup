"""Static wiring of the ported policy: paths, roles, and harness-specific wording."""
from __future__ import annotations

import re
import unittest

from _common import ROOT, MANIFEST, installer

PAYLOAD = ROOT / "payload"
CLAUDE_FILES = [p for p in sorted(PAYLOAD.rglob("*")) if p.is_file() and "shared" not in p.parts
                and p.suffix in (".md", ".txt")]
DESTINATIONS = {item["destination"] for item in MANIFEST["files"]}


class PolicyTests(unittest.TestCase):
    def test_every_referenced_workflow_path_is_installed(self):
        pattern = re.compile(r"\.claude/(?:research-workflow|agents)/[A-Za-z0-9_./-]*[A-Za-z0-9]\.(?:md|py|txt|json)")
        seen = set()
        for path in CLAUDE_FILES:
            for ref in pattern.findall(path.read_text(encoding="utf-8")):
                seen.add(ref)
                if ref == installer.META:
                    continue
                self.assertIn(ref, DESTINATIONS, f"{path.name} references a file that is not installed: {ref}")
        for guide in ("research", "monk", "code-review", "implementation", "goal", "interactive-research"):
            self.assertIn(f".claude/research-workflow/guides/{guide}.md", seen)

    def test_instruction_entrypoints_route_to_guides(self):
        block = (PAYLOAD / "CLAUDE.block.md").read_text(encoding="utf-8")
        start = (PAYLOAD / ".claude/research-workflow/RESEARCH_START.txt").read_text(encoding="utf-8")
        engineer = (PAYLOAD / ".claude/agents/engineer.md").read_text(encoding="utf-8")
        for guide in ("research", "monk", "code-review", "implementation", "goal", "interactive-research"):
            self.assertIn(f".claude/research-workflow/guides/{guide}.md", block)
        for guide in ("research", "monk", "goal", "interactive-research"):
            self.assertIn(f".claude/research-workflow/guides/{guide}.md", start)
        for guide in ("monk", "code-review", "implementation", "goal"):
            self.assertIn(f".claude/research-workflow/guides/{guide}.md", engineer)

    def test_no_stale_codex_paths_or_settings_outside_coexistence_rules(self):
        allowed_context = ("Codex", "codex", "CODEX", "harness", "marker", "import")
        for path in CLAUDE_FILES:
            if path.name == "AGENTS.coexistence.md":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                where = f"{path.relative_to(ROOT)}:{number}"
                if ".codex/" in line or "AGENTS.md" in line:
                    self.assertTrue(any(word in line for word in allowed_context), where)
                for stale in ("root AGENTS.md", "AGENTS.md의 “", "developer_instructions", "model_reasoning_effort",
                              "default_subagent_reasoning_effort", "max_concurrent_threads_per_session",
                              ".toml에", "RESEARCH_START.txt에 따라 .codex"):
                    self.assertNotIn(stale, line, where)
        block = (PAYLOAD / "CLAUDE.block.md").read_text(encoding="utf-8")
        self.assertEqual(block.count(".codex/guides/"), 1)  # only the path-mapping rule

    def test_roles_keep_default_effort_no_model_pin_and_no_nested_spawn(self):
        for role in installer.ROLES:
            fields, body = installer.frontmatter((PAYLOAD / f".claude/agents/{role}.md").read_text(encoding="utf-8"))
            self.assertEqual(fields["name"], role)
            self.assertTrue(fields["description"].strip())
            self.assertEqual(fields["effort"], "high")
            self.assertNotIn("model", fields)
            self.assertNotIn("tools", fields)
            self.assertIn("Agent", installer.tool_names(fields["disallowedTools"]))
            self.assertGreater(len(body), 500)
            self.assertIn("USER", body)
        supervisor, _ = installer.frontmatter((PAYLOAD / ".claude/agents/supervisor.md").read_text(encoding="utf-8"))
        self.assertLessEqual({"Edit", "Write"}, installer.tool_names(supervisor["disallowedTools"]))
        qa, _ = installer.frontmatter((PAYLOAD / ".claude/agents/qa.md").read_text(encoding="utf-8"))
        self.assertNotIn("Write", installer.tool_names(qa["disallowedTools"]))  # may write small validation artifacts

    def test_block_states_the_claude_specific_contract(self):
        block = (PAYLOAD / "CLAUDE.block.md").read_text(encoding="utf-8")
        self.assertTrue(block.startswith("# Research workflow\n"))
        for needle in ("## 공통: 다른 slot·Codex workflow와의 독립 운영", "Claude Code에서는 이 block이 우선한다",
                       "서로 독립적으로 연구한다", "Goal은 slot별로 독립이다", "자동으로 읽지 않으며",
                       "사용자가 지시하면", "~/.codex/sessions/", "~/.claude/projects/",
                       "`claude<N>`", "research/STATE.<slot>.md", "research/notes-<slot>/",
                       "research/GOAL_CONFIG.<slot>.md", "research/goals-<slot>/",
                       "echo $CLAUDE_CODE_SESSION_ID", "research/SESSIONS.claude.md", "research/SESSIONS.codex.md",
                       "지정이 없으면 0번", "replaced로 바꾸고", "active가 아니면 그 slot에 쓰지 않고",
                       "subagent는 그 slot만 쓴다", "0번 slot의 기록으로 그 경로에서 계속 쓴다",
                       "research/STATE.codex<N>.md", "research/notes-codex<N>/", "research/GOAL_CONFIG.codex<N>.md",
                       "research/goals-codex<N>/", "이름에 harness가 없는 이전 경로", "코드 working tree는 하나다",
                       "Agent 도구의 `effort` 인자 사용을 명시적으로 요청한다", '`subagent_type: "engineer"`',
                       '`model: "opus"`', '`effort: "xhigh"`', "USER-ONLY", "auto memory", "SendMessage",
                       "Agent 도구를 disallow한다"):
            self.assertIn(needle, block)
        self.assertNotIn(installer.BEGIN, block)
        note = (PAYLOAD / "AGENTS.coexistence.md").read_text(encoding="utf-8")
        for needle in ("`.claude/research-workflow/`", "서로 독립적으로 연구한다", "Goal은 slot별로 독립이다",
                       "자동으로 읽지 않는다", "사용자가 지시하면", "research/STATE.claude<N>.md",
                       "research/SESSIONS.claude.md"):
            self.assertIn(needle, note)
        self.assertLess(len(note.encode()), 2048)  # Codex reads AGENTS.md within a 32 KiB budget
        self.assertNotIn(installer.CODEX_BEGIN, note)
        for stale in ("harness를 통틀어 하나", "harness 공통으로 하나", "두 harness가 공유"):
            for path in CLAUDE_FILES:
                self.assertNotIn(stale, path.read_text(encoding="utf-8"), path.name)

    def test_claude_files_use_slot_paths_and_name_other_state_only_as_someone_elses(self):
        # Unnumbered or unsuffixed state names, and Codex slots, may appear only as paths that are not this session's.
        foreign = re.compile(r"research/(?:STATE|GOAL_CONFIG)(?:\.(?:codex|claude)(?:<N>|\d*))?\.md"
                             r"|research/(?:goals|notes)(?:-(?:codex|claude)(?:<N>|\d*))?/")
        own_example = re.compile(r"research/(?:(?:STATE|GOAL_CONFIG)\.claude0\.md|goals-claude0/)")
        for path in CLAUDE_FILES:
            if path.name == "AGENTS.coexistence.md":
                continue
            text = path.read_text(encoding="utf-8")
            for match in foreign.finditer(text):
                if own_example.fullmatch(match.group()):
                    # Slot 0 by name: the worked goal example and the installed-files check only.
                    self.assertIn(path.name, ("goal.md", "VERIFY_SETUP.md"), match.group())
                    continue
                window = text[max(0, match.start() - 260):match.end() + 260]
                self.assertTrue(any(word in window for word in ("Codex", "이전 경로", "이전 버전", "다른 slot")),
                                f"{path.relative_to(ROOT)}: {match.group()} is not marked as another slot's path")
        for rel, needle in ((".claude/research-workflow/RESEARCH_START.txt", "research/STATE.<slot>.md"),
                            (".claude/research-workflow/RESEARCH_START.txt", "research/SESSIONS.claude.md"),
                            (".claude/research-workflow/VERIFY_SETUP.md", "echo $CLAUDE_CODE_SESSION_ID"),
                            (".claude/research-workflow/guides/goal.md", "research/GOAL_CONFIG.<slot>.md"),
                            (".claude/research-workflow/guides/goal.md", "research/goals-claude0/g1/run-state"),
                            (".claude/research-workflow/guides/monk.md", "research/notes-<slot>/"),
                            (".claude/research-workflow/guides/interactive-research.md", "research/STATE.<slot>.md"),
                            (".claude/agents/engineer.md", "research/STATE.<slot>.md"),
                            (".claude/agents/engineer.md", "research/SESSIONS.claude.md")):
            self.assertIn(needle, (PAYLOAD / rel).read_text(encoding="utf-8"), rel)
        sessions = (PAYLOAD / "shared/research/_templates/SESSIONS.md").read_text(encoding="utf-8")
        for needle in ("| slot | session id | status | claimed | last active | task |", "active / replaced / released"):
            self.assertIn(needle, sessions)

    def test_manifest_integrity(self):
        self.assertEqual(len(DESTINATIONS), len(MANIFEST["files"]))
        sources = {item["source"] for item in MANIFEST["files"]}
        on_disk = {str(p.relative_to(ROOT)) for p in PAYLOAD.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        self.assertEqual(sources, on_disk)
        manifest, _, payload = installer.read_package()
        self.assertEqual(manifest["version"], (ROOT / "VERSION").read_text(encoding="utf-8").strip())
        self.assertEqual(set(payload), DESTINATIONS)


if __name__ == "__main__":
    unittest.main()
