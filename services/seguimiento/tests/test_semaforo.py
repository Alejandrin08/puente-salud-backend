"""Una prueba por regla del Anexo D (cortes de la NOM y supuestos de D.2)."""
from datetime import date, timedelta

import pytest

from app.services.dominio import Cita, Consulta, Expediente, Medicion, Parametros
from app.services.semaforo import estado_medicion, evaluar, metas_pa

HOY = date(2026, 11, 16)


def d(dias: int) -> date:
    return HOY - timedelta(days=dias)


def exp(enf=("hipertension",), mediciones=(), consultas=(), citas=(), confirmado=10, deteccion=40, **kw) -> Expediente:
    return Expediente(folio="PS000001", fecha_deteccion=d(deteccion), enfermedades=list(enf), programa_origen="caravanas",
                      cvegeo="1409800010001", seguridad_social=kw.pop("ss", "IMSS"), rezago=kw.pop("rezago", "Bajo"),
                      fecha_confirmacion=d(confirmado) if confirmado is not None else None,
                      mediciones=list(mediciones), consultas=list(consultas) or ([Consulta(d(confirmado), "confirmacion")] if confirmado is not None else []),
                      citas=list(citas), **kw)


# ---------------- cortes clínicos (D.1)
def test_meta_pa_con_y_sin_diabetes():
    assert metas_pa(["hipertension"]) == (140, 90)
    assert metas_pa(["hipertension", "diabetes"]) == (130, 80)


@pytest.mark.parametrize("pas,pad,enf,esperado", [
    (138, 88, ["hipertension"], True), (140, 85, ["hipertension"], False), (128, 78, ["hipertension", "diabetes"], True),
    (135, 78, ["hipertension", "diabetes"], False)])
def test_control_presion(pas, pad, enf, esperado):
    ok, _ = estado_medicion(Medicion(HOY, pas=pas, pad=pad, glucosa=110 if "diabetes" in enf else None), enf)
    assert ok is esperado


@pytest.mark.parametrize("glucosa,hba1c,esperado", [(70, None, True), (130, None, True), (131, None, False), (69, None, False),
                                                    (200, 6.8, True), (100, 7.0, False)])
def test_control_diabetes_glucosa_o_hba1c(glucosa, hba1c, esperado):
    ok, _ = estado_medicion(Medicion(HOY, glucosa=glucosa, hba1c=hba1c), ["diabetes"])
    assert ok is esperado


# ---------------- D.3 niveles
def test_verde_en_control_y_en_plazo():
    r = evaluar(exp(mediciones=[Medicion(d(10), pas=125, pad=80)]), HOY)
    assert r.nivel == "verde" and r.dimensiones == {"clinica": "verde", "seguimiento": "verde", "riesgo": "verde"}


def test_gris_sin_mediciones_y_nunca_verde():
    r = evaluar(exp(mediciones=[]), HOY)
    assert r.nivel == "gris"
    assert "sin ninguna medición" in r.resumen.lower()


def test_gris_no_oculta_rojo_de_seguimiento():
    r = evaluar(exp(mediciones=[], confirmado=None, deteccion=120), HOY)
    assert r.nivel == "rojo"


def test_amarillo_fuera_de_control_ultima_medicion():
    r = evaluar(exp(mediciones=[Medicion(d(30), pas=125, pad=80), Medicion(d(5), pas=150, pad=92)]), HOY)
    assert r.nivel == "amarillo" and "fuera de control en la última medición" in r.resumen.lower()
    assert any(m.fuente.startswith("NOM-030") for m in r.motivos)


def test_rojo_fuera_de_control_dos_mediciones_seguidas():
    r = evaluar(exp(mediciones=[Medicion(d(30), pas=150, pad=95), Medicion(d(5), pas=152, pad=96)]), HOY)
    assert r.nivel == "rojo" and "dos mediciones seguidas" in r.resumen.lower()


def test_rojo_crisis_hipertensiva():
    r = evaluar(exp(mediciones=[Medicion(d(2), pas=185, pad=100)]), HOY)
    assert r.nivel == "rojo" and "mayor de 180/110" in r.resumen.lower()
    assert any(m.fuente == "NOM-030-SSA2-2009, 6.1" for m in r.motivos)


def test_glucosa_menor_70_requiere_valoracion():
    r = evaluar(exp(enf=["diabetes"], mediciones=[Medicion(d(3), glucosa=62)]), HOY)
    assert r.nivel == "amarillo" and r.requiere_valoracion
    assert "requiere valoración del personal" in r.resumen.lower()


def test_amarillo_hba1c_mas_de_12_meses():
    ms = [Medicion(d(400), glucosa=110, hba1c=6.5), Medicion(d(20), glucosa=110)]
    r = evaluar(exp(enf=["diabetes"], mediciones=ms, confirmado=420, consultas=[Consulta(d(20), "control")]), HOY)
    assert r.nivel == "amarillo" and "hba1c con más de 12 meses" in r.resumen.lower()


def test_amarillo_sin_confirmar_a_los_30_dias():
    r = evaluar(exp(mediciones=[Medicion(d(45), pas=125, pad=80)], confirmado=None, deteccion=45), HOY)
    assert r.nivel == "amarillo" and "sin confirmar a los 45 días" in r.resumen.lower()


def test_rojo_perdida_en_la_confirmacion():
    r = evaluar(exp(mediciones=[Medicion(d(95), pas=125, pad=80)], confirmado=None, deteccion=95), HOY)
    assert r.nivel == "rojo" and "pérdida en la confirmación" in r.resumen.lower()


def test_amarillo_consulta_vencida_hasta_30_dias():
    # fuera de control -> control cada 30 días; última consulta hace 50 días -> vencida 20
    ms = [Medicion(d(50), pas=125, pad=80)]
    r = evaluar(exp(mediciones=ms, confirmado=140, consultas=[Consulta(d(50), "control")]), HOY, Parametros())
    # en control -> cada 90 días: no vencida
    assert r.nivel == "verde"
    ms = [Medicion(d(50), pas=150, pad=95)]
    r = evaluar(exp(mediciones=ms, confirmado=140, consultas=[Consulta(d(50), "control")]), HOY)
    assert r.dimensiones["seguimiento"] == "amarillo" and r.dias_vencida == 20


def test_rojo_consulta_vencida_mas_de_30_dias():
    r = evaluar(exp(mediciones=[Medicion(d(70), pas=125, pad=80)], confirmado=200,
                    consultas=[Consulta(d(130), "control")]), HOY)
    assert r.dimensiones["seguimiento"] == "rojo" and "vencida hace 40 días" in r.resumen.lower()


def test_rojo_abandono_12_meses():
    r = evaluar(exp(mediciones=[Medicion(d(400), pas=125, pad=80)], confirmado=500,
                    consultas=[Consulta(d(400), "control")]), HOY)
    assert r.nivel == "rojo" and r.resumen == "Rojo: abandono: sin consulta de control hace 13 meses"


def test_riesgo_abandono_alto_dos_factores():
    citas = [Cita(d(40), "control", "perdida"), Cita(d(20), "control", "perdida")]
    r = evaluar(exp(mediciones=[Medicion(d(10), pas=125, pad=80)], citas=citas, ss=None), HOY)
    assert r.dimensiones["riesgo"] == "amarillo" and r.nivel == "amarillo"
    assert set(r.factores_riesgo) == {"dos citas perdidas seguidas", "sin afiliación a servicios de salud"}


def test_un_solo_factor_no_es_riesgo_alto():
    r = evaluar(exp(mediciones=[Medicion(d(10), pas=125, pad=80)], rezago="Muy alto"), HOY)
    assert r.dimensiones["riesgo"] == "verde" and r.factores_riesgo == ["vive en una AGEB de rezago social muy alto"]


def test_toma_la_dimension_mas_grave_y_explica_todas():
    ms = [Medicion(d(200), pas=150, pad=95), Medicion(d(140), pas=152, pad=96)]
    r = evaluar(exp(mediciones=ms, confirmado=300, consultas=[Consulta(d(140), "control")], ss=None, rezago="Alto"), HOY)
    assert r.nivel == "rojo"
    assert {m.dimension for m in r.motivos} == {"clinica", "seguimiento", "riesgo"}
    assert r.motivos[0].nivel == "rojo"


def test_parametros_configurables_por_programa():
    p = Parametros(dias_confirmacion=15, dias_perdida_confirmacion=60)
    r = evaluar(exp(mediciones=[Medicion(d(70), pas=125, pad=80)], confirmado=None, deteccion=70), HOY, p)
    assert r.nivel == "rojo"
