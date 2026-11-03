"""core/와 skill 폴더 사이의 약속을 검사한다.

- core 사본: core/의 파일이 모든 skill 폴더에 바이트 단위로 같게 있다(dev/sync_core.py).
- slot: skill마다 SKILL.md, references/settings.md, genre.md, rubric.md, scripts/thresholds.json이 있다.
- 의존 방향: core 문서와 데이터는 skill의 단계 번호와 skill 전용 문서를 가리키지 않는다.
- 절 참조: 문서가 'X.md의 "Y"'로 가리킨 절이 같은 skill 폴더의 X.md 헤딩에 있다.
- 기준치: rules.json과 thresholds.json을 합치는 함수와 나누는 함수가 서로 반대이고, 보정하지 않은 분포 지표는 INFO다.
- 새 skill 도구: dev/new_skill.py가 slot 파일과 core 사본을 만든다.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "techblog" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import lint_ko as L  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SYNC = load("kw_sync_core_test", ROOT / "dev" / "sync_core.py")
NEW = load("kw_new_skill_test", ROOT / "dev" / "new_skill.py")
SKILLS = [Path(p) for p in SYNC.skill_dirs(str(ROOT))]
CORE_NAMES = {name for _, name in SYNC.core_files(str(ROOT))}
SLOTS = ("SKILL.md", "references/settings.md", "references/genre.md", "references/rubric.md",
         "scripts/thresholds.json")
STEP_RE = re.compile(r"[1-8](?:~[1-8])?단계")
# 단계 번호가 아니라 라벨 구분자의 예문에 든 "1단계"
STEP_EXAMPLES = ("1단계: 설정", "1단계 — 설정")
SECTION_REF = re.compile(r"([A-Za-z][\w-]*\.md)(?:의|에서)?\s*\"([^\"\n]{2,80})\"")


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return dict(re.findall(r"^([a-z-]+): ?(.*)$", m.group(1), re.M)) if m else {}


def owned_files(skill):
    """skill이 가진 문서와 데이터(core 사본이 아닌 파일)."""
    out = [skill / "SKILL.md"]
    for part in ("references", "scripts"):
        for p in sorted((skill / part).glob("*")):
            if p.is_file() and p.name not in CORE_NAMES and p.suffix in (".md", ".json"):
                out.append(p)
    return out


def todo_markers(skill):
    return [(str(p.relative_to(skill)), n) for p in owned_files(skill)
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if "TODO:" in line]


class CoreCopyTest(unittest.TestCase):
    def test_core_copies_match(self):
        self.assertEqual(SYNC.check(str(ROOT)), [], "core를 고쳤으면 python dev/sync_core.py를 실행한다")

    def test_no_slot_name_in_core(self):
        self.assertFalse(CORE_NAMES & {Path(s).name for s in SLOTS})


class SlotTest(unittest.TestCase):
    def test_every_skill_has_slots(self):
        self.assertIn(ROOT / "skills" / "techblog", SKILLS)
        for skill in SKILLS:
            for rel in SLOTS:
                with self.subTest(skill=skill.name, slot=rel):
                    self.assertTrue((skill / rel).is_file())

    def test_frontmatter_and_standard(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                fm = frontmatter((skill / "SKILL.md").read_text(encoding="utf-8"))
                self.assertEqual(fm.get("name"), skill.name)
                self.assertTrue(len(skill.name) <= 64 and NEW.NAME_RE.match(skill.name))
                self.assertTrue(fm.get("description"))
                self.assertLessEqual(len(fm["description"]), 1024)
                th = json.loads((skill / "scripts" / "thresholds.json").read_text(encoding="utf-8"))
                self.assertTrue((th.get("skill") or {}).get("standard"))

    def test_no_todo_left(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                self.assertEqual(todo_markers(skill), [])


class CoreLayeringTest(unittest.TestCase):
    """core는 어느 skill의 단계 번호나 skill 전용 문서에 기대지 않는다. skill 문서는 slot 이름으로만 가리킨다."""

    def core_texts(self):
        paths = sorted((ROOT / "core" / "references").glob("*.md")) + sorted((ROOT / "core" / "scripts").glob("*.json"))
        for p in paths:
            yield p, p.read_text(encoding="utf-8")

    def test_no_step_numbers(self):
        for p, text in self.core_texts():
            for n, line in enumerate(text.splitlines(), 1):
                for example in STEP_EXAMPLES:
                    line = line.replace(example, "")
                with self.subTest(file=p.name, line=n):
                    self.assertIsNone(STEP_RE.search(line), line[:120])

    def test_no_skill_only_documents(self):
        slot_names = {Path(s).name for s in SLOTS}
        skill_only = {p.name for skill in SKILLS for p in owned_files(skill)} - slot_names
        self.assertIn("drafting.md", skill_only)
        for p, text in self.core_texts():
            for name in sorted(skill_only):
                with self.subTest(file=p.name, doc=name):
                    self.assertNotIn(name, text)


class SectionReferenceTest(unittest.TestCase):
    def test_quoted_sections_exist(self):
        checked = 0
        for skill in SKILLS:
            docs = {p.name: p for p in (skill / "references").glob("*.md")}
            docs["SKILL.md"] = skill / "SKILL.md"
            heads = {name: [re.sub(r"^\d+\.\s*", "", m.group(1).strip())
                            for m in re.finditer(r"^#{1,6}\s+(.*)$", p.read_text(encoding="utf-8"), re.M)]
                     for name, p in docs.items()}
            for name, p in docs.items():
                for m in SECTION_REF.finditer(p.read_text(encoding="utf-8")):
                    target, section = m.group(1), m.group(2)
                    if target not in docs:
                        continue  # 저장소 문서(dev/baseline/techblog/README.md)나 명령 예에 든 파일 이름
                    checked += 1
                    with self.subTest(skill=skill.name, doc=name, ref=f"{target} {section}"):
                        self.assertTrue(any(h.startswith(section) for h in heads[target]))
        self.assertGreater(checked, 40)


class ThresholdsTest(unittest.TestCase):
    def test_split_is_inverse_of_load(self):
        merged = L.load_thresholds()
        self.assertEqual(L.split_thresholds(merged), L.load_json(L.THRESHOLDS_PATH))
        rules = L.load_json(L.RULES_PATH)
        self.assertEqual(list(merged["metrics"]), list(rules["metrics"]))
        for mid, spec in rules["metrics"].items():
            if spec.get("kind") != "gate" and not spec.get("fixed"):
                with self.subTest(metric=mid):
                    self.assertFalse(set(spec) & set(L.CALIBRATED_FIELDS))

    def test_uncalibrated_skill_reports_distribution_as_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "thresholds.json"
            path.write_text(json.dumps({"skill": {"standard": "사람이 쓴 한국어 시험 글"}, "metrics": {}}),
                            encoding="utf-8")
            th = L.load_thresholds(str(path))
            text = L.read_text(str(ROOT / "examples" / "paged-attention.default.md"))
            results = {r["id"]: r for r in L.evaluate(L.analyze(text), th, "default")["results"]}
            self.assertEqual(results["A2.comma_per_sentence"]["status"], "INFO")
            self.assertEqual(results["A2.comma_per_sentence"]["limit"], {"note": L.UNCALIBRATED_NOTE})
            self.assertIn(results["G6.emdash"]["status"], ("PASS", "GATE"))
            self.assertIn("pass_max", results["A1.np_simple"]["limit"])  # fixed 기준은 core 값으로 판정
            self.assertEqual(L.standard_text(th), "사람이 쓴 한국어 시험 글")

    def test_drop_removes_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "thresholds.json"
            path.write_text(json.dumps({"drop": ["A9.", "A16.source_subject_share"], "metrics": {}}), encoding="utf-8")
            ids = set(L.load_thresholds(str(path))["metrics"])
            self.assertEqual([m for m in ids if m.startswith("A9.")], [])
            self.assertNotIn("A16.source_subject_share", ids)
            self.assertIn("A16.source_subject", ids)


class NewSkillTest(unittest.TestCase):
    def test_new_skill_gets_slots_and_core_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "core", root / "core", ignore=shutil.ignore_patterns("__pycache__"))
            (root / "dev").mkdir()
            for name in ("sync_core.py", "new_skill.py"):
                shutil.copyfile(ROOT / "dev" / name, root / "dev" / name)
            shutil.copytree(ROOT / "dev" / "skill-template", root / "dev" / "skill-template")
            shutil.copyfile(ROOT / "plugin.json", root / "plugin.json")
            (root / "skills").mkdir()
            new = load("kw_new_skill_tmp", root / "dev" / "new_skill.py")
            new.create("demo-skill", str(root))
            skill = root / "skills" / "demo-skill"
            for rel in SLOTS + ("references/workflow.md",):
                self.assertTrue((skill / rel).is_file(), rel)
            sync = load("kw_sync_core_tmp", root / "dev" / "sync_core.py")
            self.assertEqual(sync.check(str(root)), [])
            text = (skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertEqual(frontmatter(text)["name"], "demo-skill")
            version = json.loads((root / "plugin.json").read_text(encoding="utf-8"))["version"]
            self.assertIn(f'  version: "{version}"', text)
            self.assertTrue(todo_markers(skill))  # 채우기 전에는 test_no_todo_left가 실패한다
            result = subprocess.run([sys.executable, str(skill / "scripts" / "lint_ko.py"),
                                     str(ROOT / "examples" / "paged-attention.default.md"), "--tone", "default"],
                                    capture_output=True, text=True, encoding="utf-8",
                                    env={k: v for k, v in os.environ.items() if k != "PYTHONUTF8"})
            self.assertIn(result.returncode, (0, 1), result.stderr)
            self.assertTrue(result.stdout.startswith("demo-skill lint | "), result.stdout[:80])
            with self.assertRaises(ValueError):
                new.create("demo-skill", str(root))
            with self.assertRaises(ValueError):
                new.create("Bad_Name", str(root))


if __name__ == "__main__":
    unittest.main()
