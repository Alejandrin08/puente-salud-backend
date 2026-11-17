"""Acceso a datos del esquema `seguimiento`. Consultas parametrizadas; sin reglas de negocio."""
from __future__ import annotations

import json
from datetime import date

import psycopg

from app.services.dominio import Cita, Consulta, Expediente, Medicion, Parametros, Surtido, Tratamiento


def _filtro(clues: str | None, folio: str | None) -> tuple[str, dict]:
    conds, params = [], {}
    if clues:
        conds.append("p.unidad_clues = %(clues)s")
        params["clues"] = clues
    if folio:
        conds.append("p.folio = %(folio)s")
        params["folio"] = folio
    return (" WHERE " + " AND ".join(conds)) if conds else "", params


def expedientes(conn: psycopg.Connection, clues: str | None = None, folio: str | None = None) -> list[Expediente]:
    where, params = _filtro(clues, folio)
    personas = conn.execute(
        f"""SELECT p.*, a.rezago FROM seguimiento.persona p JOIN seguimiento.ageb_ref a USING (cvegeo){where}
            ORDER BY p.folio""", params).fetchall()
    if not personas:
        return []
    exps = {}
    for p in personas:
        exps[p["folio"]] = Expediente(
            folio=p["folio"], fecha_deteccion=p["fecha_deteccion"], enfermedades=[], programa_origen=p["programa_origen"],
            cvegeo=p["cvegeo"], rezago=p["rezago"], seguridad_social=p["seguridad_social"], unidad_clues=p["unidad_clues"],
            nombre=p["nombre"], apellidos=p["apellidos"], sexo=p["sexo"], fecha_nacimiento=p["fecha_nacimiento"],
            domicilio_lat=p["domicilio_lat"], domicilio_lon=p["domicilio_lon"], curp_simulada=p["curp_simulada"],
            red_apoyo=p["red_apoyo"], dependencia_social=p["dependencia_social"], telefono_simulado=p["telefono_simulado"])
    sub = f"SELECT p.folio FROM seguimiento.persona p{where}"
    for r in conn.execute(f"SELECT folio, enfermedad, fecha_confirmacion FROM seguimiento.condicion WHERE folio IN ({sub})", params):
        e = exps[r["folio"]]
        e.enfermedades.append(r["enfermedad"])
        if r["fecha_confirmacion"] and (e.fecha_confirmacion is None or r["fecha_confirmacion"] < e.fecha_confirmacion):
            e.fecha_confirmacion = r["fecha_confirmacion"]
    for r in conn.execute(f"SELECT id, folio, fecha, pas, pad, glucosa, hba1c::float AS hba1c, programa_id FROM seguimiento.medicion WHERE folio IN ({sub})", params):
        exps[r.pop("folio")].mediciones.append(Medicion(**r))
    for r in conn.execute(f"SELECT folio, fecha, tipo, clues FROM seguimiento.consulta WHERE folio IN ({sub})", params):
        exps[r.pop("folio")].consultas.append(Consulta(**r))
    for r in conn.execute(f"SELECT folio, fecha, hora, tipo, estado, clues FROM seguimiento.cita WHERE folio IN ({sub})", params):
        exps[r.pop("folio")].citas.append(Cita(**r))
    for r in conn.execute(f"SELECT folio, fecha_inicio, medicamento, indicacion FROM seguimiento.tratamiento WHERE folio IN ({sub})", params):
        exps[r.pop("folio")].tratamientos.append(Tratamiento(**r))
    for r in conn.execute(f"SELECT folio, fecha, medicamento, dias, completo FROM seguimiento.surtido WHERE folio IN ({sub})", params):
        exps[r.pop("folio")].surtidos.append(Surtido(**r))
    for e in exps.values():
        e.enfermedades.sort()
        e.ordenar()
    return list(exps.values())


def parametros(conn: psycopg.Connection) -> dict[str, Parametros]:
    return {r.pop("programa_id"): Parametros(**r) for r in conn.execute("SELECT * FROM seguimiento.parametros_programa")}


def programas(conn: psycopg.Connection) -> dict[str, dict]:
    return {r["id"]: r for r in conn.execute("SELECT id, nombre, ambito FROM seguimiento.programa ORDER BY id")}


def unidad(conn: psycopg.Connection, clues: str) -> dict | None:
    return conn.execute("SELECT clues, nombre, institucion, lat, lon FROM seguimiento.unidad_ref WHERE clues = %s",
                        (clues,)).fetchone()


def unidades(conn: psycopg.Connection) -> dict[str, dict]:
    return {r["clues"]: r for r in conn.execute("SELECT clues, nombre, institucion FROM seguimiento.unidad_ref")}


def ageb(conn: psycopg.Connection, cvegeo: str) -> dict | None:
    return conn.execute("SELECT cvegeo, rezago, lat, lon FROM seguimiento.ageb_ref WHERE cvegeo = %s", (cvegeo,)).fetchone()


def agebs_contexto(conn: psycopg.Connection) -> dict[str, dict]:
    """Rezago y % sin afiliación por AGEB (copia en seguimiento.ageb_ref; no se cruza al esquema territorio)."""
    return {r["cvegeo"]: r for r in conn.execute(
        "SELECT cvegeo, rezago, pct_sinder::float AS pct_sinder FROM seguimiento.ageb_ref")}


def acceso_persona(conn: psycopg.Connection, folio: str) -> dict | None:
    return conn.execute(
        """SELECT p.folio, p.nombre, p.curp_simulada, p.codigo_hash, c.aceptado AS consentimiento
             FROM seguimiento.persona p LEFT JOIN seguimiento.consentimiento c USING (folio) WHERE p.folio = %s""",
        (folio,)).fetchone()


def guardar_consentimiento(conn: psycopg.Connection, folio: str, aceptado: bool) -> None:
    conn.execute(
        """INSERT INTO seguimiento.consentimiento (folio, aceptado, fecha) VALUES (%s, %s, now())
           ON CONFLICT (folio) DO UPDATE SET aceptado = EXCLUDED.aceptado, fecha = now()""", (folio, aceptado))


def insertar_medicion(conn: psycopg.Connection, folio: str, fecha: date, pas, pad, glucosa, hba1c, programa_id: str,
                      usuario: str) -> int:
    return conn.execute(
        """INSERT INTO seguimiento.medicion (folio, fecha, pas, pad, glucosa, hba1c, programa_id, registrado_por, simulated)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,false) RETURNING id""",
        (folio, fecha, pas, pad, glucosa, hba1c, programa_id, usuario)).fetchone()["id"]


def insertar_consulta(conn: psycopg.Connection, folio: str, fecha: date, clues: str | None) -> None:
    conn.execute("INSERT INTO seguimiento.consulta (folio, fecha, tipo, clues) VALUES (%s,%s,'control',%s)", (folio, fecha, clues))
    conn.execute("""UPDATE seguimiento.cita SET estado = 'atendida'
                     WHERE folio = %s AND fecha = %s AND estado = 'programada' AND tipo IN ('control','visita')""",
                 (folio, fecha))


def insertar_desacuerdo(conn: psycopg.Connection, folio: str, usuario: str, sugerido: str, propuesto: str, motivo: str) -> int:
    return conn.execute(
        """INSERT INTO seguimiento.desacuerdo (folio, usuario, nivel_sugerido, nivel_propuesto, motivo)
           VALUES (%s,%s,%s,%s,%s) RETURNING id""", (folio, usuario, sugerido, propuesto, motivo)).fetchone()["id"]


def desacuerdos(conn: psycopg.Connection, folio: str) -> list[dict]:
    return conn.execute("SELECT id, fecha, usuario, nivel_sugerido, nivel_propuesto, motivo FROM seguimiento.desacuerdo "
                        "WHERE folio = %s ORDER BY fecha DESC", (folio,)).fetchall()


def registrar(conn: psycopg.Connection, usuario: str, rol: str, accion: str, folio: str | None = None,
              detalle: dict | None = None) -> None:
    conn.execute("INSERT INTO seguimiento.bitacora (usuario, rol, accion, folio, detalle) VALUES (%s,%s,%s,%s,%s)",
                 (usuario, rol, accion, folio, json.dumps(detalle or {}, ensure_ascii=False, default=str)))


def bitacora(conn: psycopg.Connection, folio: str | None = None, limite: int = 50) -> list[dict]:
    return conn.execute(
        "SELECT id, fecha, usuario, rol, accion, folio, detalle FROM seguimiento.bitacora "
        "WHERE (%(f)s::text IS NULL OR folio = %(f)s) ORDER BY fecha DESC, id DESC LIMIT %(l)s",
        {"f": folio, "l": limite}).fetchall()
