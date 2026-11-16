"""Modelo de dominio del recorrido de una persona (independiente de la base y de la API)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time


@dataclass
class Parametros:
    """Anexo D.2: plazos por defecto, configurables por programa."""
    dias_confirmacion: int = 30
    dias_perdida_confirmacion: int = 90
    dias_control_sin_control: int = 30
    dias_control_con_control: int = 90
    dias_vencida_grave: int = 30
    meses_abandono: int = 12


@dataclass
class Medicion:
    fecha: date
    pas: int | None = None
    pad: int | None = None
    glucosa: int | None = None
    hba1c: float | None = None
    programa_id: str | None = None
    id: int | None = None

    def tiene_valores(self) -> bool:
        return any(v is not None for v in (self.pas, self.pad, self.glucosa, self.hba1c))


@dataclass
class Cita:
    fecha: date
    tipo: str
    estado: str
    hora: time | None = None
    clues: str | None = None


@dataclass
class Consulta:
    fecha: date
    tipo: str
    clues: str | None = None


@dataclass
class Tratamiento:
    fecha_inicio: date
    medicamento: str
    indicacion: str = ""


@dataclass
class Surtido:
    fecha: date
    medicamento: str
    dias: int
    completo: bool


@dataclass
class Expediente:
    folio: str
    fecha_deteccion: date
    enfermedades: list[str]
    programa_origen: str
    cvegeo: str
    rezago: str = "Sin dato"
    seguridad_social: str | None = None
    unidad_clues: str | None = None
    fecha_confirmacion: date | None = None
    mediciones: list[Medicion] = field(default_factory=list)
    consultas: list[Consulta] = field(default_factory=list)
    citas: list[Cita] = field(default_factory=list)
    tratamientos: list[Tratamiento] = field(default_factory=list)
    surtidos: list[Surtido] = field(default_factory=list)
    # Datos de presentación (no intervienen en las reglas)
    nombre: str = ""
    apellidos: str = ""
    sexo: str = ""
    fecha_nacimiento: date | None = None
    domicilio_lat: float | None = None
    domicilio_lon: float | None = None
    curp_simulada: str = ""
    red_apoyo: str | None = None
    dependencia_social: bool = False
    telefono_simulado: str | None = None

    def ordenar(self) -> "Expediente":
        self.mediciones.sort(key=lambda m: (m.fecha, m.id or 0))
        self.consultas.sort(key=lambda c: c.fecha)
        self.citas.sort(key=lambda c: (c.fecha, c.hora or time(0)))
        self.tratamientos.sort(key=lambda t: t.fecha_inicio)
        self.surtidos.sort(key=lambda s: s.fecha)
        return self
