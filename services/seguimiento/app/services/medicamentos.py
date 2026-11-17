"""Numeralia de medicamentos para la autoridad (informativa): surtido, cobertura y demanda según el semáforo.

Definiciones:
- Receta surtida completa: registro de surtido (MedicationDispense) marcado como completo.
- Persona sin medicamento cubierto: en tratamiento y, para algún medicamento, su último surtido fue incompleto,
  ya se le acabó (fecha + días cubiertos < hoy) o nunca se surtió.
- Necesidad mensual: personas en tratamiento × tabletas al día × 30.
- Prioridad de reabasto por unidad: 3 × sin cobertura en rojo + 2 × en amarillo + 1 × resto.
No es un sistema logístico: ordena y explica para apoyar la planeación.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from app.services.dominio import Expediente
from app.services.indicadores import fin_de_mes, pct
from app.services.semaforo import Resultado

DOSIS_DIA = {"Metformina 850 mg": 2, "Glibenclamida 5 mg": 1, "Losartán 50 mg": 1, "Enalapril 10 mg": 1, "Amlodipino 5 mg": 1}
ENFERMEDAD = {"Metformina 850 mg": "diabetes", "Glibenclamida 5 mg": "diabetes", "Losartán 50 mg": "hipertension",
              "Enalapril 10 mg": "hipertension", "Amlodipino 5 mg": "hipertension"}
PESO = {"rojo": 3, "amarillo": 2, "gris": 1, "verde": 1}


def faltantes(e: Expediente, hoy: date) -> list[str]:
    """Medicamentos indicados que la persona no tiene cubiertos hoy."""
    out = []
    for t in e.tratamientos:
        sur = [s for s in e.surtidos if s.medicamento == t.medicamento]
        if not sur:
            out.append(t.medicamento)
            continue
        ult = max(sur, key=lambda s: s.fecha)
        if not ult.completo or ult.fecha + timedelta(days=ult.dias) < hoy:
            out.append(t.medicamento)
    return out


def calcular(pares: list[tuple[Expediente, Resultado]], unidades: dict[str, dict], hoy: date, meses: int = 12) -> dict:
    desde = hoy - timedelta(days=365)
    rec = defaultdict(lambda: [0, 0])                     # medicamento -> [completas, total] últimos 12 meses
    rec_u = defaultdict(lambda: [0, 0])                   # unidad -> idem
    trat_med = defaultdict(int)                           # medicamento -> personas en tratamiento
    sin_med = defaultdict(lambda: defaultdict(int))       # medicamento -> nivel -> personas sin cobertura
    por_u = defaultdict(lambda: {"tratamiento": 0, "sin": defaultdict(int), "meds": defaultdict(int)})
    en_trat = sin_cob = 0
    sin_por_nivel = defaultdict(int)
    for e, r in pares:
        for s in e.surtidos:
            if s.fecha >= desde:
                rec[s.medicamento][0] += s.completo
                rec[s.medicamento][1] += 1
                rec_u[e.unidad_clues][0] += s.completo
                rec_u[e.unidad_clues][1] += 1
        if not e.tratamientos:
            continue
        en_trat += 1
        u = por_u[e.unidad_clues]
        u["tratamiento"] += 1
        for t in e.tratamientos:
            trat_med[t.medicamento] += 1
        falta = faltantes(e, hoy)
        if falta:
            sin_cob += 1
            sin_por_nivel[r.nivel] += 1
            u["sin"][r.nivel] += 1
            for m in falta:
                sin_med[m][r.nivel] += 1
                u["meds"][m] += 1

    medicamentos = []
    for m in sorted(set(trat_med) | set(rec), key=lambda x: (ENFERMEDAD.get(x, ""), x)):
        sn = sin_med[m]
        total_sin = sum(sn.values())
        medicamentos.append({
            "medicamento": m, "enfermedad": ENFERMEDAD.get(m, ""), "personas_tratamiento": trat_med[m],
            "surtido_completo_pct": pct(rec[m][0], rec[m][1]), "recetas_12m": rec[m][1],
            "sin_cobertura": total_sin, "sin_cobertura_rojo": sn["rojo"], "sin_cobertura_amarillo": sn["amarillo"],
            "necesidad_mensual_tabletas": trat_med[m] * DOSIS_DIA.get(m, 1) * 30,
            "faltante_mensual_tabletas": total_sin * DOSIS_DIA.get(m, 1) * 30,
        })

    filas_u = []
    for clues, u in por_u.items():
        info = unidades.get(clues, {})
        sin = u["sin"]
        prioridad = sum(PESO[n] * c for n, c in sin.items())
        top = sorted(u["meds"].items(), key=lambda kv: -kv[1])[:2]
        filas_u.append({
            "clues": clues, "nombre": info.get("nombre", clues), "institucion": info.get("institucion", ""),
            "personas_tratamiento": u["tratamiento"], "surtido_completo_pct": pct(rec_u[clues][0], rec_u[clues][1]),
            "sin_cobertura": sum(sin.values()), "sin_cobertura_rojo": sin["rojo"], "sin_cobertura_amarillo": sin["amarillo"],
            "prioridad": prioridad, "medicamentos_faltantes": [{"medicamento": m, "personas": c} for m, c in top],
        })
    filas_u.sort(key=lambda f: (-f["prioridad"], f["nombre"]))

    evolucion = []
    cursor = hoy.replace(day=1)
    cierres = []
    for _ in range(meses):
        cierres.append((cursor, min(fin_de_mes(cursor), hoy)))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    for ini, fin in reversed(cierres):
        c = t = 0
        for e, _ in pares:
            for s in e.surtidos:
                if ini <= s.fecha <= fin:
                    c += s.completo
                    t += 1
        evolucion.append({"mes": ini.strftime("%Y-%m"), "surtido_completo_pct": pct(c, t), "recetas": t})

    total_c = sum(v[0] for v in rec.values())
    total_t = sum(v[1] for v in rec.values())
    return {
        "resumen": {
            "recetas_12m": total_t, "surtido_completo_pct": pct(total_c, total_t), "recetas_incompletas_12m": total_t - total_c,
            "personas_tratamiento": en_trat, "personas_sin_cobertura": sin_cob,
            "sin_cobertura_por_nivel": {n: sin_por_nivel[n] for n in ("rojo", "amarillo", "gris", "verde")},
        },
        "medicamentos": medicamentos, "unidades": filas_u, "evolucion": evolucion,
    }
