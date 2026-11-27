"""The plugin-level hook that adds the base writing method to every session (hooks/).

Claude Code and Codex load hooks/hooks.json from the plugin root. The hook has to work from any install folder,
must not delay or fail a session, and its text has to fit the hosts' limits for hook output.
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
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))
import writing_method as W  # noqa: E402

# Claude Code caps hook output at 10,000 characters and Codex at roughly 2,500 tokens. The text is also paid for in
# every session, so it stays well under both.
MAX_CHARS = 3000


def run_hook(*args, stdin=subprocess.DEVNULL, script=HOOKS / "writing_method.py", timeout=10):
    return subprocess.run([sys.executable, str(script), *args], stdin=stdin, capture_output=True, timeout=timeout)


class HookConfigTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))["hooks"]

    def test_session_and_subagent_hooks_run_the_script(self):
        self.assertEqual(sorted(self.config), ["SessionStart", "SubagentStart"])
        for event, groups in self.config.items():
            with self.subTest(event=event):
                # No matcher: the session hook runs on startup, resume, clear, and after compaction.
                self.assertEqual(len(groups), 1)
                self.assertNotIn("matcher", groups[0])
                (hook,) = groups[0]["hooks"]
                self.assertEqual(hook["type"], "command")
                # python3 first, python as the fallback for Windows; both hosts set CLAUDE_PLUGIN_ROOT.
                calls = hook["command"].split(" || ")
                self.assertEqual([c.split(" ", 1)[0] for c in calls], ["python3", "python"])
                for call in calls:
                    self.assertIn('"${CLAUDE_PLUGIN_ROOT}/hooks/writing_method.py"', call)
                    self.assertEqual(call.endswith(" --subagent"), event == "SubagentStart")


class HookOutputTest(unittest.TestCase):
    def test_session_gets_the_method_as_plain_text(self):
        result = run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        text = result.stdout.decode("utf-8")
        self.assertTrue(text.startswith("# K-Writer 기본 글쓰기 방식\n"))
        self.assertNotIn(W.PLACEHOLDER, text)
        self.assertLessEqual(len(text), MAX_CHARS)
        for heading in ("## 1. 쓸 내용 정하기", "## 2. 문장 쓰기", "## 3. 점검하기", "## 4. 글의 크기에 따른 방법"):
            self.assertIn(heading, text)

    def test_paths_in_the_method_exist_in_the_installed_plugin(self):
        with tempfile.TemporaryDirectory(prefix="설치 폴더 ") as tmp:
            installed = Path(tmp) / "k-writer"
            shutil.copytree(HOOKS, installed / "hooks", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "skills" / "write", installed / "skills" / "write",
                            ignore=shutil.ignore_patterns("__pycache__"))
            text = run_hook(script=installed / "hooks" / "writing_method.py").stdout.decode("utf-8")
            root = os.path.abspath(str(installed)).replace(os.sep, "/")
            paths = re.findall(r"`(" + re.escape(root) + r"[^`]*)`", text)
            self.assertEqual(paths, [root + "/hooks/document-steps.md"])
            steps = (installed / "hooks" / "document-steps.md").read_text(encoding="utf-8")
            named = set(re.findall(re.escape(W.PLACEHOLDER) + r"(/[\w./-]+)", steps))
            self.assertEqual(named, {"/skills/write/references/planning.md", "/skills/write/references/style-guide.md",
                                     "/skills/write/scripts/plan_ko.py", "/skills/write/scripts/check_ko.py"})
            for rel in named:
                self.assertTrue((installed / rel.lstrip("/")).is_file(), rel)

    def test_sections_named_in_document_steps_exist(self):
        steps = (HOOKS / "document-steps.md").read_text(encoding="utf-8")
        guide = (ROOT / "core/references/style-guide.md").read_text(encoding="utf-8")
        planning = (ROOT / "core/references/planning.md").read_text(encoding="utf-8")
        line = next(ln for ln in steps.splitlines() if "style-guide.md" in ln)
        sections = re.findall(r'"([^"]+)"', line)
        self.assertGreaterEqual(len(sections), 3)
        for section in sections:
            self.assertRegex(guide, r"(?m)^#{2,3} " + re.escape(section) + "$")
        self.assertIn("## 설계 문서 형식", planning)
        self.assertIn('"설계 문서 형식"', steps)

    def test_subagent_gets_json_and_search_agents_get_nothing(self):
        for agent, expected in (("general-purpose", True), ("Explore", False), ("Plan", False)):
            with self.subTest(agent=agent):
                payload = json.dumps({"hook_event_name": "SubagentStart", "agent_type": agent}).encode("utf-8")
                p = subprocess.run([sys.executable, str(HOOKS / "writing_method.py"), "--subagent"], input=payload,
                                   capture_output=True, timeout=10)
                self.assertEqual(p.returncode, 0, p.stderr)
                if not expected:
                    self.assertEqual(p.stdout, b"")
                    continue
                out = json.loads(p.stdout.decode("utf-8"))["hookSpecificOutput"]
                self.assertEqual(out["hookEventName"], "SubagentStart")
                self.assertTrue(out["additionalContext"].startswith("# K-Writer 기본 글쓰기 방식"))

    def test_open_stdin_does_not_hold_the_session(self):
        # A host or shell that leaves stdin open without writing must not make the hook wait.
        for args in ((), ("--subagent",)):
            with self.subTest(args=args):
                p = subprocess.Popen([sys.executable, str(HOOKS / "writing_method.py"), *args],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    out = p.stdout.read()                 # returns when the script exits; stdin is still open
                    self.assertEqual(p.wait(timeout=8), 0)
                    self.assertIn("K-Writer 기본 글쓰기 방식", out.decode("utf-8"))
                finally:
                    p.stdin.close()
                    p.stdout.close()
                    p.stderr.close()

    def test_missing_text_prints_nothing_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "hooks" / "writing_method.py"
            script.parent.mkdir()
            shutil.copyfile(HOOKS / "writing_method.py", script)
            result = run_hook(script=script)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"")


class MethodTextTest(unittest.TestCase):
    """The method is read before every Korean text of a session, so it follows its own rules."""

    def setUp(self):
        self.text = (HOOKS / "writing-method.md").read_text(encoding="utf-8")

    def test_no_comma_after_connective_endings_or_conjunctions(self):
        body = re.sub(r"\"[^\"\n]*\"|\([^()\n]*\)", " ", self.text)
        self.assertEqual(re.findall(r"[가-힣]+(?:하고|이고|르고|쓰고|정하고|며|지만|는데),", body), [])
        self.assertEqual(re.findall(r"(?:그리고|그러나|하지만|따라서|그래서),", body), [])

    def test_covers_the_order_the_owner_asked_for(self):
        for phrase in ("핵심 주제", "단위", "전개", "문장별 내용", "문장, 단위, 글 전체 순서로 점검",
                       "핵심 주제를 설명하는 내용만", "독자에게 필요한 내용은 줄이지 않는다"):
            self.assertIn(phrase, self.text)


if __name__ == "__main__":
    unittest.main()
