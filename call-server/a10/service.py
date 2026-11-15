"""Synchronous business logic for contract A10. Every method raises ApiError on failure and
returns plain data. Side-effect notifications are returned as `events` lists
[(user_id, message_dict)] so the async layer can push them over WebSockets.
"""
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .db import Database, IntegrityError
from .ids import new_id, new_meeting_id, new_participant_id, normalize_meeting_id
from .settings import SUPPORTED_LANGS, THEMES, Settings

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def iso(ms: Optional[int]) -> Optional[str]:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(ms) % 1000:03d}Z"


def clean_text(v: Any, field: str, max_len: int, required=True) -> str:
    if v is None or (isinstance(v, str) and not v.strip()):
        if required:
            raise ApiError(400, "INVALID_INPUT", f"{field} is required.")
        return ""
    if not isinstance(v, str):
        raise ApiError(400, "INVALID_INPUT", f"{field} must be text.")
    v = "".join(ch for ch in v.strip() if ch.isprintable())
    if not v:
        raise ApiError(400, "INVALID_INPUT", f"{field} is required.")
    if len(v) > max_len:
        raise ApiError(400, "INVALID_INPUT", f"{field} must be at most {max_len} characters.")
    return v


class Service:
    def __init__(self, db: Database, settings: Settings, now_ms: Callable[[], int]):
        self.db, self.s, self.now_ms = db, settings, now_ms

    # ------------------------------------------------------------ users
    @staticmethod
    def user_public(u: dict) -> dict:
        return {
            "id": u["id"], "email": u["email"], "name": u["name"], "display_name": u["display_name"],
            "picture": u["picture"], "default_lang": u["default_lang"],
            "mic_default": bool(u["mic_default"]), "cam_default": bool(u["cam_default"]),
            "subtitles_only": bool(u["subtitles_only"]), "theme": u["theme"],
        }

    @staticmethod
    def user_card(u: dict) -> dict:
        return {"id": u["id"], "email": u["email"], "name": u["name"],
                "display_name": u["display_name"], "picture": u["picture"], "default_lang": u["default_lang"]}

    def get_user(self, uid: str) -> Optional[dict]:
        return self.db.one("SELECT * FROM users WHERE id = ?", (uid,))

    def upsert_google_user(self, claims: dict) -> dict:
        sub, email = str(claims["sub"]), str(claims["email"]).lower()
        name = (claims.get("name") or email.split("@")[0])[:80]
        picture = claims.get("picture")
        row = self.db.one("SELECT * FROM users WHERE google_sub = ?", (sub,))
        if row:
            self.db.execute("UPDATE users SET email = ?, name = ?, picture = ? WHERE id = ?",
                            (email, name, picture, row["id"]))
            return self.get_user(row["id"])
        if self.db.one("SELECT id FROM users WHERE email = ?", (email,)):
            raise ApiError(409, "EMAIL_CONFLICT", "This email is linked to another Google account.")
        uid = new_id("usr")
        try:
            self.db.execute(
                "INSERT INTO users(id, google_sub, email, name, display_name, picture, created_at) VALUES (?,?,?,?,?,?,?)",
                (uid, sub, email, name, name, picture, self.now_ms()))
        except IntegrityError:
            raise ApiError(409, "EMAIL_CONFLICT", "Account already exists.")
        return self.get_user(uid)

    def patch_me(self, uid: str, body: dict) -> dict:
        sets, vals = [], []
        if "display_name" in body:
            sets.append("display_name = ?"); vals.append(clean_text(body["display_name"], "display_name", 60))
        if "default_lang" in body:
            if body["default_lang"] not in SUPPORTED_LANGS:
                raise ApiError(400, "INVALID_INPUT", f"default_lang must be one of {list(SUPPORTED_LANGS)}.")
            sets.append("default_lang = ?"); vals.append(body["default_lang"])
        if "theme" in body:
            if body["theme"] not in THEMES:
                raise ApiError(400, "INVALID_INPUT", f"theme must be one of {list(THEMES)}.")
            sets.append("theme = ?"); vals.append(body["theme"])
        for f in ("mic_default", "cam_default", "subtitles_only"):
            if f in body:
                if not isinstance(body[f], bool):
                    raise ApiError(400, "INVALID_INPUT", f"{f} must be true or false.")
                sets.append(f"{f} = ?"); vals.append(1 if body[f] else 0)
        if sets:
            self.db.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", (*vals, uid))
        return self.user_public(self.get_user(uid))

    def delete_me(self, uid: str) -> List[Tuple[str, dict]]:
        events = []
        for f in self.db.all("SELECT user_a, user_b FROM friendships WHERE user_a = ? OR user_b = ?", (uid, uid)):
            other = f["user_b"] if f["user_a"] == uid else f["user_a"]
            events.append((other, {"type": "friend_removed", "user_id": uid}))
        hosted = [m["id"] for m in self.db.all("SELECT id FROM meetings WHERE host_id = ?", (uid,))]
        for mid in hosted:
            self.db.execute("DELETE FROM participations WHERE meeting_id = ?", (mid,))
            self.db.execute("DELETE FROM invites WHERE meeting_id = ?", (mid,))
            self.db.execute("DELETE FROM history_hidden WHERE meeting_id = ?", (mid,))
        self.db.execute("DELETE FROM meetings WHERE host_id = ?", (uid,))
        self.db.execute("DELETE FROM participations WHERE user_id = ?", (uid,))
        self.db.execute("DELETE FROM history_hidden WHERE user_id = ?", (uid,))
        self.db.execute("DELETE FROM friendships WHERE user_a = ? OR user_b = ?", (uid, uid))
        self.db.execute("DELETE FROM friend_requests WHERE from_id = ? OR to_id = ?", (uid, uid))
        self.db.execute("DELETE FROM invites WHERE from_id = ? OR to_id = ?", (uid, uid))
        self.db.execute("DELETE FROM users WHERE id = ?", (uid,))
        return events, hosted

    # --------------------------------------------------------- meetings
    def _refresh(self, m: dict) -> dict:
        """Lazy housekeeping: close stale participations; auto-end meetings that sat empty."""
        if m["ended_at"] is not None:
            return m
        now = self.now_ms()
        stale = now - self.s.stale_participation_hours * 3600_000
        self.db.execute("UPDATE participations SET left_at = joined_at WHERE meeting_id = ? AND left_at IS NULL AND joined_at < ?",
                        (m["id"], stale))
        agg = self.db.one("SELECT COUNT(CASE WHEN left_at IS NULL THEN 1 END) AS open_n, "
                          "MAX(joined_at) AS last_join, MAX(left_at) AS last_left FROM participations WHERE meeting_id = ?", (m["id"],))
        if (agg["open_n"] or 0) == 0:
            last = max(m["created_at"], agg["last_join"] or 0, agg["last_left"] or 0)
            if now - last > self.s.idle_end_minutes * 60_000:
                self.db.execute("UPDATE meetings SET ended_at = ? WHERE id = ? AND ended_at IS NULL", (last, m["id"]))
                m = dict(m, ended_at=last)
        return m

    def _meeting(self, raw_id: str) -> dict:
        mid = normalize_meeting_id(raw_id)
        if not mid:
            raise ApiError(400, "INVALID_MEETING_ID", "Meeting ID must look like abc-defg-hij.")
        m = self.db.one("SELECT * FROM meetings WHERE id = ?", (mid,))
        if not m:
            raise ApiError(404, "MEETING_NOT_FOUND", "No meeting with this ID.")
        return self._refresh(m)

    def meeting_public(self, m: dict, base_url: str) -> dict:
        host = self.get_user(m["host_id"])
        return {"id": m["id"], "title": m["title"], "host_id": m["host_id"],
                "host_name": host["display_name"] if host else None,
                "active": m["ended_at"] is None, "created_at": iso(m["created_at"]),
                "ended_at": iso(m["ended_at"]), "join_url": f"{base_url}/m/{m['id']}"}

    def create_meeting(self, uid: str, title: Any, base_url: str) -> dict:
        t = clean_text(title, "title", 80, required=False)
        for _ in range(8):
            mid = new_meeting_id()
            try:
                self.db.execute("INSERT INTO meetings(id, title, host_id, created_at) VALUES (?,?,?,?)",
                                (mid, t or f"Meeting {mid}", uid, self.now_ms()))
                return self.meeting_public(self.db.one("SELECT * FROM meetings WHERE id = ?", (mid,)), base_url)
            except IntegrityError:
                continue
        raise ApiError(500, "ID_GENERATION_FAILED", "Could not create a meeting ID, try again.")

    def get_meeting(self, raw_id: str, base_url: str) -> dict:
        return self.meeting_public(self._meeting(raw_id), base_url)

    def join_meeting(self, uid: str, raw_id: str, body: dict) -> dict:
        u = self.get_user(uid)
        m = self._meeting(raw_id)
        if m["ended_at"] is not None:
            raise ApiError(410, "MEETING_ENDED", "This meeting has ended.")
        name = clean_text(body.get("display_name") or u["display_name"], "display_name", 60)
        lang = body.get("lang") or u["default_lang"]
        if lang not in SUPPORTED_LANGS:
            raise ApiError(400, "INVALID_INPUT", f"lang must be one of {list(SUPPORTED_LANGS)}.")
        now = self.now_ms()
        self.db.execute("UPDATE participations SET left_at = ? WHERE meeting_id = ? AND user_id = ? AND left_at IS NULL",
                        (now, m["id"], uid))
        pid = new_participant_id()
        self.db.execute("INSERT INTO participations(id, meeting_id, user_id, participant_id, role, joined_at) VALUES (?,?,?,?,?,?)",
                        (new_id("prt"), m["id"], uid, pid, "host" if m["host_id"] == uid else "guest", now))
        self.db.execute("DELETE FROM history_hidden WHERE user_id = ? AND meeting_id = ?", (uid, m["id"]))
        return {"meeting_id": m["id"], "participant_id": pid, "display_name": name, "lang": lang}

    def end_meeting(self, uid: str, raw_id: str):
        m = self._meeting(raw_id)
        if m["host_id"] != uid:
            raise ApiError(403, "FORBIDDEN", "Only the host can end the meeting.")
        affected = [r["user_id"] for r in self.db.all(
            "SELECT DISTINCT user_id FROM participations WHERE meeting_id = ? AND left_at IS NULL", (m["id"],))]
        now = self.now_ms()
        self.db.execute("UPDATE meetings SET ended_at = ? WHERE id = ? AND ended_at IS NULL", (now, m["id"]))
        self.db.execute("UPDATE participations SET left_at = ? WHERE meeting_id = ? AND left_at IS NULL", (now, m["id"]))
        self.db.execute("DELETE FROM invites WHERE meeting_id = ?", (m["id"],))
        return m["id"], affected

    def participant_left(self, room_id: str, participant_id: str) -> Optional[str]:
        row = self.db.one("SELECT user_id FROM participations WHERE meeting_id = ? AND participant_id = ? AND left_at IS NULL",
                          (room_id, participant_id))
        if not row:
            return None
        self.db.execute("UPDATE participations SET left_at = ? WHERE meeting_id = ? AND participant_id = ? AND left_at IS NULL",
                        (self.now_ms(), room_id, participant_id))
        return row["user_id"]

    def room_state(self, room_id: str) -> str:
        """'active' | 'ended' | 'unknown' (not an A10 meeting)."""
        if not normalize_meeting_id(room_id):
            return "unknown"
        m = self.db.one("SELECT * FROM meetings WHERE id = ?", (room_id.lower(),))
        if not m:
            return "unknown"
        return "active" if self._refresh(m)["ended_at"] is None else "ended"

    def history(self, uid: str, cursor: Optional[str], limit: int = 20) -> dict:
        after_ts, after_id = None, None
        if cursor:
            try:
                a, b = cursor.split(":", 1)
                after_ts, after_id = int(a), b
            except ValueError:
                raise ApiError(400, "INVALID_CURSOR", "Bad cursor.")
        sql = ("SELECT m.* FROM meetings m WHERE (m.host_id = ? OR m.id IN (SELECT meeting_id FROM participations WHERE user_id = ?)) "
               "AND m.id NOT IN (SELECT meeting_id FROM history_hidden WHERE user_id = ?)")
        params: list = [uid, uid, uid]
        if after_ts is not None:
            sql += " AND (m.created_at < ? OR (m.created_at = ? AND m.id < ?))"
            params += [after_ts, after_ts, after_id]
        sql += " ORDER BY m.created_at DESC, m.id DESC LIMIT ?"
        params.append(limit + 1)
        rows = self.db.all(sql, params)
        more = len(rows) > limit
        rows = rows[:limit]
        now = self.now_ms()
        items = []
        for m in rows:
            m = self._refresh(m)
            cnt = self.db.one("SELECT COUNT(DISTINCT user_id) AS n FROM participations WHERE meeting_id = ?", (m["id"],))["n"]
            end = m["ended_at"] if m["ended_at"] is not None else now
            items.append({"id": m["id"], "title": m["title"], "started_at": iso(m["created_at"]),
                          "ended_at": iso(m["ended_at"]), "duration_s": max(0, int((end - m["created_at"]) / 1000)),
                          "participant_count": int(cnt), "role": "host" if m["host_id"] == uid else "guest",
                          "active": m["ended_at"] is None})
        nxt = f"{rows[-1]['created_at']}:{rows[-1]['id']}" if more and rows else None
        return {"items": items, "next_cursor": nxt}

    def hide_history(self, uid: str, raw_id: str):
        mid = normalize_meeting_id(raw_id)
        if not mid:
            raise ApiError(400, "INVALID_MEETING_ID", "Bad meeting ID.")
        try:
            self.db.execute("INSERT INTO history_hidden(user_id, meeting_id) VALUES (?,?)", (uid, mid))
        except IntegrityError:
            pass

    # ---------------------------------------------------------- friends
    @staticmethod
    def _pair(a: str, b: str) -> Tuple[str, str]:
        return (a, b) if a < b else (b, a)

    def are_friends(self, a: str, b: str) -> bool:
        x, y = self._pair(a, b)
        return self.db.one("SELECT 1 AS ok FROM friendships WHERE user_a = ? AND user_b = ?", (x, y)) is not None

    def friend_ids(self, uid: str) -> List[str]:
        rows = self.db.all("SELECT user_a, user_b FROM friendships WHERE user_a = ? OR user_b = ?", (uid, uid))
        return [r["user_b"] if r["user_a"] == uid else r["user_a"] for r in rows]

    def in_meeting(self, uid: str) -> bool:
        cutoff = self.now_ms() - self.s.stale_participation_hours * 3600_000
        return self.db.one("SELECT 1 AS ok FROM participations WHERE user_id = ? AND left_at IS NULL AND joined_at > ?",
                           (uid, cutoff)) is not None

    def presence(self, uid: str, connected: bool) -> str:
        if self.in_meeting(uid):
            return "in_meeting"
        return "online" if connected else "offline"

    def list_friends(self, uid: str, is_connected: Callable[[str], bool]) -> List[dict]:
        out = []
        for fid in self.friend_ids(uid):
            u = self.get_user(fid)
            if u:
                out.append({**self.user_card(u), "presence": self.presence(fid, is_connected(fid))})
        out.sort(key=lambda f: f["display_name"].lower())
        return out

    def list_requests(self, uid: str) -> List[dict]:
        out = []
        for r in self.db.all("SELECT * FROM friend_requests WHERE to_id = ? OR from_id = ? ORDER BY created_at DESC", (uid, uid)):
            if r["to_id"] == uid:
                u = self.get_user(r["from_id"])
                if u:
                    out.append({"id": r["id"], "direction": "inbound", "created_at": iso(r["created_at"]),
                                "from_user": {k: u[k] for k in ("id", "email", "name", "display_name", "picture")}})
            else:
                u = self.get_user(r["to_id"])
                if u:
                    out.append({"id": r["id"], "direction": "outbound", "created_at": iso(r["created_at"]),
                                "to_email": u["email"],
                                "to_user": {k: u[k] for k in ("id", "email", "name", "display_name", "picture")}})
        return out

    def _find_by_email(self, email: Any) -> dict:
        if not isinstance(email, str) or not EMAIL_RE.match(email.strip()):
            raise ApiError(400, "INVALID_EMAIL", "Enter a valid email address.")
        u = self.db.one("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
        if not u:
            raise ApiError(404, "USER_NOT_FOUND", "No user found with this exact email.")
        return u

    def search_user(self, uid: str, email: Any, is_connected) -> dict:
        u = self._find_by_email(email)
        if u["id"] == uid:
            raise ApiError(400, "CANNOT_ADD_SELF", "That is your own account.")
        friend = self.are_friends(uid, u["id"])
        rel = "friend" if friend else "none"
        if not friend:
            if self.db.one("SELECT 1 AS ok FROM friend_requests WHERE from_id = ? AND to_id = ?", (uid, u["id"])):
                rel = "pending_out"
            elif self.db.one("SELECT 1 AS ok FROM friend_requests WHERE from_id = ? AND to_id = ?", (u["id"], uid)):
                rel = "pending_in"
        return {**self.user_card(u), "presence": self.presence(u["id"], is_connected(u["id"])) if friend else "offline",
                "relationship": rel}

    def send_request(self, uid: str, email: Any):
        u = self._find_by_email(email)
        if u["id"] == uid:
            raise ApiError(400, "CANNOT_ADD_SELF", "You cannot add yourself.")
        if self.are_friends(uid, u["id"]):
            raise ApiError(409, "ALREADY_FRIENDS", "You are already friends.")
        if self.db.one("SELECT 1 AS ok FROM friend_requests WHERE from_id = ? AND to_id = ?", (uid, u["id"])):
            raise ApiError(409, "REQUEST_PENDING", "Request already sent.")
        reverse = self.db.one("SELECT id FROM friend_requests WHERE from_id = ? AND to_id = ?", (u["id"], uid))
        if reverse:  # they already asked us: both agree, so become friends
            events = self._make_friends(reverse["id"], uid, u["id"])
            return {"accepted": True, "id": reverse["id"], "to_email": u["email"], "direction": "outbound"}, events
        rid = new_id("req")
        now = self.now_ms()
        self.db.execute("INSERT INTO friend_requests(id, from_id, to_id, created_at) VALUES (?,?,?,?)", (rid, uid, u["id"], now))
        return ({"id": rid, "to_email": u["email"], "created_at": iso(now), "direction": "outbound"},
                [(u["id"], {"type": "friend_request"})])

    def _make_friends(self, req_id: str, a: str, b: str):
        x, y = self._pair(a, b)
        self.db.execute("DELETE FROM friend_requests WHERE id = ?", (req_id,))
        self.db.execute("DELETE FROM friend_requests WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?)", (a, b, b, a))
        try:
            self.db.execute("INSERT INTO friendships(user_a, user_b, created_at) VALUES (?,?,?)", (x, y, self.now_ms()))
        except IntegrityError:
            pass
        return [(a, {"type": "friend_accepted", "user_id": b}), (b, {"type": "friend_accepted", "user_id": a})]

    def accept_request(self, uid: str, req_id: str):
        r = self.db.one("SELECT * FROM friend_requests WHERE id = ? AND to_id = ?", (req_id, uid))
        if not r:
            raise ApiError(404, "REQUEST_NOT_FOUND", "Request not found.")
        return self._make_friends(r["id"], uid, r["from_id"])

    def decline_request(self, uid: str, req_id: str):
        n = self.db.execute("DELETE FROM friend_requests WHERE id = ? AND (to_id = ? OR from_id = ?)", (req_id, uid, uid))
        if not n:
            raise ApiError(404, "REQUEST_NOT_FOUND", "Request not found.")

    def remove_friend(self, uid: str, other: str):
        x, y = self._pair(uid, other)
        n = self.db.execute("DELETE FROM friendships WHERE user_a = ? AND user_b = ?", (x, y))
        if not n:
            raise ApiError(404, "NOT_FRIENDS", "Not in your friends list.")
        return [(other, {"type": "friend_removed", "user_id": uid})]

    # ---------------------------------------------------------- invites
    def invite(self, uid: str, raw_id: str, to_user: Any, base_url: str):
        m = self._meeting(raw_id)
        if m["ended_at"] is not None:
            raise ApiError(410, "MEETING_ENDED", "This meeting has ended.")
        if m["host_id"] != uid and not self.db.one(
                "SELECT 1 AS ok FROM participations WHERE meeting_id = ? AND user_id = ? AND left_at IS NULL", (m["id"], uid)):
            raise ApiError(403, "FORBIDDEN", "Join the meeting before inviting people.")
        if not isinstance(to_user, str) or not self.are_friends(uid, to_user):
            raise ApiError(403, "NOT_FRIENDS", "You can only invite friends.")
        self.db.execute("DELETE FROM invites WHERE meeting_id = ? AND to_id = ?", (m["id"], to_user))
        self.db.execute("INSERT INTO invites(id, meeting_id, from_id, to_id, created_at) VALUES (?,?,?,?,?)",
                        (new_id("inv"), m["id"], uid, to_user, self.now_ms()))
        return [(to_user, self.invite_event(m, self.get_user(uid), base_url))]

    def invite_event(self, m: dict, from_user: dict, base_url: str) -> dict:
        return {"type": "invite", "meeting_id": m["id"], "title": m["title"], "join_url": f"{base_url}/m/{m['id']}",
                "from_user": {"id": from_user["id"], "display_name": from_user["display_name"], "picture": from_user["picture"]}}

    def pending_invites(self, uid: str, base_url: str) -> List[dict]:
        cutoff = self.now_ms() - 3600_000
        out = []
        for i in self.db.all("SELECT * FROM invites WHERE to_id = ? AND created_at > ? ORDER BY created_at", (uid, cutoff)):
            m = self.db.one("SELECT * FROM meetings WHERE id = ?", (i["meeting_id"],))
            f = self.get_user(i["from_id"])
            if m and f and self._refresh(m)["ended_at"] is None:
                out.append(self.invite_event(m, f, base_url))
        return out
