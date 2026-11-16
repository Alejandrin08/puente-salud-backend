"""Casos de uso de la persona (paciente o cuidador): acceso, consentimiento, inicio y recorrido."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import asdict
from datetime import date

import psycopg
from fastapi import HTTPException

from app.config import Identidad
from app.repositories import seguimiento_repo as repo
from app.schemas import (AccesoOut, CitaOut, EtapaOut, EventoRecorrido, PersonaInicio, PersonaRecorrido,
                         SiguientePasoOut, UnidadOut)
from app.services import recorrido
from app.services.semaforo import estado_medicion

MENORES = {"de", "del", "la", "las", "los", "el", "y", "en", "a"}
SIGLAS = {"umf", "imss", "issste", "ssa", "cmct", "dif"}


def nombre_propio(texto: str) -> str:
    """«CENTRO DE SALUD SAN JOSÉ» -> «Centro de Salud San José»; conserva siglas."""
    out = []
    for i, w in enumerate(texto.lower().split()):
        if w in SIGLAS:
            out.append(w.upper())
        elif i and w in MENORES:
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


TIPO_CITA = {"confirmacion": "Cita para confirmar diagnóstico", "control": "Consulta de control", "visita": "Visita a domicilio"}


def verificar_acceso(conn: psycopg.Connection, folio: str, codigo: str) -> AccesoOut:
    folio = folio.strip().upper()
    p = repo.acceso_persona(conn, folio)
    esperado = hashlib.sha256(f"{folio}:{codigo.strip()}".encode()).hexdigest()
    if not p or not hmac.compare_digest(p["codigo_hash"], esperado):
        raise HTTPException(401, "El folio o el código no coinciden")
    repo.registrar(conn, folio, "persona", "acceso_persona", folio, {})
    conn.commit()
    return AccesoOut(folio=p["folio"], nombre=p["nombre"], curp_simulada=p["curp_simulada"], consentimiento=p["consentimiento"])


def _propio(ident: Identidad, folio: str) -> None:
    if ident.rol != "persona" or ident.folio != folio:
        raise HTTPException(403, "Solo puedes ver tu propio recorrido")


def consentimiento(conn: psycopg.Connection, ident: Identidad, folio: str, aceptado: bool) -> dict:
    _propio(ident, folio)
    repo.guardar_consentimiento(conn, folio, aceptado)
    repo.registrar(conn, folio, "persona", "consentimiento", folio, {"aceptado": aceptado})
    conn.commit()
    return {"folio": folio, "aceptado": aceptado}


def _expediente_con_consentimiento(conn, ident: Identidad, folio: str):
    _propio(ident, folio)
    p = repo.acceso_persona(conn, folio)
    if not p:
        raise HTTPException(404, "Folio no encontrado")
    if not p["consentimiento"]:
        raise HTTPException(409, "Primero acepta el uso de tus datos")
    return repo.expedientes(conn, folio=folio)[0]


def inicio(conn: psycopg.Connection, ident: Identidad, folio: str, hoy: date) -> PersonaInicio:
    e = _expediente_con_consentimiento(conn, ident, folio)
    u = repo.unidad(conn, e.unidad_clues)
    nombre_u = nombre_propio(u["nombre"]) if u else "tu centro de salud"
    ets = recorrido.etapas(e)
    sp = recorrido.siguiente_paso(e, hoy, nombre_u)
    zona = repo.ageb(conn, e.cvegeo) or {}
    return PersonaInicio(
        folio=folio, nombre=e.nombre, paso_actual=recorrido.paso_actual(ets), completado=all(x.completada for x in ets),
        etapas=[EtapaOut(**asdict(x)) for x in ets],
        siguiente_paso=SiguientePasoOut(titulo=sp.titulo, texto=sp.texto,
                                        cita=CitaOut(fecha=sp.cita.fecha, hora=sp.cita.hora, tipo=sp.cita.tipo,
                                                     estado=sp.cita.estado) if sp.cita else None),
        unidad=UnidadOut(**{**u, "nombre": nombre_u}) if u else UnidadOut(clues=e.unidad_clues or "", nombre="Tu centro de salud"),
        # Para «cercanos» se usa el centro de la AGEB, no el domicilio exacto
        zona={"lat": zona.get("lat"), "lon": zona.get("lon")})


def mi_recorrido(conn: psycopg.Connection, ident: Identidad, folio: str, hoy: date) -> PersonaRecorrido:
    e = _expediente_con_consentimiento(conn, ident, folio)
    ets = recorrido.etapas(e)
    ev: list[EventoRecorrido] = [EventoRecorrido(fecha=e.fecha_deteccion, tipo="deteccion", titulo="Te detectaron",
                                                 detalle="Primera medición en un programa de salud", estado="hecho")]
    for c in e.citas:
        if c.tipo == "visita" and c.estado != "atendida":
            continue
        estado = {"atendida": "hecho", "programada": "pendiente", "perdida": "perdido"}[c.estado]
        detalle = {"hecho": "Asististe", "pendiente": "Próxima cita", "perdido": "No asististe; puedes pedir otra cita"}[estado]
        ev.append(EventoRecorrido(fecha=c.fecha, tipo=c.tipo, titulo=TIPO_CITA[c.tipo], detalle=detalle, estado=estado))
    for t in e.tratamientos:
        ev.append(EventoRecorrido(fecha=t.fecha_inicio, tipo="tratamiento", titulo="Inicio de tratamiento",
                                  detalle=f"{t.medicamento}: {t.indicacion}", estado="hecho"))
    ultimas = [m for m in e.mediciones if m.tiene_valores()][-3:]
    for m in ultimas:
        ok, _ = estado_medicion(m, e.enfermedades)
        partes = ([f"presión {m.pas}/{m.pad}"] if m.pas else []) + ([f"glucosa {m.glucosa}"] if m.glucosa else []) + \
                 ([f"HbA1c {m.hba1c}%"] if m.hba1c else [])
        ev.append(EventoRecorrido(fecha=m.fecha, tipo="medicion", titulo="En tu meta" if ok else "Fuera de tu meta",
                                  detalle=", ".join(partes), estado="hecho"))
    ev.sort(key=lambda x: x.fecha)
    return PersonaRecorrido(folio=folio, paso_actual=recorrido.paso_actual(ets),
                            etapas=[EtapaOut(**asdict(x)) for x in ets], eventos=ev[-20:])
