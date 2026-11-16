#!/usr/bin/env python3
"""Descarga los datasets listados en data/datasets.json a data/raw/.

Uso:  python scripts/fetch_data.py [--force] [--only NOMBRE]
No sobrescribe archivos existentes salvo con --force. Verifica sha256 si está indicado.
Los datasets con "manual": true solo imprimen instrucciones.
"""
import argparse, hashlib, json, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "datasets.json"
RAW = ROOT / "data" / "raw"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()
    items = json.loads(MANIFEST.read_text(encoding="utf-8"))["datasets"]
    RAW.mkdir(parents=True, exist_ok=True)
    failed = 0
    for d in items:
        if args.only and d["nombre"] != args.only:
            continue
        dest = RAW / d["archivo"]
        if d.get("manual"):
            print(f"[manual] {d['nombre']}: {d.get('nota') or 'descarga manual'} -> guardar como {dest}")
            continue
        if dest.exists() and not args.force:
            print(f"[ok] {d['nombre']} ya existe ({dest.name})")
            continue
        try:
            print(f"[descargando] {d['nombre']} <- {d['url']}")
            urllib.request.urlretrieve(d["url"], dest)
        except Exception as e:  # red, 404, etc.
            print(f"[error] {d['nombre']}: {e}", file=sys.stderr)
            failed += 1
            continue
        expected = d.get("sha256")
        if expected and sha256(dest) != expected:
            print(f"[error] {d['nombre']}: sha256 distinto al esperado", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
