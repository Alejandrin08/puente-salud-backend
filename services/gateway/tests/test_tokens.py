import pytest

from app.services import tokens


def test_emitir_y_verificar():
    t, exp = tokens.emitir({"u": "ana", "r": "autoridad"}, "s3creto", 1, ahora=1000)
    d = tokens.verificar(t, "s3creto", ahora=1001)
    assert d["u"] == "ana" and d["r"] == "autoridad" and d["exp"] == exp == 4600


def test_firma_alterada():
    t, _ = tokens.emitir({"r": "persona"}, "s3creto", 1)
    cuerpo, firma = t.split(".")
    falso, _ = tokens.emitir({"r": "autoridad"}, "otro", 1)
    with pytest.raises(tokens.TokenInvalido):
        tokens.verificar(falso.split(".")[0] + "." + firma, "s3creto")
    with pytest.raises(tokens.TokenInvalido):
        tokens.verificar(t, "otro-secreto")


def test_expirado_y_malformado():
    t, _ = tokens.emitir({"u": "x"}, "s", 1, ahora=0)
    with pytest.raises(tokens.TokenInvalido, match="expiró"):
        tokens.verificar(t, "s", ahora=10_000)
    with pytest.raises(tokens.TokenInvalido):
        tokens.verificar("sin-punto", "s")
