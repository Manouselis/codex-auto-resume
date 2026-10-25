import unittest

from auto_resume.checkpoints import BLOCKED_MARKER, CHECKPOINT_MARKER, COMPLETE_MARKER, context_checkpoint


def turn(text, *, phase="final_answer", status="completed"):
    return {"status": status, "completedAt": 1234, "error": None,
            "items": [{"type": "agentMessage", "phase": phase, "text": text}]}


class CheckpointTests(unittest.TestCase):
    def test_heartbeat_checkpoint_marker_inside_message(self):
        for decision in ("DONT_NOTIFY", "NOTIFY"):
            text = ("<heartbeat>\n  <automation_id>resume-research</automation_id>\n"
                    f"  <decision>{decision}</decision>\n"
                    "  <message>I0047–I0052 completed; checks &amp; backup passed. "
                    "Exact next action saved for I0053.\n" + CHECKPOINT_MARKER + "</message>\n</heartbeat>")
            with self.subTest(decision=decision):
                self.assertTrue(context_checkpoint(turn(text)))

    def test_heartbeat_stops_and_nonterminal_outputs_never_authorize_recovery(self):
        template = ("<heartbeat><automation_id>resume-research</automation_id>"
                    "<decision>DONT_NOTIFY</decision><message>{}</message></heartbeat>")
        for marker in (COMPLETE_MARKER, BLOCKED_MARKER):
            self.assertFalse(context_checkpoint(turn(template.format(marker + "\n" + CHECKPOINT_MARKER))))
        for status in ("inProgress", "interrupted", "failed"):
            self.assertFalse(context_checkpoint(turn(template.format(CHECKPOINT_MARKER), status=status)))
        value = turn(template.format(CHECKPOINT_MARKER))
        value["completedAt"] = None
        self.assertFalse(context_checkpoint(value))

    def test_malformed_ambiguous_or_nested_heartbeat_is_rejected(self):
        text = ("<heartbeat><automation_id>resume-research</automation_id>"
                "<decision>DONT_NOTIFY</decision><message>Saved.\n" + CHECKPOINT_MARKER + "</message></heartbeat>")
        malformed = (
            text.replace("</heartbeat>", ""),
            text.replace("<decision>", "<decision extra='value'>"),
            text.replace("</heartbeat>", "<message>extra</message></heartbeat>"),
            text.replace("</heartbeat>", "<extra>value</extra></heartbeat>"),
            text.replace("<message>", "<message><nested>example</nested>"),
            text.replace("DONT_NOTIFY", "UNKNOWN"),
            text.replace("<message>", "<!DOCTYPE message><message>"),
            text + "\n" + CHECKPOINT_MARKER,
            text.replace("<message>Saved.\n", ""),
        )
        for value in malformed:
            with self.subTest(text=value):
                self.assertFalse(context_checkpoint(turn(value)))

    def test_heartbeat_examples_and_nonfinal_message_marker_do_not_trigger(self):
        text = ("<heartbeat><automation_id>resume-research</automation_id>"
                "<decision>DONT_NOTIFY</decision><message>Saved.\n" + CHECKPOINT_MARKER + "</message></heartbeat>")
        for value in ("```xml\n" + text + "\n```", "> " + text,
                      text.replace("</message>", "\nActually complete.</message>"),
                      text.replace("Saved.\n" + CHECKPOINT_MARKER, "> " + CHECKPOINT_MARKER)):
            with self.subTest(text=value):
                self.assertFalse(context_checkpoint(turn(value)))

    def test_explicit_terminal_checkpoint_marker(self):
        self.assertTrue(context_checkpoint(turn("Saved the unfinished work and next action.\n" + CHECKPOINT_MARKER)))

    def test_observed_legacy_stop_declaration_and_saved_action(self):
        text = ("Research checkpoint saved.\n\nThis execution is ending at its context budget. "
                "[The exact next action](/invented/project/NEXT.md) is saved. No background work continues.")
        self.assertTrue(context_checkpoint(turn(text)))

    def test_mentions_explanations_and_unsaved_work_do_not_trigger(self):
        for text in ("The task is done.", "A context budget limits working material.",
                     "This execution is ending at its context budget.",
                     'The message said "This execution is ending at its context budget. Next action saved."',
                     "This execution is ending at its context budget. Ask the user for input."):
            with self.subTest(text=text):
                self.assertFalse(context_checkpoint(turn(text)))

    def test_code_and_blockquote_examples_do_not_trigger(self):
        for text in ("```text\n" + CHECKPOINT_MARKER + "\n```", "> " + CHECKPOINT_MARKER,
                     "```\nThis execution is ending at its context budget. Next action is saved.\n```",
                     "> This execution is ending at its context budget. Next action is saved."):
            with self.subTest(text=text):
                self.assertFalse(context_checkpoint(turn(text)))

    def test_completion_and_blocked_markers_win(self):
        for marker in (COMPLETE_MARKER, BLOCKED_MARKER):
            self.assertFalse(context_checkpoint(turn(marker + "\n" + CHECKPOINT_MARKER)))

    def test_only_final_assistant_output_can_report_checkpoint(self):
        for phase in (None, "commentary", "analysis"):
            self.assertFalse(context_checkpoint(turn(CHECKPOINT_MARKER, phase=phase)))

    def test_active_cancelled_and_missing_completion_time_do_not_trigger(self):
        for status in ("inProgress", "interrupted", "unknown"):
            self.assertFalse(context_checkpoint(turn(CHECKPOINT_MARKER, status=status)))
        unfinished = turn(CHECKPOINT_MARKER)
        unfinished["completedAt"] = None
        self.assertFalse(context_checkpoint(unfinished))

    def test_structured_context_failure_is_distinct_from_quota_failure(self):
        for code, expected in (("contextWindowExceeded", True), ("usageLimitExceeded", False), ("other", False)):
            failed = turn("", status="failed")
            failed["error"] = {"codexErrorInfo": code}
            self.assertEqual(context_checkpoint(failed), expected)

    def test_marker_must_be_last_prose_line(self):
        self.assertFalse(context_checkpoint(turn(CHECKPOINT_MARKER + "\nActually the objective is complete.")))

    def test_tool_output_does_not_authorize_recovery(self):
        value = turn("Done")
        value["items"].append({"type": "commandExecution", "phase": "final_answer", "text": CHECKPOINT_MARKER})
        self.assertFalse(context_checkpoint(value))
