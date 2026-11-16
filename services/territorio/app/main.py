from fastapi import FastAPI

from app.routers import territorio

app = FastAPI(title="Puente Salud · territorio", version="1.0.0",
              description="Datos públicos y agregados de Tlaquepaque: AGEB, unidades de salud, ferias y mortalidad.")
app.include_router(territorio.router)


@app.get("/health")
def health():
    return {"status": "ok", "servicio": "territorio"}
