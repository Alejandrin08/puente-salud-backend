import psycopg
from fastapi import APIRouter, Depends

from app.config import Identidad, get_conn, hoy, identidad, internal_only, requiere
from app.schemas import AccesoIn, AccesoOut, ConsentimientoIn, PersonaInicio, PersonaRecorrido
from app.services import persona_service as svc

# Verificación de folio + código: la usa solo el gateway al iniciar la sesión de la persona
interno = APIRouter(prefix="/v1/interno", tags=["interno"], dependencies=[Depends(internal_only)])


@interno.post("/persona/verificar", response_model=AccesoOut)
def verificar(body: AccesoIn, conn: psycopg.Connection = Depends(get_conn)):
    return svc.verificar_acceso(conn, body.folio, body.codigo)


router = APIRouter(prefix="/v1/persona", tags=["persona"],
                   dependencies=[Depends(internal_only), Depends(requiere("persona"))])


@router.post("/{folio}/consentimiento")
def consentimiento(folio: str, body: ConsentimientoIn, ident: Identidad = Depends(identidad),
                   conn: psycopg.Connection = Depends(get_conn)):
    return svc.consentimiento(conn, ident, folio.upper(), body.aceptado)


@router.get("/{folio}/inicio", response_model=PersonaInicio)
def inicio(folio: str, ident: Identidad = Depends(identidad), conn: psycopg.Connection = Depends(get_conn)):
    return svc.inicio(conn, ident, folio.upper(), hoy())


@router.get("/{folio}/recorrido", response_model=PersonaRecorrido)
def recorrido(folio: str, ident: Identidad = Depends(identidad), conn: psycopg.Connection = Depends(get_conn)):
    return svc.mi_recorrido(conn, ident, folio.upper(), hoy())
