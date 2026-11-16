"""El gateway se prueba contra los servicios reales (uvicorn en subprocesos) y la base de pruebas."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql://prueba:prueba@127.0.0.1:55432/puente_prueba")
BACKEND = Path(__file__).resolve().parents[3]
PUERTOS = {"seguimiento": 18001, "territorio": 18002}
os.environ.update({
    "TOKEN_SECRET": "secreto-de-prueba",
    "INTERNAL_TOKEN": "token-prueba",
    "SEGUIMIENTO_URL": f"http://127.0.0.1:{PUERTOS['seguimiento']}",
    "TERRITORIO_URL": f"http://127.0.0.1:{PUERTOS['territorio']}",
    "CORS_ORIGINS": "http://localhost:5173",
    "DEMO_USERS": json.dumps([
        {"usuario": "enfermeria.tateposco", "password": "demo-salud", "rol": "personal_salud", "nombre": "Enf. Laura", "clues": "JCSSA005951"},
        {"usuario": "autoridad.rxii", "password": "demo-autoridad", "rol": "autoridad", "nombre": "Región XII", "clues": None},
    ]),
})


@pytest.fixture(scope="session")
def servicios_reales():
    r = subprocess.run([sys.executable, str(BACKEND / "scripts" / "seed.py"), "--fecha", "2026-11-16"],
                       env={**os.environ, "DATABASE_ADMIN_URL": TEST_DB}, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr or r.stdout
    env = {**os.environ, "DATABASE_URL": TEST_DB, "FECHA_REFERENCIA": "2026-11-16"}
    procs = []
    for nombre, puerto in PUERTOS.items():
        procs.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(puerto), "--log-level", "warning"],
                                      cwd=BACKEND / "services" / nombre, env=env))
    try:
        for puerto in PUERTOS.values():
            for _ in range(100):
                try:
                    if httpx.get(f"http://127.0.0.1:{puerto}/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.1)
            else:
                pytest.fail(f"El servicio en el puerto {puerto} no arrancó")
        yield
    finally:
        for p in procs:
            p.terminate()
            p.wait(10)


@pytest.fixture(scope="session")
def gw(servicios_reales):
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c


def _login(gw, usuario, password):
    r = gw.post("/api/v1/auth/login", json={"usuario": usuario, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session")
def h_personal(gw):
    return _login(gw, "enfermeria.tateposco", "demo-salud")


@pytest.fixture(scope="session")
def h_autoridad(gw):
    return _login(gw, "autoridad.rxii", "demo-autoridad")
