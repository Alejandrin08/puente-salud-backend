import json
import os
from dataclasses import dataclass, field


@dataclass
class Config:
    token_secret: str = field(default_factory=lambda: os.environ.get("TOKEN_SECRET", ""))
    token_horas: float = field(default_factory=lambda: float(os.environ.get("TOKEN_HORAS", "8")))
    internal_token: str = field(default_factory=lambda: os.environ.get("INTERNAL_TOKEN", ""))
    seguimiento_url: str = field(default_factory=lambda: os.environ.get("SEGUIMIENTO_URL", "http://seguimiento:8001"))
    territorio_url: str = field(default_factory=lambda: os.environ.get("TERRITORIO_URL", "http://territorio:8002"))
    cors_origins: list[str] = field(default_factory=lambda: [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()])
    demo_users: list[dict] = field(default_factory=lambda: json.loads(os.environ.get("DEMO_USERS") or "[]"))


config = Config()
if not config.token_secret:
    raise RuntimeError("Define TOKEN_SECRET en el entorno (ver .env.example)")
