from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from app.config import Identidad, get_conn, hoy, identidad, internal_only, requiere
from app.schemas import Evolucion, Indicadores, IndicadoresAgeb, Medicamentos
from app.services import autoridad_service as svc

# Solo datos agregados. El personal de salud también puede consultarlos.
router = APIRouter(prefix="/v1/indicadores", tags=["autoridad"],
                   dependencies=[Depends(internal_only), Depends(requiere("autoridad", "personal_salud"))])


@router.get("", response_model=Indicadores)
def indicadores(conn: psycopg.Connection = Depends(get_conn)):
    return svc.indicadores(conn, hoy())


@router.get("/evolucion", response_model=Evolucion)
def evolucion(meses: int = Query(12, ge=3, le=24), conn: psycopg.Connection = Depends(get_conn)):
    return svc.evolucion(conn, hoy(), meses)


@router.get("/ageb", response_model=IndicadoresAgeb)
def ageb(conn: psycopg.Connection = Depends(get_conn)):
    return svc.por_ageb(conn, hoy())


@router.get("/export", response_class=PlainTextResponse)
def exportar(por: Literal["programa", "ageb"] = "programa", ident: Identidad = Depends(identidad),
             conn: psycopg.Connection = Depends(get_conn)):
    fecha = hoy()
    return PlainTextResponse(svc.exportar_csv(conn, ident, fecha, por), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="puente-salud-indicadores-{por}-{fecha}.csv"'})


medicamentos = APIRouter(prefix="/v1/medicamentos", tags=["autoridad"],
                         dependencies=[Depends(internal_only), Depends(requiere("autoridad"))])


@medicamentos.get("", response_model=Medicamentos)
def numeralia_medicamentos(conn: psycopg.Connection = Depends(get_conn)):
    return svc.medicamentos(conn, hoy())


@medicamentos.get("/export", response_class=PlainTextResponse)
def exportar_medicamentos(ident: Identidad = Depends(identidad), conn: psycopg.Connection = Depends(get_conn)):
    fecha = hoy()
    return PlainTextResponse(svc.exportar_medicamentos_csv(conn, ident, fecha), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="puente-salud-medicamentos-{fecha}.csv"'})
