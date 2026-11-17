# Distribution repository instructions

This is the **workflow distribution repository**, not the user's research project.
The research project's actual instructions are in `payload/CLAUDE.block.md` (named so that Claude Code
does not load it as a nested CLAUDE.md here); its policy does not govern work in this repository.

This package is the Claude Code counterpart of `codex-research-setup` and must stay installable
next to it in one project.

When asked to install this repository into another project:
1. Read `README.md` and `BOOTSTRAP.md` before making changes.
2. Keep the source checkout separate from the target. Do not install over this repository.
3. The main agent may perform bootstrap setup directly; no engineer must exist yet.
4. Preserve target code, project-specific instructions, research state, model/effort,
   credentials, security settings, and any installed Codex workflow. Never run heavy experiments.
5. Review the installer before executing it. Start with its default dry run.
6. Distinguish files installed from a fresh Claude Code session loading the configuration.

When asked to maintain this distribution:
- Port policy changes from the upstream Codex release; do not let the two policies drift.
  Record the upstream version and revision in `manifest.json` and `codex-compat.json`, and
  version this package as `<upstream version>+claude.<n>`.
- Coexistence invariants, enforced by `tests/test_coexistence.py`:
  - never write under `.codex/` or inside the `CODEX RESEARCH WORKFLOW` block of `AGENTS.md`;
  - never modify `.claude/settings*.json`;
  - keep every file listed in `codex-compat.json` byte-identical to the recorded Codex release
    (copy it from upstream; do not edit it here);
  - keep markers, metadata, and backup paths distinct from the Codex package's.
- Keep main's direct code access, single writer, USER-ONLY final experiments, and adaptive
  high/xhigh. Role files keep `effort: high` as the default only, no `model`, and `Agent` disallowed.
- Preserve active research invention and mathematical analysis; do not add rigid idea quotas
  or claim a measured creativity/potential improvement without evidence.
- After intentional payload edits run `python3 -B scripts/update_manifest.py`.
- Run only `python3 -B -m unittest discover -s tests -v` or similarly light, reviewed checks.
  Tests read a neighbouring `codex-research-setup` checkout (or `CODEX_RESEARCH_SETUP`) but
  must never write to it.
- Do not start Claude Code, Codex, a model, GPU jobs, package downloads, or workflow
  installation in the source root.
