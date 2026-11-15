"""HTTP + WebSocket layer for contract A10 (Starlette; mounted into the FastAPI call-server)."""
import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.websockets import WebSocket, WebSocketDisconnect

from . import sessions
from .db import Database
from .ratelimit import RateLimiter
from .service import ApiError, Service
from .settings import Settings

log = logging.getLogger("a10")
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


class RoomBridge:
    """Connects A10 to the existing call-server room/LiveKit code. main.py provides a real one."""

    async def join(self, meeting_id: str, participant_id: str, name: str, lang: str) -> Dict[str, Any]:
        """Return {"livekit_token": ..., "livekit_url": ...}."""
        raise NotImplementedError

    async def end_meeting(self, meeting_id: str) -> None:
        """Tell everybody in the room the meeting ended and close their sockets."""
        raise NotImplementedError


def default_google_verifier(client_id: str) -> Callable[[str], dict]:
    def verify(credential: str) -> dict:
        from google.auth.transport import requests as greq  # type: ignore
        from google.oauth2 import id_token  # type: ignore
        return id_token.verify_oauth2_token(credential, greq.Request(), client_id)
    return verify


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


class A10:
    def __init__(self, settings: Settings, bridge: RoomBridge, verifier: Optional[Callable[[str], dict]] = None,
                 now_ms: Optional[Callable[[], int]] = None, db: Optional[Database] = None):
        settings.validate()
        self.s = settings
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))
        self.db = db or Database(settings.database_url)
        self.db.migrate()
        self.svc = Service(self.db, settings, self.now_ms)
        self.bridge = bridge
        if verifier is None:
            if not settings.google_client_id:
                raise RuntimeError("GOOGLE_CLIENT_ID is not set")
            verifier = default_google_verifier(settings.google_client_id)
        self.verifier = verifier
        self.rl = RateLimiter()
        self.conns: Dict[str, Set[WebSocket]] = {}
        self.rest_app = Starlette(routes=self._routes(), exception_handlers={Exception: self._unhandled})

    # ---------------------------------------------------------------- plumbing
    async def _unhandled(self, request, exc):
        log.exception("A10 unhandled error: %s", exc)
        return _err(500, "INTERNAL_ERROR", "Something went wrong on our side.")

    def _ip(self, conn) -> str:
        if self.s.trust_proxy:
            xff = conn.headers.get("x-forwarded-for")
            if xff:
                parts = [x.strip() for x in xff.split(",") if x.strip()]
                if parts:  # entries are appended by each proxy; count from the right so clients cannot spoof
                    return parts[-self.s.proxy_hops] if len(parts) >= self.s.proxy_hops else parts[0]
        return conn.client.host if conn.client else "unknown"

    def _base_url(self, request: Request) -> str:
        if self.s.public_url:
            return self.s.public_url
        proto, host = request.url.scheme, request.headers.get("host", "localhost")
        if self.s.trust_proxy:
            proto = request.headers.get("x-forwarded-proto", proto)
            host = request.headers.get("x-forwarded-host", host)
        return f"{proto}://{host}"

    def _origin_ok(self, conn) -> bool:
        origin = conn.headers.get("origin")
        if not origin:
            return True
        origin = origin.rstrip("/")
        if origin in self.s.allowed_origins:
            return True
        host = conn.headers.get("x-forwarded-host", "") if self.s.trust_proxy else ""
        host = host or conn.headers.get("host", "")
        return origin.split("://", 1)[-1] == host

    def _user_from(self, conn) -> Optional[dict]:
        tok = conn.cookies.get(self.s.cookie_name)
        if not tok:
            return None
        uid = sessions.verify(self.s.session_secret, tok)
        return self.svc.get_user(uid) if uid else None

    def _set_cookie(self, resp: JSONResponse, uid: str):
        resp.set_cookie(self.s.cookie_name, sessions.sign(self.s.session_secret, uid, self.s.session_days),
                        max_age=self.s.session_days * 86400, httponly=True, secure=self.s.cookie_secure,
                        samesite="lax", path="/")

    def _clear_cookie(self, resp: JSONResponse):
        resp.delete_cookie(self.s.cookie_name, path="/", httponly=True, secure=self.s.cookie_secure, samesite="lax")

    def _wrap(self, fn, auth=True, rl: Optional[tuple] = None):
        """rl = (bucket, limit, window_s); keyed by user id (or IP when anonymous)."""
        async def handler(request: Request):
            try:
                if request.method in UNSAFE and not self._origin_ok(request):
                    return _err(403, "BAD_ORIGIN", "Cross-site request blocked.")
                user = None
                if auth:
                    user = await asyncio.to_thread(self._user_from, request)
                    if not user:
                        return _err(401, "UNAUTHORIZED", "Please sign in.")
                if rl:
                    key = f"{rl[0]}:{user['id'] if user else self._ip(request)}"
                    if not self.rl.allow(key, rl[1], rl[2]):
                        return _err(429, "RATE_LIMITED", "Too many requests. Please slow down.")
                return await fn(request, user)
            except ApiError as e:
                return _err(e.status, e.code, e.message)
        return handler

    async def _body(self, request: Request) -> dict:
        raw = await request.body()
        if len(raw) > 16384:
            raise ApiError(413, "TOO_LARGE", "Request body too large.")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except ValueError:
            raise ApiError(400, "INVALID_JSON", "Body must be valid JSON.")
        if not isinstance(data, dict):
            raise ApiError(400, "INVALID_JSON", "Body must be a JSON object.")
        return data

    def _run(self, fn, *a):
        return asyncio.to_thread(fn, *a)

    # --------------------------------------------------------------- presence
    def is_connected(self, uid: str) -> bool:
        return bool(self.conns.get(uid))

    async def send_user(self, uid: str, msg: dict) -> bool:
        ok = False
        for ws in list(self.conns.get(uid, ())):
            try:
                await ws.send_text(json.dumps(msg))
                ok = True
            except Exception:
                self.conns.get(uid, set()).discard(ws)
        return ok

    async def push(self, events: List[tuple]):
        for uid, msg in events:
            await self.send_user(uid, msg)

    async def notify_presence(self, uid: str):
        """Tell this user's online friends about the user's new presence (friends only)."""
        def work():
            return self.svc.friend_ids(uid), self.svc.presence(uid, self.is_connected(uid))
        fids, state = await self._run(work)
        for fid in fids:
            await self.send_user(fid, {"type": "presence", "user_id": uid, "presence": state})

    async def user_ws(self, ws: WebSocket):
        if not self._origin_ok(ws):
            await ws.close(code=4403)
            return
        user = await self._run(self._user_from, ws)
        if not user:
            await ws.close(code=4401)
            return
        uid = user["id"]
        if len(self.conns.get(uid, ())) >= 5:
            await ws.close(code=4429)
            return
        await ws.accept()
        self.conns.setdefault(uid, set()).add(ws)
        try:
            await self.notify_presence(uid)
            for ev in await self._run(self.svc.pending_invites, uid, self._base_url_ws(ws)):
                await ws.send_text(json.dumps(ev))
            while True:
                msg = await ws.receive_text()
                if msg == "ping":
                    await ws.send_text("pong")
        except WebSocketDisconnect:
            pass
        except Exception as e:
            log.debug("user ws closed: %s", e)
        finally:
            self.conns.get(uid, set()).discard(ws)
            if not self.conns.get(uid):
                self.conns.pop(uid, None)
            await self.notify_presence(uid)

    def _base_url_ws(self, ws: WebSocket) -> str:
        if self.s.public_url:
            return self.s.public_url
        host = ws.headers.get("host", "localhost")
        proto = "https" if self.s.cookie_secure else "http"
        return f"{proto}://{host}"

    # -------------------------------------------------- hooks for call-server
    async def on_participant_left(self, room_id: str, participant_id: str):
        uid = await self._run(self.svc.participant_left, room_id, participant_id)
        if uid:
            await self.notify_presence(uid)

    async def room_allowed(self, room_id: str) -> bool:
        """False when /ws/room or /ws/audio must refuse this room (ended, or unknown in strict mode)."""
        state = await self._run(self.svc.room_state, room_id)
        if state == "ended":
            return False
        if state == "unknown" and self.s.strict_rooms:
            return False
        return True

    # ----------------------------------------------------------------- routes
    def _routes(self):
        w = self._wrap
        return [
            Route("/auth/google", w(self.h_google, auth=False, rl=("auth", 10, 60)), methods=["POST"]),
            Route("/auth/logout", w(self.h_logout, auth=False), methods=["POST"]),
            Route("/me", w(self.h_me_get), methods=["GET"]),
            Route("/me", w(self.h_me_patch, rl=("patch_me", 30, 60)), methods=["PATCH"]),
            Route("/me", w(self.h_me_delete, rl=("del_me", 3, 3600)), methods=["DELETE"]),
            Route("/me/meetings", w(self.h_history), methods=["GET"]),
            Route("/me/meetings/{mid}", w(self.h_history_hide), methods=["DELETE"]),
            Route("/meetings", w(self.h_meeting_create, rl=("mk_meeting", 20, 3600)), methods=["POST"]),
            Route("/meetings/{mid}", w(self.h_meeting_get, rl=("get_meeting", 120, 60)), methods=["GET"]),
            Route("/meetings/{mid}/join", w(self.h_meeting_join, rl=("join", 60, 60)), methods=["POST"]),
            Route("/meetings/{mid}/end", w(self.h_meeting_end), methods=["POST"]),
            Route("/meetings/{mid}/invite", w(self.h_invite, rl=("invite", 30, 60)), methods=["POST"]),
            Route("/friends", w(self.h_friends), methods=["GET"]),
            Route("/friends/requests", w(self.h_requests), methods=["GET"]),
            Route("/friends/requests", w(self.h_request_send, rl=("friend_req", 20, 3600)), methods=["POST"]),
            Route("/friends/requests/{rid}/accept", w(self.h_request_accept), methods=["POST"]),
            Route("/friends/requests/{rid}/decline", w(self.h_request_decline), methods=["POST"]),
            Route("/friends/{uid}", w(self.h_friend_remove), methods=["DELETE"]),
            Route("/users/search", w(self.h_search, rl=("search", 20, 60)), methods=["GET"]),
        ]

    async def h_google(self, request, _):
        body = await self._body(request)
        cred = body.get("credential")
        if not isinstance(cred, str) or not cred or len(cred) > 4096:
            raise ApiError(400, "INVALID_INPUT", "Missing Google credential.")
        try:
            claims = await asyncio.to_thread(self.verifier, cred)
        except Exception as e:
            log.info("google verify failed: %s", e)
            raise ApiError(401, "INVALID_CREDENTIAL", "Google sign-in could not be verified.")
        if not claims.get("email_verified") or not claims.get("sub") or not claims.get("email"):
            raise ApiError(401, "INVALID_CREDENTIAL", "Google account email is not verified.")
        user = await self._run(self.svc.upsert_google_user, claims)
        resp = JSONResponse(self.svc.user_public(user))
        self._set_cookie(resp, user["id"])
        return resp

    async def h_logout(self, request, _):
        resp = JSONResponse({"ok": True})
        self._clear_cookie(resp)
        return resp

    async def h_me_get(self, request, user):
        return JSONResponse(self.svc.user_public(user))

    async def h_me_patch(self, request, user):
        body = await self._body(request)
        return JSONResponse(await self._run(self.svc.patch_me, user["id"], body))

    async def h_me_delete(self, request, user):
        events, hosted = await self._run(self.svc.delete_me, user["id"])
        for mid in hosted:
            try:
                await self.bridge.end_meeting(mid)
            except Exception:
                log.exception("bridge.end_meeting failed")
        for ws in list(self.conns.pop(user["id"], ())):
            try:
                await ws.close()
            except Exception:
                pass
        await self.push(events)
        resp = JSONResponse({"ok": True})
        self._clear_cookie(resp)
        return resp

    async def h_history(self, request, user):
        return JSONResponse(await self._run(self.svc.history, user["id"], request.query_params.get("cursor")))

    async def h_history_hide(self, request, user):
        await self._run(self.svc.hide_history, user["id"], request.path_params["mid"])
        return JSONResponse({"ok": True})

    async def h_meeting_create(self, request, user):
        body = await self._body(request)
        data = await self._run(self.svc.create_meeting, user["id"], body.get("title"), self._base_url(request))
        return JSONResponse(data, status_code=201)

    async def h_meeting_get(self, request, user):
        return JSONResponse(await self._run(self.svc.get_meeting, request.path_params["mid"], self._base_url(request)))

    async def h_meeting_join(self, request, user):
        body = await self._body(request)
        info = await self._run(self.svc.join_meeting, user["id"], request.path_params["mid"], body)
        try:
            lk = await self.bridge.join(info["meeting_id"], info["participant_id"], info["display_name"], info["lang"])
        except Exception:
            log.exception("bridge.join failed")
            await self._run(self.svc.participant_left, info["meeting_id"], info["participant_id"])
            raise ApiError(502, "MEDIA_UNAVAILABLE", "Could not get a media token. Try again.")
        await self.notify_presence(user["id"])
        return JSONResponse({**lk, "participant_id": info["participant_id"], "meeting_id": info["meeting_id"]})

    async def h_meeting_end(self, request, user):
        mid, affected = await self._run(self.svc.end_meeting, user["id"], request.path_params["mid"])
        try:
            await self.bridge.end_meeting(mid)
        except Exception:
            log.exception("bridge.end_meeting failed")
        for uid in set(affected):
            await self.send_user(uid, {"type": "meeting_ended", "meeting_id": mid})
            await self.notify_presence(uid)
        return JSONResponse({"ok": True})

    async def h_invite(self, request, user):
        body = await self._body(request)
        events = await self._run(self.svc.invite, user["id"], request.path_params["mid"], body.get("user_id"), self._base_url(request))
        delivered = False
        for uid, msg in events:
            delivered = await self.send_user(uid, msg) or delivered
        return JSONResponse({"sent": True, "recipient": body.get("user_id"), "delivered": delivered})

    async def h_friends(self, request, user):
        return JSONResponse(await self._run(self.svc.list_friends, user["id"], self.is_connected))

    async def h_requests(self, request, user):
        return JSONResponse(await self._run(self.svc.list_requests, user["id"]))

    async def h_search(self, request, user):
        return JSONResponse(await self._run(self.svc.search_user, user["id"], request.query_params.get("email"), self.is_connected))

    async def h_request_send(self, request, user):
        body = await self._body(request)
        data, events = await self._run(self.svc.send_request, user["id"], body.get("email"))
        await self.push(events)
        return JSONResponse(data)

    async def h_request_accept(self, request, user):
        events = await self._run(self.svc.accept_request, user["id"], request.path_params["rid"])
        await self.push(events)
        for uid, msg in events:
            await self.notify_presence(uid)
        return JSONResponse({"ok": True})

    async def h_request_decline(self, request, user):
        await self._run(self.svc.decline_request, user["id"], request.path_params["rid"])
        return JSONResponse({"ok": True})

    async def h_friend_remove(self, request, user):
        events = await self._run(self.svc.remove_friend, user["id"], request.path_params["uid"])
        await self.push(events)
        return JSONResponse({"ok": True})


def create_a10(bridge: RoomBridge, settings: Optional[Settings] = None, **kw) -> A10:
    return A10(settings or Settings.from_env(), bridge, **kw)
