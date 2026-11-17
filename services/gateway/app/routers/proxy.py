"""Rutas públicas del API. Cada una declara qué roles la usan y a qué servicio interno va."""
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from app.repositories import servicios as srv
from app.services.auth import Sesion, con_rol

router = APIRouter(prefix="/api/v1")
PERSONA = con_rol("persona")
PERSONAL = con_rol("personal_salud")
INSTITUCION = con_rol("personal_salud", "autoridad")


async def _json(req: Request):
    return await req.json()


# ---------------- públicas (datos abiertos: mapa de atención de la persona)
@router.get("/unidades", tags=["territorio"])
async def unidades(tipo: Literal["todas", "folios", "urgencias"] = "todas", lat: float | None = None, lon: float | None = None):
    return await srv.reenviar("territorio", "GET", "/v1/unidades", params={k: v for k, v in
                              {"tipo": tipo, "lat": lat, "lon": lon}.items() if v is not None})


@router.get("/ferias", tags=["territorio"])
async def ferias(lat: float | None = None, lon: float | None = None):
    return await srv.reenviar("territorio", "GET", "/v1/ferias", params={k: v for k, v in {"lat": lat, "lon": lon}.items() if v is not None})


# ---------------- persona
@router.post("/persona/consentimiento", tags=["persona"])
async def consentimiento(req: Request, s: Sesion = Depends(PERSONA)):
    return await srv.reenviar("seguimiento", "POST", f"/v1/persona/{s.folio}/consentimiento", s.cabeceras_internas(),
                              json=await _json(req))


@router.get("/persona/me", tags=["persona"])
async def persona_inicio(s: Sesion = Depends(PERSONA)):
    return await srv.reenviar("seguimiento", "GET", f"/v1/persona/{s.folio}/inicio", s.cabeceras_internas())


@router.get("/persona/me/recorrido", tags=["persona"])
async def persona_recorrido(s: Sesion = Depends(PERSONA)):
    return await srv.reenviar("seguimiento", "GET", f"/v1/persona/{s.folio}/recorrido", s.cabeceras_internas())


# ---------------- personal de salud
@router.get("/seguimiento/resumen", tags=["personal de salud"])
async def resumen(s: Sesion = Depends(PERSONAL)):
    return await srv.reenviar("seguimiento", "GET", "/v1/seguimiento/resumen", s.cabeceras_internas())


@router.get("/seguimiento/pacientes", tags=["personal de salud"])
async def pacientes(nivel: str | None = None, q: str | None = Query(None, max_length=60), s: Sesion = Depends(PERSONAL)):
    return await srv.reenviar("seguimiento", "GET", "/v1/seguimiento/pacientes", s.cabeceras_internas(),
                              params={k: v for k, v in {"nivel": nivel, "q": q}.items() if v})


@router.get("/pacientes/{folio}", tags=["personal de salud"])
async def paciente(folio: str, s: Sesion = Depends(PERSONAL)):
    return await srv.reenviar("seguimiento", "GET", f"/v1/pacientes/{folio}", s.cabeceras_internas())


@router.post("/pacientes/{folio}/mediciones", tags=["personal de salud"])
async def medicion(folio: str, req: Request, s: Sesion = Depends(PERSONAL)):
    return await srv.reenviar("seguimiento", "POST", f"/v1/pacientes/{folio}/mediciones", s.cabeceras_internas(),
                              json=await _json(req))


@router.post("/pacientes/{folio}/desacuerdo", tags=["personal de salud"])
async def desacuerdo(folio: str, req: Request, s: Sesion = Depends(PERSONAL)):
    return await srv.reenviar("seguimiento", "POST", f"/v1/pacientes/{folio}/desacuerdo", s.cabeceras_internas(),
                              json=await _json(req))


@router.get("/visitas/ruta", tags=["personal de salud"])
async def ruta(s: Sesion = Depends(PERSONAL)):
    return await srv.reenviar("seguimiento", "GET", "/v1/visitas/ruta", s.cabeceras_internas())


# ---------------- autoridad (y personal): agregados y contexto
@router.get("/indicadores", tags=["autoridad"])
async def indicadores(s: Sesion = Depends(INSTITUCION)):
    return await srv.reenviar("seguimiento", "GET", "/v1/indicadores", s.cabeceras_internas())


@router.get("/indicadores/evolucion", tags=["autoridad"])
async def evolucion(meses: int = 12, s: Sesion = Depends(INSTITUCION)):
    return await srv.reenviar("seguimiento", "GET", "/v1/indicadores/evolucion", s.cabeceras_internas(), params={"meses": meses})


@router.get("/indicadores/ageb", tags=["autoridad"])
async def indicadores_ageb(s: Sesion = Depends(INSTITUCION)):
    return await srv.reenviar("seguimiento", "GET", "/v1/indicadores/ageb", s.cabeceras_internas())


@router.get("/indicadores/export", tags=["autoridad"])
async def exportar(por: Literal["programa", "ageb"] = "programa", s: Sesion = Depends(INSTITUCION)):
    return await srv.reenviar("seguimiento", "GET", "/v1/indicadores/export", s.cabeceras_internas(), params={"por": por})


@router.get("/geo/ageb", tags=["autoridad"])
async def geo_ageb(s: Sesion = Depends(INSTITUCION)):
    return await srv.reenviar("territorio", "GET", "/v1/ageb")


@router.get("/geo/resumen", tags=["autoridad"])
async def geo_resumen(s: Sesion = Depends(INSTITUCION)):
    return await srv.reenviar("territorio", "GET", "/v1/ageb/resumen")


@router.get("/contexto/mortalidad", tags=["autoridad"])
async def mortalidad(s: Sesion = Depends(INSTITUCION)):
    return await srv.reenviar("territorio", "GET", "/v1/contexto/mortalidad")


# ---------------- autoridad: numeralia de medicamentos (informativa)
AUTORIDAD = con_rol("autoridad")


@router.get("/medicamentos", tags=["autoridad"])
async def medicamentos(s: Sesion = Depends(AUTORIDAD)):
    return await srv.reenviar("seguimiento", "GET", "/v1/medicamentos", s.cabeceras_internas())


@router.get("/medicamentos/export", tags=["autoridad"])
async def medicamentos_export(s: Sesion = Depends(AUTORIDAD)):
    return await srv.reenviar("seguimiento", "GET", "/v1/medicamentos/export", s.cabeceras_internas())


@router.get("/contexto/surtido", tags=["autoridad"])
async def referencia_surtido(s: Sesion = Depends(AUTORIDAD)):
    return await srv.reenviar("territorio", "GET", "/v1/contexto/surtido")
