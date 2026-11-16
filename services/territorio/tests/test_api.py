"""Integración: API de territorio contra PostgreSQL + PostGIS con los seeds reales."""
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import FeatureCollection, Mortalidad, ResumenMunicipio, Unidad


def test_health():
    assert TestClient(app).get("/health").json()["status"] == "ok"


def test_rechaza_sin_token_interno(client):
    assert TestClient(app).get("/v1/ageb").status_code == 401


def test_ageb_geojson_real(client):
    r = client.get("/v1/ageb")
    assert r.status_code == 200
    fc = FeatureCollection.model_validate(r.json())
    assert len(fc.features) == 234
    f = fc.features[0]
    assert f["geometry"]["type"] == "MultiPolygon"
    assert {"cvegeo", "rezago", "psinder_18_est", "p_18ymas"} <= f["properties"].keys()
    rezagos = {x["properties"]["rezago"] for x in fc.features}
    assert rezagos <= {"Muy bajo", "Bajo", "Medio", "Alto", "Muy alto", "Sin dato"}
    assert sum(x["properties"]["rezago"] == "Sin dato" for x in fc.features) == 2


def test_resumen_municipio(client):
    r = ResumenMunicipio.model_validate(client.get("/v1/ageb/resumen").json())
    assert r.agebs == 234 and r.poblacion == 678905
    assert r.rezago["Alto"] == 21 and r.rezago["Muy alto"] == 1


def test_unidades_ordenadas_por_cercania(client):
    r = client.get("/v1/unidades", params={"tipo": "folios", "lat": 20.62, "lon": -103.31})
    us = [Unidad.model_validate(u) for u in r.json()]
    assert len(us) == 22 and all(u.asigna_folios and u.ubicacion_simulada for u in us)
    d = [u.distancia_km for u in us]
    assert d == sorted(d)


def test_unidades_urgencias(client):
    us = client.get("/v1/unidades", params={"tipo": "urgencias"}).json()
    assert us and all(u["urgencias"] for u in us)
    assert any("CRUZ ROJA" in u["nombre"] for u in us)


def test_ferias_futuras(client):
    fs = client.get("/v1/ferias", params={"desde": "2026-11-16"}).json()
    assert len(fs) == 12 and all(f["simulated"] for f in fs)


def test_mortalidad_real(client):
    m = Mortalidad.model_validate(client.get("/v1/contexto/mortalidad").json())
    dm = next(s for s in m.series if s.causa == "diabetes")
    assert [p.defunciones for p in dm.serie] == [432, 437, 374]
    ht = next(s for s in m.series if s.causa == "hipertension")
    assert [p.defunciones for p in ht.serie] == [183, 198, 192]
