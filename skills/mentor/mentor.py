#!/usr/bin/env python3
"""mentor: the bookkeeping behind /mentor.

Claude writes the code, you make the calls. Every feature has three checkpoints that must be answered in
your own words before any code gets written:

  scope     what the feature does for the person using it
  behavior  what happens in the edge cases (coming back later, deleting, empty states, errors)
  design    how you think it should be built (where the data lives, what talks to what)

While a feature is locked, the PreToolUse hook (`mentor.py gate`) blocks Claude's Write and Edit tools
outside `.mentor/`. After the code is written, you explain it back in your own words, and the feature
closes with the concepts you learned logged in `.mentor/RECAP.md`.

Everything lives in `.mentor/` in the folder you run it in. Nothing else on your machine is touched.

usage:
  mentor.py start --goal "a Notion clone" [--level beginner|some|experienced]
  mentor.py feature "sign in and create a note"
  mentor.py answer scope|behavior|design --text "..."   (or --file path)
  mentor.py status
  mentor.py unlock
  mentor.py explain --text "..." [--concept "..."]...
  mentor.py recap
  mentor.py stop
  mentor.py gate          (the hook; reads the tool call as JSON on stdin)
"""
import argparse
import datetime as dt
import json
import os
import sys

ROOT = ".mentor"
STATE = os.path.join(ROOT, "state.json")
ACTIVE = os.path.join(ROOT, "ACTIVE")
RECAP = os.path.join(ROOT, "RECAP.md")
CHECKPOINTS = ("scope", "behavior", "design")
MIN_WORDS = {"scope": 6, "behavior": 8, "design": 8, "explain": 12}
LEVELS = ("beginner", "some", "experienced")
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
CREDIT = "Made with /mentor by Alex Chen (@nocodealex): github.com/alexyc9381/mentor-skill"


class MentorError(Exception):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state():
    if not os.path.exists(STATE):
        raise MentorError("no mentor session here: run `mentor.py start --goal \"...\"` first")
    with open(STATE, encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    os.makedirs(ROOT, exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATE)


def current(state):
    feats = state["features"]
    return feats[-1] if feats else None


def word_count(text):
    return len(text.split())


# ---------- commands ----------
def cmd_start(goal, level="beginner"):
    if level not in LEVELS:
        raise MentorError("level must be one of: " + ", ".join(LEVELS))
    if not goal or not goal.strip():
        raise MentorError("say what you are building: --goal \"...\"")
    os.makedirs(ROOT, exist_ok=True)
    state = {"goal": goal.strip(), "level": level, "started": now(), "features": []}
    save_state(state)
    open(ACTIVE, "w").close()
    return "mentor on: %s (%s). Next: name the first feature with `feature`." % (state["goal"], level)


def cmd_feature(name):
    state = load_state()
    cur = current(state)
    if cur and cur["status"] != "done":
        raise MentorError("finish \"%s\" first (explain it back), or it stays open" % cur["name"])
    if not name or not name.strip():
        raise MentorError("name the feature")
    state["features"].append({"name": name.strip(), "status": "locked", "opened": now(),
                              "answers": {}, "explain": None, "concepts": []})
    save_state(state)
    return "feature \"%s\" is locked until you answer: %s" % (name.strip(), ", ".join(CHECKPOINTS))


def cmd_answer(checkpoint, text):
    if checkpoint not in CHECKPOINTS:
        raise MentorError("checkpoint must be one of: " + ", ".join(CHECKPOINTS))
    state = load_state()
    cur = current(state)
    if not cur or cur["status"] == "done":
        raise MentorError("no open feature: start one with `feature`")
    text = (text or "").strip()
    need = MIN_WORDS[checkpoint]
    if word_count(text) < need:
        raise MentorError("that %s answer is too short (%d words, need %d): say it in your own words"
                          % (checkpoint, word_count(text), need))
    cur["answers"][checkpoint] = {"text": text, "at": now()}
    save_state(state)
    left = [c for c in CHECKPOINTS if c not in cur["answers"]]
    return "saved %s. %s" % (checkpoint, ("Still to answer: " + ", ".join(left)) if left
                             else "All three answered: run `unlock` to let Claude write the code.")


def cmd_unlock():
    state = load_state()
    cur = current(state)
    if not cur:
        raise MentorError("no feature yet")
    left = [c for c in CHECKPOINTS if c not in cur["answers"]]
    if left:
        raise MentorError("still locked: answer %s first" % ", ".join(left))
    cur["status"] = "building"
    cur["unlocked"] = now()
    save_state(state)
    return "unlocked \"%s\": Claude can write the code now, then you explain it back." % cur["name"]


def cmd_explain(text, concepts=()):
    state = load_state()
    cur = current(state)
    if not cur or cur["status"] != "building":
        raise MentorError("nothing is being built: unlock a feature first")
    text = (text or "").strip()
    if word_count(text) < MIN_WORDS["explain"]:
        raise MentorError("explain what changed in your own words (%d words, need %d)"
                          % (word_count(text), MIN_WORDS["explain"]))
    cur["explain"] = {"text": text, "at": now()}
    cur["concepts"] = [c.strip() for c in concepts if c and c.strip()]
    cur["status"] = "done"
    cur["closed"] = now()
    save_state(state)
    write_recap(state)
    return "\"%s\" done. %d concept(s) logged in %s." % (cur["name"], len(cur["concepts"]), RECAP)


def cmd_status():
    state = load_state()
    cur = current(state)
    lines = ["goal: %s (%s)" % (state["goal"], state["level"]),
             "features done: %d" % sum(1 for f in state["features"] if f["status"] == "done")]
    if not cur:
        lines.append("no feature yet: name one with `feature`")
    else:
        lines.append("current: \"%s\" (%s)" % (cur["name"], cur["status"]))
        if cur["status"] == "locked":
            for c in CHECKPOINTS:
                lines.append("  [%s] %s" % ("x" if c in cur["answers"] else " ", c))
    lines.append("code is %s" % ("LOCKED" if is_locked() else "open"))
    return "\n".join(lines)


def write_recap(state):
    out = ["# What you built and learned", "", "Goal: %s" % state["goal"], ""]
    for f in state["features"]:
        if f["status"] != "done":
            continue
        out += ["## %s" % f["name"], ""]
        for c in CHECKPOINTS:
            if c in f["answers"]:
                out.append("- **Your %s call:** %s" % (c, f["answers"][c]["text"]))
        out.append("- **How you explained it back:** %s" % f["explain"]["text"])
        if f["concepts"]:
            out.append("- **Concepts:** %s" % ", ".join(f["concepts"]))
        out.append("")
    out += ["---", CREDIT, ""]
    with open(RECAP, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    return RECAP


def cmd_recap():
    return "wrote " + write_recap(load_state())


def cmd_stop():
    if os.path.exists(ACTIVE):
        os.remove(ACTIVE)
    return "mentor off: Claude can write code freely again. Your notes stay in .mentor/."


# ---------- the hook ----------
def is_locked():
    if not os.path.exists(ACTIVE) or not os.path.exists(STATE):
        return False
    try:
        cur = current(load_state())
    except (MentorError, ValueError):
        return False
    return cur is None or cur["status"] != "building"


def inside_mentor_dir(path):
    if not path:
        return False
    root = os.path.realpath(ROOT)
    target = os.path.realpath(path)
    return target == root or target.startswith(root + os.sep)


def gate(event):
    """Return (allowed, message) for one PreToolUse event."""
    if event.get("tool_name") not in WRITE_TOOLS:
        return True, ""
    if not is_locked():
        return True, ""
    tool_input = event.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if inside_mentor_dir(path):
        return True, ""
    try:
        cur = current(load_state())
    except MentorError:
        cur = None
    if cur is None:
        why = "no feature is open"
    else:
        left = [c for c in CHECKPOINTS if c not in cur["answers"]]
        why = ("the user still has to answer: " + ", ".join(left)) if left else "run `mentor.py unlock` first"
    return False, ("/mentor: code is locked (%s). Ask the user the next question with no suggested answer, "
                   "record their own words with `mentor.py answer`, then unlock. They can turn mentor off with "
                   "/mentor stop." % why)


def cmd_gate(stdin):
    try:
        event = json.loads(stdin or "{}")
    except ValueError:
        return 0, ""
    allowed, msg = gate(event)
    return (0, "") if allowed else (2, msg)


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentor.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start"); s.add_argument("--goal", required=True); s.add_argument("--level", default="beginner")
    s = sub.add_parser("feature"); s.add_argument("name", nargs="+")
    s = sub.add_parser("answer"); s.add_argument("checkpoint"); s.add_argument("--text"); s.add_argument("--file")
    sub.add_parser("status"); sub.add_parser("unlock"); sub.add_parser("recap"); sub.add_parser("stop")
    s = sub.add_parser("explain"); s.add_argument("--text"); s.add_argument("--file")
    s.add_argument("--concept", action="append", default=[])
    sub.add_parser("gate")
    a = p.parse_args(argv)

    def text_of(a):
        if getattr(a, "file", None):
            with open(a.file, encoding="utf-8") as f:
                return f.read()
        return a.text

    try:
        if a.cmd == "gate":
            code, msg = cmd_gate(sys.stdin.read())
            if msg:
                print(msg, file=sys.stderr)
            return code
        out = {"start": lambda: cmd_start(a.goal, a.level),
               "feature": lambda: cmd_feature(" ".join(a.name)),
               "answer": lambda: cmd_answer(a.checkpoint, text_of(a)),
               "unlock": cmd_unlock, "status": cmd_status, "recap": cmd_recap, "stop": cmd_stop,
               "explain": lambda: cmd_explain(text_of(a), a.concept)}[a.cmd]()
        print(out)
        return 0
    except MentorError as e:
        print("mentor: " + str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
