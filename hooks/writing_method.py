#!/usr/bin/env python3
"""Print the K-Writer base writing method, so that the host adds it to the context of a session or a subagent.

hooks/hooks.json runs this script when a session starts (SessionStart: startup, resume, clear, and again after
compaction) and when a subagent starts (SubagentStart, with --subagent). Claude Code and Codex both load
hooks/hooks.json from the plugin root and add what the hook prints to the model's context, so the method in
writing-method.md applies to every Korean text of the session without a skill call.

- A session gets the text as plain stdout.
- A subagent gets it as JSON (hookSpecificOutput.additionalContext). Agent types that only search or plan
  (SKIP_AGENTS) get nothing.
- "<K-Writer 경로>" in the text is replaced with the folder of the installed plugin, taken from the location of this
  file, so the model can open the documents and run the scripts that the text names.

The script never fails or delays the session: on any error it prints nothing and exits 0, and it reads the hook input
from stdin only for a subagent and waits for it one second at most.
Uses only the standard library (Python 3.8 or later).
"""

import json
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
METHOD = os.path.join(HERE, "writing-method.md")
PLACEHOLDER = "<K-Writer 경로>"
# Built-in agent types whose output is a search result or a plan for the main agent, not a text for a reader.
SKIP_AGENTS = ("Explore", "Plan", "statusline-setup", "claude-code-guide", "web-fetch")


def method_text(root=ROOT, path=METHOD):
    """The method with the plugin folder filled in. Forward slashes work in every shell the hosts use."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return text.replace(PLACEHOLDER, root.replace(os.sep, "/")).strip() + "\n"


def hook_input(stream=None, wait=1.0):
    """The JSON the host sends on stdin, or {} when there is none.

    The read runs in a thread and is given up after `wait` seconds: a host or a shell that leaves stdin open without
    writing to it must not make the session wait for this hook.
    """
    stream = stream or sys.stdin
    box = []

    def read():
        try:
            box.append(stream.read())
        except (OSError, ValueError):
            pass

    try:
        if stream.isatty():
            return {}
    except (AttributeError, ValueError):
        pass
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    reader.join(wait)
    try:
        data = json.loads(box[0]) if box and box[0].strip() else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def output(argv, read_input=hook_input):
    """What to print for this hook call: plain text for a session, JSON for a subagent, "" to add nothing.
    Only the subagent call needs the hook input (the agent type), so a session call does not read stdin."""
    if "--subagent" not in argv:
        return method_text()
    if read_input().get("agent_type") in SKIP_AGENTS:
        return ""
    return json.dumps({"hookSpecificOutput": {"hookEventName": "SubagentStart",
                                              "additionalContext": method_text()}}, ensure_ascii=False)


def main(argv=None):
    try:
        text = output(sys.argv[1:] if argv is None else argv)
        if text:
            sys.stdout.buffer.write(text.encode("utf-8"))
            sys.stdout.buffer.flush()
    except Exception:  # noqa: BLE001 - a hook error must not stop or clutter the session
        pass
    # os._exit skips the join of the reader thread, which may still be blocked on a stdin that nobody closes.
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
