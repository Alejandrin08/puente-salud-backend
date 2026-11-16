"""Token de sesión firmado con HMAC-SHA256 (sin dependencias externas). Va en la cabecera Authorization."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


class TokenInvalido(Exception):
    pass


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def emitir(datos: dict, secreto: str, horas: float, ahora: float | None = None) -> tuple[str, int]:
    exp = int((time.time() if ahora is None else ahora) + horas * 3600)
    cuerpo = _b64(json.dumps({**datos, "exp": exp}, separators=(",", ":"), ensure_ascii=False).encode())
    firma = _b64(hmac.new(secreto.encode(), cuerpo.encode(), hashlib.sha256).digest())
    return f"{cuerpo}.{firma}", exp


def verificar(token: str, secreto: str, ahora: float | None = None) -> dict:
    try:
        cuerpo, firma = token.split(".")
    except ValueError as e:
        raise TokenInvalido("Formato de token inválido") from e
    esperada = _b64(hmac.new(secreto.encode(), cuerpo.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(firma, esperada):
        raise TokenInvalido("Firma inválida")
    datos = json.loads(_unb64(cuerpo))
    if datos.get("exp", 0) < (time.time() if ahora is None else ahora):
        raise TokenInvalido("La sesión expiró")
    return datos
