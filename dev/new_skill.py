#!/usr/bin/env python3
"""새 skill 폴더를 만든다.

dev/skill-template/의 *.tmpl로 skill이 가지는 파일(SKILL.md, references/settings.md, genre.md, rubric.md,
workflow.md, scripts/thresholds.json)을 만들고, dev/sync_core.py로 core 문서와 검사 스크립트를 복사한다.
만든 파일의 "TODO:"를 모두 채우기 전에는 tests/test_core.py가 실패한다. 이미 있는 폴더는 건드리지 않는다.

사용법
  python dev/new_skill.py NAME

NAME은 Agent Skills 이름 규칙(소문자, 숫자, 하이픈, 64자 이하, 하이픈으로 시작하거나 끝나지 않고 두 번
잇지 않음)을 따른다. 종료 코드: 0 만듦, 2 사용법 또는 입력 오류
"""

import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# 템플릿 파일 이름 → skill 폴더 안의 경로
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
    """skills/NAME을 만들고 만든 파일의 경로 목록을 돌려준다."""
    if len(name) > 64 or not NAME_RE.match(name):
        raise ValueError(f"skill 이름 규칙에 맞지 않는다: {name}")
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
        print(f"만듦: {os.path.relpath(path, ROOT)}")
    print("TODO:를 채운 뒤 python -m unittest discover -s tests로 확인한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
