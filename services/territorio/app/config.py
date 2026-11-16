import os
from collections.abc import Iterator

import psycopg
from fastapi import Header, HTTPException
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get("DATABASE_URL", "")
INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN", "")


def get_conn() -> Iterator[psycopg.Connection]:
    if not DATABASE_URL:
        raise HTTPException(503, "DATABASE_URL no configurada")
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn


def internal_only(x_internal_token: str = Header(default="")) -> None:
    """Solo el gateway llama a este servicio (red privada + secreto compartido)."""
    if INTERNAL_TOKEN and x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(401, "Acceso solo desde el gateway")
