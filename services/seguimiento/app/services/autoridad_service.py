"""Casos de uso de la autoridad: solo datos agregados (por programa y por AGEB), con exportación."""
from __future__ import annotations

import csv
import io
from datetime import date

import psycopg

from app.config import Identidad
from app.repositories import seguimiento_repo as repo
from app.schemas import (Cuatro, Evolucion, IndicadorAgeb, Indicadores, IndicadoresAgeb, IndicadoresPrograma,
                         PuntoEvolucion)
from app.services import indicadores as ind

MINIMO_CASOS = 3
DEFINICIONES = {
    "confirmacion": "Personas detectadas con consulta de confirmación dentro de 30 días ÷ personas detectadas hace más de 30 días.",
    "dias_primera_consulta": "Mediana de días entre la detección y la primera consulta en la unidad de salud.",
    "retencion": "Personas que iniciaron tratamiento hace al menos 6 meses (o 12) y siguen con consulta de control a los 6 meses (o 12) ÷ personas que iniciaron tratamiento hace al menos 6 meses (o 12).",
    "control": "Personas con diagnóstico confirmado en meta de la NOM-015 (diabetes) o NOM-030 (hipertensión) en su última medición ÷ personas con diagnóstico confirmado.",
}


def _resumenes(conn) -> list[ind.Resumen]:
    return [ind.resumir(e) for e in repo.expedientes(conn)]


def indicadores(conn: psycopg.Connection, hoy: date) -> Indicadores:
    rs = _resumenes(conn)
    progs = repo.programas(conn)
    grupos = ind.agrupar(rs, "programa")
    por = [IndicadoresPrograma(programa_id=pid, programa=p["nombre"], ambito=p["ambito"], **ind.cuatro(grupos.get(pid, []), hoy))
           for pid, p in progs.items()]
    por.sort(key=lambda x: -(x.control_pct or 0))
    return Indicadores(fecha_corte=hoy, total=Cuatro(**ind.cuatro(rs, hoy)), por_programa=por, definiciones=DEFINICIONES)


def evolucion(conn: psycopg.Connection, hoy: date, meses: int = 12) -> Evolucion:
    rs = _resumenes(conn)
    progs = repo.programas(conn)
    grupos = ind.agrupar(rs, "programa")
    return Evolucion(total=[PuntoEvolucion(**p) for p in ind.evolucion_control(rs, hoy, meses)],
                     por_programa={pid: [PuntoEvolucion(**p) for p in ind.evolucion_control(grupos.get(pid, []), hoy, meses)]
                                   for pid in progs},
                     programas={pid: p["nombre"] for pid, p in progs.items()})


def por_ageb(conn: psycopg.Connection, hoy: date) -> IndicadoresAgeb:
    rs = _resumenes(conn)
    ctx = repo.agebs_contexto(conn)
    grupos = ind.agrupar(rs, "cvegeo")
    out = []
    for cvegeo, c in ctx.items():
        g = grupos.get(cvegeo, [])
        ctl, ctln, ctld = ind.en_control(g)
        conf, _, _ = ind.confirmacion(g, hoy)
        suficiente = ctld >= MINIMO_CASOS
        prio, fact = ind.prioridad_zona(ctl, c["rezago"], c["pct_sinder"]) if suficiente else (None, [])
        out.append(IndicadorAgeb(cvegeo=cvegeo, detectadas=len(g), confirmadas=ctld, control_pct=ctl if suficiente else None,
                                 control_num=ctln, confirmacion_pct=conf if suficiente else None, rezago=c["rezago"],
                                 pct_sinder=c["pct_sinder"], prioridad=prio, factores=fact, suficiente=suficiente))
    zonas = sorted([a for a in out if a.prioridad is not None], key=lambda a: -a.prioridad)[:10]
    return IndicadoresAgeb(
        fecha_corte=hoy, minimo_casos=MINIMO_CASOS, agebs=sorted(out, key=lambda a: a.cvegeo), zonas_prioritarias=zonas,
        nota=(f"Porcentaje en control calculado con datos simulados; se muestra solo en AGEB con al menos {MINIMO_CASOS} "
              "personas confirmadas. Prioridad = 50% brecha de control + 30% rezago social (CONEVAL) + 20% sin afiliación (Censo)."))


def exportar_csv(conn: psycopg.Connection, ident: Identidad, hoy: date, por: str) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    campos = ["detectadas", "confirmacion_pct", "dias_primera_consulta_mediana", "retencion_6_pct", "retencion_12_pct", "control_pct"]
    w.writerow(["# Puente Salud · indicadores E.4 · datos simulados", f"corte {hoy.isoformat()}"])
    if por == "programa":
        data = indicadores(conn, hoy)
        w.writerow(["programa_id", "programa"] + campos)
        for p in data.por_programa:
            w.writerow([p.programa_id, p.programa] + [getattr(p, c) for c in campos])
        w.writerow(["total", "Todos los programas"] + [getattr(data.total, c) for c in campos])
    else:
        rs = _resumenes(conn)
        ctx = repo.agebs_contexto(conn)
        grupos = ind.agrupar(rs, "cvegeo")
        w.writerow(["cvegeo", "rezago", "pct_sin_afiliacion"] + campos + ["casos_suficientes"])
        for cvegeo in sorted(ctx):
            cu = ind.cuatro(grupos.get(cvegeo, []), hoy)
            w.writerow([cvegeo, ctx[cvegeo]["rezago"], ctx[cvegeo]["pct_sinder"]] + [cu[c] for c in campos]
                       + [cu["control_den"] >= MINIMO_CASOS])
    repo.registrar(conn, ident.usuario, ident.rol, "exportar_indicadores", None, {"por": por})
    conn.commit()
    return buf.getvalue()
