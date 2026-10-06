import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..", "skills", "mentor")
sys.path.insert(0, SKILL)
import mentor  # noqa: E402

SCOPE = "people open the app, sign in and create a note"
BEHAVIOR = "notes stay saved when they come back tomorrow on another device"
DESIGN = "notes live in a database table with the user id so each person only sees theirs"
EXPLAIN = "we added a notes table keyed by user id and the page loads only that user's notes on sign in"


def write_event(path, tool="Write"):
    return {"tool_name": tool, "tool_input": {"file_path": path}}


class MentorTest(unittest.TestCase):
    def setUp(self):
        self.old = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.tmp)

    def answer_all(self):
        mentor.cmd_answer("scope", SCOPE)
        mentor.cmd_answer("behavior", BEHAVIOR)
        mentor.cmd_answer("design", DESIGN)

    def test_no_session_never_blocks(self):
        self.assertEqual(mentor.gate(write_event("app.py")), (True, ""))

    def test_code_is_locked_until_all_three_answers(self):
        mentor.cmd_start("a Notion clone")
        mentor.cmd_feature("sign in and create a note")
        allowed, msg = mentor.gate(write_event("app.py"))
        self.assertFalse(allowed)
        self.assertIn("scope, behavior, design", msg)
        mentor.cmd_answer("scope", SCOPE)
        with self.assertRaises(mentor.MentorError):
            mentor.cmd_unlock()
        mentor.cmd_answer("behavior", BEHAVIOR)
        mentor.cmd_answer("design", DESIGN)
        self.assertFalse(mentor.gate(write_event("app.py"))[0])   # answered but not unlocked yet
        mentor.cmd_unlock()
        self.assertTrue(mentor.gate(write_event("app.py"))[0])
        self.assertTrue(mentor.gate(write_event("app.py", "Edit"))[0])

    def test_notes_inside_mentor_folder_are_always_allowed(self):
        mentor.cmd_start("a Notion clone")
        self.assertTrue(mentor.gate(write_event(".mentor/notes.md"))[0])
        self.assertFalse(mentor.gate(write_event(".mentorx/notes.md"))[0])

    def test_reads_are_never_blocked(self):
        mentor.cmd_start("a Notion clone")
        self.assertTrue(mentor.gate({"tool_name": "Read", "tool_input": {"file_path": "app.py"}})[0])

    def test_short_answers_are_refused(self):
        mentor.cmd_start("a Notion clone")
        mentor.cmd_feature("notes")
        with self.assertRaises(mentor.MentorError):
            mentor.cmd_answer("design", "a database")

    def test_explain_back_closes_the_feature_and_relocks(self):
        mentor.cmd_start("a Notion clone")
        mentor.cmd_feature("notes")
        self.answer_all()
        mentor.cmd_unlock()
        with self.assertRaises(mentor.MentorError):
            mentor.cmd_explain("it works")
        mentor.cmd_explain(EXPLAIN, ["foreign keys", "per-user data"])
        state = mentor.load_state()
        self.assertEqual(state["features"][0]["status"], "done")
        self.assertFalse(mentor.gate(write_event("app.py"))[0])   # locked again until the next feature
        with open(mentor.RECAP) as f:
            recap = f.read()
        self.assertIn("foreign keys", recap)
        self.assertIn(DESIGN, recap)
        self.assertIn("alexyc9381/mentor-skill", recap)

    def test_cannot_open_a_second_feature_before_finishing(self):
        mentor.cmd_start("a Notion clone")
        mentor.cmd_feature("notes")
        with self.assertRaises(mentor.MentorError):
            mentor.cmd_feature("folders")

    def test_stop_lifts_the_lock(self):
        mentor.cmd_start("a Notion clone")
        mentor.cmd_feature("notes")
        mentor.cmd_stop()
        self.assertTrue(mentor.gate(write_event("app.py"))[0])

    def test_hook_exit_codes(self):
        script = os.path.join(SKILL, "mentor.py")
        run = lambda event: subprocess.run([sys.executable, script, "gate"], input=json.dumps(event),
                                           capture_output=True, text=True)
        self.assertEqual(run(write_event("app.py")).returncode, 0)
        mentor.cmd_start("a Notion clone")
        r = run(write_event("app.py"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("code is locked", r.stderr)
        self.assertEqual(run({"garbage": True}).returncode, 0)


if __name__ == "__main__":
    unittest.main()
