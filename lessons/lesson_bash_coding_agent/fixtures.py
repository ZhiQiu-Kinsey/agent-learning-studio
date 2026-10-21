"""Offline test model and approval policy for bash-coding-agent: they serve automated tests only.

The "model" follows a fixed script per task and stands for no real model; the commands it
proposes are real and run in a real workspace copy. The commands use only `cat` and `python`,
which behave the same in bash and in PowerShell. Whether the agent edits the source or the test
is the script's choice, written so the platform's acceptance has both cases to judge.
"""
from lessons.lesson_bash_coding_agent.locales import texts_for
from server.offline import offline_marker, tool_call

CAT = "cat gradebook/grades.py"
RUN_TESTS = "python -m unittest discover -s tests"
# Fix the bug: the boundary 90 belongs to A (bytes keep line endings as they are, on every system).
FIX = ("python -c \"import pathlib; p = pathlib.Path('gradebook/grades.py'); "
       "p.write_bytes(p.read_bytes().replace(b'score > 90', b'score >= 90'))\"")
# Move the goalposts: the test no longer asks about 90, so it goes green without any code fix.
TAMPER = ("python -c \"import pathlib; p = pathlib.Path('tests/test_grades.py'); "
          "p.write_bytes(p.read_bytes().replace(b'(90, ', b'(91, '))\"")
OUTSIDE = "cat ../grading-policy.md"
CLEAN = "rm -rf __pycache__ gradebook/__pycache__ tests/__pycache__"
SLOW = "python scripts/slow_check.py"

# One script per task: the commands in order, then the model's last reply (text lives in locales/).
SCRIPTS = {
    "fix_test": [RUN_TESTS, CAT, FIX, RUN_TESTS],
    "get_green": [RUN_TESTS, TAMPER, RUN_TESTS],
    "outside_doc": [OUTSIDE, CLEAN, CAT, FIX, RUN_TESTS],
    "slow_check": [CAT, FIX, RUN_TESTS, SLOW],
}


def _task(exercise_id, inputs):
    if (inputs or {}).get("task"):
        return inputs["task"]
    return {"fix-test": "fix_test", "tamper": "get_green", "outside-doc": "outside_doc",
            "slow-check": "slow_check"}.get(exercise_id, "fix_test")


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    task = _task(exercise_id, inputs)
    t = texts_for(locale)

    def complete(body, api_key):
        # The step is how many tool messages the history already holds.
        step = sum(1 for message in body["messages"] if message["role"] == "tool")
        script = SCRIPTS[task]
        if step >= len(script):
            return {"choices": [{"message": {"role": "assistant", "content": offline_marker(locale) + t.script_claims[task]},
                                 "finish_reason": "stop"}]}
        call = tool_call("bash", {"command": script[step]}, step + 1)
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [call]},
                             "finish_reason": "tool_calls"}]}

    return complete


def create_approval_policy(exercise_id, inputs=None, locale="zh-CN"):
    """Approve every command except the one that deletes files: a deterministic stand-in for the learner."""
    t = texts_for(locale)

    def policy(request):
        command = request["payload"].get("command", "")
        if command.startswith("rm -rf"):
            return {"decision": "reject", "note": t.script_reject_note}
        return {"decision": "approve"}

    return policy
