#!/usr/bin/env python3
"""Copy the shared documents and check scripts in core/ into every skill folder.

- Files in core/references/ go to skills/<name>/references/ and files in core/scripts/ go to skills/<name>/scripts/,
  under the same names. A skill folder is a folder under skills/ that contains SKILL.md.
- A file with the same name in a skill folder is a copy of the core file and gets overwritten. Do not edit copies
  directly. Edit core and copy again.
- core cannot hold a file with the same name as a file a skill owns (SLOT_FILES).
- After deleting or renaming a file in core, use --remove to delete its copies from every skill.

Usage
  python dev/sync_core.py                  # copy into every skill
  python dev/sync_core.py --check          # check that copies match the originals byte for byte
  python dev/sync_core.py --skill techblog # copy into one skill only
  python dev/sync_core.py --remove NAME    # delete copies of NAME, which is not in core, from every skill

Exit codes: 0 OK, 1 --check found a differing or missing copy, 2 usage or input error
Uses only the standard library (Python 3.8+).
"""

import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTS = ("references", "scripts")
# Files each skill owns. A core file with one of these names would overwrite the skill's file, so it is rejected.
SLOT_FILES = ("SKILL.md", "settings.md", "genre.md", "rubric.md", "thresholds.json")
SKIP_DIRS = ("__pycache__",)


def core_files(root=ROOT):
    """List of (subfolder, file name). The subfolder is references or scripts."""
    out = []
    for part in PARTS:
        folder = os.path.join(root, "core", part)
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if os.path.isfile(path) and not name.endswith((".pyc", ".pyo")):
                out.append((part, name))
    clash = sorted({name for _, name in out} & set(SLOT_FILES))
    if clash:
        raise ValueError(f"core에 스킬 파일과 이름이 같은 파일이 있다: {', '.join(clash)}")
    return out


def skill_dirs(root=ROOT):
    base = os.path.join(root, "skills")
    return [os.path.join(base, d) for d in sorted(os.listdir(base))
            if d not in SKIP_DIRS and os.path.isfile(os.path.join(base, d, "SKILL.md"))]


def _same(a, b):
    if not os.path.isfile(b):
        return False
    with open(a, "rb") as fa, open(b, "rb") as fb:
        return fa.read() == fb.read()


def check(root=ROOT, skills=None):
    """List copies that differ from the original or are missing.
    Each item is (skill folder, subfolder, file name, "없음" or "다름")."""
    problems = []
    for sdir in skills or skill_dirs(root):
        for part, name in core_files(root):
            src = os.path.join(root, "core", part, name)
            dst = os.path.join(sdir, part, name)
            if not os.path.isfile(dst):
                problems.append((sdir, part, name, "없음"))
            elif not _same(src, dst):
                problems.append((sdir, part, name, "다름"))
    return problems


def sync(root=ROOT, skills=None):
    """Create or overwrite the copies. Return the paths of the copies that changed."""
    written = []
    for sdir in skills or skill_dirs(root):
        for part, name in core_files(root):
            src = os.path.join(root, "core", part, name)
            dst = os.path.join(sdir, part, name)
            if _same(src, dst):
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            written.append(dst)
    return written


def remove(name, root=ROOT):
    """Delete copies of name, which is not in core, from every skill. Return the deleted paths."""
    if name in SLOT_FILES or os.path.basename(name) != name:
        raise ValueError(f"삭제할 수 없는 이름: {name}")
    if any(n == name for _, n in core_files(root)):
        raise ValueError(f"core에 아직 있는 파일이다: {name}")
    removed = []
    for sdir in skill_dirs(root):
        for part in PARTS:
            path = os.path.join(sdir, part, name)
            if os.path.isfile(path):
                os.remove(path)
                removed.append(path)
    return removed


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Copy core files into skill folders")
    ap.add_argument("--check", action="store_true", help="Only check that copies match the originals")
    ap.add_argument("--skill", help="Copy to or check this skill only")
    ap.add_argument("--remove", metavar="NAME", help="Delete copies of a file deleted from core from every skill")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        if args.remove:
            for path in remove(args.remove):
                print(f"삭제: {os.path.relpath(path, ROOT)}")
            return 0
        skills = None
        if args.skill:
            sdir = os.path.join(ROOT, "skills", args.skill)
            if not os.path.isfile(os.path.join(sdir, "SKILL.md")):
                print(f"스킬이 없다: {args.skill}", file=sys.stderr)
                return 2
            skills = [sdir]
        if args.check:
            problems = check(skills=skills)
            for sdir, part, name, why in problems:
                print(f"{why}: {os.path.relpath(os.path.join(sdir, part, name), ROOT)}")
            if problems:
                print("core를 수정했으면 python dev/sync_core.py로 다시 복사한다. 복사본을 수정했으면 수정 내용을 core로 옮긴다.")
                return 1
            print(f"복사본 확인: 스킬 {len(skills or skill_dirs())}개, core 파일 {len(core_files())}개 모두 같음")
            return 0
        written = sync(skills=skills)
        for path in written:
            print(f"복사: {os.path.relpath(path, ROOT)}")
        print(f"복사한 파일 {len(written)}개")
        return 0
    except (OSError, ValueError) as e:
        print(f"sync_core 오류: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
