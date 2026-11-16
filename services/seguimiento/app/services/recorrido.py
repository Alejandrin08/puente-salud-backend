"""Etapas del recorrido de la persona (arco de 4 pasos) y siguiente paso en lenguaje claro."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.services.dominio import Cita, Expediente
from app.services.semaforo import estado_medicion

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def fecha_larga(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


@dataclass
class Etapa:
    paso: int
    clave: str
    titulo: str
    completada: bool
    fecha: date | None
    detalle: str


@dataclass
class SiguientePaso:
    titulo: str
    texto: str
    cita: Cita | None


def etapas(e: Expediente) -> list[Etapa]:
    e.ordenar()
    trat = e.tratamientos[0].fecha_inicio if e.tratamientos else None
    evaluadas = [(m, estado_medicion(m, e.enfermedades)[0]) for m in e.mediciones if m.tiene_valores()]
    evaluadas = [x for x in evaluadas if x[1] is not None]
    en_control = bool(evaluadas) and evaluadas[-1][1] and e.fecha_confirmacion is not None
    enf = " y ".join({"diabetes": "diabetes", "hipertension": "presión alta"}[x] for x in e.enfermedades)
    return [
        Etapa(1, "deteccion", "Te detectaron", True, e.fecha_deteccion, f"Un programa de salud detectó posible {enf}."),
        Etapa(2, "confirmacion", "Confirmar", e.fecha_confirmacion is not None, e.fecha_confirmacion,
              "Tu diagnóstico está confirmado." if e.fecha_confirmacion else "Falta confirmar tu diagnóstico en tu centro de salud."),
        Etapa(3, "tratamiento", "Tratamiento", trat is not None, trat,
              "Ya tienes tratamiento." if trat else "Tu médica o médico te indicará tu tratamiento."),
        Etapa(4, "control", "En control", en_control, evaluadas[-1][0].fecha if en_control else None,
              "Tus valores están dentro de la meta." if en_control else "La meta es que tus valores estén en rango."),
    ]


def paso_actual(ets: list[Etapa]) -> int:
    for et in ets:
        if not et.completada:
            return et.paso
    return 4


def proxima_cita(e: Expediente, hoy: date) -> Cita | None:
    futuras = [c for c in e.citas if c.estado == "programada" and c.fecha >= hoy and c.tipo != "visita"]
    return futuras[0] if futuras else None


def siguiente_paso(e: Expediente, hoy: date, unidad: str) -> SiguientePaso:
    ets = etapas(e)
    paso = paso_actual(ets)
    cita = proxima_cita(e, hoy)
    cuando = (f"el {fecha_larga(cita.fecha)}" + (f" a las {cita.hora.strftime('%H:%M')}" if cita.hora else "")) if cita else None
    if paso == 2:
        if cita:
            return SiguientePaso("Confirma tu diagnóstico", f"Acude a tu cita {cuando} en {unidad}. Lleva tu folio.", cita)
        return SiguientePaso("Confirma tu diagnóstico",
                             f"Acude a {unidad} para confirmar tu diagnóstico. Lleva tu folio; no necesitas cita.", None)
    if paso == 3:
        txt = f"En tu consulta {cuando} te indicarán tu tratamiento." if cita else f"Pide tu consulta en {unidad} para iniciar tratamiento."
        return SiguientePaso("Inicia tu tratamiento", txt, cita)
    if not ets[3].completada:
        txt = (f"Toma tu medicamento como te indicaron y acude a tu control {cuando} en {unidad}." if cita
               else f"Toma tu medicamento y pide tu cita de control en {unidad}.")
        return SiguientePaso("Llega a tu meta", txt, cita)
    txt = f"Vas muy bien. Tu próximo control es {cuando} en {unidad}." if cita else f"Vas muy bien. Pide tu próximo control en {unidad}."
    return SiguientePaso("Mantén tu control", txt, cita)
