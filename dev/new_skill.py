#!/usr/bin/env python3
"""Create a new skill folder.

Generates the files a skill owns (SKILL.md, references/settings.md, genre.md, rubric.md, workflow.md,
scripts/thresholds.json) from the *.tmpl files in dev/skill-template/, then copies the core documents and check
scripts with dev/sync_core.py. tests/test_core.py fails until every "TODO:" in the generated files is filled in.
An existing folder is left untouched.

Usage
  python dev/new_skill.py NAME

NAME follows the Agent Skills naming rule: lowercase letters, digits, and hyphens, at most 64 characters, not
starting or ending with a hyphen, and no two hyphens in a row. Exit codes: 0 created, 2 usage or input error
"""

import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Template file name -> path inside the skill folder
TARGETS = {
    "SKILL.md.tmpl": "SKILL.md",
    "settings.md.tmpl": os.path.join("references", "settings.md"),
    "genre.md.tmpl": os.path.join("references", "genre.md"),
    "rubric.md.tmpl": os.path.join("references", "rubric.md"),
    "workflow.md.tmpl": os.path.join("references", "workflow.md"),
    "thresholds.json.tmpl": os.path.join("scripts", "thresholds.json"),
}


def _sync_module(root):
    spec = importlib.util.spec_from_file_location("kw_sync_core", os.path.join(root, "dev", "sync_core.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def create(name, root=ROOT):
    """Create skills/NAME and return the paths of the created files."""
    if len(name) > 64 or not NAME_RE.match(name):
        raise ValueError(f"스킬 이름 규칙에 맞지 않는다: {name}")
    sdir = os.path.join(root, "skills", name)
    if os.path.exists(sdir):
        raise ValueError(f"이미 있는 폴더다: {sdir}")
    with open(os.path.join(root, "plugin.json"), encoding="utf-8") as f:
        version = json.load(f)["version"]
    made = []
    for tmpl, rel in TARGETS.items():
        with open(os.path.join(root, "dev", "skill-template", tmpl), encoding="utf-8") as f:
            text = f.read()
        text = text.replace("{{name}}", name).replace("{{version}}", version)
        path = os.path.join(sdir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        made.append(path)
    made += _sync_module(root).sync(root, [sdir])
    return made


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0].startswith("-"):
        print("사용법: python dev/new_skill.py NAME", file=sys.stderr)
        return 2
    try:
        made = create(args[0])
    except (OSError, ValueError, KeyError) as e:
        print(f"new_skill 오류: {e}", file=sys.stderr)
        return 2
    for path in made:
        print(f"생성: {os.path.relpath(path, ROOT)}")
    print("TODO:를 채운 뒤 python -m unittest discover -s tests로 확인한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
