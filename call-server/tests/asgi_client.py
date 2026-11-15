"""Minimal ASGI test client (httpx is not required). Supports cookies, JSON and WebSockets."""
import asyncio
import json
from urllib.parse import urlsplit


class Resp:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.body = status, headers, body

    def json(self):
        return json.loads(self.body or b"null")

    def set_cookies(self):
        return [v for k, v in self.headers if k == "set-cookie"]


class Client:
    def __init__(self, app, host="vaak.test", client_ip="1.2.3.4", origin=None):
        self.app, self.host, self.ip, self.origin = app, host, client_ip, origin
        self.cookies = {}

    def _headers(self, extra=None):
        h = [(b"host", self.host.encode())]
        if self.cookies:
            h.append((b"cookie", "; ".join(f"{k}={v}" for k, v in self.cookies.items()).encode()))
        if self.origin:
            h.append((b"origin", self.origin.encode()))
        for k, v in (extra or {}).items():
            h.append((k.lower().encode(), v.encode()))
        return h

    async def request(self, method, url, json_body=None, headers=None, raw=None):
        u = urlsplit(url)
        body = raw if raw is not None else (json.dumps(json_body).encode() if json_body is not None else b"")
        hdrs = self._headers(headers)
        if body:
            hdrs.append((b"content-type", b"application/json"))
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http",
                 "path": u.path, "raw_path": u.path.encode(), "query_string": u.query.encode(), "root_path": "",
                 "headers": hdrs, "client": (self.ip, 5000), "server": (self.host, 80)}
        sent = {"done": False}
        out = {"status": 0, "headers": [], "body": b""}

        async def receive():
            if not sent["done"]:
                sent["done"] = True
                return {"type": "http.request", "body": body, "more_body": False}
            await asyncio.sleep(3600)

        async def send(msg):
            if msg["type"] == "http.response.start":
                out["status"] = msg["status"]
                out["headers"] = [(k.decode().lower(), v.decode()) for k, v in msg["headers"]]
            elif msg["type"] == "http.response.body":
                out["body"] += msg.get("body", b"")

        await self.app(scope, receive, send)
        r = Resp(out["status"], out["headers"], out["body"])
        for c in r.set_cookies():
            name, _, rest = c.partition("=")
            val = rest.split(";", 1)[0]
            if val in ('""', ""):
                self.cookies.pop(name, None)
            else:
                self.cookies[name] = val
        return r

    def get(self, url, **k): return self.request("GET", url, **k)
    def post(self, url, json_body=None, **k): return self.request("POST", url, json_body=json_body, **k)
    def patch(self, url, json_body=None, **k): return self.request("PATCH", url, json_body=json_body, **k)
    def delete(self, url, **k): return self.request("DELETE", url, **k)

    def ws(self, path):
        return WS(self.app, path, self._headers(), (self.ip, 5000), self.host)


class WS:
    def __init__(self, app, path, headers, client, host):
        self.app, self.path, self.headers, self.client, self.host = app, path, headers, client, host
        self.inq, self.outq = asyncio.Queue(), asyncio.Queue()
        self.accepted = None
        self.close_code = None
        self.task = None

    async def __aenter__(self):
        scope = {"type": "websocket", "asgi": {"version": "3.0"}, "scheme": "ws", "path": self.path, "raw_path": self.path.encode(),
                 "query_string": b"", "root_path": "", "headers": self.headers, "client": self.client,
                 "server": (self.host, 80), "subprotocols": []}
        await self.inq.put({"type": "websocket.connect"})

        async def receive():
            return await self.inq.get()

        async def send(msg):
            await self.outq.put(msg)

        self.task = asyncio.create_task(self.app(scope, receive, send))
        first = await asyncio.wait_for(self.outq.get(), 3)
        if first["type"] == "websocket.accept":
            self.accepted = True
        else:
            self.accepted = False
            self.close_code = first.get("code")
        return self

    async def recv(self, timeout=2):
        msg = await asyncio.wait_for(self.outq.get(), timeout)
        if msg["type"] == "websocket.send":
            return json.loads(msg["text"]) if msg["text"].startswith("{") else msg["text"]
        self.close_code = msg.get("code")
        return None

    async def recv_all(self, wait=0.2):
        out = []
        while True:
            try:
                out.append(await self.recv(wait))
            except asyncio.TimeoutError:
                return out

    async def send_text(self, t):
        await self.inq.put({"type": "websocket.receive", "text": t})

    async def __aexit__(self, *a):
        await self.inq.put({"type": "websocket.disconnect", "code": 1000})
        try:
            await asyncio.wait_for(self.task, 3)
        except Exception:
            self.task.cancel()
