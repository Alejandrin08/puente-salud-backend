"""Numeralia de medicamentos: cobertura, demanda por nivel del semáforo y prioridad por unidad."""
from datetime import date, timedelta

from app.services import medicamentos as med
from app.services.dominio import Expediente, Surtido, Tratamiento
from app.services.semaforo import Resultado

HOY = date(2026, 11, 16)


def d(n):
    return HOY - timedelta(days=n)


def exp(folio, clues, surtidos, meds=("Losartán 50 mg",)):
    return Expediente(folio=folio, fecha_deteccion=d(300), enfermedades=["hipertension"], programa_origen="p", cvegeo="A",
                      unidad_clues=clues, tratamientos=[Tratamiento(d(250), m) for m in meds], surtidos=surtidos)


def res(nivel):
    return Resultado(nivel=nivel, resumen="", motivos=[], dimensiones={})


def test_faltantes_incompleto_vencido_o_sin_surtido():
    assert med.faltantes(exp("a", "U1", [Surtido(d(10), "Losartán 50 mg", 30, True)]), HOY) == []
    assert med.faltantes(exp("b", "U1", [Surtido(d(10), "Losartán 50 mg", 30, False)]), HOY) == ["Losartán 50 mg"]
    assert med.faltantes(exp("c", "U1", [Surtido(d(40), "Losartán 50 mg", 30, True)]), HOY) == ["Losartán 50 mg"]
    assert med.faltantes(exp("d", "U1", []), HOY) == ["Losartán 50 mg"]


def test_calcular_resumen_medicamento_y_prioridad_por_unidad():
    pares = [
        (exp("a", "U1", [Surtido(d(10), "Losartán 50 mg", 30, False)]), res("rojo")),
        (exp("b", "U1", [Surtido(d(10), "Losartán 50 mg", 30, True)]), res("verde")),
        (exp("c", "U2", [Surtido(d(10), "Losartán 50 mg", 30, False)]), res("verde")),
    ]
    r = med.calcular(pares, {"U1": {"nombre": "Uno", "institucion": "SSA"}, "U2": {"nombre": "Dos", "institucion": "SSA"}}, HOY, meses=2)
    assert r["resumen"]["personas_tratamiento"] == 3 and r["resumen"]["personas_sin_cobertura"] == 2
    assert r["resumen"]["sin_cobertura_por_nivel"]["rojo"] == 1
    los = r["medicamentos"][0]
    assert los["surtido_completo_pct"] == 33.3 and los["necesidad_mensual_tabletas"] == 90 and los["faltante_mensual_tabletas"] == 60
    assert [u["clues"] for u in r["unidades"]] == ["U1", "U2"]  # la persona en rojo pesa más
    assert r["unidades"][0]["prioridad"] == 3 and r["unidades"][0]["medicamentos_faltantes"][0]["medicamento"] == "Losartán 50 mg"
    assert len(r["evolucion"]) == 2


def test_metformina_dos_tabletas_al_dia():
    pares = [(exp("a", "U1", [], meds=("Metformina 850 mg",)), res("amarillo"))]
    m = med.calcular(pares, {}, HOY)["medicamentos"][0]
    assert m["necesidad_mensual_tabletas"] == 60
