import pytest

from app.services.territorio_service import construir_mortalidad, haversine_km, ordenar_por_cercania, tendencia


def test_haversine_distancia_conocida():
    # Centro de Tlaquepaque a Centro de Guadalajara: ~6.5 km
    d = haversine_km(20.6407, -103.3110, 20.6767, -103.3475)
    assert 5.0 < d < 6.0


def test_ordenar_por_cercania_agrega_distancia_y_ordena():
    items = [{"id": "lejos", "lat": 20.70, "lon": -103.30}, {"id": "cerca", "lat": 20.601, "lon": -103.301}]
    out = ordenar_por_cercania(items, 20.60, -103.30)
    assert [i["id"] for i in out] == ["cerca", "lejos"]
    assert out[0]["distancia_km"] < 0.2


def test_ordenar_sin_origen_no_cambia():
    items = [{"lat": 1, "lon": 1}]
    assert ordenar_por_cercania(items, None, None) == items
    assert "distancia_km" not in items[0]


@pytest.mark.parametrize("valores,esperado", [([432, 437, 374], "baja"), ([183, 198, 192], "estable"), ([100, 110], "sube"),
                                              ([100, 102], "estable"), ([5], "estable")])
def test_tendencia(valores, esperado):
    assert tendencia(valores)[1] == esperado


def test_construir_mortalidad():
    filas = []
    for anio, dm, ht, tot in [(2023, 432, 183, 3956), (2024, 437, 198, 4213), (2025, 374, 192, 3963)]:
        for causa, n in [("diabetes", dm), ("hipertension", ht), ("total", tot)]:
            filas.append({"anio": anio, "causa": causa, "sexo": "total", "defunciones": n, "poblacion_ref": 687127,
                          "tasa_100k": round(n / 687127 * 1e5, 1)})
            filas.append({"anio": anio, "causa": causa, "sexo": "mujer", "defunciones": n // 2, "poblacion_ref": 687127,
                          "tasa_100k": None})
    m = construir_mortalidad(filas)
    dm = m.series[0]
    assert dm.causa == "diabetes" and [p.defunciones for p in dm.serie] == [432, 437, 374]
    assert dm.tendencia == "baja" and dm.variacion_pct == pytest.approx(-13.4)
    assert dm.por_sexo == {"mujer": 187}
    assert m.ultimo_anio == 2025 and m.total_defunciones_ultimo_anio == 3963
