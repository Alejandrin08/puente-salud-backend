"""Casos de uso del personal de salud: lista ordenada por semáforo, recorrido, medición, desacuerdo y ruta."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date

import psycopg
from fastapi import HTTPException

from app.config import Identidad
from app.repositories import seguimiento_repo as repo
from app.schemas import (Adherencia, AgendaItem, CitaOut, DesacuerdoOut, EtapaOut, EventoBitacora, MedicionCreada,
                         MedicionIn, MedicionOut, PacienteDetalle, PacienteFila, ParadaRuta, PersonaDetalle,
                         ResumenSeguimiento, Ruta, SemaforoOut, SurtidoOut, UnidadOut)
from app.services import recorrido, rutas
from app.services.dominio import Expediente, Parametros
from app.services.semaforo import SEVERIDAD, Resultado, estado_medicion, evaluar

PROGRAMA_DE_UNIDAD = "centros_rxii"
VISTAS = {"consultar_recorrido", "sugerencia_semaforo"}  # se auditan todas; en pantalla se resumen  # el personal de las unidades registra como Centros de salud Región XII


def edad(e: Expediente, hoy: date) -> int:
    n = e.fecha_nacimiento
    return hoy.year - n.year - ((hoy.month, hoy.day) < (n.month, n.day)) if n else 0


def semaforo_out(r: Resultado) -> SemaforoOut:
    return SemaforoOut(nivel=r.nivel, resumen=r.resumen, motivos=[asdict(m) for m in r.motivos], dimensiones=r.dimensiones,
                       requiere_valoracion=r.requiere_valoracion, factores_riesgo=r.factores_riesgo, dias_vencida=r.dias_vencida)


def cita_out(c) -> CitaOut | None:
    return CitaOut(fecha=c.fecha, hora=c.hora, tipo=c.tipo, estado=c.estado) if c else None


def evaluar_todos(conn: psycopg.Connection, hoy: date, clues: str | None = None) -> list[tuple[Expediente, Resultado]]:
    params = repo.parametros(conn)
    return [(e, evaluar(e, hoy, params.get(e.programa_origen, Parametros()))) for e in repo.expedientes(conn, clues=clues)]


def orden_prioridad(par: tuple[Expediente, Resultado]) -> tuple:
    e, r = par
    return (-SEVERIDAD[r.nivel], -r.dias_vencida, -len(r.factores_riesgo), e.folio)


def fila(e: Expediente, r: Resultado, hoy: date) -> PacienteFila:
    return PacienteFila(folio=e.folio, nombre=f"{e.nombre} {e.apellidos}", edad=edad(e, hoy), sexo=e.sexo,
                        enfermedades=e.enfermedades, programa=e.programa_origen, nivel=r.nivel, resumen=r.resumen,
                        dias_vencida=r.dias_vencida, proxima_cita=cita_out(recorrido.proxima_cita(e, hoy)))


def _unidad(conn, clues: str | None) -> dict:
    if not clues:
        raise HTTPException(403, "Tu cuenta no tiene unidad de salud asignada")
    u = repo.unidad(conn, clues)
    if not u:
        raise HTTPException(404, "Unidad no encontrada")
    return u


def resumen(conn: psycopg.Connection, ident: Identidad, hoy: date) -> ResumenSeguimiento:
    u = _unidad(conn, ident.clues)
    pares = sorted(evaluar_todos(conn, hoy, ident.clues), key=orden_prioridad)
    conteo = {n: 0 for n in ("rojo", "amarillo", "gris", "verde")}
    for _, r in pares:
        conteo[r.nivel] += 1
    agenda = []
    for e, r in pares:
        for c in e.citas:
            if c.fecha == hoy and c.estado == "programada":
                agenda.append(AgendaItem(hora=c.hora, folio=e.folio, nombre=f"{e.nombre} {e.apellidos}", tipo=c.tipo,
                                         nivel=r.nivel, resumen=r.resumen))
    agenda.sort(key=lambda a: (a.hora is None, a.hora))
    prioridades = [fila(e, r, hoy) for e, r in pares if r.nivel in ("rojo", "amarillo")][:8]
    repo.registrar(conn, ident.usuario, ident.rol, "ver_lista_semaforo", None,
                   {"clues": ident.clues, "conteo": conteo, "sugeridos": [p.folio for p in prioridades]})
    conn.commit()
    return ResumenSeguimiento(fecha=hoy, unidad=UnidadOut(**u), total=len(pares), conteo=conteo, prioridades=prioridades,
                              agenda=agenda)


def pacientes(conn: psycopg.Connection, ident: Identidad, hoy: date, nivel: str | None, q: str | None) -> list[PacienteFila]:
    _unidad(conn, ident.clues)
    pares = sorted(evaluar_todos(conn, hoy, ident.clues), key=orden_prioridad)
    out = []
    for e, r in pares:
        if nivel and r.nivel != nivel:
            continue
        if q and q.lower() not in f"{e.folio} {e.nombre} {e.apellidos}".lower():
            continue
        out.append(fila(e, r, hoy))
    return out


def _expediente_autorizado(conn, ident: Identidad, folio: str) -> Expediente:
    exps = repo.expedientes(conn, folio=folio)
    if not exps:
        raise HTTPException(404, "Folio no encontrado")
    e = exps[0]
    if ident.rol == "personal_salud" and e.unidad_clues != ident.clues:
        raise HTTPException(403, "Este folio no está a cargo de tu unidad")
    return e


def _adherencia(e: Expediente, hoy: date) -> Adherencia:
    regs = [SurtidoOut(fecha=s.fecha, medicamento=s.medicamento, dias=s.dias, completo=s.completo) for s in e.surtidos]
    if not regs:
        return Adherencia(registros=[], porcentaje_completo=None, dias_desde_ultimo=None, cubierto_hoy=False)
    ult = max(e.surtidos, key=lambda s: s.fecha)
    return Adherencia(registros=regs[-12:], porcentaje_completo=round(sum(s.completo for s in e.surtidos) / len(e.surtidos) * 100, 1),
                      dias_desde_ultimo=(hoy - ult.fecha).days, cubierto_hoy=(hoy - ult.fecha).days <= ult.dias)


def detalle(conn: psycopg.Connection, ident: Identidad, folio: str, hoy: date) -> PacienteDetalle:
    e = _expediente_autorizado(conn, ident, folio)
    params = repo.parametros(conn).get(e.programa_origen, Parametros())
    r = evaluar(e, hoy, params)
    progs = repo.programas(conn)
    u = repo.unidad(conn, e.unidad_clues) or {"clues": e.unidad_clues, "nombre": e.unidad_clues}
    meds = []
    for m in e.mediciones:
        ok, _ = estado_medicion(m, e.enfermedades)
        meds.append(MedicionOut(id=m.id, fecha=m.fecha, pas=m.pas, pad=m.pad, glucosa=m.glucosa, hba1c=m.hba1c,
                                programa_id=m.programa_id, programa=progs.get(m.programa_id, {}).get("nombre"),
                                otro_programa=m.programa_id not in (None, PROGRAMA_DE_UNIDAD), en_control=ok))
    repo.registrar(conn, ident.usuario, ident.rol, "consultar_recorrido", folio, {})
    repo.registrar(conn, "plataforma", "sistema", "sugerencia_semaforo", folio,
                   {"nivel": r.nivel, "resumen": r.resumen, "dimensiones": r.dimensiones})
    conn.commit()
    eventos = repo.bitacora(conn, folio, 200)
    persona = PersonaDetalle(
        folio=e.folio, nombre=f"{e.nombre} {e.apellidos}", curp_simulada=e.curp_simulada, edad=edad(e, hoy), sexo=e.sexo,
        enfermedades=e.enfermedades, seguridad_social=e.seguridad_social, programa_origen=e.programa_origen,
        programa_nombre=progs.get(e.programa_origen, {}).get("nombre", e.programa_origen), unidad=UnidadOut(**u),
        cvegeo=e.cvegeo, rezago=e.rezago, red_apoyo=e.red_apoyo, dependencia_social=e.dependencia_social,
        telefono_simulado=e.telefono_simulado, fecha_deteccion=e.fecha_deteccion, fecha_confirmacion=e.fecha_confirmacion)
    return PacienteDetalle(
        persona=persona, semaforo=semaforo_out(r), etapas=[EtapaOut(**asdict(x)) for x in recorrido.etapas(e)],
        mediciones=meds, tratamientos=[asdict(t) for t in e.tratamientos], adherencia=_adherencia(e, hoy),
        citas=[cita_out(c) for c in e.citas][-12:],
        desacuerdos=[DesacuerdoOut(**d) for d in repo.desacuerdos(conn, folio)],
        bitacora=[EventoBitacora(**b) for b in eventos if b["accion"] not in VISTAS][:12],
        consultas_registradas=sum(1 for b in eventos if b["accion"] in VISTAS))


def registrar_medicion(conn: psycopg.Connection, ident: Identidad, folio: str, m: MedicionIn, hoy: date) -> MedicionCreada:
    e = _expediente_autorizado(conn, ident, folio)
    params = repo.parametros(conn).get(e.programa_origen, Parametros())
    antes = evaluar(e, hoy, params)
    fecha = m.fecha or hoy
    if fecha > hoy:
        raise HTTPException(422, "La fecha de la medición no puede ser futura")
    mid = repo.insertar_medicion(conn, folio, fecha, m.pas, m.pad, m.glucosa, m.hba1c, PROGRAMA_DE_UNIDAD, ident.usuario)
    if m.es_consulta:
        repo.insertar_consulta(conn, folio, fecha, ident.clues)
    e2 = repo.expedientes(conn, folio=folio)[0]
    despues = evaluar(e2, hoy, params)
    repo.registrar(conn, ident.usuario, ident.rol, "registrar_medicion", folio,
                   {"medicion_id": mid, "valores": m.model_dump(exclude_none=True), "nivel_anterior": antes.nivel,
                    "nivel_nuevo": despues.nivel})
    conn.commit()
    return MedicionCreada(medicion_id=mid, semaforo_anterior=antes.nivel, semaforo=semaforo_out(despues))


def registrar_desacuerdo(conn: psycopg.Connection, ident: Identidad, folio: str, nivel_propuesto: str, motivo: str,
                         hoy: date) -> DesacuerdoOut:
    e = _expediente_autorizado(conn, ident, folio)
    r = evaluar(e, hoy, repo.parametros(conn).get(e.programa_origen, Parametros()))
    did = repo.insertar_desacuerdo(conn, folio, ident.usuario, r.nivel, nivel_propuesto, motivo)
    repo.registrar(conn, ident.usuario, ident.rol, "desacuerdo_semaforo", folio,
                   {"nivel_sugerido": r.nivel, "nivel_propuesto": nivel_propuesto, "motivo": motivo})
    conn.commit()
    return next(DesacuerdoOut(**d) for d in repo.desacuerdos(conn, folio) if d["id"] == did)


def ruta(conn: psycopg.Connection, ident: Identidad, hoy: date, maximo: int = 8) -> Ruta:
    u = _unidad(conn, ident.clues)
    pares = evaluar_todos(conn, hoy, ident.clues)
    cands = []
    for e, r in pares:
        programada = any(c.tipo == "visita" and c.estado == "programada" and 0 <= (c.fecha - hoy).days <= 6 for c in e.citas)
        if programada or r.nivel == "rojo":
            cands.append((not programada, -SEVERIDAD[r.nivel], -r.dias_vencida, e.folio, e, r, programada))
    cands.sort(key=lambda x: x[:4])
    paradas = [{"folio": e.folio, "nombre": f"{e.nombre} {e.apellidos}", "nivel": r.nivel, "resumen": r.resumen,
                "lat": e.domicilio_lat, "lon": e.domicilio_lon, "visita_programada": prog}
               for *_, e, r, prog in cands[:maximo]]
    orden = rutas.ordenar_ruta((u["lat"], u["lon"]), paradas)
    tot = rutas.totales(orden)
    repo.registrar(conn, ident.usuario, ident.rol, "generar_ruta_visitas", None, {"folios": [p["folio"] for p in orden]})
    conn.commit()
    return Ruta(fecha=hoy, origen=UnidadOut(**u), paradas=[ParadaRuta(**p) for p in orden], **tot,
                nota="Distancia en línea recta y tiempo aproximado (18 km/h más 20 minutos por visita). "
                     "Domicilios y ubicación de la unidad simulados.")
