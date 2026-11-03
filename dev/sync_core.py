#!/usr/bin/env python3
"""core/의 공통 문서와 검사 스크립트를 모든 skill 폴더에 복사한다.

- core/references/의 파일은 skills/<이름>/references/로, core/scripts/의 파일은 skills/<이름>/scripts/로 같은
  이름으로 복사한다. skill 폴더는 skills/ 아래에서 SKILL.md가 있는 폴더다.
- skill 폴더의 같은 이름 파일은 core의 사본이라 덮어쓴다. 사본은 손으로 고치지 않고 core를 고친 뒤 다시 복사한다.
- skill이 가지는 파일(SLOT_FILES)과 이름이 같은 파일은 core에 둘 수 없다.
- core에서 파일을 지우거나 이름을 바꾸면 --remove로 모든 skill에서 그 사본도 지운다.

사용법
  python dev/sync_core.py                  # 모든 skill에 복사
  python dev/sync_core.py --check          # 사본이 원본과 바이트 단위로 같은지 확인
  python dev/sync_core.py --skill techblog # 한 skill에만 복사
  python dev/sync_core.py --remove NAME    # core에 없는 NAME 사본을 모든 skill에서 지운다

종료 코드: 0 정상, 1 --check에서 다른 사본이나 없는 사본이 있음, 2 사용법 또는 입력 오류
표준 라이브러리만 쓴다(Python 3.8 이상).
"""

import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTS = ("references", "scripts")
# skill마다 따로 쓰는 파일. core에 같은 이름이 있으면 skill의 파일을 덮어쓰게 되므로 막는다.
SLOT_FILES = ("SKILL.md", "settings.md", "genre.md", "rubric.md", "thresholds.json")
SKIP_DIRS = ("__pycache__",)


def core_files(root=ROOT):
    """(하위 폴더, 파일 이름) 목록. 하위 폴더는 references 또는 scripts다."""
    out = []
    for part in PARTS:
        folder = os.path.join(root, "core", part)
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if os.path.isfile(path) and not name.endswith((".pyc", ".pyo")):
                out.append((part, name))
    clash = sorted({name for _, name in out} & set(SLOT_FILES))
    if clash:
        raise ValueError(f"core에 skill 파일과 같은 이름이 있다: {', '.join(clash)}")
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
    """원본과 다르거나 없는 사본 목록. 항목은 (skill 폴더, 하위 폴더, 파일 이름, "없음" 또는 "다름")."""
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
    """사본을 만들거나 덮어쓴다. 바뀐 사본의 경로 목록을 돌려준다."""
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
    """core에 없는 name의 사본을 모든 skill에서 지운다. 지운 경로 목록을 돌려준다."""
    if name in SLOT_FILES or os.path.basename(name) != name:
        raise ValueError(f"지울 수 없는 이름: {name}")
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
    ap = argparse.ArgumentParser(description="core 파일을 skill 폴더에 복사한다")
    ap.add_argument("--check", action="store_true", help="사본이 원본과 같은지 확인만 한다")
    ap.add_argument("--skill", help="이 skill에만 복사하거나 확인한다")
    ap.add_argument("--remove", metavar="NAME", help="core에서 지운 파일의 사본을 모든 skill에서 지운다")
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
                print(f"skill이 없다: {args.skill}", file=sys.stderr)
                return 2
            skills = [sdir]
        if args.check:
            problems = check(skills=skills)
            for sdir, part, name, why in problems:
                print(f"{why}: {os.path.relpath(os.path.join(sdir, part, name), ROOT)}")
            if problems:
                print("core를 고쳤으면 python dev/sync_core.py로 다시 복사한다. 사본을 고쳤으면 그 수정을 core로 옮긴다.")
                return 1
            print(f"사본 확인: skill {len(skills or skill_dirs())}개, core 파일 {len(core_files())}개 모두 같음")
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
