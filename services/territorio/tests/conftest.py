import os
import subprocess
import sys
from pathlib import Path

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql://prueba:prueba@127.0.0.1:55432/puente_prueba")
os.environ["DATABASE_URL"] = TEST_DB
os.environ["INTERNAL_TOKEN"] = "token-prueba"
BACKEND = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def client():
    """Base de pruebas con migraciones y datos (fecha de referencia fija). Requiere docker-compose.test.yml."""
    r = subprocess.run([sys.executable, str(BACKEND / "scripts" / "seed.py"), "--si-vacio", "--fecha", "2026-11-16"],
                       env={**os.environ, "DATABASE_ADMIN_URL": TEST_DB}, capture_output=True, text=True)
    assert r.returncode == 0, f"No se pudo preparar la base de pruebas: {r.stderr or r.stdout}"
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app, headers={"X-Internal-Token": "token-prueba"}) as c:
        yield c
