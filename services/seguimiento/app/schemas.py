"""Contratos de la API de seguimiento (Pydantic)."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Nivel = Literal["verde", "amarillo", "rojo", "gris"]


class MotivoOut(BaseModel):
    dimension: Literal["clinica", "seguimiento", "riesgo"]
    nivel: Nivel
    texto: str
    fuente: str
    dato: str | None = None


class SemaforoOut(BaseModel):
    nivel: Nivel
    resumen: str
    motivos: list[MotivoOut]
    dimensiones: dict[str, Nivel]
    requiere_valoracion: bool
    factores_riesgo: list[str]
    dias_vencida: int
    aviso: str = "El semáforo ordena y explica; no diagnostica. La decisión es del personal de salud."


class CitaOut(BaseModel):
    fecha: date
    hora: time | None
    tipo: str
    estado: str


class PacienteFila(BaseModel):
    folio: str
    nombre: str
    edad: int
    sexo: str
    enfermedades: list[str]
    programa: str
    nivel: Nivel
    resumen: str
    dias_vencida: int
    proxima_cita: CitaOut | None
    simulated: bool = True


class AgendaItem(BaseModel):
    hora: time | None
    folio: str
    nombre: str
    tipo: str
    nivel: Nivel
    resumen: str


class UnidadOut(BaseModel):
    clues: str
    nombre: str
    institucion: str | None = None
    lat: float | None = None
    lon: float | None = None


class ResumenSeguimiento(BaseModel):
    fecha: date
    unidad: UnidadOut
    total: int
    conteo: dict[Nivel, int]
    prioridades: list[PacienteFila]
    agenda: list[AgendaItem]
    simulated: bool = True


class EtapaOut(BaseModel):
    paso: int
    clave: str
    titulo: str
    completada: bool
    fecha: date | None
    detalle: str


class MedicionOut(BaseModel):
    id: int | None
    fecha: date
    pas: int | None
    pad: int | None
    glucosa: int | None
    hba1c: float | None
    programa_id: str | None
    programa: str | None
    otro_programa: bool
    en_control: bool | None


class SurtidoOut(BaseModel):
    fecha: date
    medicamento: str
    dias: int
    completo: bool


class Adherencia(BaseModel):
    registros: list[SurtidoOut]
    porcentaje_completo: float | None
    dias_desde_ultimo: int | None
    cubierto_hoy: bool


class DesacuerdoOut(BaseModel):
    id: int
    fecha: datetime
    usuario: str
    nivel_sugerido: str
    nivel_propuesto: str
    motivo: str


class EventoBitacora(BaseModel):
    id: int
    fecha: datetime
    usuario: str
    rol: str
    accion: str
    folio: str | None
    detalle: dict[str, Any]


class PersonaDetalle(BaseModel):
    folio: str
    nombre: str
    curp_simulada: str
    edad: int
    sexo: str
    enfermedades: list[str]
    seguridad_social: str | None
    programa_origen: str
    programa_nombre: str
    unidad: UnidadOut
    cvegeo: str
    rezago: str
    red_apoyo: str | None
    dependencia_social: bool
    telefono_simulado: str | None
    fecha_deteccion: date
    fecha_confirmacion: date | None


class PacienteDetalle(BaseModel):
    persona: PersonaDetalle
    semaforo: SemaforoOut
    etapas: list[EtapaOut]
    mediciones: list[MedicionOut]
    tratamientos: list[dict[str, Any]]
    adherencia: Adherencia
    citas: list[CitaOut]
    desacuerdos: list[DesacuerdoOut]
    bitacora: list[EventoBitacora]
    consultas_registradas: int = 0  # vistas del recorrido y sugerencias del semáforo (se auditan todas)
    simulated: bool = True


class MedicionIn(BaseModel):
    fecha: date | None = None
    pas: int | None = Field(None, ge=50, le=300)
    pad: int | None = Field(None, ge=30, le=200)
    glucosa: int | None = Field(None, ge=20, le=700)
    hba1c: float | None = Field(None, ge=3, le=20)
    es_consulta: bool = True

    @model_validator(mode="after")
    def validar(self):
        if (self.pas is None) != (self.pad is None):
            raise ValueError("Captura la presión completa: sistólica y diastólica")
        if all(v is None for v in (self.pas, self.glucosa, self.hba1c)):
            raise ValueError("Captura al menos un valor")
        if self.pas is not None and self.pad is not None and self.pas <= self.pad:
            raise ValueError("La sistólica debe ser mayor que la diastólica")
        return self


class MedicionCreada(BaseModel):
    medicion_id: int
    semaforo_anterior: Nivel
    semaforo: SemaforoOut


class DesacuerdoIn(BaseModel):
    nivel_propuesto: Nivel
    motivo: str = Field(min_length=5, max_length=500)


class ParadaRuta(BaseModel):
    orden: int
    folio: str
    nombre: str
    nivel: Nivel
    resumen: str
    lat: float
    lon: float
    distancia_km: float
    minutos_traslado: int
    visita_programada: bool


class Ruta(BaseModel):
    fecha: date
    origen: UnidadOut
    paradas: list[ParadaRuta]
    distancia_km: float
    minutos_traslado: int
    minutos_total: int
    nota: str
    simulated: bool = True


# ---------------- persona
class AccesoIn(BaseModel):
    folio: str = Field(min_length=4, max_length=12)
    codigo: str = Field(min_length=4, max_length=12)


class AccesoOut(BaseModel):
    folio: str
    nombre: str
    curp_simulada: str
    consentimiento: bool | None


class ConsentimientoIn(BaseModel):
    aceptado: bool


class SiguientePasoOut(BaseModel):
    titulo: str
    texto: str
    cita: CitaOut | None


class PersonaInicio(BaseModel):
    folio: str
    nombre: str
    paso_actual: int
    completado: bool
    etapas: list[EtapaOut]
    siguiente_paso: SiguientePasoOut
    unidad: UnidadOut
    zona: dict[str, float | None]
    simulated: bool = True


class EventoRecorrido(BaseModel):
    fecha: date
    tipo: str
    titulo: str
    detalle: str
    estado: Literal["hecho", "pendiente", "perdido"]


class PersonaRecorrido(BaseModel):
    folio: str
    paso_actual: int
    etapas: list[EtapaOut]
    eventos: list[EventoRecorrido]
    simulated: bool = True


# ---------------- autoridad
class Cuatro(BaseModel):
    detectadas: int
    confirmacion_pct: float | None
    confirmacion_num: int
    confirmacion_den: int
    dias_primera_consulta_mediana: float | None
    dias_primera_consulta_n: int
    dias_primera_consulta_p25: float | None
    dias_primera_consulta_p75: float | None
    retencion_6_pct: float | None
    retencion_6_num: int
    retencion_6_den: int
    retencion_12_pct: float | None
    retencion_12_num: int
    retencion_12_den: int
    control_pct: float | None
    control_num: int
    control_den: int


class IndicadoresPrograma(Cuatro):
    programa_id: str
    programa: str
    ambito: str


class Indicadores(BaseModel):
    fecha_corte: date
    total: Cuatro
    por_programa: list[IndicadoresPrograma]
    definiciones: dict[str, str]
    simulated: bool = True


class PuntoEvolucion(BaseModel):
    mes: str
    control_pct: float | None
    num: int
    den: int


class Evolucion(BaseModel):
    total: list[PuntoEvolucion]
    por_programa: dict[str, list[PuntoEvolucion]]
    programas: dict[str, str]
    simulated: bool = True


class IndicadorAgeb(BaseModel):
    cvegeo: str
    detectadas: int
    confirmadas: int
    control_pct: float | None
    control_num: int
    confirmacion_pct: float | None
    rezago: str
    pct_sinder: float | None
    prioridad: float | None
    factores: list[str]
    suficiente: bool


class IndicadoresAgeb(BaseModel):
    fecha_corte: date
    minimo_casos: int
    agebs: list[IndicadorAgeb]
    zonas_prioritarias: list[IndicadorAgeb]
    nota: str
    simulated: bool = True
