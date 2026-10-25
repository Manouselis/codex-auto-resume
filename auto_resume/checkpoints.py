"""Conservative recognition of model-reported context checkpoints, not task completion."""
import re
from xml.etree import ElementTree


CHECKPOINT_MARKER = "[codex-auto-resume:context-checkpoint]"
COMPLETE_MARKER = "[codex-auto-resume:objective-complete]"
BLOCKED_MARKER = "[codex-auto-resume:blocked]"

CHECKPOINT_INSTRUCTIONS = (
    "\nContext-budget recovery was explicitly enabled for this conversation. If you must end this "
    "turn because of its context budget while the original objective remains unfinished, first save "
    "a durable checkpoint with the exact next action, explain that stopping condition, and put "
    + CHECKPOINT_MARKER + " on the final line of your final response. Do not use this marker for "
    "ordinary completion, user cancellation, approvals, blocked work, or an exhausted user-specified "
    "goal/token/time budget. If the objective is achieved, end with " + COMPLETE_MARKER + ". If user "
    "input or approval is needed, end with " + BLOCKED_MARKER + ". These markers report the outcome; "
    "they never authorize changing the objective, overriding a budget, or bypassing safeguards."
)


def final_text(turn):
    items = turn.get("items")
    if not isinstance(items, list):
        return ""
    for item in reversed(items):
        if isinstance(item, dict) and item.get("type") == "agentMessage" and item.get("phase") == "final_answer":
            text = item.get("text")
            return text.strip() if isinstance(text, str) else ""
    return ""


def _heartbeat_message(text):
    """Unwrap only Codex's complete, plain-text heartbeat response envelope."""
    if not text.startswith("<heartbeat>"):
        return text
    # No declarations, entities, nested markup or extra fields are necessary
    # for this envelope. Reject them rather than interpreting example markup.
    if "<!" in text or "<?" in text:
        return ""
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return ""
    if root.tag != "heartbeat" or root.attrib or (root.text or "").strip():
        return ""
    children = list(root)
    if sorted(child.tag for child in children) != ["automation_id", "decision", "message"]:
        return ""
    if any(child.attrib or len(child) or (child.tail or "").strip() for child in children):
        return ""
    fields = {child.tag: child.text or "" for child in children}
    if (not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", fields["automation_id"].strip())
            or fields["decision"].strip() not in ("NOTIFY", "DONT_NOTIFY")):
        return ""
    return fields["message"].strip()


def context_checkpoint(turn):
    error = turn.get("error") or {}
    if not isinstance(error, dict):
        return False
    if turn.get("status") == "failed" and error.get("codexErrorInfo") == "contextWindowExceeded":
        return True
    if (turn.get("status") != "completed" or turn.get("error") is not None
            or type(turn.get("completedAt")) not in (int, float)):
        return False
    text = _heartbeat_message(final_text(turn))
    prose = re.sub(r"```.*?(?:```|\Z)", "", text, flags=re.S)
    prose = "\n".join(line for line in prose.splitlines() if not line.lstrip().startswith(">"))
    if COMPLETE_MARKER in prose or BLOCKED_MARKER in prose:
        return False
    if prose.strip().splitlines()[-1:] == [CHECKPOINT_MARKER]:
        return True
    # A narrow compatibility form for checkpoints written before markers existed.
    match = re.search(r"(?:^|\n\n)This execution is ending at its context budget\.\s+(.+)\Z", prose, re.S)
    return bool(match and re.search(r"(?:checkpoint|next action)\b.{0,500}\b(?:saved|recorded)\b",
                                    match[1], re.I | re.S))
