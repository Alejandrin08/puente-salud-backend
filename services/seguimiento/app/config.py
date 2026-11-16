import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

import psycopg
from fastapi import Header, HTTPException
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get("DATABASE_URL", "")
INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN", "")


def hoy() -> date:
    """Fecha de referencia del recorrido. FECHA_REFERENCIA permite fijarla (pruebas, demostraciones)."""
    f = os.environ.get("FECHA_REFERENCIA")
    return date.fromisoformat(f) if f else date.today()


def get_conn() -> Iterator[psycopg.Connection]:
    if not DATABASE_URL:
        raise HTTPException(503, "DATABASE_URL no configurada")
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn


def internal_only(x_internal_token: str = Header(default="")) -> None:
    if INTERNAL_TOKEN and x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(401, "Acceso solo desde el gateway")


@dataclass(frozen=True)
class Identidad:
    """Identidad que el gateway ya verificó y reenvía en cabeceras internas."""
    usuario: str
    rol: str
    clues: str | None
    folio: str | None


def identidad(x_usuario: str = Header(default="anonimo"), x_rol: str = Header(default=""),
              x_clues: str = Header(default=""), x_folio: str = Header(default="")) -> Identidad:
    return Identidad(x_usuario, x_rol, x_clues or None, x_folio or None)


def requiere(*roles: str):
    def dep(x_rol: str = Header(default="")) -> None:
        if x_rol not in roles:
            raise HTTPException(403, "Tu rol no tiene acceso a este recurso")
    return dep
