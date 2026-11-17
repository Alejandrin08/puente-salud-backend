"""Lógica del territorio: distancias, orden por cercanía y lectura de la mortalidad."""
from __future__ import annotations

import math
from datetime import date

import psycopg

from app.repositories import territorio_repo as repo
from app.schemas import (Feria, FeatureCollection, FilaReferencia, Mortalidad, PuntoMortalidad, ReferenciaSurtido,
                         ResumenMunicipio, SerieMortalidad,
                         Unidad)

ORDEN_REZAGO = ["Muy bajo", "Bajo", "Medio", "Alto", "Muy alto", "Sin dato"]
ETIQUETAS = {"diabetes": "Diabetes (E10–E14)", "hipertension": "Enfermedades hipertensivas (I10–I15)"}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def ordenar_por_cercania(items: list[dict], lat: float | None, lon: float | None) -> list[dict]:
    if lat is None or lon is None:
        return items
    for it in items:
        it["distancia_km"] = round(haversine_km(lat, lon, it["lat"], it["lon"]), 2)
    return sorted(items, key=lambda it: it["distancia_km"])


def tendencia(valores: list[int]) -> tuple[float | None, str]:
    """Variación porcentual entre el primer y el último año; «estable» si cambia menos de 5%."""
    if len(valores) < 2 or valores[0] == 0:
        return None, "estable"
    var = round((valores[-1] - valores[0]) / valores[0] * 100, 1)
    return var, "sube" if var >= 5 else ("baja" if var <= -5 else "estable")


def construir_mortalidad(filas: list[dict]) -> Mortalidad:
    if not filas:
        raise ValueError("Sin datos de mortalidad")
    series = []
    for causa in ("diabetes", "hipertension"):
        tot = [f for f in filas if f["causa"] == causa and f["sexo"] == "total"]
        ultimo = max(f["anio"] for f in tot)
        var, tend = tendencia([f["defunciones"] for f in tot])
        series.append(SerieMortalidad(
            causa=causa, etiqueta=ETIQUETAS[causa],
            serie=[PuntoMortalidad(anio=f["anio"], defunciones=f["defunciones"], tasa_100k=f["tasa_100k"]) for f in tot],
            por_sexo={f["sexo"]: f["defunciones"] for f in filas
                      if f["causa"] == causa and f["sexo"] != "total" and f["anio"] == ultimo},
            variacion_pct=var, tendencia=tend))
    total = [f for f in filas if f["causa"] == "total" and f["sexo"] == "total"]
    ult = max(total, key=lambda f: f["anio"])
    return Mortalidad(
        series=series, total_defunciones_ultimo_anio=ult["defunciones"], ultimo_anio=ult["anio"],
        poblacion_ref=ult["poblacion_ref"],
        fuente="INEGI, Estadísticas de Defunciones Registradas 2023–2025 (residencia habitual en San Pedro Tlaquepaque)",
        nota="Mortalidad municipal, no por AGEB. Tasa cruda con la población del Censo 2020 (687,127).")


def agebs(conn: psycopg.Connection) -> FeatureCollection:
    feats = []
    for r in repo.agebs_geojson(conn):
        geom = r.pop("geometry")
        feats.append({"type": "Feature", "id": r["cvegeo"], "geometry": geom,
                      "properties": {**r, "pct_sinder": float(r["pct_sinder"]) if r["pct_sinder"] is not None else None}})
    return FeatureCollection(features=feats, fuente="INEGI Censo 2020 y Marco Geoestadístico; CONEVAL rezago social AGEB 2020")


def unidades(conn: psycopg.Connection, tipo: str, lat: float | None, lon: float | None) -> list[Unidad]:
    filas = repo.unidades(conn, solo_folios=tipo == "folios", solo_urgencias=tipo == "urgencias")
    return [Unidad(**f) for f in ordenar_por_cercania(filas, lat, lon)]


def ferias(conn: psycopg.Connection, desde: date, lat: float | None, lon: float | None) -> list[Feria]:
    return [Feria(**f) for f in ordenar_por_cercania(repo.ferias(conn, desde), lat, lon)]


def mortalidad(conn: psycopg.Connection) -> Mortalidad:
    return construir_mortalidad(repo.mortalidad(conn))


def resumen(conn: psycopg.Connection) -> ResumenMunicipio:
    r = repo.resumen(conn)
    return ResumenMunicipio(
        agebs=r["agebs"], poblacion=r["poblacion"], poblacion_18ymas=r["p18"], sin_afiliacion=r["sinder"],
        sin_afiliacion_18_est=r["sinder18"], con_discapacidad=r["disc"],
        rezago={k: r["rezago"].get(k, 0) for k in ORDEN_REZAGO}, unidades_publicas=r["publicas"],
        unidades_total=r["total"], fuente="INEGI Censo 2020 (234 AGEB urbanas), CONEVAL 2020, CLUES 2024")


def referencia_surtido(conn: psycopg.Connection) -> ReferenciaSurtido:
    return ReferenciaSurtido(
        filas=[FilaReferencia(**f) for f in repo.referencia_surtido(conn)],
        fuente="ISSSTE, «Recetas de medicamentos efectivamente surtidas a la población derechohabiente», datos.gob.mx (CC-BY 4.0)",
        nota="Dato real de todas las recetas del ISSSTE (no solo diabetes e hipertensión). Sirve como referencia, no se mezcla con el surtido simulado.")
