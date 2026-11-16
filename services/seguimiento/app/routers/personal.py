from typing import Literal

import psycopg
from fastapi import APIRouter, Depends

from app.config import Identidad, get_conn, hoy, identidad, internal_only, requiere
from app.schemas import (DesacuerdoIn, DesacuerdoOut, MedicionCreada, MedicionIn, PacienteDetalle, PacienteFila,
                         ResumenSeguimiento, Ruta)
from app.services import seguimiento_service as svc

router = APIRouter(prefix="/v1", tags=["personal de salud"],
                   dependencies=[Depends(internal_only), Depends(requiere("personal_salud"))])


@router.get("/seguimiento/resumen", response_model=ResumenSeguimiento)
def resumen(ident: Identidad = Depends(identidad), conn: psycopg.Connection = Depends(get_conn)):
    return svc.resumen(conn, ident, hoy())


@router.get("/seguimiento/pacientes", response_model=list[PacienteFila])
def pacientes(nivel: Literal["verde", "amarillo", "rojo", "gris"] | None = None, q: str | None = None,
              ident: Identidad = Depends(identidad), conn: psycopg.Connection = Depends(get_conn)):
    return svc.pacientes(conn, ident, hoy(), nivel, q)


@router.get("/pacientes/{folio}", response_model=PacienteDetalle)
def paciente(folio: str, ident: Identidad = Depends(identidad), conn: psycopg.Connection = Depends(get_conn)):
    return svc.detalle(conn, ident, folio.upper(), hoy())


@router.post("/pacientes/{folio}/mediciones", response_model=MedicionCreada, status_code=201)
def medicion(folio: str, body: MedicionIn, ident: Identidad = Depends(identidad),
             conn: psycopg.Connection = Depends(get_conn)):
    return svc.registrar_medicion(conn, ident, folio.upper(), body, hoy())


@router.post("/pacientes/{folio}/desacuerdo", response_model=DesacuerdoOut, status_code=201)
def desacuerdo(folio: str, body: DesacuerdoIn, ident: Identidad = Depends(identidad),
               conn: psycopg.Connection = Depends(get_conn)):
    return svc.registrar_desacuerdo(conn, ident, folio.upper(), body.nivel_propuesto, body.motivo, hoy())


@router.get("/visitas/ruta", response_model=Ruta)
def ruta(ident: Identidad = Depends(identidad), conn: psycopg.Connection = Depends(get_conn)):
    return svc.ruta(conn, ident, hoy())
