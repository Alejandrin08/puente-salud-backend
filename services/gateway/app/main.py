from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.repositories import servicios
from app.routers import auth, proxy


@asynccontextmanager
async def ciclo(_app: FastAPI):
    yield
    await servicios.cerrar()


app = FastAPI(title="Puente Salud · API", version="1.0.0", lifespan=ciclo,
              description="Gateway: único punto de entrada. Sesión por token en la cabecera Authorization y roles "
                          "(persona, personal_salud, autoridad). Los datos de personas son simulados.")
app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"],
                   expose_headers=["Content-Disposition"])
app.include_router(auth.router)
app.include_router(proxy.router)


@app.get("/health")
async def health():
    return {"status": "ok", "servicio": "gateway"}


@app.get("/api/v1/estado")
async def estado():
    s, t = await servicios.salud("seguimiento"), await servicios.salud("territorio")
    return {"gateway": True, "seguimiento": s, "territorio": t, "ok": s and t}
