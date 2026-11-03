"""The installed bundle must work without Claude variables or the source checkout.

Each skill folder is installed and loaded on its own (plugin cache, ~/.claude/skills, ~/.agents/skills,
Codex $skill-installer), so every check below runs for every skills/<name>/ that has a SKILL.md.
"""
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
SKILLS = sorted(p.parent for p in (ROOT / "skills").glob("*/SKILL.md"))


class PortableBundleTest(unittest.TestCase):
    def test_skills_exist(self):
        self.assertIn(ROOT / "skills/techblog", SKILLS)

    def test_entrypoint_fits_codex_plugin_prompt_with_headroom(self):
        # Codex rust-v0.162.1 ext/skills/src/render.rs caps plugin prompts at
        # 8,000 UTF-8 bytes, including frontmatter. Keep 2,000 bytes of headroom.
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                path = skill / "SKILL.md"
                content = path.read_text(encoding="utf-8")
                self.assertLessEqual(len(path.read_bytes()), 6000)
                self.assertLessEqual(len(content.replace("\n", "\r\n").encode("utf-8")), 6000)

    def test_packaged_markdown_links_resolve_without_source_checkout(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name), tempfile.TemporaryDirectory() as tmp:
                installed = Path(tmp) / skill.name
                shutil.copytree(skill, installed)
                for document in installed.rglob("*.md"):
                    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
                        if "://" in target or target.startswith("#"):
                            continue
                        destination = (document.parent / target.split("#", 1)[0]).resolve()
                        self.assertIn(installed.resolve(), destination.parents, (document, target))
                        self.assertTrue(destination.is_file(), (document, target))

    def test_shared_plugin_identity_and_local_source(self):
        manifests = [json.loads((ROOT / p).read_text(encoding="utf-8")) for p in
                     ("plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json")]
        self.assertEqual({m["name"] for m in manifests}, {"k-writer"})
        self.assertEqual(len({m["version"] for m in manifests}), 1)
        marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
        source = ROOT / marketplace["plugins"][0]["source"]["path"]
        self.assertTrue((source / ".codex-plugin/plugin.json").is_file())
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                text = (skill / "SKILL.md").read_text(encoding="utf-8")
                self.assertEqual(re.search(r'^  version: "([^"]+)"$', text, re.M).group(1), manifests[0]["version"])
                self.assertTrue((source / manifests[2]["skills"] / skill.name / "SKILL.md").is_file())

    def test_scripts_from_installed_path_and_unrelated_cwd(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name), tempfile.TemporaryDirectory(prefix=f"{skill.name} 공백 ") as tmp:
                self._run_installed(skill, Path(tmp))

    def _run_installed(self, skill, base):
        installed = base / "설치 폴더" / skill.name
        shutil.copytree(skill, installed)
        work = base / "작업 폴더"
        work.mkdir()
        default = work / "input.default.md"
        casual = work / "input.casual.md"
        shutil.copyfile(ROOT / "examples/paged-attention.default.md", default)
        shutil.copyfile(ROOT / "examples/paged-attention.casual.md", casual)
        env = dict(os.environ)
        env.pop("CLAUDE_SKILL_DIR", None)
        env.pop("CLAUDE_PLUGIN_ROOT", None)

        def run(script, *args):
            return subprocess.run([sys.executable, str(installed / "scripts" / script)] + list(args),
                                  cwd=str(work), env=env, capture_output=True, text=True, encoding="utf-8")

        result = run("lint_ko.py", str(default), "--tone", "default", "--json")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        self.assertIn("summary", json.loads(result.stdout))
        result = run("lint_ko.py", str(default), "--tone", "default")
        self.assertTrue(result.stdout.startswith(f"{skill.name} lint | "), result.stdout[:80])
        result = run("tone_check.py", str(default), str(casual))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        article = work / "article.md"
        shutil.copyfile(default, article)
        result = run("revise_ko.py", "start", str(article))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        snapshot = work / "article.unrevised.md"
        repeats = work / "article.repeats.md"
        self.assertEqual(snapshot.read_bytes(), article.read_bytes())
        self.assertTrue(repeats.exists())
        result = run("revise_ko.py", "check", str(article))
        self.assertIn(result.returncode, (0, 1), result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        result = run("tone_check.py", "--cleanup", str(snapshot), str(repeats))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(snapshot.exists())
        self.assertFalse(repeats.exists())
        self.assertEqual(article.read_bytes(), default.read_bytes())


if __name__ == "__main__":
    unittest.main()
