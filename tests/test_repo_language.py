"""Language rules for the repository's own text (AGENTS.md).

- Comments and docstrings in Python code are in English. Korean words that a comment discusses stay inside quotes.
- The word tables that catch awkward Korean in articles also apply to the documents people read first.
"""
import ast
import io
from pathlib import Path
import re
import sys
import tokenize
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "techblog" / "scripts"))
import lint_ko as L  # noqa: E402

HANGUL = re.compile("[가-힣]")
LATIN = re.compile("[A-Za-z]")
QUOTED = re.compile(r"\"[^\"\n]*\"|'[^'\n]*'|“[^”\n]*”|‘[^’\n]*’|«[^»\n]*»")
CODE_DIRS = ("core", "dev", "tests")
FRONT_DOCS = ("README.md", "ARCHITECTURE.md", "skills/techblog/README.md", "examples/README.md")


def mostly_korean(line):
    """True when the line, without quoted examples, holds more Hangul than Latin letters."""
    bare = QUOTED.sub(" ", line)
    return len(HANGUL.findall(bare)) > len(LATIN.findall(bare))


def python_files():
    for top in CODE_DIRS:
        yield from sorted((ROOT / top).rglob("*.py"))


def comment_lines(source):
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            yield tok.start[0], tok.string


def docstring_lines(source):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                first = node.body[0].lineno
                for offset, line in enumerate(doc.split("\n")):
                    yield first + offset, line


class CodeCommentLanguageTest(unittest.TestCase):
    def test_comments_and_docstrings_are_english(self):
        for path in python_files():
            source = path.read_text(encoding="utf-8")
            korean = [(n, text.strip()) for reader in (comment_lines, docstring_lines) for n, text in reader(source)
                      if mostly_korean(text)]
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertEqual(korean, [])


class FrontDocWordsTest(unittest.TestCase):
    """A5.plain_terms counts words that human posts name differently. Documents people read first must not use them
    outside quotes, because a model that reads them repeats them."""

    def setUp(self):
        spec = L.load_json(L.PATTERNS_PATH)["patterns"]
        self.rxs = [(pid, re.compile(r)) for pid in ("A6.version_pan", "A5.plain_terms") for r in spec[pid]["regex"]]

    def test_front_docs_use_plain_terms_outside_quotes(self):
        for name in FRONT_DOCS:
            text = (ROOT / name).read_text(encoding="utf-8")
            text = re.sub(r"```.*?```", " ", text, flags=re.S)
            for line in text.splitlines():
                bare = QUOTED.sub(" ", re.sub(r"`[^`\n]*`", " ", line))
                for pid, rx in self.rxs:
                    match = rx.search(bare)
                    with self.subTest(doc=name, item=pid):
                        self.assertIsNone(match, line[:120])


if __name__ == "__main__":
    unittest.main()
