import asyncio
import re

import pytest
from starlette.applications import Starlette
from starlette.routing import Mount, WebSocketRoute

from a10 import create_a10
from a10 import sessions
from a10.app import RoomBridge
from a10.ids import new_meeting_id, normalize_meeting_id
from a10.settings import Settings
from tests.asgi_client import Client

SECRET = "x" * 48
CLAIMS = {
    "tok-alice": {"sub": "g-alice", "email": "Alice@Example.com", "email_verified": True, "name": "Alice A", "picture": "http://p/a"},
    "tok-bob": {"sub": "g-bob", "email": "bob@example.com", "email_verified": True, "name": "Bob B"},
    "tok-carol": {"sub": "g-carol", "email": "carol@example.com", "email_verified": True, "name": "Carol C"},
    "tok-unverified": {"sub": "g-x", "email": "x@example.com", "email_verified": False, "name": "X"},
}


def fake_verify(cred):
    if cred in CLAIMS:
        return CLAIMS[cred]
    raise ValueError("bad token")


class FakeBridge(RoomBridge):
    def __init__(self):
        self.ended, self.joined = [], []

    async def join(self, meeting_id, participant_id, name, lang):
        self.joined.append((meeting_id, participant_id, name, lang))
        return {"livekit_token": f"jwt-for-{participant_id}", "livekit_url": "ws://lk.test:7880"}

    async def end_meeting(self, meeting_id):
        self.ended.append(meeting_id)


class Env:
    def __init__(self, **over):
        self.t = 1_700_000_000_000
        s = Settings(database_url="sqlite:///:memory:", session_secret=SECRET, cookie_secure=True, **over)
        self.bridge = FakeBridge()
        self.a10 = create_a10(self.bridge, s, verifier=fake_verify, now_ms=lambda: self.t)
        self.app = Starlette(routes=[Mount("/api/v1", app=self.a10.rest_app), WebSocketRoute("/ws/user", self.a10.user_ws)])

    def client(self, **k):
        return Client(self.app, **k)

    async def login(self, who, **k):
        c = self.client(**k)
        r = await c.post("/api/v1/auth/google", {"credential": f"tok-{who}"})
        assert r.status == 200, r.body
        return c, r.json()


def run(coro):
    return asyncio.run(coro)


def test_meeting_id_format():
    for _ in range(200):
        assert re.fullmatch(r"[a-z0-9]{3}-[a-z0-9]{4}-[a-z0-9]{3}", new_meeting_id())
    assert normalize_meeting_id("ABC-defg-hij") == "abc-defg-hij"
    assert normalize_meeting_id("abc-defg-hi") is None
    assert normalize_meeting_id("../etc/passwd") is None


def test_session_cookie_sign_verify():
    tok = sessions.sign(SECRET, "usr_1", 1, now_s=1000)
    assert sessions.verify(SECRET, tok, now_s=1001) == "usr_1"
    assert sessions.verify(SECRET, tok, now_s=1000 + 86400 + 1) is None
    assert sessions.verify("y" * 48, tok, now_s=1001) is None
    p, m = tok.split(".")
    assert sessions.verify(SECRET, p + "." + m[:-2] + "AA", now_s=1001) is None
    assert sessions.verify(SECRET, "garbage", now_s=1001) is None


def test_settings_require_strong_secret():
    with pytest.raises(RuntimeError):
        Settings(session_secret="short").validate()


def test_auth_flow_and_cookie_flags():
    async def go():
        e = Env()
        c = e.client()
        assert (await c.get("/api/v1/me")).status == 401
        r = await c.post("/api/v1/auth/google", {"credential": "nope"})
        assert r.status == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIAL"
        r = await c.post("/api/v1/auth/google", {"credential": "tok-unverified"})
        assert r.status == 401
        assert (await c.post("/api/v1/auth/google", {})).status == 400
        r = await c.post("/api/v1/auth/google", {"credential": "tok-alice"})
        assert r.status == 200
        ck = r.set_cookies()[0].lower()
        assert "httponly" in ck and "secure" in ck and "samesite=lax" in ck and "path=/" in ck
        u = r.json()
        assert u["email"] == "alice@example.com" and u["display_name"] == "Alice A" and u["id"].startswith("usr_")
        assert set(u) >= {"id", "email", "name", "display_name", "picture", "default_lang", "mic_default", "cam_default", "subtitles_only", "theme"}
        assert (await c.get("/api/v1/me")).json()["id"] == u["id"]
        # signing in again keeps the same account
        r2 = await c.post("/api/v1/auth/google", {"credential": "tok-alice"})
        assert r2.json()["id"] == u["id"]
        r = await c.post("/api/v1/auth/logout")
        assert r.status == 200
        assert (await c.get("/api/v1/me")).status == 401
    run(go())


def test_profile_patch_and_validation():
    async def go():
        e = Env()
        c, u = await e.login("alice")
        r = await c.patch("/api/v1/me", {"display_name": "  Ali  ", "default_lang": "hi", "theme": "dark",
                                         "mic_default": False, "cam_default": False, "subtitles_only": True,
                                         "email": "evil@x.com", "id": "usr_hacker"})
        d = r.json()
        assert r.status == 200 and d["display_name"] == "Ali" and d["default_lang"] == "hi" and d["theme"] == "dark"
        assert d["mic_default"] is False and d["subtitles_only"] is True
        assert d["email"] == "alice@example.com" and d["id"] == u["id"]
        for bad in ({"default_lang": "fr"}, {"theme": "neon"}, {"display_name": ""}, {"display_name": "x" * 61}, {"mic_default": "yes"}):
            assert (await c.patch("/api/v1/me", bad)).status == 400, bad
        assert (await c.patch("/api/v1/me", raw=b"{nope")).status == 400
    run(go())


def test_origin_check_blocks_cross_site_writes():
    async def go():
        e = Env()
        c, _ = await e.login("alice")
        c.origin = "https://evil.example"
        r = await c.post("/api/v1/meetings", {})
        assert r.status == 403 and r.json()["error"]["code"] == "BAD_ORIGIN"
        c.origin = "http://vaak.test"
        assert (await c.post("/api/v1/meetings", {})).status == 201
        c.origin = "https://evil.example"
        assert (await c.get("/api/v1/me")).status == 200  # reads are not blocked (SameSite=Lax + no CORS)
        e2 = Env(allowed_origins=("https://app.example.com",))
        c2, _ = await e2.login("alice")
        c2.origin = "https://app.example.com"
        assert (await c2.post("/api/v1/meetings", {})).status == 201
    run(go())


def test_meeting_lifecycle_and_history():
    async def go():
        e = Env()
        a, au = await e.login("alice")
        b, bu = await e.login("bob")
        r = await a.post("/api/v1/meetings", {"title": "Sprint <b>sync</b>"})
        m = r.json()
        assert r.status == 201 and re.fullmatch(r"[a-z0-9]{3}-[a-z0-9]{4}-[a-z0-9]{3}", m["id"])
        assert m["join_url"] == f"http://vaak.test/m/{m['id']}" and m["title"] == "Sprint <b>sync</b>"
        assert m["active"] is True and m["host_id"] == au["id"]
        g = await b.get(f"/api/v1/meetings/{m['id'].upper()}")
        assert g.status == 200 and g.json()["id"] == m["id"]
        assert (await b.get("/api/v1/meetings/abc-defg-hij")).status == 404
        assert (await b.get("/api/v1/meetings/not-an-id")).status == 400
        # join
        r = await b.post(f"/api/v1/meetings/{m['id']}/join", {"display_name": "Bobby", "lang": "kn"})
        j = r.json()
        assert r.status == 200 and j["livekit_token"] == f"jwt-for-{j['participant_id']}" and j["livekit_url"] == "ws://lk.test:7880"
        assert re.fullmatch(r"p-[0-9a-f]{8}", j["participant_id"])
        assert e.bridge.joined[-1] == (m["id"], j["participant_id"], "Bobby", "kn")
        assert (await b.post(f"/api/v1/meetings/{m['id']}/join", {"display_name": "B", "lang": "xx"})).status == 400
        assert (await b.post("/api/v1/meetings/abc-defg-hij/join", {"display_name": "B", "lang": "en"})).status == 404
        # host joins
        ja = (await a.post(f"/api/v1/meetings/{m['id']}/join", {"display_name": "Alice", "lang": "en"})).json()
        # history
        h = (await b.get("/api/v1/me/meetings")).json()
        assert h["next_cursor"] is None and len(h["items"]) == 1
        it = h["items"][0]
        assert it["id"] == m["id"] and it["role"] == "guest" and it["active"] is True and it["participant_count"] == 2
        assert set(it) == {"id", "title", "started_at", "ended_at", "duration_s", "participant_count", "role", "active"}
        assert (await a.get("/api/v1/me/meetings")).json()["items"][0]["role"] == "host"
        # only host can end
        r = await b.post(f"/api/v1/meetings/{m['id']}/end")
        assert r.status == 403
        e.t += 125_000
        assert (await a.post(f"/api/v1/meetings/{m['id']}/end")).status == 200
        assert e.bridge.ended == [m["id"]]
        assert (await a.post(f"/api/v1/meetings/{m['id']}/end")).status == 200  # idempotent
        it = (await b.get("/api/v1/me/meetings")).json()["items"][0]
        assert it["active"] is False and it["duration_s"] == 125 and it["ended_at"].endswith("Z")
        assert (await b.get(f"/api/v1/meetings/{m['id']}")).json()["active"] is False
        r = await b.post(f"/api/v1/meetings/{m['id']}/join", {"display_name": "B", "lang": "en"})
        assert r.status == 410 and r.json()["error"]["code"] == "MEETING_ENDED"
        # hide from my history only
        assert (await b.delete(f"/api/v1/me/meetings/{m['id']}")).status == 200
        assert (await b.get("/api/v1/me/meetings")).json()["items"] == []
        assert len((await a.get("/api/v1/me/meetings")).json()["items"]) == 1
    run(go())


def test_history_pagination():
    async def go():
        e = Env()
        a, _ = await e.login("alice")
        ids = []
        for i in range(25):
            e.t += 1000
            e.a10.rl.hits.clear()  # the 20/hour create limit is tested separately
            ids.append((await a.post("/api/v1/meetings", {"title": f"m{i}"})).json()["id"])
        p1 = (await a.get("/api/v1/me/meetings")).json()
        assert len(p1["items"]) == 20 and p1["next_cursor"]
        p2 = (await a.get(f"/api/v1/me/meetings?cursor={p1['next_cursor']}")).json()
        assert len(p2["items"]) == 5 and p2["next_cursor"] is None
        got = [i["id"] for i in p1["items"] + p2["items"]]
        assert got == list(reversed(ids)) and len(set(got)) == 25
        assert (await a.get("/api/v1/me/meetings?cursor=garbage")).status == 400
    run(go())


def test_empty_meeting_auto_ends_after_idle():
    async def go():
        e = Env(idle_end_minutes=10)
        a, _ = await e.login("alice")
        m = (await a.post("/api/v1/meetings", {})).json()
        j = (await a.post(f"/api/v1/meetings/{m['id']}/join", {"display_name": "A", "lang": "en"})).json()
        e.t += 3_600_000
        assert (await a.get(f"/api/v1/meetings/{m['id']}")).json()["active"] is True   # someone is still inside
        await e.a10.on_participant_left(m["id"], j["participant_id"])
        e.t += 9 * 60_000
        assert (await a.get(f"/api/v1/meetings/{m['id']}")).json()["active"] is True   # grace period
        e.t += 2 * 60_000
        assert (await a.get(f"/api/v1/meetings/{m['id']}")).json()["active"] is False  # auto-ended
        assert await e.a10.room_allowed(m["id"]) is False
    run(go())


def test_stale_open_participation_is_closed():
    async def go():
        e = Env(stale_participation_hours=12, idle_end_minutes=10)
        a, _ = await e.login("alice")
        m = (await a.post("/api/v1/meetings", {})).json()
        await a.post(f"/api/v1/meetings/{m['id']}/join", {"display_name": "A", "lang": "en"})  # never sends a leave
        e.t += 13 * 3_600_000
        assert (await a.get(f"/api/v1/meetings/{m['id']}")).json()["active"] is False
    run(go())


def test_room_allowed_hook():
    async def go():
        lax = Env()
        a, _ = await lax.login("alice")
        m = (await a.post("/api/v1/meetings", {})).json()
        assert await lax.a10.room_allowed(m["id"]) is True
        assert await lax.a10.room_allowed("loadtest-room") is True          # legacy rooms allowed by default
        strict = Env(strict_rooms=True)
        assert await strict.a10.room_allowed("loadtest-room") is False
        assert await strict.a10.room_allowed("abc-defg-hij") is False
        a2, _ = await strict.login("alice")
        m2 = (await a2.post("/api/v1/meetings", {})).json()
        assert await strict.a10.room_allowed(m2["id"]) is True
        await a2.post(f"/api/v1/meetings/{m2['id']}/end")
        assert await strict.a10.room_allowed(m2["id"]) is False
    run(go())


def test_friends_flow():
    async def go():
        e = Env()
        a, au = await e.login("alice")
        b, bu = await e.login("bob")
        c, cu = await e.login("carol")
        assert (await a.get("/api/v1/users/search?email=nobody@example.com")).status == 404
        assert (await a.get("/api/v1/users/search?email=notanemail")).status == 400
        assert (await a.get("/api/v1/users/search?email=alice@example.com")).json()["error"]["code"] == "CANNOT_ADD_SELF"
        s = (await a.get("/api/v1/users/search?email=BOB@example.com")).json()
        assert s["id"] == bu["id"] and s["relationship"] == "none" and s["presence"] == "offline"
        r = await a.post("/api/v1/friends/requests", {"email": "bob@example.com"})
        assert r.status == 200 and r.json()["direction"] == "outbound"
        assert (await a.post("/api/v1/friends/requests", {"email": "bob@example.com"})).status == 409
        assert (await a.get("/api/v1/users/search?email=bob@example.com")).json()["relationship"] == "pending_out"
        assert (await a.get("/api/v1/friends")).json() == []                   # not mutual yet
        reqs = (await b.get("/api/v1/friends/requests")).json()
        assert len(reqs) == 1 and reqs[0]["direction"] == "inbound" and reqs[0]["from_user"]["id"] == au["id"]
        out = (await a.get("/api/v1/friends/requests")).json()
        assert out[0]["direction"] == "outbound" and out[0]["to_email"] == "bob@example.com"
        # the sender cannot accept their own request, a third party cannot either
        assert (await a.post(f"/api/v1/friends/requests/{reqs[0]['id']}/accept")).status == 404
        assert (await c.post(f"/api/v1/friends/requests/{reqs[0]['id']}/accept")).status == 404
        assert (await b.post(f"/api/v1/friends/requests/{reqs[0]['id']}/accept")).status == 200
        fa = (await a.get("/api/v1/friends")).json()
        fb = (await b.get("/api/v1/friends")).json()
        assert [f["id"] for f in fa] == [bu["id"]] and [f["id"] for f in fb] == [au["id"]]
        assert fa[0]["presence"] == "offline" and fa[0]["display_name"] == "Bob B"
        assert (await a.post("/api/v1/friends/requests", {"email": "bob@example.com"})).json()["error"]["code"] == "ALREADY_FRIENDS"
        # decline + cancel
        await c.post("/api/v1/friends/requests", {"email": "alice@example.com"})
        ra = (await a.get("/api/v1/friends/requests")).json()
        assert (await a.post(f"/api/v1/friends/requests/{ra[0]['id']}/decline")).status == 200
        assert (await a.get("/api/v1/friends/requests")).json() == []
        await c.post("/api/v1/friends/requests", {"email": "alice@example.com"})
        rc = (await c.get("/api/v1/friends/requests")).json()
        assert (await c.post(f"/api/v1/friends/requests/{rc[0]['id']}/decline")).status == 200  # cancel by sender
        # crossing requests auto-accept
        await c.post("/api/v1/friends/requests", {"email": "alice@example.com"})
        r = await a.post("/api/v1/friends/requests", {"email": "carol@example.com"})
        assert r.json()["accepted"] is True
        assert len((await a.get("/api/v1/friends")).json()) == 2
        # remove
        assert (await a.delete(f"/api/v1/friends/{bu['id']}")).status == 200
        assert (await b.get("/api/v1/friends")).json() == []
        assert (await a.delete(f"/api/v1/friends/{bu['id']}")).status == 404
    run(go())


def test_rate_limits():
    async def go():
        e = Env()
        a, _ = await e.login("alice")
        codes = [(await a.get("/api/v1/users/search?email=zz%d@example.com" % i)).status for i in range(22)]
        assert codes[:20] == [404] * 20 and codes[20:] == [429, 429]
        # auth endpoint limited per IP
        c = e.client(client_ip="9.9.9.9")
        codes = [(await c.post("/api/v1/auth/google", {"credential": "bad"})).status for _ in range(12)]
        assert codes[:10] == [401] * 10 and codes[10:] == [429, 429]
        # other IPs unaffected
        assert (await e.client(client_ip="8.8.8.8").post("/api/v1/auth/google", {"credential": "tok-bob"})).status == 200
    run(go())


async def _befriend(e, a, b, bemail):
    await a.post("/api/v1/friends/requests", {"email": bemail})
    rid = (await b.get("/api/v1/friends/requests")).json()[0]["id"]
    await b.post(f"/api/v1/friends/requests/{rid}/accept")


def test_presence_over_websocket_friends_only():
    async def go():
        e = Env()
        a, au = await e.login("alice")
        b, bu = await e.login("bob")
        c, cu = await e.login("carol")
        await _befriend(e, a, b, "bob@example.com")
        async with b.ws("/ws/user") as wb, c.ws("/ws/user") as wc:
            assert wb.accepted and wc.accepted
            await wb.recv_all(); await wc.recv_all()
            async with a.ws("/ws/user") as wa:
                ev = await wb.recv()
                assert ev == {"type": "presence", "user_id": au["id"], "presence": "online"}
                assert (await wc.recv_all()) == []                          # carol is not a friend: sees nothing
                assert (await b.get("/api/v1/friends")).json()[0]["presence"] == "online"
                m = (await a.post("/api/v1/meetings", {})).json()
                j = (await a.post(f"/api/v1/meetings/{m['id']}/join", {"display_name": "A", "lang": "en"})).json()
                assert (await wb.recv())["presence"] == "in_meeting"
                assert (await b.get("/api/v1/friends")).json()[0]["presence"] == "in_meeting"
                await e.a10.on_participant_left(m["id"], j["participant_id"])
                assert (await wb.recv())["presence"] == "online"
            assert (await wb.recv())["presence"] == "offline"
        assert (await e.client().ws("/ws/user").__aenter__()).close_code == 4401
    run(go())


def test_ws_rejects_bad_origin_and_session():
    async def go():
        e = Env()
        a, _ = await e.login("alice")
        a.origin = "https://evil.example"
        w = await a.ws("/ws/user").__aenter__()
        assert w.accepted is False and w.close_code == 4403
        anon = e.client()
        w = await anon.ws("/ws/user").__aenter__()
        assert w.accepted is False and w.close_code == 4401
    run(go())


def test_invites_live_and_queued_and_friends_only():
    async def go():
        e = Env()
        a, au = await e.login("alice")
        b, bu = await e.login("bob")
        c, cu = await e.login("carol")
        await _befriend(e, a, b, "bob@example.com")
        m = (await a.post("/api/v1/meetings", {"title": "Standup"})).json()
        # must be inside the meeting to invite
        r = await a.post(f"/api/v1/meetings/{m['id']}/invite", {"user_id": bu["id"]})
        assert r.status == 200  # host may invite even before joining
        assert (await b.post(f"/api/v1/meetings/{m['id']}/invite", {"user_id": au["id"]})).status == 403  # b not in meeting
        assert (await a.post(f"/api/v1/meetings/{m['id']}/invite", {"user_id": cu["id"]})).json()["error"]["code"] == "NOT_FRIENDS"
        assert (await a.post(f"/api/v1/meetings/{m['id']}/invite", {})).status == 403
        # queued invite is delivered when bob connects
        async with b.ws("/ws/user") as wb:
            evs = await wb.recv_all()
            inv = [x for x in evs if x and x.get("type") == "invite"]
            assert len(inv) == 1 and inv[0]["meeting_id"] == m["id"] and inv[0]["from_user"]["id"] == au["id"]
            assert inv[0]["join_url"].endswith(f"/m/{m['id']}") and inv[0]["title"] == "Standup"
            # live delivery
            m2 = (await a.post("/api/v1/meetings", {"title": "Live"})).json()
            r = await a.post(f"/api/v1/meetings/{m2['id']}/invite", {"user_id": bu["id"]})
            assert r.json()["delivered"] is True and (await wb.recv())["meeting_id"] == m2["id"]
        # ended meetings are not invitable and queued invites vanish
        await a.post(f"/api/v1/meetings/{m['id']}/end")
        assert (await a.post(f"/api/v1/meetings/{m['id']}/invite", {"user_id": bu["id"]})).status == 410
    run(go())


def test_meeting_end_notifies_participants_over_user_ws():
    async def go():
        e = Env()
        a, _ = await e.login("alice")
        b, _ = await e.login("bob")
        m = (await a.post("/api/v1/meetings", {})).json()
        await b.post(f"/api/v1/meetings/{m['id']}/join", {"display_name": "B", "lang": "en"})
        async with b.ws("/ws/user") as wb:
            await wb.recv_all()
            await a.post(f"/api/v1/meetings/{m['id']}/end")
            evs = await wb.recv_all()
            assert {"type": "meeting_ended", "meeting_id": m["id"]} in evs
    run(go())


def test_bridge_failure_rolls_back_join():
    async def go():
        e = Env()

        async def boom(*a):
            raise RuntimeError("livekit down")
        e.bridge.join = boom
        a, _ = await e.login("alice")
        m = (await a.post("/api/v1/meetings", {})).json()
        r = await a.post(f"/api/v1/meetings/{m['id']}/join", {"display_name": "A", "lang": "en"})
        assert r.status == 502 and r.json()["error"]["code"] == "MEDIA_UNAVAILABLE"
        assert e.a10.svc.in_meeting((await a.get("/api/v1/me")).json()["id"]) is False
    run(go())


def test_delete_account_removes_everything():
    async def go():
        e = Env()
        a, au = await e.login("alice")
        b, bu = await e.login("bob")
        await _befriend(e, a, b, "bob@example.com")
        m = (await a.post("/api/v1/meetings", {})).json()
        await a.post(f"/api/v1/meetings/{m['id']}/join", {"display_name": "A", "lang": "en"})
        r = await a.delete("/api/v1/me")
        assert r.status == 200
        assert (await a.get("/api/v1/me")).status == 401
        assert (await b.get("/api/v1/friends")).json() == []
        assert (await b.get(f"/api/v1/meetings/{m['id']}")).status == 404
        assert e.bridge.ended == [m["id"]]
        for t in ("users", "meetings", "participations", "friendships", "friend_requests", "invites"):
            n = e.a10.db.one(f"SELECT COUNT(*) AS n FROM {t}")["n"]
            assert n == (1 if t == "users" else 0), t
        # a fresh sign-in with the same Google account creates a brand new account
        a2, au2 = await e.login("alice")
        assert au2["id"] != au["id"]
    run(go())


def test_body_limits_and_errors_are_json():
    async def go():
        e = Env()
        a, _ = await e.login("alice")
        r = await a.post("/api/v1/meetings", raw=b"x" * 20000)
        assert r.status == 413 and "error" in r.json()
        r = await a.post("/api/v1/meetings", raw=b"[1,2]")
        assert r.status == 400
        r = await a.post("/api/v1/meetings", {"title": "t" * 81})
        assert r.status == 400
        assert (await a.get("/api/v1/nope")).status == 404
    run(go())


def test_migrations_idempotent():
    from a10.db import Database
    d = Database("sqlite:///:memory:")
    d.migrate(); d.migrate()
    assert d.one("SELECT COUNT(*) AS n FROM schema_migrations")["n"] >= 8


def test_client_ip_from_forwarded_for_cannot_be_spoofed():
    async def go():
        e = Env(trust_proxy=True, proxy_hops=1)
        c = e.client(client_ip="10.0.0.2")
        # nginx appends the real client address; whatever the client put in front is ignored
        hdr = {"x-forwarded-for": "6.6.6.6, 203.0.113.7"}
        codes = [(await c.request("POST", "/api/v1/auth/google", {"credential": "bad"}, headers=hdr)).status for _ in range(11)]
        assert codes[-1] == 429
        # a different real client (last entry) gets its own bucket even if the spoofed prefix is the same
        r = await c.request("POST", "/api/v1/auth/google", {"credential": "tok-bob"}, headers={"x-forwarded-for": "6.6.6.6, 203.0.113.8"})
        assert r.status == 200
        e2 = Env(trust_proxy=False)
        assert e2.a10._ip(type("C", (), {"headers": {"x-forwarded-for": "1.1.1.1"}, "client": type("A", (), {"host": "9.9.9.9"})()})()) == "9.9.9.9"
    run(go())
