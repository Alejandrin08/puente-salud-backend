from fastapi import FastAPI

from app.routers import autoridad, persona, personal

app = FastAPI(title="Puente Salud · seguimiento", version="1.0.0",
              description="Folio Único de Seguimiento, semáforo (Anexo D), indicadores (E.4) y bitácora. Datos simulados.")
app.include_router(personal.router)
app.include_router(persona.interno)
app.include_router(persona.router)
app.include_router(autoridad.router)


@app.get("/health")
def health():
    return {"status": "ok", "servicio": "seguimiento"}
