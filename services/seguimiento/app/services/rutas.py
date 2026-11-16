"""Ruta de visitas domiciliarias: orden por prioridad y vecino más cercano.

Distancia en línea recta (haversine) y tiempo aproximado: 18 km/h promedio urbano + 20 minutos por visita.
No es una ruta por calles (fuera del MVP, Anexo E.7).
"""
from __future__ import annotations

import math

VELOCIDAD_KMH = 18.0
MIN_POR_VISITA = 20


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def minutos(km: float) -> int:
    return round(km / VELOCIDAD_KMH * 60)


def ordenar_ruta(origen: tuple[float, float], paradas: list[dict]) -> list[dict]:
    """Primero las rojas y luego las demás; dentro de cada grupo, vecino más cercano desde el punto anterior."""
    ruta: list[dict] = []
    actual = origen
    for grupo in ("rojo", "amarillo", "gris", "verde"):
        pend = [p for p in paradas if p["nivel"] == grupo]
        while pend:
            sig = min(pend, key=lambda p: haversine_km(actual[0], actual[1], p["lat"], p["lon"]))
            km = haversine_km(actual[0], actual[1], sig["lat"], sig["lon"])
            ruta.append({**sig, "orden": len(ruta) + 1, "distancia_km": round(km, 2), "minutos_traslado": minutos(km)})
            actual = (sig["lat"], sig["lon"])
            pend.remove(sig)
    return ruta


def totales(ruta: list[dict]) -> dict:
    km = sum(p["distancia_km"] for p in ruta)
    traslado = sum(p["minutos_traslado"] for p in ruta)
    return {"distancia_km": round(km, 2), "minutos_traslado": traslado,
            "minutos_total": traslado + MIN_POR_VISITA * len(ruta)}
