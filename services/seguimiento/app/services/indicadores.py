"""Los cuatro indicadores de éxito (Anexo E.4), calculados desde el folio.

- Confirmación (%): detectadas con consulta de confirmación dentro del plazo ÷ detectadas.
  Solo cuentan quienes ya cumplieron el plazo (detección hace más de `dias_confirmacion` días).
- Tiempo a la primera consulta: mediana de días entre detección y primera consulta en la unidad.
- Retención R_k (%): iniciaron tratamiento hace al menos k meses y tienen consulta de control a los k meses
  (desde el mes k − 1 en adelante, tolerancia de 30 días) ÷ iniciaron tratamiento hace al menos k meses.
- Personas en control por programa C_p (%): en control en su última medición ÷ con diagnóstico confirmado.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, timedelta

from app.services.dominio import Expediente
from app.services.semaforo import estado_medicion


@dataclass
class Resumen:
    """Lo que cada folio aporta a los indicadores (no contiene datos personales)."""
    programa: str
    cvegeo: str
    deteccion: date
    confirmacion: date | None
    primera_consulta: date | None
    inicio_tratamiento: date | None
    controles: list[date]
    en_control: bool
    historial_control: list[tuple[date, bool]]


def resumir(e: Expediente) -> Resumen:
    e.ordenar()
    hist = []
    for m in e.mediciones:
        ok, _ = estado_medicion(m, e.enfermedades)
        if ok is not None:
            hist.append((m.fecha, ok))
    return Resumen(
        programa=e.programa_origen, cvegeo=e.cvegeo, deteccion=e.fecha_deteccion, confirmacion=e.fecha_confirmacion,
        primera_consulta=e.consultas[0].fecha if e.consultas else None,
        inicio_tratamiento=e.tratamientos[0].fecha_inicio if e.tratamientos else None,
        controles=[c.fecha for c in e.consultas if c.tipo == "control"],
        en_control=e.fecha_confirmacion is not None and bool(hist) and hist[-1][1],
        historial_control=hist)


def pct(num: int, den: int) -> float | None:
    return round(num / den * 100, 1) if den else None


def confirmacion(rs: list[Resumen], hoy: date, plazo: int = 30) -> tuple[float | None, int, int]:
    eleg = [r for r in rs if (hoy - r.deteccion).days > plazo]
    ok = [r for r in eleg if r.confirmacion and (r.confirmacion - r.deteccion).days <= plazo]
    return pct(len(ok), len(eleg)), len(ok), len(eleg)


def dias_primera_consulta(rs: list[Resumen]) -> tuple[float | None, int, float | None, float | None]:
    dias = sorted((r.primera_consulta - r.deteccion).days for r in rs if r.primera_consulta)
    if not dias:
        return None, 0, None, None
    q = statistics.quantiles(dias, n=4) if len(dias) >= 2 else [dias[0]] * 3
    return float(statistics.median(dias)), len(dias), float(q[0]), float(q[2])


def retencion(rs: list[Resumen], hoy: date, k: int) -> tuple[float | None, int, int]:
    dias_k = k * 30
    eleg = [r for r in rs if r.inicio_tratamiento and (hoy - r.inicio_tratamiento).days >= dias_k]
    ok = [r for r in eleg if any(c >= r.inicio_tratamiento + timedelta(days=dias_k - 30) for c in r.controles)]
    return pct(len(ok), len(eleg)), len(ok), len(eleg)


def en_control(rs: list[Resumen]) -> tuple[float | None, int, int]:
    conf = [r for r in rs if r.confirmacion]
    ok = [r for r in conf if r.en_control]
    return pct(len(ok), len(conf)), len(ok), len(conf)


def cuatro(rs: list[Resumen], hoy: date) -> dict:
    c, cn, cd = confirmacion(rs, hoy)
    med, n_med, p25, p75 = dias_primera_consulta(rs)
    r6, r6n, r6d = retencion(rs, hoy, 6)
    r12, r12n, r12d = retencion(rs, hoy, 12)
    ctl, ctln, ctld = en_control(rs)
    return {
        "detectadas": len(rs),
        "confirmacion_pct": c, "confirmacion_num": cn, "confirmacion_den": cd,
        "dias_primera_consulta_mediana": med, "dias_primera_consulta_n": n_med,
        "dias_primera_consulta_p25": p25, "dias_primera_consulta_p75": p75,
        "retencion_6_pct": r6, "retencion_6_num": r6n, "retencion_6_den": r6d,
        "retencion_12_pct": r12, "retencion_12_num": r12n, "retencion_12_den": r12d,
        "control_pct": ctl, "control_num": ctln, "control_den": ctld,
    }


def agrupar(rs: list[Resumen], clave: str) -> dict[str, list[Resumen]]:
    g: dict[str, list[Resumen]] = {}
    for r in rs:
        g.setdefault(getattr(r, clave), []).append(r)
    return g


def fin_de_mes(d: date) -> date:
    sig = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return sig - timedelta(days=1)


def evolucion_control(rs: list[Resumen], hoy: date, meses: int = 12) -> list[dict]:
    """% en control al cierre de cada mes, entre quienes ya tenían diagnóstico confirmado a esa fecha."""
    puntos = []
    cursor = hoy.replace(day=1)
    cierres = []
    for _ in range(meses):
        cierres.append(min(fin_de_mes(cursor), hoy))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    for cierre in reversed(cierres):
        den = num = 0
        for r in rs:
            if not r.confirmacion or r.confirmacion > cierre:
                continue
            den += 1
            prev = [ok for f, ok in r.historial_control if f <= cierre]
            num += bool(prev) and prev[-1]
        puntos.append({"mes": cierre.strftime("%Y-%m"), "control_pct": pct(num, den), "num": num, "den": den})
    return puntos


REZAGO_PESO = {"Muy bajo": 0.0, "Bajo": 0.25, "Medio": 0.5, "Alto": 0.75, "Muy alto": 1.0}


def prioridad_zona(control_pct: float | None, rezago: str, pct_sinder: float | None) -> tuple[float, list[str]]:
    """Índice ponderado (0 a 100) para ordenar zonas: 50% brecha de control, 30% rezago, 20% sin afiliación."""
    brecha = 1 - (control_pct or 0) / 100
    rz = REZAGO_PESO.get(rezago, 0.5)
    sa = (pct_sinder or 0) / 100
    score = round((0.5 * brecha + 0.3 * rz + 0.2 * sa) * 100, 1)
    factores = []
    if control_pct is not None and control_pct == 0:
        factores.append("nadie en control")
    elif control_pct is not None and control_pct < 40:
        factores.append(f"solo {control_pct:.0f}% en control")
    if rezago in ("Alto", "Muy alto", "Medio"):
        factores.append(f"rezago social {rezago.lower()}")
    if pct_sinder is not None and pct_sinder >= 35:
        factores.append(f"{pct_sinder:.0f}% sin afiliación")
    return score, factores
