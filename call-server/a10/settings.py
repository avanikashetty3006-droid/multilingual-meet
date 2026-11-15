import os
from dataclasses import dataclass, field
from typing import Optional, Tuple

SUPPORTED_LANGS = ("en", "hi", "kn", "ta", "te", "ml", "mr")
THEMES = ("light", "dark", "system")


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    database_url: str = "sqlite:///vaak.db"
    google_client_id: str = ""
    session_secret: str = ""
    cookie_secure: bool = True
    session_days: int = 14
    allowed_origins: Tuple[str, ...] = ()
    trust_proxy: bool = False
    proxy_hops: int = 1                 # trusted reverse proxies in front (nginx=1, Caddy+nginx=2)
    strict_rooms: bool = False          # refuse /ws/room for unknown meeting ids
    idle_end_minutes: int = 10          # empty meeting auto-ends after this
    stale_participation_hours: int = 12
    cookie_name: str = "vaak_session"
    public_url: str = ""                # e.g. https://meet.example.com (used for join_url)

    @staticmethod
    def from_env() -> "Settings":
        origins = tuple(o.strip().rstrip("/") for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip())
        s = Settings(
            database_url=os.getenv("DATABASE_URL", "sqlite:///vaak.db"),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
            session_secret=os.getenv("SESSION_SECRET", ""),
            cookie_secure=_bool("COOKIE_SECURE", True),
            allowed_origins=origins,
            trust_proxy=_bool("TRUST_PROXY", False),
            proxy_hops=max(1, int(os.getenv("TRUSTED_PROXY_HOPS", "1"))),
            strict_rooms=_bool("A10_STRICT_ROOMS", False),
            public_url=os.getenv("PUBLIC_URL", "").rstrip("/"),
        )
        return s

    def validate(self):
        if len(self.session_secret) < 32:
            raise RuntimeError(
                "SESSION_SECRET must be set to a random string of at least 32 characters "
                "(PowerShell: -join ((1..48) | % { '{0:x}' -f (Get-Random -Max 16) }) )"
            )
