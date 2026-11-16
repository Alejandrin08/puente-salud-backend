#!/usr/bin/env python3
"""Aplica migraciones y carga los datos (reales y simulados) en PostgreSQL + PostGIS.

Uso local o contra una base remota:
    DATABASE_ADMIN_URL=postgresql://... APP_DB_USER=puente_app python scripts/seed.py
Opciones:
    --solo-migrar      aplica migraciones y no carga datos
    --si-vacio         carga solo si la base no tiene personas (para arranques repetidos de Docker)
    --fecha AAAA-MM-DD fecha de referencia del recorrido simulado (por defecto, hoy o FECHA_REFERENCIA)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb  # noqa: F401  (disponible para detalles futuros)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "db" / "seeds" / "simulated"))
import generar  # noqa: E402

MIGRACIONES = ROOT / "db" / "migrations"
REAL = ROOT / "db" / "seeds" / "real"

TABLAS_SEG = ["bitacora", "desacuerdo", "consentimiento", "surtido", "tratamiento", "cita", "consulta", "medicion",
              "condicion", "persona", "unidad_ref", "ageb_ref", "parametros_programa", "programa"]
TABLAS_TER = ["feria", "unidad", "mortalidad", "ageb"]


def migrar(conn: psycopg.Connection, app_user: str | None) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS public.schema_migraciones (nombre text PRIMARY KEY, aplicada timestamptz DEFAULT now())")
    hechas = {r[0] for r in conn.execute("SELECT nombre FROM public.schema_migraciones")}
    for f in sorted(MIGRACIONES.glob("*.sql")):
        texto = f.read_text(encoding="utf-8")
        if ':"app_user"' in texto:
            if not app_user:
                print(f"[omitida] {f.name}: APP_DB_USER no definido (se usará el mismo usuario)")
                continue
            texto = texto.replace(':"app_user"', sql.Identifier(app_user).as_string(conn))
            conn.execute(texto)  # permisos: se reaplican siempre (tablas nuevas)
            print(f"[permisos] {f.name}")
            continue
        if f.name in hechas:
            continue
        conn.execute(texto)
        conn.execute("INSERT INTO public.schema_migraciones (nombre) VALUES (%s)", (f.name,))
        print(f"[migración] {f.name}")
    conn.commit()


def leer_agebs() -> list[dict]:
    p = REAL / "ageb.geojson"
    if not p.exists():
        sys.exit("Falta db/seeds/real/ageb.geojson. Ejecuta scripts/build_territorio.py (ver README).")
    gj = json.loads(p.read_text(encoding="utf-8"))
    return [{**f["properties"], "geom": f["geometry"]} for f in gj["features"]]


def leer_unidades() -> list[dict]:
    with open(REAL / "unidades_clues.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["publica"] = r["publica"] == "True"
        r["urgencias"] = r["urgencias"] == "True"
    return rows


def cargar(conn: psycopg.Connection, hoy: date) -> None:
    agebs = leer_agebs()
    datos = generar.generar(agebs, leer_unidades(), hoy)
    cur = conn.cursor()
    cur.execute("TRUNCATE " + ", ".join(f"seguimiento.{t}" for t in TABLAS_SEG) + " RESTART IDENTITY CASCADE")
    cur.execute("TRUNCATE " + ", ".join(f"territorio.{t}" for t in TABLAS_TER) + " RESTART IDENTITY CASCADE")

    # ---- reales
    for a in agebs:
        lat, lon = generar.centroide(a["geom"])
        cur.execute(
            """INSERT INTO territorio.ageb (cvegeo, cve_loc, cve_ageb, nom_loc, pobtot, p_18ymas, p_60ymas, psinder,
                 pder_ss, pcon_disc, psinder_18_est, pct_sinder, rezago, geom, centro_lat, centro_lon)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s),4326)), %s, %s)""",
            (a["cvegeo"], a["cve_loc"], a["cve_ageb"], a.get("nom_loc"), a.get("pobtot"), a.get("p_18ymas"),
             a.get("p_60ymas"), a.get("psinder"), a.get("pder_ss"), a.get("pcon_disc"), a.get("psinder_18_est"),
             a.get("pct_sinder"), a.get("rezago") or "Sin dato", json.dumps(a["geom"]), lat, lon))
        cur.execute("INSERT INTO seguimiento.ageb_ref (cvegeo, rezago, pct_sinder, lat, lon) VALUES (%s,%s,%s,%s,%s)",
                    (a["cvegeo"], a.get("rezago") or "Sin dato", a.get("pct_sinder"), lat, lon))
    with open(REAL / "mortalidad.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            cur.execute("INSERT INTO territorio.mortalidad VALUES (%s,%s,%s,%s,%s,%s)",
                        (int(r["anio"]), r["causa"], r["sexo"], int(r["defunciones"]), int(r["poblacion_ref"]),
                         float(r["tasa_100k"]) if r["tasa_100k"] else None))

    # ---- unidades (catálogo real + ubicación, horario y servicios simulados)
    for u in datos["unidades"]:
        cur.execute(
            """INSERT INTO territorio.unidad (clues, nombre, institucion, tipo, tipologia, localidad, estatus, publica,
                 urgencias, asigna_folios, cvegeo, lat, lon, ubicacion_simulada, horario, servicios, datos_simulados)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s,%s,true)""",
            (u["clues"], u["nombre"], u["institucion"], u["tipo"], u["tipologia"], u["localidad"], u["estatus"],
             u["publica"], u["urgencias"], u["asigna_folios"], u["cvegeo"], u["lat"], u["lon"], u["horario"], u["servicios"]))
        cur.execute("INSERT INTO seguimiento.unidad_ref VALUES (%s,%s,%s,%s,%s)",
                    (u["clues"], u["nombre"], u["institucion"], u["lat"], u["lon"]))
    for f in datos["ferias"]:
        cur.execute("""INSERT INTO territorio.feria (nombre, programa, fecha, horario, lugar, cvegeo, lat, lon, servicios)
                       VALUES (%(nombre)s,%(programa)s,%(fecha)s,%(horario)s,%(lugar)s,%(cvegeo)s,%(lat)s,%(lon)s,%(servicios)s)""", f)

    # ---- seguimiento simulado
    for p in datos["programas"]:
        cur.execute("INSERT INTO seguimiento.programa (id, nombre, ambito) VALUES (%(id)s,%(nombre)s,%(ambito)s)", p)
        cur.execute("INSERT INTO seguimiento.parametros_programa (programa_id) VALUES (%s)", (p["id"],))
    with cur.copy("""COPY seguimiento.persona (folio, curp_simulada, nombre, apellidos, sexo, fecha_nacimiento, cvegeo,
                     domicilio_lat, domicilio_lon, seguridad_social, programa_origen, unidad_clues, fecha_deteccion,
                     dependencia_social, red_apoyo, telefono_simulado, codigo_hash) FROM STDIN""") as cp:
        for p in datos["personas"]:
            cp.write_row((p.folio, p.curp_simulada, p.nombre, p.apellidos, p.sexo, p.fecha_nacimiento, p.cvegeo,
                          p.domicilio_lat, p.domicilio_lon, p.seguridad_social, p.programa_origen, p.unidad_clues,
                          p.fecha_deteccion, p.dependencia_social, p.red_apoyo, p.telefono_simulado,
                          generar.hash_codigo(p.folio, p.codigo)))
    copias = {
        "condicion": ["folio", "enfermedad", "fecha_confirmacion"],
        "medicion": ["folio", "fecha", "pas", "pad", "glucosa", "hba1c", "programa_id"],
        "consulta": ["folio", "fecha", "tipo", "clues"],
        "cita": ["folio", "fecha", "hora", "tipo", "estado", "clues"],
        "tratamiento": ["folio", "fecha_inicio", "medicamento", "indicacion"],
        "surtido": ["folio", "fecha", "medicamento", "dias", "completo"],
        "consentimiento": ["folio", "aceptado", "fecha"],
    }
    origen = {"condicion": "condiciones", "medicion": "mediciones", "consulta": "consultas", "cita": "citas",
              "tratamiento": "tratamientos", "surtido": "surtidos", "consentimiento": "consentimientos"}
    for tabla, cols in copias.items():
        with cur.copy(f"COPY seguimiento.{tabla} ({', '.join(cols)}) FROM STDIN") as cp:
            for r in datos[origen[tabla]]:
                cp.write_row(tuple(r[c] for c in cols))
    conn.commit()
    n = {t: len(datos[o]) for t, o in origen.items()}
    print(f"[datos] {len(agebs)} AGEB, {len(datos['unidades'])} unidades, {len(datos['ferias'])} ferias, "
          f"{len(datos['personas'])} personas simuladas, " + ", ".join(f"{v} {k}" for k, v in n.items())
          + f" · fecha de referencia {hoy.isoformat()}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-migrar", action="store_true")
    ap.add_argument("--si-vacio", action="store_true")
    ap.add_argument("--fecha")
    args = ap.parse_args()
    url = os.environ.get("DATABASE_ADMIN_URL") or os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Define DATABASE_ADMIN_URL (usuario dueño de la base) o DATABASE_URL.")
    fecha = args.fecha or os.environ.get("FECHA_REFERENCIA")
    hoy = date.fromisoformat(fecha) if fecha else date.today()
    with psycopg.connect(url) as conn:
        migrar(conn, os.environ.get("APP_DB_USER"))
        if args.solo_migrar:
            return 0
        if args.si_vacio:
            n = conn.execute("SELECT count(*) FROM seguimiento.persona").fetchone()[0]
            if n:
                print(f"[datos] la base ya tiene {n} personas; no se recarga (usa sin --si-vacio para reiniciar)")
                return 0
        cargar(conn, hoy)
        migrar(conn, os.environ.get("APP_DB_USER"))  # permisos sobre tablas recién llenadas
    return 0


if __name__ == "__main__":
    sys.exit(main())
