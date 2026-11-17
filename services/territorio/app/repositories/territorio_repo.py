"""Acceso a datos del esquema `territorio`. Consultas parametrizadas, sin lógica de negocio."""
import psycopg


def agebs_geojson(conn: psycopg.Connection) -> list[dict]:
    return conn.execute(
        """SELECT cvegeo, cve_ageb, nom_loc, pobtot, p_18ymas, p_60ymas, psinder, psinder_18_est, pct_sinder,
                  pcon_disc, rezago, centro_lat, centro_lon, ST_AsGeoJSON(geom, 5)::json AS geometry
             FROM territorio.ageb ORDER BY cvegeo"""
    ).fetchall()


def unidades(conn: psycopg.Connection, solo_folios: bool, solo_urgencias: bool) -> list[dict]:
    return conn.execute(
        """SELECT clues, nombre, institucion, tipo, publica, urgencias, asigna_folios, lat, lon, horario, servicios,
                  ubicacion_simulada, datos_simulados
             FROM territorio.unidad
            WHERE estatus = 'EN OPERACION'
              AND (NOT %(f)s OR asigna_folios)
              AND (NOT %(u)s OR urgencias)
            ORDER BY nombre""",
        {"f": solo_folios, "u": solo_urgencias},
    ).fetchall()


def ferias(conn: psycopg.Connection, desde) -> list[dict]:
    return conn.execute(
        "SELECT id, nombre, programa, fecha, horario, lugar, lat, lon, servicios, simulated FROM territorio.feria "
        "WHERE fecha >= %s ORDER BY fecha",
        (desde,),
    ).fetchall()


def mortalidad(conn: psycopg.Connection) -> list[dict]:
    return conn.execute(
        "SELECT anio, causa, sexo, defunciones, poblacion_ref, tasa_100k::float AS tasa_100k "
        "FROM territorio.mortalidad ORDER BY causa, sexo, anio"
    ).fetchall()


def referencia_surtido(conn: psycopg.Connection) -> list[dict]:
    return conn.execute(
        """SELECT periodo, ambito, nombre, clues, unidades, recetas, completas_pct::float AS completas_pct,
                  parciales_pct::float AS parciales_pct, negadas_pct::float AS negadas_pct
             FROM territorio.referencia_surtido
            WHERE periodo = (SELECT max(periodo) FROM territorio.referencia_surtido)
            ORDER BY CASE ambito WHEN 'unidad' THEN 0 WHEN 'estatal' THEN 1 ELSE 2 END, nombre"""
    ).fetchall()


def resumen(conn: psycopg.Connection) -> dict:
    tot = conn.execute(
        """SELECT count(*) AS agebs, coalesce(sum(pobtot),0) AS poblacion, coalesce(sum(p_18ymas),0) AS p18,
                  coalesce(sum(psinder),0) AS sinder, coalesce(sum(psinder_18_est),0) AS sinder18,
                  coalesce(sum(pcon_disc),0) AS disc FROM territorio.ageb"""
    ).fetchone()
    rez = conn.execute("SELECT rezago, count(*) AS n FROM territorio.ageb GROUP BY rezago").fetchall()
    uni = conn.execute(
        "SELECT count(*) FILTER (WHERE publica) AS publicas, count(*) AS total FROM territorio.unidad "
        "WHERE estatus = 'EN OPERACION'"
    ).fetchone()
    return {**tot, "rezago": {r["rezago"]: r["n"] for r in rez}, **uni}
