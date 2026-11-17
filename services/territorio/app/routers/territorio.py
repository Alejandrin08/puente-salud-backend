from datetime import date
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, Query

from app.config import get_conn, internal_only
from app.schemas import Feria, FeatureCollection, Mortalidad, ReferenciaSurtido, ResumenMunicipio, Unidad
from app.services import territorio_service as svc

router = APIRouter(prefix="/v1", dependencies=[Depends(internal_only)])


@router.get("/ageb", response_model=FeatureCollection)
def ageb(conn: psycopg.Connection = Depends(get_conn)):
    return svc.agebs(conn)


@router.get("/ageb/resumen", response_model=ResumenMunicipio)
def ageb_resumen(conn: psycopg.Connection = Depends(get_conn)):
    return svc.resumen(conn)


@router.get("/unidades", response_model=list[Unidad])
def unidades(tipo: Literal["todas", "folios", "urgencias"] = "todas",
             lat: float | None = Query(None, ge=-90, le=90), lon: float | None = Query(None, ge=-180, le=180),
             conn: psycopg.Connection = Depends(get_conn)):
    return svc.unidades(conn, tipo, lat, lon)


@router.get("/ferias", response_model=list[Feria])
def ferias(desde: date | None = None, lat: float | None = Query(None, ge=-90, le=90),
           lon: float | None = Query(None, ge=-180, le=180), conn: psycopg.Connection = Depends(get_conn)):
    return svc.ferias(conn, desde or date.today(), lat, lon)


@router.get("/contexto/mortalidad", response_model=Mortalidad)
def mortalidad(conn: psycopg.Connection = Depends(get_conn)):
    return svc.mortalidad(conn)


@router.get("/contexto/surtido", response_model=ReferenciaSurtido)
def referencia_surtido(conn: psycopg.Connection = Depends(get_conn)):
    return svc.referencia_surtido(conn)
