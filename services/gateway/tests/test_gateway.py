"""Happy path de las tres vistas, de punta a punta por el gateway, y control de roles."""
import psycopg

from tests.conftest import TEST_DB

CODIGO = "246810"


def test_health_y_estado(gw):
    assert gw.get("/health").json()["status"] == "ok"
    assert gw.get("/api/v1/estado").json()["ok"] is True


def test_cors_solo_origen_configurado(gw):
    ok = gw.options("/api/v1/auth/login", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    malo = gw.options("/api/v1/auth/login", headers={"Origin": "https://otro.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in malo.headers


def test_login_incorrecto(gw):
    assert gw.post("/api/v1/auth/login", json={"usuario": "autoridad.rxii", "password": "x"}).status_code == 401


def test_sin_token_y_token_falso(gw):
    assert gw.get("/api/v1/indicadores").status_code == 401
    assert gw.get("/api/v1/indicadores", headers={"Authorization": "Bearer abc.def"}).status_code == 401


def test_publico_mapa_de_atencion(gw):
    us = gw.get("/api/v1/unidades", params={"tipo": "folios", "lat": 20.6, "lon": -103.3}).json()
    assert len(us) == 22 and us[0]["distancia_km"] <= us[-1]["distancia_km"]
    assert gw.get("/api/v1/ferias").status_code == 200


def test_happy_path_persona(gw):
    with psycopg.connect(TEST_DB) as c:
        folio = c.execute("""SELECT p.folio FROM seguimiento.persona p JOIN seguimiento.consentimiento c USING (folio)
                             ORDER BY p.folio LIMIT 1""").fetchone()[0]
    assert gw.post("/api/v1/persona/acceso", json={"folio": folio, "codigo": "111111"}).status_code == 401
    r = gw.post("/api/v1/persona/acceso", json={"folio": folio, "codigo": CODIGO})
    assert r.status_code == 200 and r.json()["rol"] == "persona" and r.json()["consentimiento"] is True
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    ini = gw.get("/api/v1/persona/me", headers=h).json()
    assert ini["folio"] == folio and len(ini["etapas"]) == 4
    assert gw.get("/api/v1/persona/me/recorrido", headers=h).status_code == 200
    # la persona no entra al panel institucional
    assert gw.get("/api/v1/seguimiento/resumen", headers=h).status_code == 403
    assert gw.get("/api/v1/indicadores", headers=h).status_code == 403


def test_happy_path_personal_salud(gw, h_personal):
    res = gw.get("/api/v1/seguimiento/resumen", headers=h_personal).json()
    folio = res["prioridades"][0]["folio"]
    det = gw.get(f"/api/v1/pacientes/{folio}", headers=h_personal).json()
    assert det["semaforo"]["motivos"]
    r = gw.post(f"/api/v1/pacientes/{folio}/mediciones", headers=h_personal, json={"glucosa": 110, "pas": 125, "pad": 78})
    assert r.status_code == 201
    assert gw.post(f"/api/v1/pacientes/{folio}/desacuerdo", headers=h_personal,
                   json={"nivel_propuesto": "verde", "motivo": "Valores en meta hoy"}).status_code == 201
    assert len(gw.get("/api/v1/visitas/ruta", headers=h_personal).json()["paradas"]) >= 1


def test_happy_path_autoridad(gw, h_autoridad):
    assert len(gw.get("/api/v1/indicadores", headers=h_autoridad).json()["por_programa"]) == 5
    assert len(gw.get("/api/v1/indicadores/evolucion", headers=h_autoridad).json()["total"]) == 12
    assert len(gw.get("/api/v1/geo/ageb", headers=h_autoridad).json()["features"]) == 234
    assert len(gw.get("/api/v1/indicadores/ageb", headers=h_autoridad).json()["agebs"]) == 234
    assert gw.get("/api/v1/geo/resumen", headers=h_autoridad).json()["agebs"] == 234
    assert len(gw.get("/api/v1/contexto/mortalidad", headers=h_autoridad).json()["series"]) == 2
    csv = gw.get("/api/v1/indicadores/export", params={"por": "ageb"}, headers=h_autoridad)
    assert csv.status_code == 200 and "attachment" in csv.headers["content-disposition"]


def test_autoridad_no_ve_personas(gw, h_autoridad):
    assert gw.get("/api/v1/seguimiento/pacientes", headers=h_autoridad).status_code == 403
    assert gw.get("/api/v1/pacientes/PS104729", headers=h_autoridad).status_code == 403
    assert gw.get("/api/v1/visitas/ruta", headers=h_autoridad).status_code == 403


def test_medicamentos_por_gateway(gw, h_autoridad, h_personal):
    assert gw.get("/api/v1/medicamentos", headers=h_autoridad).json()["unidades"]
    assert gw.get("/api/v1/medicamentos/export", headers=h_autoridad).status_code == 200
    assert gw.get("/api/v1/medicamentos", headers=h_personal).status_code == 403
    assert len(gw.get("/api/v1/contexto/surtido", headers=h_autoridad).json()["filas"]) == 3
