from datetime import date
from typing import Any, Literal

from pydantic import BaseModel


class Unidad(BaseModel):
    clues: str
    nombre: str
    institucion: str
    tipo: str | None
    publica: bool
    urgencias: bool
    asigna_folios: bool
    lat: float
    lon: float
    horario: str | None
    servicios: list[str]
    distancia_km: float | None = None
    ubicacion_simulada: bool = True
    datos_simulados: bool = True


class Feria(BaseModel):
    id: int
    nombre: str
    programa: str
    fecha: date
    horario: str
    lugar: str
    lat: float
    lon: float
    servicios: list[str]
    distancia_km: float | None = None
    simulated: bool = True


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[dict[str, Any]]
    fuente: str


class PuntoMortalidad(BaseModel):
    anio: int
    defunciones: int
    tasa_100k: float | None


class SerieMortalidad(BaseModel):
    causa: Literal["diabetes", "hipertension"]
    etiqueta: str
    serie: list[PuntoMortalidad]
    por_sexo: dict[str, int]
    variacion_pct: float | None
    tendencia: Literal["sube", "baja", "estable"]


class Mortalidad(BaseModel):
    series: list[SerieMortalidad]
    total_defunciones_ultimo_anio: int
    ultimo_anio: int
    poblacion_ref: int
    fuente: str
    nota: str


class FilaReferencia(BaseModel):
    periodo: str
    ambito: Literal["nacional", "estatal", "unidad"]
    nombre: str
    clues: str | None
    unidades: int
    recetas: int
    completas_pct: float
    parciales_pct: float
    negadas_pct: float


class ReferenciaSurtido(BaseModel):
    filas: list[FilaReferencia]
    fuente: str
    nota: str


class ResumenMunicipio(BaseModel):
    agebs: int
    poblacion: int
    poblacion_18ymas: int
    sin_afiliacion: int
    sin_afiliacion_18_est: int
    con_discapacidad: int
    rezago: dict[str, int]
    unidades_publicas: int
    unidades_total: int
    fuente: str
