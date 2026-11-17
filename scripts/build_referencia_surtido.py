#!/usr/bin/env python3
"""Deriva la referencia real de surtido de recetas (ISSSTE) para la vista Medicamentos.

Uso: python scripts/build_referencia_surtido.py [--raw RUTA_A_data/raw]
Lee data/raw/recetas_issste/*.csv (descarga manual, ver data/datasets.json) y escribe
db/seeds/real/referencia_surtido.csv con: nacional, Jalisco y las unidades ISSSTE de Tlaquepaque.
Solo biblioteca estándar.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "db" / "seeds" / "real" / "referencia_surtido.csv"
# Unidades ISSSTE ubicadas en Tlaquepaque (CLUES 2024) y su nombre en el archivo del ISSSTE
TLAQUEPAQUE = {"san martín de las flores": "JCIST000750"}
MESES = {m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                       "septiembre", "octubre", "noviembre", "diciembre"], 1)}


def agregado(filas: list[dict]) -> dict:
    s = sum(int(r["numero_recetas_surtidas"]) for r in filas)
    p = sum(int(r["numero_recetas_parciales"]) for r in filas)
    n = sum(int(r["numero_recetas_negadas"]) for r in filas)
    t = sum(int(r["total_recetas"]) for r in filas)
    return {"unidades": len(filas), "recetas": t, "completas_pct": round(s / t * 100, 1),
            "parciales_pct": round(p / t * 100, 1), "negadas_pct": round(n / t * 100, 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT / "data" / "raw"))
    carpeta = Path(ap.parse_args().raw) / "recetas_issste"
    archivos = sorted(carpeta.glob("*.csv"))
    if not archivos:
        sys.exit(f"Falta el CSV en {carpeta}. Descárgalo a mano (ver data/datasets.json, recetas_issste).")
    salida = []
    for a in archivos:
        filas = list(csv.DictReader(open(a, encoding="utf-8-sig")))
        if not filas:
            continue
        periodo = f"{filas[0]['anio']}-{MESES[filas[0]['mes'].strip().lower()]:02d}"
        jal = [r for r in filas if r["delegacion"].strip().lower() == "jalisco"]
        salida.append({"periodo": periodo, "ambito": "nacional", "nombre": "ISSSTE nacional", "clues": "", **agregado(filas)})
        salida.append({"periodo": periodo, "ambito": "estatal", "nombre": "ISSSTE Jalisco", "clues": "", **agregado(jal)})
        for r in jal:
            clues = TLAQUEPAQUE.get(r["unidade_medica"].strip().lower())
            if clues:
                salida.append({"periodo": periodo, "ambito": "unidad", "nombre": f"UMF {r['unidade_medica'].strip()} (ISSSTE, Tlaquepaque)",
                               "clues": clues, **agregado([r])})
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["periodo", "ambito", "nombre", "clues", "unidades", "recetas", "completas_pct",
                                           "parciales_pct", "negadas_pct"])
        w.writeheader()
        w.writerows(salida)
    for s in salida:
        print(f"{s['periodo']} · {s['nombre']}: {s['recetas']:,} recetas, {s['completas_pct']}% completas, "
              f"{s['parciales_pct']}% parciales, {s['negadas_pct']}% negadas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
