from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.repositories import servicios
from app.services import auth

router = APIRouter(prefix="/api/v1", tags=["sesión"])


class LoginIn(BaseModel):
    usuario: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=120)


class AccesoPersonaIn(BaseModel):
    folio: str = Field(min_length=4, max_length=12)
    codigo: str = Field(min_length=4, max_length=12)


class SesionOut(BaseModel):
    token: str
    expira: int
    usuario: str
    rol: str
    nombre: str
    clues: str | None = None
    folio: str | None = None
    consentimiento: bool | None = None
    curp_simulada: str | None = None


@router.post("/auth/login", response_model=SesionOut)
def login(body: LoginIn):
    s = auth.login_demo(body.usuario.strip(), body.password)
    token, exp = auth.emitir(s)
    return SesionOut(token=token, expira=exp, usuario=s.usuario, rol=s.rol, nombre=s.nombre, clues=s.clues)


@router.post("/persona/acceso", response_model=SesionOut)
async def acceso_persona(body: AccesoPersonaIn):
    r = await servicios.llamar("seguimiento", "POST", "/v1/interno/persona/verificar", json=body.model_dump())
    if r.status_code != 200:
        raise HTTPException(r.status_code if r.status_code in (401, 422) else 502,
                            r.json().get("detail", "No se pudo verificar el folio") if r.headers.get("content-type", "").startswith("application/json") else "No se pudo verificar el folio")
    d = r.json()
    s = auth.Sesion(usuario=d["folio"], rol="persona", nombre=d["nombre"], folio=d["folio"])
    token, exp = auth.emitir(s)
    return SesionOut(token=token, expira=exp, usuario=s.usuario, rol=s.rol, nombre=s.nombre, folio=s.folio,
                     consentimiento=d["consentimiento"], curp_simulada=d["curp_simulada"])


@router.get("/auth/me")
def me(s: auth.Sesion = Depends(auth.sesion_actual)):
    return {"usuario": s.usuario, "rol": s.rol, "nombre": s.nombre, "clues": s.clues, "folio": s.folio}
