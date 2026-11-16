"""Etapas del recorrido, indicadores E.4 y ruta de visitas."""
from datetime import date, time, timedelta

from app.services import indicadores as ind
from app.services.dominio import Cita, Consulta, Expediente, Medicion, Tratamiento
from app.services.recorrido import etapas, fecha_larga, paso_actual, siguiente_paso
from app.services.rutas import ordenar_ruta, totales

HOY = date(2026, 11, 16)


def d(n: int) -> date:
    return HOY - timedelta(days=n)


def base(**kw) -> Expediente:
    datos = dict(folio="PS1", fecha_deteccion=d(100), enfermedades=["diabetes"], programa_origen="ferias",
                 cvegeo="A", fecha_confirmacion=None)
    datos.update(kw)
    return Expediente(**datos)


# ---------------- etapas
def test_paso_2_sin_confirmar_con_cita():
    e = base(citas=[Cita(HOY + timedelta(days=3), "confirmacion", "programada", time(9, 30))])
    ets = etapas(e)
    assert paso_actual(ets) == 2 and [x.completada for x in ets] == [True, False, False, False]
    sp = siguiente_paso(e, HOY, "Centro de Salud Toluquilla")
    assert "jueves 19 de noviembre a las 09:30" in sp.texto and "Toluquilla" in sp.texto


def test_paso_3_y_4():
    e = base(fecha_confirmacion=d(70), consultas=[Consulta(d(70), "confirmacion")])
    assert paso_actual(etapas(e)) == 3
    e.tratamientos = [Tratamiento(d(70), "Metformina 850 mg")]
    e.mediciones = [Medicion(d(10), glucosa=180)]
    assert paso_actual(etapas(e)) == 4 and not etapas(e)[3].completada
    e.mediciones.append(Medicion(d(2), glucosa=110))
    ets = etapas(e)
    assert all(x.completada for x in ets) and paso_actual(ets) == 4
    assert siguiente_paso(e, HOY, "X").titulo == "Mantén tu control"


def test_fecha_larga():
    assert fecha_larga(date(2026, 11, 16)) == "lunes 16 de noviembre"


# ---------------- indicadores
def resumen(det, conf=None, primera=None, inicio=None, controles=(), hist=(), programa="p", cvegeo="A"):
    hist = list(hist)
    return ind.Resumen(programa, cvegeo, d(det), d(conf) if conf is not None else None,
                       d(primera) if primera is not None else None, d(inicio) if inicio is not None else None,
                       [d(c) for c in controles], bool(conf is not None and hist and hist[-1][1]),
                       [(d(f), ok) for f, ok in hist])


def test_confirmacion_en_plazo_excluye_recientes():
    rs = [resumen(100, conf=80), resumen(100, conf=50), resumen(100), resumen(10)]
    assert ind.confirmacion(rs, HOY) == (33.3, 1, 3)


def test_mediana_dias_primera_consulta():
    rs = [resumen(100, primera=90), resumen(100, primera=80), resumen(100, primera=40), resumen(100)]
    med, n, _, _ = ind.dias_primera_consulta(rs)
    assert med == 20.0 and n == 3


def test_retencion_6_meses():
    rs = [resumen(300, inicio=250, controles=[100]),   # 150 días después del inicio >= 150 -> retenida
          resumen(300, inicio=250, controles=[200]),   # solo a los 50 días -> no
          resumen(300, inicio=100)]                     # menos de 6 meses: no elegible
    assert ind.retencion(rs, HOY, 6) == (50.0, 1, 2)


def test_control_entre_confirmados():
    rs = [resumen(100, conf=80, hist=[(10, True)]), resumen(100, conf=80, hist=[(10, False)]), resumen(100)]
    assert ind.en_control(rs) == (50.0, 1, 2)


def test_evolucion_mensual():
    rs = [resumen(400, conf=380, hist=[(370, False), (40, True)])]
    ev = ind.evolucion_control(rs, HOY, meses=3)
    assert [p["mes"] for p in ev] == ["2026-09", "2026-10", "2026-11"]
    assert ev[0]["control_pct"] == 0.0 and ev[-1]["control_pct"] == 100.0


def test_prioridad_zona():
    alto, f = ind.prioridad_zona(20.0, "Alto", 45.0)
    bajo, _ = ind.prioridad_zona(80.0, "Muy bajo", 10.0)
    assert alto > bajo and "rezago social alto" in f and "solo 20% en control" in f
    assert "nadie en control" in ind.prioridad_zona(0.0, "Bajo", 10.0)[1]


# ---------------- ruta
def test_ruta_rojos_primero_y_vecino_mas_cercano():
    origen = (20.60, -103.30)
    paradas = [{"folio": "a", "nivel": "amarillo", "lat": 20.601, "lon": -103.301},
               {"folio": "r1", "nivel": "rojo", "lat": 20.63, "lon": -103.33},
               {"folio": "r2", "nivel": "rojo", "lat": 20.61, "lon": -103.31}]
    ruta = ordenar_ruta(origen, paradas)
    assert [p["folio"] for p in ruta] == ["r2", "r1", "a"]
    assert [p["orden"] for p in ruta] == [1, 2, 3]
    t = totales(ruta)
    assert t["minutos_total"] == t["minutos_traslado"] + 60 and t["distancia_km"] > 0


def test_nombre_propio():
    from app.services.persona_service import nombre_propio
    assert nombre_propio("CENTRO DE SALUD SAN JOSÉ TATEPOSCO") == "Centro de Salud San José Tateposco"
    assert nombre_propio("UMF 54 TLAQUEPAQUE") == "UMF 54 Tlaquepaque"
