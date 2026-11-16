"""Cliente de los servicios internos (red privada). Único lugar donde el gateway habla con ellos."""
from __future__ import annotations

import httpx
from fastapi import HTTPException
from fastapi.responses import Response

from app.config import config

NOMBRES = {"seguimiento": "seguimiento", "territorio": "territorio"}
_clientes: dict[str, httpx.AsyncClient] = {}


def cliente(servicio: str) -> httpx.AsyncClient:
    if servicio not in _clientes:
        base = config.seguimiento_url if servicio == "seguimiento" else config.territorio_url
        _clientes[servicio] = httpx.AsyncClient(base_url=base, timeout=httpx.Timeout(15.0, connect=3.0),
                                                headers={"X-Internal-Token": config.internal_token})
    return _clientes[servicio]


async def cerrar() -> None:
    for c in _clientes.values():
        await c.aclose()
    _clientes.clear()


async def llamar(servicio: str, metodo: str, ruta: str, cabeceras: dict | None = None, params=None,
                 json=None) -> httpx.Response:
    try:
        return await cliente(servicio).request(metodo, ruta, headers=cabeceras or {}, params=params, json=json)
    except httpx.HTTPError as e:
        raise HTTPException(503, f"El servicio de {NOMBRES[servicio]} no responde. Intenta de nuevo en un momento.") from e


async def reenviar(servicio: str, metodo: str, ruta: str, cabeceras: dict | None = None, params=None, json=None) -> Response:
    r = await llamar(servicio, metodo, ruta, cabeceras, params, json)
    salida = {k: v for k, v in r.headers.items() if k.lower() in ("content-type", "content-disposition")}
    return Response(content=r.content, status_code=r.status_code, headers=salida)


async def salud(servicio: str) -> bool:
    try:
        return (await cliente(servicio).get("/health")).status_code == 200
    except httpx.HTTPError:
        return False
