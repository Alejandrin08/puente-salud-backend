"""Integración: cada endpoint del happy path contra PostgreSQL, validando el contrato Pydantic."""
import csv
import io

import psycopg
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (AccesoOut, Medicamentos, DesacuerdoOut, Evolucion, Indicadores, IndicadoresAgeb, MedicionCreada,
                         PacienteDetalle, PacienteFila, PersonaInicio, PersonaRecorrido, ResumenSeguimiento, Ruta)
from tests.conftest import CLUES_DEMO, TEST_DB

CODIGO = "246810"


def test_health():
    assert TestClient(app).get("/health").json()["servicio"] == "seguimiento"


def test_sin_token_interno_rechaza(app_client):
    assert TestClient(app).get("/v1/seguimiento/resumen", headers={"X-Rol": "personal_salud"}).status_code == 401


# ---------------- personal de salud
def test_resumen_conteo_prioridades_agenda(personal):
    r = ResumenSeguimiento.model_validate(personal.get("/v1/seguimiento/resumen").json())
    assert r.unidad.clues == CLUES_DEMO and r.total == sum(r.conteo.values()) > 20
    assert r.prioridades and all(p.nivel in ("rojo", "amarillo") for p in r.prioridades)
    assert r.prioridades[0].nivel == "rojo" and r.prioridades[0].resumen.startswith("Rojo:")
    assert r.agenda, "La agenda del día no debe estar vacía"


def test_lista_ordenada_y_filtrable(personal):
    filas = [PacienteFila.model_validate(x) for x in personal.get("/v1/seguimiento/pacientes").json()]
    orden = {"rojo": 0, "amarillo": 1, "gris": 2, "verde": 3}
    assert [orden[f.nivel] for f in filas] == sorted(orden[f.nivel] for f in filas)
    verdes = personal.get("/v1/seguimiento/pacientes", params={"nivel": "verde"}).json()
    assert verdes and all(v["nivel"] == "verde" for v in verdes)


def test_detalle_explicado_y_bitacora(personal):
    folio = personal.get("/v1/seguimiento/pacientes", params={"nivel": "rojo"}).json()[0]["folio"]
    d = PacienteDetalle.model_validate(personal.get(f"/v1/pacientes/{folio}").json())
    assert d.semaforo.nivel == "rojo" and d.semaforo.motivos and d.semaforo.motivos[0].fuente
    assert "no diagnostica" in d.semaforo.aviso
    # se auditan todas las vistas y sugerencias; la pantalla las resume en un conteo
    assert d.consultas_registradas >= 2
    assert not {b.accion for b in d.bitacora} & {"consultar_recorrido", "sugerencia_semaforo"}


def test_folio_de_otra_unidad_prohibido(personal):
    with psycopg.connect(TEST_DB) as c:
        otro = c.execute("SELECT folio FROM seguimiento.persona WHERE unidad_clues <> %s LIMIT 1", (CLUES_DEMO,)).fetchone()[0]
    assert personal.get(f"/v1/pacientes/{otro}").status_code == 403


def test_registrar_medicion_recalcula_semaforo(personal):
    fila = next(f for f in personal.get("/v1/seguimiento/pacientes").json() if "hipertension" in f["enfermedades"])
    r = personal.post(f"/v1/pacientes/{fila['folio']}/mediciones", json={"pas": 186, "pad": 112})
    assert r.status_code == 201
    m = MedicionCreada.model_validate(r.json())
    assert m.semaforo.nivel == "rojo" and "180/110" in m.semaforo.resumen
    d = personal.get(f"/v1/pacientes/{fila['folio']}").json()
    assert d["mediciones"][-1]["pas"] == 186
    assert any(b["accion"] == "registrar_medicion" for b in d["bitacora"])


def test_medicion_invalida(personal):
    folio = personal.get("/v1/seguimiento/pacientes").json()[0]["folio"]
    assert personal.post(f"/v1/pacientes/{folio}/mediciones", json={"pas": 140}).status_code == 422
    assert personal.post(f"/v1/pacientes/{folio}/mediciones", json={}).status_code == 422
    assert personal.post(f"/v1/pacientes/{folio}/mediciones", json={"glucosa": 5000}).status_code == 422


def test_desacuerdo_queda_en_bitacora(personal):
    folio = personal.get("/v1/seguimiento/pacientes", params={"nivel": "rojo"}).json()[0]["folio"]
    r = personal.post(f"/v1/pacientes/{folio}/desacuerdo",
                      json={"nivel_propuesto": "amarillo", "motivo": "Ya acudió a su unidad; falta capturar la consulta"})
    assert r.status_code == 201
    des = DesacuerdoOut.model_validate(r.json())
    assert des.nivel_sugerido == "rojo" and des.nivel_propuesto == "amarillo"
    d = personal.get(f"/v1/pacientes/{folio}").json()
    assert d["desacuerdos"][0]["motivo"].startswith("Ya acudió")
    assert any(b["accion"] == "desacuerdo_semaforo" for b in d["bitacora"])


def test_ruta_de_visitas(personal):
    r = Ruta.model_validate(personal.get("/v1/visitas/ruta").json())
    assert 1 <= len(r.paradas) <= 8 and [p.orden for p in r.paradas] == list(range(1, len(r.paradas) + 1))
    assert r.minutos_total >= r.minutos_traslado and "línea recta" in r.nota


def test_personal_no_entra_a_vista_persona(personal):
    folio = personal.get("/v1/seguimiento/pacientes").json()[0]["folio"]
    assert personal.get(f"/v1/persona/{folio}/inicio").status_code == 403


# ---------------- persona
def _folio_sin_consentimiento():
    with psycopg.connect(TEST_DB) as c:
        return c.execute("""SELECT p.folio FROM seguimiento.persona p LEFT JOIN seguimiento.consentimiento c USING (folio)
                            WHERE c.folio IS NULL ORDER BY p.folio LIMIT 1""").fetchone()[0]


def test_persona_acceso_consentimiento_inicio_recorrido(app_client, persona_de):
    folio = _folio_sin_consentimiento()
    c = persona_de(folio)
    assert c.post("/v1/interno/persona/verificar", json={"folio": folio, "codigo": "000000"}).status_code == 401
    acc = AccesoOut.model_validate(c.post("/v1/interno/persona/verificar", json={"folio": folio.lower(), "codigo": CODIGO}).json())
    assert acc.folio == folio and acc.consentimiento is None and acc.curp_simulada.endswith(acc.curp_simulada[-2:])
    assert c.get(f"/v1/persona/{folio}/inicio").status_code == 409  # sin consentimiento no hay datos
    assert c.post(f"/v1/persona/{folio}/consentimiento", json={"aceptado": True}).status_code == 200
    ini = PersonaInicio.model_validate(c.get(f"/v1/persona/{folio}/inicio").json())
    assert 1 <= ini.paso_actual <= 4 and len(ini.etapas) == 4 and ini.etapas[0].completada
    assert ini.siguiente_paso.texto and ini.zona["lat"]
    rec = PersonaRecorrido.model_validate(c.get(f"/v1/persona/{folio}/recorrido").json())
    assert rec.eventos[0].tipo == "deteccion"


def test_persona_no_ve_otro_folio(app_client, persona_de):
    with psycopg.connect(TEST_DB) as c:
        a, b = [r[0] for r in c.execute("SELECT folio FROM seguimiento.persona ORDER BY folio LIMIT 2")]
    assert persona_de(a).get(f"/v1/persona/{b}/inicio").status_code == 403


# ---------------- autoridad (agregados)
def test_indicadores_cuatro_por_programa(autoridad):
    i = Indicadores.model_validate(autoridad.get("/v1/indicadores").json())
    assert i.total.detectadas == 1000 and len(i.por_programa) == 5
    assert 25 <= i.total.control_pct <= 65
    assert all(p.confirmacion_pct is not None and p.retencion_6_pct is not None for p in i.por_programa)
    assert set(i.definiciones) == {"confirmacion", "dias_primera_consulta", "retencion", "control"}


def test_evolucion(autoridad):
    e = Evolucion.model_validate(autoridad.get("/v1/indicadores/evolucion").json())
    assert len(e.total) == 12 and len(e.por_programa) == 5


def test_indicadores_ageb_y_prioridad(autoridad):
    a = IndicadoresAgeb.model_validate(autoridad.get("/v1/indicadores/ageb").json())
    assert len(a.agebs) == 234 and len(a.zonas_prioritarias) == 10
    pr = [z.prioridad for z in a.zonas_prioritarias]
    assert pr == sorted(pr, reverse=True)
    assert all(x.control_pct is None for x in a.agebs if not x.suficiente)


def test_autoridad_no_ve_personas(autoridad):
    assert autoridad.get("/v1/seguimiento/pacientes").status_code == 403
    assert autoridad.get("/v1/pacientes/PS104729").status_code == 403
    texto = str(autoridad.get("/v1/indicadores/ageb").json()) + str(autoridad.get("/v1/indicadores").json())
    assert "PS1" not in texto and "curp" not in texto.lower()


def test_exportar_csv(autoridad):
    for por, filas_min in (("programa", 6), ("ageb", 234)):
        r = autoridad.get("/v1/indicadores/export", params={"por": por})
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
        assert "attachment" in r.headers["content-disposition"]
        filas = list(csv.reader(io.StringIO(r.text)))
        assert "simulados" in filas[0][0] and len(filas) >= filas_min + 2


def test_medicamentos_solo_autoridad(autoridad):
    m = Medicamentos.model_validate(autoridad.get("/v1/medicamentos").json())
    assert m.resumen["personas_tratamiento"] > 0 and m.resumen["personas_sin_cobertura"] > 0
    assert {x.medicamento for x in m.medicamentos} >= {"Metformina 850 mg", "Losartán 50 mg"}
    pr = [u.prioridad for u in m.unidades]
    assert pr == sorted(pr, reverse=True) and len(m.evolucion) == 12
    r = autoridad.get("/v1/medicamentos/export")
    assert r.status_code == 200 and "simulados" in r.text and "attachment" in r.headers["content-disposition"]


def test_medicamentos_prohibido_para_personal(personal):
    assert personal.get("/v1/medicamentos").status_code == 403


def test_medicion_con_programa(personal):
    folio = next(f for f in personal.get("/v1/seguimiento/pacientes").json() if "hipertension" in f["enfermedades"])["folio"]
    assert personal.post(f"/v1/pacientes/{folio}/mediciones", json={"pas": 120, "pad": 78, "programa_id": "ferias"}).status_code == 201
    d = personal.get(f"/v1/pacientes/{folio}").json()
    assert d["mediciones"][-1]["programa_id"] == "ferias" and d["mediciones"][-1]["otro_programa"]
    assert personal.post(f"/v1/pacientes/{folio}/mediciones", json={"pas": 120, "pad": 78, "programa_id": "inventado"}).status_code == 422
