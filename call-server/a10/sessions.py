"""Stateless signed session cookie: base64url(json).hmac_sha256. No tokens in localStorage."""
import base64
import hashlib
import hmac
import json
import time
from typing import Optional


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign(secret: str, user_id: str, days: int, now_s: Optional[float] = None) -> str:
    now_s = time.time() if now_s is None else now_s
    payload = _b64(json.dumps({"uid": user_id, "exp": int(now_s + days * 86400)}, separators=(",", ":")).encode())
    mac = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{mac}"


def verify(secret: str, token: str, now_s: Optional[float] = None) -> Optional[str]:
    now_s = time.time() if now_s is None else now_s
    try:
        payload, mac = token.split(".", 1)
        good = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(mac, good):
            return None
        data = json.loads(_unb64(payload))
        if data["exp"] < now_s:
            return None
        return str(data["uid"])
    except Exception:
        return None
