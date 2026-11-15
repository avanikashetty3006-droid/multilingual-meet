"""Contract A10: production JSON API (auth, meetings, history, friends, presence).

Usage from main.py:
    from a10 import create_a10
    a10 = create_a10(bridge=MyBridge(...))
    app.mount("/api/v1", a10.rest_app)
    app.add_api_websocket_route("/ws/user", a10.user_ws)   # or see main_patch notes
"""
from .app import create_a10, A10, RoomBridge  # noqa: F401
