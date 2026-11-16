import os
import subprocess
import sys
from pathlib import Path

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql://prueba:prueba@127.0.0.1:55432/puente_prueba")
os.environ["DATABASE_URL"] = TEST_DB
os.environ["INTERNAL_TOKEN"] = "token-prueba"
os.environ["FECHA_REFERENCIA"] = "2026-11-16"
BACKEND = Path(__file__).resolve().parents[3]
CLUES_DEMO = "JCSSA005951"


def _preparar_base(recargar: bool = False) -> None:
    args = [sys.executable, str(BACKEND / "scripts" / "seed.py"), "--fecha", "2026-11-16"]
    if not recargar:
        args.append("--si-vacio")
    r = subprocess.run(args, env={**os.environ, "DATABASE_ADMIN_URL": TEST_DB}, capture_output=True, text=True)
    assert r.returncode == 0, f"No se pudo preparar la base de pruebas: {r.stderr or r.stdout}"


@pytest.fixture(scope="session")
def app_client():
    _preparar_base(recargar=True)  # las pruebas escriben (mediciones, bitácora): se parte de datos limpios
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c


def _headers(rol: str, usuario: str = "prueba", clues: str = "", folio: str = "") -> dict:
    return {"X-Internal-Token": "token-prueba", "X-Rol": rol, "X-Usuario": usuario, "X-Clues": clues, "X-Folio": folio}


@pytest.fixture
def personal(app_client):
    app_client.headers.clear()
    app_client.headers.update(_headers("personal_salud", "enfermeria.tateposco", CLUES_DEMO))
    return app_client


@pytest.fixture
def autoridad(app_client):
    app_client.headers.clear()
    app_client.headers.update(_headers("autoridad", "autoridad.rxii"))
    return app_client


@pytest.fixture
def persona_de(app_client):
    def _f(folio: str):
        app_client.headers.clear()
        app_client.headers.update(_headers("persona", folio, folio=folio))
        return app_client
    return _f
