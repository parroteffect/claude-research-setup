#!/usr/bin/env python3
"""Maintenance helper: refresh payload checksums after intentional payload edits.

Rewrites only the sha256 fields of manifest.json and codex-compat.json. It never adds,
removes, or re-routes entries, and never touches a target project or a Codex checkout.
A changed hash in codex-compat.json means a shared file no longer matches the recorded
Codex release; re-port from upstream instead of accepting that silently.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def refresh(name: str, key: str, source_key: str) -> int:
    path = ROOT / name
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for item in data[key]:
        actual = hashlib.sha256((ROOT / item[source_key]).read_bytes()).hexdigest()
        if item.get("sha256") != actual:
            print(f"UPDATED {name}: {item[source_key]}")
            item["sha256"] = actual
            changed += 1
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return changed


if __name__ == "__main__":
    total = refresh("manifest.json", "files", "source")
    drift = refresh("codex-compat.json", "identical", "claude_source")
    print(f"DONE manifest entries changed: {total}; shared entries changed: {drift}")
    if drift:
        print("ATTENTION shared files changed; they must stay byte-identical to the recorded Codex release")
