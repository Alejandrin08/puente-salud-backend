#!/usr/bin/env python3
"""Construye los seeds reales de territorio a partir de data/raw/.

Uso:
    python -m venv .venv-datos && .venv-datos/bin/pip install -r scripts/requirements-datos.txt
    .venv-datos/bin/python scripts/build_territorio.py [--raw RUTA_A_data/raw]

Salidas (pequeñas, versionables) en db/seeds/real/:
    ageb.geojson         234 AGEB urbanas de Tlaquepaque con Censo 2020 y rezago CONEVAL (EPSG:4326, simplificadas)
    unidades_clues.csv   95 establecimientos CLUES 2024 de Tlaquepaque (sin coordenadas: el catálogo no las trae)
    mortalidad.csv       defunciones por diabetes (E10-E14) e hipertensivas (I10-I15), residencia Tlaquepaque, 2023-2025
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "db" / "seeds" / "real"
ENT, MUN = "14", "098"
POB_MUNICIPAL_2020 = 687127  # Censo 2020, total municipal (fila LOC=0000)


def need(path: Path) -> Path:
    if not path.exists():
        sys.exit(f"Falta {path}. Ejecuta: python scripts/fetch_data.py (y descarga los manuales; ver data/datasets.json)")
    return path


def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.replace({"*": None, "N/D": None}), errors="coerce")


def censo(raw: Path) -> pd.DataFrame:
    zf = zipfile.ZipFile(need(raw / "censo2020_ageb_jalisco.zip"))
    name = next(n for n in zf.namelist() if n.lower().endswith(".csv") and "conjunto_de_datos_ageb" in n.lower())
    c = pd.read_csv(zf.open(name), dtype=str, encoding="latin-1", low_memory=False)
    c.columns = [x.replace("﻿", "").replace("ï»¿", "").strip() for x in c.columns]
    a = c[(c.MUN == MUN) & (c.MZA == "000") & (c.AGEB != "0000")].copy()
    a["cvegeo"] = ENT + a.MUN + a.LOC + a.AGEB
    out = pd.DataFrame({"cvegeo": a.cvegeo, "cve_loc": a.LOC, "cve_ageb": a.AGEB, "nom_loc": a.NOM_LOC})
    for src, dst in [("POBTOT", "pobtot"), ("P_18YMAS", "p_18ymas"), ("P_60YMAS", "p_60ymas"),
                     ("PSINDER", "psinder"), ("PDER_SS", "pder_ss"), ("PCON_DISC", "pcon_disc")]:
        out[dst] = num(a[src])
    # No existe «18+ sin afiliación» en el Censo: se estima proporcionalmente y se rotula como estimación.
    out["psinder_18_est"] = (out.psinder * out.p_18ymas / out.pobtot).round()
    out["pct_sinder"] = (out.psinder / out.pobtot * 100).round(1)
    return out


def rezago(raw: Path) -> pd.DataFrame:
    zf = zipfile.ZipFile(need(raw / "rezago_social_ageb_2020.zip"))
    name = next(n for n in zf.namelist() if n.endswith(".xlsx"))
    r = pd.read_excel(io.BytesIO(zf.read(name)), sheet_name="GRS 2020", header=None, dtype=str)
    keycol = next(c for c in r.columns if r[c].astype(str).str.fullmatch(r"\d{12}[0-9A-Z]").sum() > 1000)
    rt = r[r[keycol].str.startswith(ENT + MUN, na=False)]
    return pd.DataFrame({"cvegeo": rt[keycol].values, "rezago": rt.iloc[:, -1].str.strip().values})


def poligonos(raw: Path) -> gpd.GeoDataFrame:
    zp = need(raw / "mgn_ageb_jalisco.zip")
    shp = next(n for n in zipfile.ZipFile(zp).namelist() if n.endswith("14a.shp"))
    g = gpd.read_file(f"zip://{zp}!{shp}")
    g = g[g.CVE_MUN == MUN].copy()
    g["cvegeo"] = g.CVE_ENT + g.CVE_MUN + g.CVE_LOC + g.CVE_AGEB
    g = g[["cvegeo", "geometry"]].to_crs(32613)
    g["geometry"] = g.geometry.simplify(4, preserve_topology=True)  # 4 m en UTM 13N
    return g.to_crs(4326)


def clues(raw: Path) -> pd.DataFrame:
    cl = pd.read_csv(need(raw / "clues.csv"), dtype=str, encoding="latin-1")
    t = cl[(cl["CLAVE DE LA ENTIDAD"].str.zfill(2) == ENT) & (cl["CLAVE DEL MUNICIPIO"].str.zfill(3) == MUN)].copy()
    inst = t["NOMBRE DE LA INSTITUCION"].str.strip()
    tipo = t["NOMBRE TIPO ESTABLECIMIENTO"].str.strip()
    tipologia = t["NOMBRE DE TIPOLOGIA"].str.strip()
    return pd.DataFrame({
        "clues": t["CLUES"].str.strip(),
        "nombre": t["NOMBRE DE LA UNIDAD"].str.strip(),
        "institucion": inst,
        "tipo": tipo,
        "tipologia": tipologia,
        "localidad": t["NOMBRE DE LA LOCALIDAD"].str.strip(),
        "cve_loc": t["CLAVE DE LA LOCALIDAD"].str.zfill(4),
        "estatus": t["ESTATUS DE OPERACION"].str.strip(),
        "publica": ~inst.str.contains("PRIVADOS", na=False),
        "urgencias": tipo.str.contains("HOSPITALIZ", na=False) | inst.str.contains("CRUZ ROJA", na=False),
    }).sort_values("clues")


def mortalidad(raw: Path) -> pd.DataFrame:
    rows = []
    for z in sorted(need(raw / "defunciones_inegi").glob("*.zip")):
        zf = zipfile.ZipFile(z)
        name = max((n for n in zf.namelist() if n.lower().endswith(".csv") and "catalogo" not in n.lower()
                    and "diccionario" not in n.lower()), key=lambda n: zf.getinfo(n).file_size)
        df = pd.read_csv(zf.open(name), dtype=str, encoding="latin-1", low_memory=False,
                         usecols=lambda c: c.lower() in {"ent_resid", "mun_resid", "causa_def", "sexo", "anio_regis"})
        df.columns = [c.lower() for c in df.columns]
        t = df[(df.ent_resid.str.zfill(2) == ENT) & (df.mun_resid.str.zfill(3) == MUN)]
        anio = int(pd.to_numeric(t.anio_regis, errors="coerce").mode().iloc[0])
        cd = t.causa_def.fillna("").str[:3]
        grupos = {
            "diabetes": cd.isin([f"E1{i}" for i in range(5)]),
            "hipertension": cd.isin([f"I1{i}" for i in range(6)]),
            "total": pd.Series(True, index=t.index),
        }
        for causa, mask in grupos.items():
            for sexo, sm in {"total": pd.Series(True, index=t.index), "hombre": t.sexo == "1", "mujer": t.sexo == "2"}.items():
                n = int((mask & sm).sum())
                rows.append({"anio": anio, "causa": causa, "sexo": sexo, "defunciones": n,
                             "poblacion_ref": POB_MUNICIPAL_2020,
                             "tasa_100k": round(n / POB_MUNICIPAL_2020 * 1e5, 1) if sexo == "total" else None})
    return pd.DataFrame(rows).sort_values(["causa", "sexo", "anio"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT / "data" / "raw"))
    raw = Path(ap.parse_args().raw)
    OUT.mkdir(parents=True, exist_ok=True)

    c = censo(raw)
    r = rezago(raw)
    g = poligonos(raw)
    a = g.merge(c, on="cvegeo", how="inner").merge(r, on="cvegeo", how="left")
    a["rezago"] = a.rezago.fillna("Sin dato")
    a["geometry"] = a.geometry.set_precision(1e-5)
    print(f"AGEB con polígono y Censo: {len(a)} (polígonos sin Censo omitidos: {len(g) - len(a)}); con rezago: {(a.rezago != 'Sin dato').sum()}")
    gj = json.loads(a.to_json(drop_id=True))
    for f in gj["features"]:
        f["properties"] = {k: (None if isinstance(v, float) and v != v else v) for k, v in f["properties"].items()}
    gj["metadata"] = {"fuente": "INEGI Censo 2020, Marco Geoestadístico dic. 2025, CONEVAL GRS AGEB 2020",
                      "nota": "psinder_18_est es una estimación proporcional; '*' y 'N/D' del Censo quedan como null"}
    (OUT / "ageb.geojson").write_text(json.dumps(gj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    u = clues(raw)
    u.to_csv(OUT / "unidades_clues.csv", index=False)
    print(f"Unidades CLUES: {len(u)} ({u.publica.sum()} públicas, {(u.estatus == 'EN OPERACION').sum()} en operación)")

    m = mortalidad(raw)
    m.to_csv(OUT / "mortalidad.csv", index=False)
    print(m[m.sexo == "total"].pivot(index="anio", columns="causa", values="defunciones"))
    for p in sorted(OUT.iterdir()):
        print(f"  {p.name}: {p.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
