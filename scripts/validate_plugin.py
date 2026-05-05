#!/usr/bin/env python3
"""Validate repository-local Claude SRE plugin assets."""

from __future__ import annotations

import json
import py_compile
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: Path) -> str:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def frontmatter(path: Path) -> dict[str, str]:
    text = read(path)
    if not text.startswith("---\n"):
        fail(f"{path.relative_to(ROOT)} is missing YAML frontmatter")
    try:
        _, raw, _ = text.split("---", 2)
    except ValueError:
        fail(f"{path.relative_to(ROOT)} has malformed frontmatter")

    values: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.startswith(" "):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip('"')
    return values


def validate_plugin_json() -> None:
    data = json.loads(read(ROOT / ".claude-plugin/plugin.json"))
    for key in ("name", "version", "description", "author", "keywords"):
        if key not in data:
            fail(f".claude-plugin/plugin.json missing {key}")
    if data["name"] != "sre-skills":
        fail("plugin name must remain sre-skills")
    if not isinstance(data["keywords"], list) or "sre" not in data["keywords"]:
        fail("plugin keywords must include sre")


def validate_markdown_assets() -> None:
    commands = sorted((ROOT / "commands").glob("*.md"))
    skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
    if not commands:
        fail("no commands found")
    if not skills:
        fail("no skills found")

    for path in commands:
        fm = frontmatter(path)
        for key in ("description", "allowed-tools"):
            if key not in fm:
                fail(f"{path.relative_to(ROOT)} missing {key}")

    for path in skills:
        fm = frontmatter(path)
        for key in ("name", "description", "version"):
            if key not in fm:
                fail(f"{path.relative_to(ROOT)} missing {key}")

    agent = ROOT / "agents/sre.md"
    if "model: opus" not in read(agent):
        fail("agents/sre.md should declare model: opus for multi-step SRE work")


def validate_examples() -> None:
    config = read(ROOT / "examples/sre/config.yaml")
    sensitive_key = re.compile(r"^\s*(password|token|secret|api[_-]?key)\s*:", re.IGNORECASE)
    for line_number, line in enumerate(config.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if sensitive_key.search(line):
            fail(f"examples/sre/config.yaml:{line_number} contains a committed sensitive key")

    for path in sorted((ROOT / "examples/dashboards").glob("*.py")):
        py_compile.compile(str(path), doraise=True)


def main() -> None:
    validate_plugin_json()
    validate_markdown_assets()
    validate_examples()
    print("Plugin validation passed")


if __name__ == "__main__":
    main()
