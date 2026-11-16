"""Autenticación mínima y roles: cuentas de demostración (DEMO_USERS) y acceso de la persona con folio + código."""
from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from app.config import config
from app.services import tokens

ROLES = ("persona", "personal_salud", "autoridad")


@dataclass(frozen=True)
class Sesion:
    usuario: str
    rol: str
    nombre: str
    clues: str | None = None
    folio: str | None = None

    def cabeceras_internas(self) -> dict[str, str]:
        return {"X-Usuario": self.usuario, "X-Rol": self.rol, "X-Clues": self.clues or "", "X-Folio": self.folio or ""}


def login_demo(usuario: str, password: str) -> Sesion:
    for u in config.demo_users:
        if hmac.compare_digest(u["usuario"], usuario) and hmac.compare_digest(u["password"], password):
            if u["rol"] not in ROLES:
                break
            return Sesion(usuario=u["usuario"], rol=u["rol"], nombre=u.get("nombre") or u["usuario"], clues=u.get("clues"))
    raise HTTPException(401, "Usuario o contraseña incorrectos")


def emitir(s: Sesion) -> tuple[str, int]:
    return tokens.emitir({"u": s.usuario, "r": s.rol, "n": s.nombre, "c": s.clues, "f": s.folio},
                         config.token_secret, config.token_horas)


def sesion_actual(authorization: str = Header(default="")) -> Sesion:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Inicia sesión para continuar", headers={"WWW-Authenticate": "Bearer"})
    try:
        d = tokens.verificar(authorization[7:].strip(), config.token_secret)
    except tokens.TokenInvalido as e:
        raise HTTPException(401, str(e), headers={"WWW-Authenticate": "Bearer"}) from e
    return Sesion(usuario=d["u"], rol=d["r"], nombre=d["n"], clues=d.get("c"), folio=d.get("f"))


def con_rol(*roles: str):
    """El gateway comprueba el rol en cada petición; los servicios lo vuelven a comprobar."""
    def dep(s: Sesion = Depends(sesion_actual)) -> Sesion:
        if s.rol not in roles:
            raise HTTPException(403, "Tu rol no tiene acceso a esta sección")
        return s
    return dep
