import re
import secrets

_ALPHA = "abcdefghijklmnopqrstuvwxyz0123456789"
MEETING_ID_RE = re.compile(r"^[a-z0-9]{3}-[a-z0-9]{4}-[a-z0-9]{3}$")


def new_meeting_id() -> str:
    c = lambda n: "".join(secrets.choice(_ALPHA) for _ in range(n))
    return f"{c(3)}-{c(4)}-{c(3)}"


def normalize_meeting_id(raw: str):
    if not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    return s if MEETING_ID_RE.match(s) else None


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def new_participant_id() -> str:
    return "p-" + secrets.token_hex(4)
