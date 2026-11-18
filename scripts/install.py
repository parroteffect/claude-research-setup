#!/usr/bin/env python3
"""Install the Claude Code research workflow payload. No network, subprocesses, or package installs.

Python 3.9+ is required. Default: plan only. Use --apply to write; --check performs
static checks only and does not claim that a running Claude Code session is ready.

Independence contract with codex-research-setup (same project, both installed):
- nothing is ever written under .codex/, and the CODEX RESEARCH WORKFLOW block of
  AGENTS.md is never edited; only a separately marked coexistence note may be appended;
- the two harnesses keep separate, harness-named research state. This package creates
  research/STATE.claude.md and research/GOAL_CONFIG.claude.md and never writes the Codex workflow's
  research/STATE.codex.md, research/GOAL_CONFIG.codex.md, research/goals-codex/, research/notes-codex/,
  nor the unsuffixed paths of the layout before Codex 5.5.0 (research/STATE.md, research/GOAL_CONFIG.md,
  research/goals/, research/notes/);
- only the read-only form templates under */_templates/ are shared byte-for-byte, and they are
  never overwritten while the Codex workflow is installed (that package keeps updating them);
- .claude/settings*.json is never read for writing and never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import uuid
from datetime import datetime, timezone

if sys.version_info < (3, 9):
    sys.exit("Python 3.9+ is required. Do not install dependencies automatically; see BOOTSTRAP.md.")

ROOT = Path(__file__).resolve().parents[1]
BEGIN = "<!-- BEGIN CLAUDE RESEARCH WORKFLOW -->"
END = "<!-- END CLAUDE RESEARCH WORKFLOW -->"
NOTE_BEGIN = "<!-- BEGIN CLAUDE-CODEX COEXISTENCE NOTE -->"
NOTE_END = "<!-- END CLAUDE-CODEX COEXISTENCE NOTE -->"
# Read-only knowledge of the other package; these are never written by this installer.
CODEX_BEGIN = "<!-- BEGIN CODEX RESEARCH WORKFLOW -->"
CODEX_END = "<!-- END CODEX RESEARCH WORKFLOW -->"
CODEX_META = ".codex/research-workflow-install.json"
CODEX_GUARD = ".codex/tools/goal_guard.py"
CODEX_DOC_LIMIT = 32 * 1024  # Codex's documented default project-instruction budget.
# Research state of the Codex workflow: its harness-named paths, and the unsuffixed paths used
# before Codex 5.5.0. Neither set is ever written by this installer.
CODEX_RESEARCH_FILES = ("research/STATE.codex.md", "research/GOAL_CONFIG.codex.md",
                        "research/STATE.md", "research/GOAL_CONFIG.md")
CODEX_RESEARCH_DIRS = ("research/goals-codex", "research/notes-codex", "research/goals", "research/notes")
# Releases of this package that kept Claude's records in the unsuffixed files, shared with Codex.
SHARED_STATE_RELEASES = ("5.4.0+claude.1",)
# Claude-owned create-only state -> where such a release wrote instead: the unsuffixed path, or the
# Codex-named path once the Codex installer (5.5.0+) has carried that file over.
SPLIT_FROM = {"research/STATE.claude.md": ("research/STATE.md", "research/STATE.codex.md"),
              "research/GOAL_CONFIG.claude.md": ("research/GOAL_CONFIG.md", "research/GOAL_CONFIG.codex.md")}

WORKDIR = ".claude/research-workflow"
META = WORKDIR + "/install.json"
BACKUPS = WORKDIR + "/backups"
GUARD = WORKDIR + "/tools/goal_guard.py"
ROLES = ("engineer", "supervisor", "qa")
DEFAULT_EFFORT = "high"
IGNORE_BEGIN = "# BEGIN CLAUDE RESEARCH WORKFLOW"
IGNORE_END = "# END CLAUDE RESEARCH WORKFLOW"
IGNORE = f"{IGNORE_BEGIN}\n/{BACKUPS}/\n{IGNORE_END}"
MODES = {"managed-file", "claude-block", "codex-note", "create-only", "shared-file"}
INSTRUCTION_FILES = ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md")


class Conflict(Exception):
    """An input needs review; do not guess or overwrite it."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def codex_owned(relative: str) -> bool:
    rel = Path(relative)
    posix = rel.as_posix()
    return (rel.parts[0] == ".codex" or posix in CODEX_RESEARCH_FILES
            or any(posix == d or posix.startswith(d + "/") for d in CODEX_RESEARCH_DIRS))


def safe_path(root: Path, relative: str, write: bool = True) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(p in ("..", ".git") for p in rel.parts):
        raise Conflict(f"Unsafe path: {relative!r}")
    if write and codex_owned(relative):
        raise Conflict(f"Refusing to write a Codex-owned path: {relative}")
    p = root
    for part in rel.parts:
        p = p / part
        if p.is_symlink():
            hint = ""
            if relative in INSTRUCTION_FILES:
                hint = (". A CLAUDE.md symlink (often to AGENTS.md) would put the Claude block into the "
                        "file Codex reads; replace it with a real file as described in BOOTSTRAP.md")
            raise Conflict(f"Refusing a symlink: {p}{hint}")
    if not p.resolve().is_relative_to(root.resolve()):
        raise Conflict(f"Path escapes the target: {relative}")
    return p


def read_bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    if not path.is_file():
        raise Conflict(f"Expected a file: {path}")
    if path.stat().st_size > 2_000_000:
        raise Conflict(f"Unexpectedly large configuration file: {path}")
    return path.read_bytes()


def decode(data: bytes | None) -> str:
    try:
        return (data or b"").decode("utf-8")
    except UnicodeError as exc:
        raise Conflict("Expected UTF-8 configuration text") from exc


def block(text: str, begin: str, end: str) -> tuple[int, int] | None:
    n, m = text.count(begin), text.count(end)
    if n == m == 0:
        return None
    if n != 1 or m != 1 or text.index(begin) >= text.index(end):
        raise Conflict(f"Malformed or repeated managed block: {begin}")
    return text.index(begin), text.index(end) + len(end)


def append_or_replace(text: str, content: str, begin: str, end: str) -> str:
    span = block(text, begin, end)
    if span:
        return text[:span[0]] + content + text[span[1]:]
    return text + ("\n\n" if text and not text.endswith("\n\n") else "") + content + "\n"


def managed_block(text: str, body: bytes, begin: str, end: str, recorded: str | None,
                  legacy: list[str], label: str) -> tuple[str, str]:
    """Return (new text, block hash). Markers alone are not provenance."""
    content = begin + "\n" + decode(body).rstrip() + "\n" + end
    span = block(text, begin, end)
    if span:
        existing = text[span[0]:span[1]]
        inner = existing[len(begin):-len(end)]
        pristine_legacy = (inner.startswith("\n") and inner.endswith("\n")
                           and digest(inner[1:].encode()) in legacy)
        if existing != content and digest(existing.encode()) != recorded and not pristine_legacy:
            raise Conflict(f"Managed {label} has local edits or unknown provenance; preserve and merge it manually")
    return append_or_replace(text, content, begin, end), digest(content.encode())


def frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    """Minimal reader for the flat `key: value` YAML subset used by subagent files."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fields = {}
            for line in lines[1:i]:
                match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
                if match:
                    value = match.group(2).strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                        value = value[1:-1]
                    fields[match.group(1)] = value
            return fields, "\n".join(lines[i + 1:])
    return None


def tool_names(value: str) -> set[str]:
    return {re.sub(r"\(.*\)$", "", item.strip()) for item in value.strip("[]").split(",") if item.strip()}


def duplicate_roles(target: Path) -> list[str]:
    found = []
    agents_dir = safe_path(target, ".claude/agents")
    if agents_dir.is_dir():
        for file in sorted(agents_dir.glob("*.md")):
            if file.name in {role + ".md" for role in ROLES}:
                continue
            parsed = frontmatter(decode(read_bytes(safe_path(target, str(file.relative_to(target))))))
            if parsed and parsed[0].get("name") in ROLES:
                found.append(f'Duplicate project-scoped {parsed[0]["name"]} subagent: {file.name}')
    return found


def read_package() -> tuple[dict, dict, dict[str, bytes]]:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    legacy = json.loads((ROOT / "legacy-hashes.json").read_text(encoding="utf-8"))
    files = {}
    for item in manifest["files"]:
        if item["mode"] not in MODES:
            raise Conflict(f"Unknown manifest mode: {item['mode']}")
        data = safe_path(ROOT, item["source"], write=False).read_bytes()
        if digest(data) != item["sha256"]:
            raise Conflict(f"Payload checksum mismatch: {item['source']}")
        destination = Path(item["destination"])
        if item["mode"] != "codex-note" and (codex_owned(item["destination"]) or destination.name.startswith("AGENTS")):
            raise Conflict(f"Manifest destination belongs to the Codex workflow: {item['destination']}")
        files[item["destination"]] = data
    return manifest, legacy, files


def target_root(value: str) -> Path:
    raw = Path(value).expanduser().absolute()
    if raw.is_symlink():
        raise Conflict("Use a real project directory, not a symlink")
    target = raw.resolve()
    if not target.is_dir():
        raise Conflict("Target must be an existing project directory")
    home = Path.home().resolve()
    homes = {home, home / ".claude", home / ".codex",
             Path(os.environ.get("CLAUDE_CONFIG_DIR", str(home / ".claude"))).resolve()}
    if target == Path(target.anchor) or target in homes:
        raise Conflict("Refusing a filesystem root, home, or Claude/Codex home as installation target")
    if target == ROOT or target.is_relative_to(ROOT) or ROOT.is_relative_to(target):
        raise Conflict("Keep this source checkout outside the target project")
    return target


def codex_state(target: Path) -> dict:
    """Read-only view of a co-installed Codex workflow."""
    agents = decode(read_bytes(safe_path(target, "AGENTS.md", write=False)))
    meta_bytes = read_bytes(safe_path(target, CODEX_META, write=False))
    version = None
    if meta_bytes:
        try:
            version = json.loads(decode(meta_bytes)).get("version")
        except ValueError:
            version = "UNREADABLE"
    span = block(agents, CODEX_BEGIN, CODEX_END)
    outside = agents
    if span:
        outside = agents[:span[0]] + agents[span[1]:]
    note = block(outside, NOTE_BEGIN, NOTE_END)
    if note:
        outside = outside[:note[0]] + outside[note[1]:]
    return {"installed": bool(meta_bytes) or span is not None, "version": version,
            "block": agents[span[0]:span[1]] if span else None,
            "project_text_outside_blocks": bool(outside.strip()),
            "guard": read_bytes(safe_path(target, CODEX_GUARD, write=False))}


def coexistence_notices(target: Path, manifest: dict, payload: dict[str, bytes], codex: dict) -> list[str]:
    notes = []
    if not codex["installed"]:
        return notes
    upstream = manifest.get("upstream", {})
    notes.append(f"CODEX_DETECTED workflow version {codex['version'] or 'UNKNOWN'}; .codex/ and the Codex "
                 "AGENTS.md block stay untouched")
    if codex["version"] and codex["version"] != upstream.get("version"):
        notes.append(f"ATTENTION policy revisions differ: installed Codex workflow {codex['version']} vs this port of "
                     f"{upstream.get('version')}; align both packages before relying on shared templates")
    if codex["guard"] is not None and codex["guard"] != payload[GUARD]:
        notes.append("ATTENTION goal guard copies differ between harnesses; do not continue a goal started by the "
                     "other harness until the revisions are reconciled")
    return notes


def make_plan(target: Path, revision: str, codex_note: bool = True
              ) -> tuple[list[tuple[str, bytes | None, bytes]], list[str]]:
    manifest, legacy, payload = read_package()
    previous_data = read_bytes(safe_path(target, META))
    previous = json.loads(decode(previous_data)) if previous_data else {}
    if previous and previous.get("package") != manifest["package"]:
        raise Conflict("Existing install metadata belongs to a different package")
    duplicates = duplicate_roles(target)
    if duplicates:
        raise Conflict(duplicates[0])
    nested = decode(read_bytes(safe_path(target, ".claude/CLAUDE.md")))
    if BEGIN in nested or END in nested:
        raise Conflict("The workflow block already exists in .claude/CLAUDE.md; keep one copy, in root CLAUDE.md")
    codex = codex_state(target)
    had_instructions = any(read_bytes(safe_path(target, rel)) is not None for rel in INSTRUCTION_FILES)
    tracked = previous.get("installed_hashes", {})
    tracked_shared = previous.get("shared_hashes", {})
    changes, notices, hashes, shared_hashes = [], [], {}, {}
    block_hash, note_hash = None, previous.get("codex_note_hash")
    for item in manifest["files"]:
        rel, mode = item["destination"], item["mode"]
        path = safe_path(target, rel, write=mode != "codex-note" or codex_note)
        old = read_bytes(path)
        new = payload[rel]
        known = set(legacy.get(rel, []))
        if mode == "claude-block":
            text, block_hash = managed_block(decode(old), new, BEGIN, END, previous.get("claude_block_hash"),
                                             legacy.get(rel, []), "CLAUDE.md block")
            new = text.encode()
            if re.search(r"(?m)^\s*@(\./)?AGENTS\.md\s*$", decode(old)):
                notices.append("NOTE CLAUDE.md imports AGENTS.md; the Claude block declares precedence over a "
                               "co-loaded Codex block, so no change is required")
        elif mode == "codex-note":
            text = decode(old)
            present = block(text, NOTE_BEGIN, NOTE_END) is not None
            if not codex_note or not (codex["installed"] or present):
                if codex["installed"] and not present:
                    notices.append("SKIPPED Codex-side coexistence note in AGENTS.md (--no-codex-note)")
                continue
            text, note_hash = managed_block(text, new, NOTE_BEGIN, NOTE_END, previous.get("codex_note_hash"),
                                            legacy.get("AGENTS.md#note", []), "AGENTS.md coexistence note")
            after = block(text, CODEX_BEGIN, CODEX_END)
            if (text[after[0]:after[1]] if after else None) != codex["block"]:
                raise Conflict("Internal error: the Codex AGENTS.md block would change; nothing was installed")
            new = text.encode()
            if len(new) > CODEX_DOC_LIMIT:
                notices.append(f"ATTENTION AGENTS.md would be {len(new)} bytes, above Codex's default 32 KiB "
                               "project-instruction budget; the trailing note may be truncated in Codex")
        elif mode == "create-only":
            if old is not None:
                new = old
                notices.append(f"PRESERVED existing {rel}")
            elif rel in SPLIT_FROM:
                unsuffixed, codex_named = SPLIT_FROM[rel]
                if previous.get("version") in SHARED_STATE_RELEASES:
                    candidates = (unsuffixed, codex_named)  # Claude's earlier records are in one of these
                elif not previous and not codex["installed"]:
                    candidates = (unsuffixed,)  # an older record of unknown origin
                else:
                    candidates = ()  # a fresh install next to Codex: those files are simply Codex's
                for earlier_rel in candidates:
                    earlier = read_bytes(safe_path(target, earlier_rel, write=False))
                    if earlier is not None and digest(earlier) not in legacy.get(earlier_rel, []):
                        notices.append(f"ATTENTION {rel} starts empty: Claude's research state is now kept apart from "
                                       f"{earlier_rel}, which is left untouched and is no longer read automatically. "
                                       "If an earlier Claude session recorded work there, ask Claude to carry over "
                                       "what is still needed (BOOTSTRAP.md)")
        elif mode == "shared-file":
            if tracked_shared.get(rel):
                known.add(tracked_shared[rel])
            if old is not None and old != new:
                if codex["installed"] or digest(old) not in known:
                    notices.append(f"PRESERVED shared {rel} (differs from this package; "
                                   + ("owned by the Codex workflow)" if codex["installed"] else "locally edited)"))
                    new = old
            if old != new:
                shared_hashes[rel] = digest(new)
            elif rel in tracked_shared:
                shared_hashes[rel] = tracked_shared[rel]
        else:  # managed-file
            if rel in tracked:
                known.add(tracked[rel])
            if old is not None and old != new and digest(old) not in known:
                raise Conflict(f"Locally customized file: {rel}. Preserve and merge it manually; "
                               "no force overwrite is provided")
            hashes[rel] = digest(new)
        if old != new:
            changes.append((rel, old, new))
    ignore_old = read_bytes(safe_path(target, ".gitignore"))
    ignore_new = append_or_replace(decode(ignore_old), IGNORE, IGNORE_BEGIN, IGNORE_END).encode()
    if ignore_old != ignore_new:
        changes.append((".gitignore", ignore_old, ignore_new))
    metadata = {"package": manifest["package"], "version": manifest["version"],
                "upstream": manifest.get("upstream", {}),
                "source_revision": revision or previous.get("source_revision", "UNSPECIFIED"),
                "installed_hashes": hashes, "shared_hashes": shared_hashes,
                "claude_block_hash": block_hash, "codex_note_hash": note_hash,
                "runtime_status": "NOT_VERIFIED"}
    metadata_bytes = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode()
    if previous_data != metadata_bytes:
        changes.append((META, previous_data, metadata_bytes))
    notices.extend(coexistence_notices(target, manifest, payload, codex))
    if not had_instructions and codex["project_text_outside_blocks"]:
        notices.append("ATTENTION Claude Code reads AGENTS.md only while no CLAUDE.md exists. Creating CLAUDE.md "
                       "ends that fallback, and AGENTS.md has project instructions outside the workflow blocks; "
                       "carry the ones Claude must follow into CLAUDE.md outside the managed block (BOOTSTRAP.md)")
    if read_bytes(safe_path(target, "AGENTS.override.md", write=False)) and codex["installed"]:
        notices.append("ATTENTION root AGENTS.override.md masks AGENTS.md in Codex; merge the coexistence note "
                       "into the active override manually")
    return changes, notices


def atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".workflow-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply_plan(target: Path, changes: list[tuple[str, bytes | None, bytes]]) -> str | None:
    if not changes:
        return None
    # Check the entire plan before any write, and recheck each file at replacement.
    for rel, old, _ in changes:
        if read_bytes(safe_path(target, rel)) != old:
            raise Conflict(f"File changed after planning: {rel}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    backup = safe_path(target, BACKUPS + "/" + stamp)
    backup.mkdir(parents=True, mode=0o700)
    os.chmod(backup, 0o700)
    records = []
    for rel, old, new in changes:
        records.append({"path": rel, "existed": old is not None,
                        "before_sha256": digest(old) if old is not None else None,
                        "after_sha256": digest(new)})
        if old is not None:
            atomic_write(safe_path(backup, rel, write=False), old, 0o600)
    atomic_write(backup / "RESTORE.json", (json.dumps(records, indent=2) + "\n").encode(), 0o600)
    print(f"BACKUP {backup}", flush=True)
    for rel, old, new in changes:
        path = safe_path(target, rel)
        if read_bytes(path) != old:
            raise Conflict(f"Concurrent edit at {rel}; some earlier files may be installed. Review backup {backup}")
        mode = stat.S_IMODE(path.stat().st_mode) if old is not None else 0o644
        atomic_write(path, new, mode)
    return str(backup)


def effort_overrides(target: Path) -> list[str]:
    found = []
    if os.environ.get("CLAUDE_CODE_EFFORT_LEVEL"):
        found.append("the current environment")
    for rel in (".claude/settings.json", ".claude/settings.local.json"):
        data = read_bytes(safe_path(target, rel, write=False))
        if not data:
            continue
        try:
            env = json.loads(decode(data)).get("env", {})
        except (ValueError, AttributeError):
            found.append(f"{rel} (unreadable JSON)")
            continue
        if isinstance(env, dict) and env.get("CLAUDE_CODE_EFFORT_LEVEL"):
            found.append(rel)
    return found


def check(target: Path) -> int:
    manifest, _, payload = read_package()
    errors, notes = [], []
    for item in manifest["files"]:
        if item["mode"] == "codex-note":
            continue
        if read_bytes(safe_path(target, item["destination"])) is None:
            errors.append(f"Missing {item['destination']}")
    for role in ROLES:
        data = read_bytes(safe_path(target, f".claude/agents/{role}.md"))
        parsed = frontmatter(decode(data)) if data is not None else None
        if parsed is None:
            errors.append(f"Subagent file .claude/agents/{role}.md has no YAML frontmatter")
            continue
        fields, body = parsed
        if fields.get("name") != role:
            errors.append(f"Subagent name must be {role}")
        if not fields.get("description", "").strip() or not body.strip():
            errors.append(f"Missing subagent description or instructions: {role}")
        if "model" in fields:
            errors.append(f"Remove pinned {role}.model to keep the user's model selection")
        if fields.get("effort") != DEFAULT_EFFORT:
            errors.append(f"{role}.effort must stay {DEFAULT_EFFORT!r}: it is only the default used when main "
                          "omits the spawn argument")
        allowed = "Agent" in tool_names(fields["tools"]) if "tools" in fields else True
        if allowed and "Agent" not in tool_names(fields.get("disallowedTools", "")):
            errors.append(f"{role} can spawn further agents; keep Agent in disallowedTools")
    text = decode(read_bytes(safe_path(target, "CLAUDE.md")))
    span = block(text, BEGIN, END)
    if span is None:
        errors.append("CLAUDE.md managed workflow block is missing")
    elif text[span[0]:span[1]] != BEGIN + "\n" + decode(payload["CLAUDE.md"]).rstrip() + "\n" + END:
        notes.append("Local workflow block differs from payload; review its meaning manually")
    nested = decode(read_bytes(safe_path(target, ".claude/CLAUDE.md")))
    if BEGIN in nested:
        errors.append("Duplicate workflow block in .claude/CLAUDE.md; keep one copy, in root CLAUDE.md")
    errors.extend(duplicate_roles(target))
    codex = codex_state(target)
    for line in coexistence_notices(target, manifest, payload, codex):
        if line.startswith("ATTENTION"):
            notes.append(line[len("ATTENTION "):])
    if codex["installed"]:
        agents = decode(read_bytes(safe_path(target, "AGENTS.md", write=False)))
        if block(agents, NOTE_BEGIN, NOTE_END) is None:
            notes.append("Codex is installed but AGENTS.md has no coexistence note; Codex is not told to leave "
                         "CLAUDE.md, .claude/ and Claude's research state alone")
    for source in effort_overrides(target):
        notes.append(f"CLAUDE_CODE_EFFORT_LEVEL is set in {source}; it overrides subagent and per-spawn effort")
    for note in notes:
        print("REVIEW " + note)
    for error in errors:
        print("FAIL " + error)
    if errors:
        return 2
    print("PASS local file presence, subagent frontmatter (name, default effort, no model pin, no nested spawn), "
          "and the CLAUDE.md block")
    print("PASS independence layout: no file of this package lives under .codex/, in the Codex AGENTS.md block, "
          "or at a Codex research-state path (research/*.codex.md, research/*-codex/, or the earlier unsuffixed ones)")
    print("NOT_CHECKED user/managed settings and environment overrides, the active instruction chain, runtime "
          "subagent registration, or the effort actually applied to a spawn")
    print(f"NEXT restart Claude Code in the target project, then read {WORKDIR}/VERIFY_SETUP.md")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True, help="Existing research project directory, not the source checkout")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true", help="Write the reviewed installation plan")
    group.add_argument("--check", action="store_true", help="Static verification only")
    parser.add_argument("--source-revision", default="", help="Reviewed source commit or release identifier; never credentials")
    parser.add_argument("--no-codex-note", action="store_true",
                        help="Never touch AGENTS.md, even when the Codex workflow is installed")
    args = parser.parse_args()
    try:
        if args.source_revision and not re.fullmatch(r"[A-Za-z0-9._/+:-]{1,128}", args.source_revision):
            raise Conflict("Source revision must be a short commit/tag identifier without credentials or whitespace")
        target = target_root(args.target)
        if args.check:
            return check(target)
        changes, notes = make_plan(target, args.source_revision, codex_note=not args.no_codex_note)
        for note in notes:
            print(note)
        for rel, old, _ in changes:
            print(("CREATE " if old is None else "UPDATE ") + rel)
        print(f"PLAN {len(changes)} changed files")
        if not args.apply:
            print("DRY_RUN no files written; review BOOTSTRAP.md and use --apply when ready")
            return 0
        apply_plan(target, changes)
        print("FILES_INSTALLED; runtime is NOT_VERIFIED")
        return check(target)
    except (Conflict, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"BLOCKED {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
