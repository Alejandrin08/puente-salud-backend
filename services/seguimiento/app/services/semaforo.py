"""Semáforo de seguimiento (Anexo D de la investigación).

Tres dimensiones —control clínico, seguimiento y riesgo de abandono— y se toma la más grave.
Gris solo si no hay ninguna medición clínica, y nunca se muestra como verde.
El semáforo ordena y explica; no diagnostica: la decisión es del personal de salud.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.services.dominio import Expediente, Medicion, Parametros

SEVERIDAD = {"verde": 0, "gris": 1, "amarillo": 2, "rojo": 3}
NOM_HTA = "NOM-030-SSA2-2009"
NOM_DM = "NOM-015-SSA2-2010"
SUPUESTO = "Supuesto del proyecto (Anexo D.2)"


@dataclass
class Motivo:
    dimension: str  # clinica | seguimiento | riesgo
    nivel: str
    texto: str
    fuente: str
    dato: str | None = None


@dataclass
class Resultado:
    nivel: str
    resumen: str
    motivos: list[Motivo]
    dimensiones: dict[str, str]
    requiere_valoracion: bool = False
    factores_riesgo: list[str] = field(default_factory=list)
    dias_vencida: int = 0
    en_control: bool | None = None


# ------------------------------------------------------------------ control clínico
def metas_pa(enfermedades: list[str]) -> tuple[int, int]:
    """PA en control: < 140/90; < 130/80 si también tiene diabetes (NOM-030 3.7; NOM-015 11.11.7.3)."""
    return (130, 80) if "diabetes" in enfermedades else (140, 90)


def estado_medicion(m: Medicion, enfermedades: list[str]) -> tuple[bool | None, list[str]]:
    """Devuelve (en_control, razones de fuera de control). None si la medición no aplica a sus enfermedades."""
    evaluado, fuera = False, []
    if "hipertension" in enfermedades and m.pas is not None and m.pad is not None:
        evaluado = True
        ms, md = metas_pa(enfermedades)
        if not (m.pas < ms and m.pad < md):
            fuera.append(f"presión {m.pas}/{m.pad} mmHg (meta menor de {ms}/{md})")
    if "diabetes" in enfermedades and (m.glucosa is not None or m.hba1c is not None):
        evaluado = True
        if m.hba1c is not None:
            if m.hba1c >= 7:
                fuera.append(f"HbA1c {m.hba1c}% (meta menor de 7%)")
        elif m.glucosa is not None and not (70 <= m.glucosa <= 130):
            fuera.append(f"glucosa en ayuno {m.glucosa} mg/dl (meta de 70 a 130)")
    if not evaluado:
        return None, []
    return not fuera, fuera


def _crisis(m: Medicion) -> bool:
    return (m.pas is not None and m.pas > 180) or (m.pad is not None and m.pad > 110)


def dimension_clinica(e: Expediente, hoy: date) -> tuple[str, list[Motivo], bool, bool | None]:
    con_valores = [m for m in e.mediciones if m.tiene_valores()]
    if not con_valores:
        return "gris", [Motivo("clinica", "gris", "Sin ninguna medición clínica registrada", SUPUESTO)], False, None
    motivos: list[Motivo] = []
    nivel = "verde"
    valoracion = False
    evaluadas = [(m, *estado_medicion(m, e.enfermedades)) for m in con_valores]
    evaluadas = [x for x in evaluadas if x[1] is not None]
    ultima = con_valores[-1]
    fuente_ctrl = " y ".join(([NOM_HTA + ", 3.7"] if "hipertension" in e.enfermedades else [])
                             + ([NOM_DM + ", 3.10"] if "diabetes" in e.enfermedades else []))
    if _crisis(ultima):
        nivel = "rojo"
        motivos.append(Motivo("clinica", "rojo", f"Presión arterial muy alta: {ultima.pas}/{ultima.pad} mmHg (mayor de 180/110)",
                              NOM_HTA + ", 6.1", ultima.fecha.isoformat()))
    en_control = evaluadas[-1][1] if evaluadas else None
    if evaluadas:
        m1, ok1, razones1 = evaluadas[-1]
        if not ok1:
            # Glucosa < 70: fuera de control con la leyenda «requiere valoración del personal» (Anexo D.3)
            if m1.glucosa is not None and m1.glucosa < 70 and m1.hba1c is None:
                valoracion = True
                razones1 = [r + ", requiere valoración del personal" if r.startswith("glucosa") else r for r in razones1]
            if len(evaluadas) >= 2 and not evaluadas[-2][1]:
                nivel = "rojo"
                motivos.append(Motivo("clinica", "rojo", "Fuera de control en dos mediciones seguidas: " + "; ".join(razones1),
                                      fuente_ctrl, m1.fecha.isoformat()))
            else:
                nivel = max(nivel, "amarillo", key=SEVERIDAD.get)
                motivos.append(Motivo("clinica", "amarillo", "Fuera de control en la última medición: " + "; ".join(razones1),
                                      fuente_ctrl, m1.fecha.isoformat()))
    if "diabetes" in e.enfermedades and e.fecha_confirmacion:
        hba = [m for m in con_valores if m.hba1c is not None]
        ref = hba[-1].fecha if hba else None
        if (ref and (hoy - ref).days > 365) or (not ref and (hoy - e.fecha_confirmacion).days > 365):
            nivel = max(nivel, "amarillo", key=SEVERIDAD.get)
            txt = f"HbA1c con más de 12 meses (última: {ref.isoformat()})" if ref else "Sin HbA1c en más de 12 meses desde el diagnóstico"
            motivos.append(Motivo("clinica", "amarillo", txt, NOM_DM + ", 11.11.1.4"))
    if nivel == "verde":
        motivos.append(Motivo("clinica", "verde", "En control en la última medición", fuente_ctrl, ultima.fecha.isoformat()))
    return nivel, motivos, valoracion, en_control


# ------------------------------------------------------------------ seguimiento
def ultima_consulta(e: Expediente) -> date | None:
    fechas = [c.fecha for c in e.consultas]
    return max(fechas) if fechas else None


def dimension_seguimiento(e: Expediente, hoy: date, p: Parametros, en_control: bool | None) -> tuple[str, list[Motivo], int]:
    if not e.fecha_confirmacion:
        dias = (hoy - e.fecha_deteccion).days
        if dias > p.dias_perdida_confirmacion:
            return "rojo", [Motivo("seguimiento", "rojo", f"Pérdida en la confirmación: sin confirmar a los {dias} días de la detección",
                                   SUPUESTO)], dias - p.dias_confirmacion
        if dias > p.dias_confirmacion:
            return "amarillo", [Motivo("seguimiento", "amarillo", f"Sin confirmar a los {dias} días de la detección", SUPUESTO)], \
                dias - p.dias_confirmacion
        return "verde", [Motivo("seguimiento", "verde", f"En plazo para confirmar el diagnóstico (día {dias} de {p.dias_confirmacion})",
                                SUPUESTO)], 0
    ultima = ultima_consulta(e) or e.fecha_confirmacion
    dias_sin = (hoy - ultima).days
    if dias_sin > p.meses_abandono * 30:
        meses = dias_sin // 30
        return "rojo", [Motivo("seguimiento", "rojo", f"Abandono: sin consulta de control hace {meses} meses", SUPUESTO,
                               ultima.isoformat())], dias_sin
    plazo = p.dias_control_con_control if en_control else p.dias_control_sin_control
    vencida = dias_sin - plazo
    if vencida > p.dias_vencida_grave:
        return "rojo", [Motivo("seguimiento", "rojo", f"Consulta de control vencida hace {vencida} días", SUPUESTO,
                               ultima.isoformat())], vencida
    if vencida > 0:
        return "amarillo", [Motivo("seguimiento", "amarillo", f"Consulta de control vencida hace {vencida} días", SUPUESTO,
                                   ultima.isoformat())], vencida
    return "verde", [Motivo("seguimiento", "verde", f"Consulta dentro del plazo (cada {plazo} días)", SUPUESTO,
                            ultima.isoformat())], 0


# ------------------------------------------------------------------ riesgo de abandono
def factores_riesgo(e: Expediente, hoy: date, vencida: bool) -> list[str]:
    f = []
    pasadas = [c for c in e.citas if c.fecha <= hoy and c.estado in ("atendida", "perdida")]
    if len(pasadas) >= 2 and pasadas[-1].estado == "perdida" and pasadas[-2].estado == "perdida":
        f.append("dos citas perdidas seguidas")
    if not e.seguridad_social:
        f.append("sin afiliación a servicios de salud")
    if e.rezago in ("Alto", "Muy alto"):
        f.append(f"vive en una AGEB de rezago social {e.rezago.lower()}")
    if vencida:
        f.append("consulta vencida")
    return f


def evaluar(e: Expediente, hoy: date, p: Parametros | None = None) -> Resultado:
    p = p or Parametros()
    e.ordenar()
    n_cli, m_cli, valoracion, en_control = dimension_clinica(e, hoy)
    n_seg, m_seg, dias_vencida = dimension_seguimiento(e, hoy, p, en_control)
    fr = factores_riesgo(e, hoy, dias_vencida > 0)
    if len(fr) >= 2:
        n_rie, m_rie = "amarillo", [Motivo("riesgo", "amarillo", "Riesgo de abandono alto: " + ", ".join(fr), SUPUESTO)]
    else:
        n_rie, m_rie = "verde", []
    dims = {"clinica": n_cli, "seguimiento": n_seg, "riesgo": n_rie}
    nivel = max(dims.values(), key=SEVERIDAD.get)
    if nivel == "gris" or (nivel == "verde" and n_cli == "gris"):
        nivel = "gris"
    motivos = sorted(m_cli + m_seg + m_rie, key=lambda m: -SEVERIDAD[m.nivel])
    principal = next((m for m in motivos if m.nivel == nivel), motivos[0])
    etiqueta = {"verde": "Verde", "amarillo": "Amarillo", "rojo": "Rojo", "gris": "Gris"}[nivel]
    return Resultado(nivel=nivel, resumen=f"{etiqueta}: {principal.texto[0].lower()}{principal.texto[1:]}",
                     motivos=motivos, dimensiones=dims, requiere_valoracion=valoracion, factores_riesgo=fr,
                     dias_vencida=max(dias_vencida, 0), en_control=en_control)
