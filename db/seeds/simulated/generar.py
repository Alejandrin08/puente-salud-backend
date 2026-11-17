"""Generador de datos simulados de Puente Salud (semilla fija, Python estándar).

Todo lo que sale de aquí es SIMULADO y se marca así (columna `simulated` / `datos_simulados`).
Se parametriza con datos reales (población adulta y sin afiliación por AGEB del Censo 2020,
rezago CONEVAL, catálogo CLUES) y con tasas publicadas (Anexos C y E.7 de la investigación):
  - control de diabetes ~25-33% (Basto-Abreu 2024), hipertensión tratada en control ~60% (Campos-Nonato 2025)
  - la pérdida ocurre después de la detección (Lozano 2021): la confirmación varía mucho por programa.

La fecha de referencia («hoy» del recorrido simulado) se pasa como argumento: con la misma semilla
las personas y sus recorridos relativos son idénticos sin importar el día en que se genere.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from datetime import date, time, timedelta

SEMILLA = 2026
CODIGO_DEMO = "246810"  # código de acceso de demostración, igual para todas las personas simuladas
N_PERSONAS = 1000
# Cadena de dos estados (en control / fuera de control) en cada consulta de seguimiento.
# Calibrada para que ~40-55% de las personas confirmadas esté en control (Basto-Abreu 2024; Campos-Nonato 2025).
CTRL_ENTRA = 0.4
CTRL_RACHA = 0.01
CTRL_TOPE = 0.25
CTRL_PERMANECE = 0.40

PROGRAMAS = [
    # id, nombre, ámbito, peso, prob. confirmación, prob. asistir a cita, riesgo mensual de abandono, prob. base de control
    ("centros_rxii", "Centros de salud Región Sanitaria XII", "Piloto municipal", 0.30, 0.86, 0.85, 0.020, 0.46),
    ("caravanas", "Caravanas de Salud", "Piloto municipal", 0.22, 0.72, 0.80, 0.030, 0.40),
    ("ferias", "Ferias de salud", "Programa estatal", 0.20, 0.46, 0.72, 0.050, 0.32),
    ("medicos_hogar", "Médicas y Médicos de Jalisco en tu Hogar", "Programa estatal", 0.13, 0.78, 0.84, 0.025, 0.44),
    ("casa_por_casa", "Salud Casa por Casa", "Otra institución", 0.15, 0.62, 0.78, 0.035, 0.38),
]

NOMBRES_M = ["María", "Rosa", "Guadalupe", "Juana", "Margarita", "Josefina", "Verónica", "Leticia", "Patricia",
             "Teresa", "Alicia", "Martha", "Elena", "Silvia", "Gabriela", "Laura", "Carmen", "Socorro", "Irma", "Lucía"]
NOMBRES_H = ["José", "Juan", "Francisco", "Jesús", "Antonio", "Miguel", "Pedro", "Manuel", "Javier", "Rafael",
             "Luis", "Jorge", "Alfredo", "Ramón", "Salvador", "Arturo", "Fernando", "Roberto", "Enrique", "Raúl"]
APELLIDOS = ["García", "Hernández", "López", "Martínez", "González", "Rodríguez", "Pérez", "Sánchez", "Ramírez",
             "Cruz", "Flores", "Gómez", "Morales", "Vázquez", "Reyes", "Jiménez", "Torres", "Díaz", "Gutiérrez",
             "Ruiz", "Mendoza", "Aguilar", "Ortiz", "Castillo", "Navarro", "Ramos", "Delgado", "Partida", "Orozco"]
LUGARES_FERIA = ["Plaza principal", "Unidad deportiva", "Explanada del mercado", "Atrio del templo",
                 "Escuela primaria", "Centro comunitario", "Parque de la colonia", "Delegación municipal"]

MED_DM = ["Metformina 850 mg", "Glibenclamida 5 mg"]
MED_HTA = ["Losartán 50 mg", "Enalapril 10 mg", "Amlodipino 5 mg"]
# Tabletas por día (para estimar la necesidad mensual)
DOSIS_DIA = {"Metformina 850 mg": 2, "Glibenclamida 5 mg": 1, "Losartán 50 mg": 1, "Enalapril 10 mg": 1, "Amlodipino 5 mg": 1}


class Abasto:
    """Probabilidad de surtido completo por unidad y medicamento, con periodos de desabasto.

    Usa su propia semilla para no alterar la secuencia de las personas (los folios de demostración no cambian).
    Base 85% (SSJ reporta 85% en primer nivel; la prensa midió cerca de 60%), con variación por unidad
    y algunos desabastos de 2 a 4 meses en pares unidad-medicamento.
    """

    def __init__(self, semilla: int, hoy: date):
        self.r = random.Random(semilla + 17)
        self.hoy = hoy
        self.base: dict[str, float] = {}
        self.cortes: dict[tuple[str, str], tuple[date, date]] = {}

    def _unidad(self, clues: str) -> float:
        if clues not in self.base:
            self.base[clues] = min(max(self.r.gauss(0.84, 0.07), 0.6), 0.97)
            for m in MED_DM + MED_HTA:
                if self.r.random() < 0.22:
                    ini = self.hoy - timedelta(days=self.r.randint(20, 330))
                    self.cortes[(clues, m)] = (ini, ini + timedelta(days=self.r.randint(60, 120)))
        return self.base[clues]

    def completo(self, clues: str, med: str, fecha: date) -> bool:
        p = self._unidad(clues)
        corte = self.cortes.get((clues, med))
        if corte and corte[0] <= fecha <= corte[1]:
            p = 0.25
        return self.r.random() < p


# ---------------------------------------------------------------- utilidades geográficas
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _en_anillo(x: float, y: float, anillo: list) -> bool:
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi:
            dentro = not dentro
        j = i
    return dentro


def en_poligono(x: float, y: float, geom: dict) -> bool:
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    for poly in polys:
        if _en_anillo(x, y, poly[0]) and not any(_en_anillo(x, y, h) for h in poly[1:]):
            return True
    return False


def bbox(geom: dict) -> tuple[float, float, float, float]:
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    xs = [p[0] for poly in polys for p in poly[0]]
    ys = [p[1] for poly in polys for p in poly[0]]
    return min(xs), min(ys), max(xs), max(ys)


def punto_en(geom: dict, rng: random.Random) -> tuple[float, float]:
    """Punto aleatorio dentro del polígono (lat, lon)."""
    x0, y0, x1, y1 = bbox(geom)
    for _ in range(500):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if en_poligono(x, y, geom):
            return round(y, 6), round(x, 6)
    return round((y0 + y1) / 2, 6), round((x0 + x1) / 2, 6)


def centroide(geom: dict) -> tuple[float, float]:
    x0, y0, x1, y1 = bbox(geom)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if en_poligono(cx, cy, geom):
        return round(cy, 6), round(cx, 6)
    return punto_en(geom, random.Random(hash((x0, y0)) & 0xFFFF))


# ---------------------------------------------------------------- unidades y ferias
def unidad_asigna_folios(u: dict) -> bool:
    n = u["nombre"].upper()
    return (u["publica"] and u["estatus"] == "EN OPERACION" and "CONSULTA EXTERNA" in u["tipo"].upper()
            and ("CENTRO DE SALUD" in n or "MEDICINA FAMILIAR" in n or n.startswith("UMF") or "MUNICIPALES" in n))


def ubicar_unidades(unidades: list[dict], agebs: list[dict], rng: random.Random) -> list[dict]:
    """CLUES no trae coordenadas: cada unidad se asigna a una AGEB (misma localidad si existe), ponderada por población."""
    por_loc: dict[str, list[dict]] = {}
    for a in agebs:
        por_loc.setdefault(a["cve_loc"], []).append(a)
    out = []
    for u in sorted(unidades, key=lambda r: r["clues"]):
        cands = por_loc.get(u.get("cve_loc") or "", []) or por_loc["0001"]
        pesos = [max(a.get("pobtot") or 1, 1) for a in cands]
        a = rng.choices(cands, weights=pesos, k=1)[0]
        lat, lon = punto_en(a["geom"], rng)
        folios = unidad_asigna_folios(u)
        if u["urgencias"]:
            horario, servicios = "Abierto las 24 horas", ["Urgencias", "Hospitalización" if "HOSPITAL" in u["tipo"].upper() else "Atención prehospitalaria"]
        elif folios:
            horario = rng.choice(["Lunes a viernes, 8:00 a 15:00", "Lunes a viernes, 8:00 a 20:00",
                                  "Lunes a sábado, 7:00 a 14:00"])
            servicios = ["Detección de diabetes e hipertensión", "Consulta de control", "Farmacia"]
            if rng.random() < 0.6:
                servicios.append("Laboratorio: glucosa y HbA1c")
            if rng.random() < 0.4:
                servicios.append("Nutrición")
        else:
            horario = rng.choice(["Lunes a viernes, 9:00 a 18:00", "Lunes a sábado, 9:00 a 14:00"])
            servicios = ["Consulta general"]
        out.append({**u, "asigna_folios": folios, "cvegeo": a["cvegeo"], "lat": lat, "lon": lon,
                    "horario": horario, "servicios": servicios})
    return out


def generar_ferias(agebs: list[dict], hoy: date, rng: random.Random) -> list[dict]:
    grandes = sorted(agebs, key=lambda a: -(a.get("p_18ymas") or 0))[:60]
    ferias = []
    for i in range(12):
        a = rng.choice(grandes)
        lat, lon = centroide(a["geom"])
        prog = rng.choice(["Ferias de salud", "Caravanas de Salud"])
        ferias.append({
            "nombre": f"{prog}: jornada de detección",
            "programa": prog,
            "fecha": hoy + timedelta(days=rng.randint(1, 45)),
            "horario": rng.choice(["9:00 a 14:00", "8:00 a 13:00", "10:00 a 15:00"]),
            "lugar": f"{rng.choice(LUGARES_FERIA)}, {(a.get('nom_loc') or 'Tlaquepaque').title()}",
            "cvegeo": a["cvegeo"], "lat": lat, "lon": lon,
            "servicios": ["Toma de presión arterial", "Glucosa capilar", "Orientación nutricional"]
                         + (["Vacunación"] if rng.random() < 0.5 else []),
        })
    return sorted(ferias, key=lambda f: f["fecha"])


# ---------------------------------------------------------------- personas y recorridos
@dataclass
class Persona:
    folio: str
    curp_simulada: str
    nombre: str
    apellidos: str
    sexo: str
    fecha_nacimiento: date
    cvegeo: str
    domicilio_lat: float
    domicilio_lon: float
    seguridad_social: str | None
    programa_origen: str
    unidad_clues: str
    fecha_deteccion: date
    dependencia_social: bool
    red_apoyo: str | None
    telefono_simulado: str
    codigo: str
    enfermedades: list[str] = field(default_factory=list)


def hash_codigo(folio: str, codigo: str) -> str:
    return hashlib.sha256(f"{folio}:{codigo}".encode()).hexdigest()


def _b36(n: int) -> str:
    d = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return d[n // 36 % 36] + d[n % 36]


def _sin_acentos(s: str) -> str:
    return s.upper().translate(str.maketrans("ÁÉÍÓÚÜÑ", "AEIOUUX"))


def _medicion(rng: random.Random, enf: list[str], controlado: bool, con_hba1c: bool) -> dict:
    m: dict = {"pas": None, "pad": None, "glucosa": None, "hba1c": None}
    if "hipertension" in enf:
        meta_s, meta_d = (130, 80) if "diabetes" in enf else (140, 90)
        if controlado:
            m["pas"] = int(min(rng.gauss(meta_s - 14, 6), meta_s - 1))
            m["pad"] = int(min(rng.gauss(meta_d - 9, 4), meta_d - 1))
        elif rng.random() < 0.05:
            m["pas"], m["pad"] = rng.randint(182, 200), rng.randint(105, 118)
        else:
            m["pas"] = int(max(rng.gauss(152, 11), meta_s + 1))
            m["pad"] = int(max(rng.gauss(95, 6), meta_d - 4))
    if "diabetes" in enf:
        if controlado:
            m["glucosa"] = int(min(max(rng.gauss(108, 12), 72), 129))
            if con_hba1c:
                m["hba1c"] = round(min(rng.gauss(6.4, 0.3), 6.9), 1)
        else:
            m["glucosa"] = rng.randint(60, 68) if rng.random() < 0.03 else int(max(rng.gauss(188, 40), 131))
            if con_hba1c:
                m["hba1c"] = round(max(rng.gauss(8.7, 1.0), 7.1), 1)
    return m


def generar(agebs: list[dict], unidades_clues: list[dict], hoy: date, n: int = N_PERSONAS, semilla: int = SEMILLA) -> dict:
    rng = random.Random(semilla)
    abasto = Abasto(semilla, hoy)
    unidades = ubicar_unidades(unidades_clues, agebs, rng)
    ferias = generar_ferias(agebs, hoy, rng)
    de_folios = [u for u in unidades if u["asigna_folios"]]
    por_inst = {
        "SSA": [u for u in de_folios if "SECRETARIA" in u["institucion"] or "MUNICIPALES" in u["institucion"]],
        "IMSS": [u for u in de_folios if "MEXICANO DEL SEGURO" in u["institucion"]],
        "ISSSTE": [u for u in de_folios if "SEGURIDAD Y SERVICIOS" in u["institucion"]],
    }
    prog_ids = [p[0] for p in PROGRAMAS]
    prog_pesos = [p[3] for p in PROGRAMAS]
    prog_param = {p[0]: p for p in PROGRAMAS}
    con_adultos = [a for a in agebs if (a.get("p_18ymas") or 0) > 0]

    personas, condiciones, mediciones, consultas, citas, tratamientos, surtidos, consent = [], [], [], [], [], [], [], []

    for idx in range(n):
        a = rng.choices(con_adultos, weights=[x["p_18ymas"] for x in con_adultos], k=1)[0]
        lat, lon = punto_en(a["geom"], rng)
        sexo = "M" if rng.random() < 0.54 else "H"
        edad = min(max(int(rng.gauss(58, 11)), 30), 88)
        nac = hoy - timedelta(days=edad * 365 + rng.randint(0, 364))
        nombre = rng.choice(NOMBRES_M if sexo == "M" else NOMBRES_H)
        ap1, ap2 = rng.choice(APELLIDOS), rng.choice(APELLIDOS)
        # Los programas de detección llegan sobre todo a quien no tiene afiliación: se sobrerrepresenta x2 (tope 85%)
        p_sin = min(2 * (a.get("psinder") or 0) / max(a.get("pobtot") or 1, 1), 0.85)
        if rng.random() < p_sin:
            ss = None
        else:
            r = rng.random()
            ss = "IMSS" if r < 0.80 else ("ISSSTE" if r < 0.92 else "Otra")
        pool = por_inst.get(ss or "SSA") or por_inst["SSA"]
        unidad = min(pool, key=lambda u: haversine_km(lat, lon, u["lat"], u["lon"]))
        prog = rng.choices(prog_ids, weights=prog_pesos, k=1)[0]
        _, _, _, _, p_conf, p_asiste, h_aband, p_ctrl = prog_param[prog]
        r = rng.random()
        enf = ["diabetes"] if r < 0.35 else (["hipertension"] if r < 0.80 else ["diabetes", "hipertension"])
        deteccion = hoy - timedelta(days=rng.randint(3, 730))
        folio = f"PS{(idx * 7919 + 104729) % 1_000_000:06d}"
        a1 = _sin_acentos(ap1)
        curp = (a1[0] + next((c for c in a1[1:] if c in "AEIOU"), "X") + _sin_acentos(ap2)[0] + _sin_acentos(nombre)[0]
                + nac.strftime("%y%m%d") + sexo + "JC" + "XXX" + _b36(idx))
        rng.random()  # conserva la secuencia aleatoria
        codigo = CODIGO_DEMO
        p = Persona(folio, curp, nombre, f"{ap1} {ap2}", sexo, nac, a["cvegeo"], lat, lon, ss, prog,
                    unidad["clues"], deteccion, rng.random() < (0.25 if edad >= 70 else 0.08),
                    rng.choice([None, "Hija o hijo", "Pareja", "Vecina o vecino", "Promotora de salud"]),
                    f"33 {rng.randint(1000, 9999)} {rng.randint(1000, 9999)}", codigo, enf)
        personas.append(p)
        if rng.random() < 0.97:
            consent.append({"folio": folio, "aceptado": True,
                            "fecha": deteccion})

        # Tamizaje en el programa de origen (95% con medición; el resto sin medición -> gris)
        controlado = rng.random() < p_ctrl * 0.7
        if rng.random() < 0.95:
            mediciones.append({"folio": folio, "fecha": deteccion, "programa_id": prog,
                               **_medicion(rng, enf, controlado, False)})

        # Confirmación
        retraso = int(rng.choice([rng.randint(14, 30)] * 3 + [rng.randint(31, 80)]))
        fecha_conf = deteccion + timedelta(days=retraso)
        confirmado = rng.random() < p_conf and fecha_conf <= hoy
        clues = unidad["clues"]
        for e in enf:
            condiciones.append({"folio": folio, "enfermedad": e, "fecha_confirmacion": fecha_conf if confirmado else None})
        if not confirmado:
            cita_f = deteccion + timedelta(days=min(retraso, 21))
            citas.append({"folio": folio, "fecha": cita_f, "hora": time(rng.randint(8, 13), rng.choice([0, 30])),
                          "tipo": "confirmacion", "clues": clues,
                          "estado": "perdida" if cita_f < hoy else "programada"})
            # personas perdidas en la confirmación: algunas con visita domiciliaria programada
            if (hoy - deteccion).days > 30 and rng.random() < 0.35:
                citas.append({"folio": folio, "fecha": hoy + timedelta(days=rng.randint(0, 6)),
                              "hora": time(rng.randint(9, 13), 0), "tipo": "visita", "clues": clues,
                              "estado": "programada"})
            continue

        citas.append({"folio": folio, "fecha": fecha_conf, "hora": time(rng.randint(8, 13), rng.choice([0, 30])),
                      "tipo": "confirmacion", "clues": clues, "estado": "atendida"})
        consultas.append({"folio": folio, "fecha": fecha_conf, "tipo": "confirmacion", "clues": clues})
        meds = ([rng.choice(MED_DM)] if "diabetes" in enf else []) + ([rng.choice(MED_HTA)] if "hipertension" in enf else [])
        if rng.random() < 0.95:
            for m in meds:
                tratamientos.append({"folio": folio, "fecha_inicio": fecha_conf, "medicamento": m,
                                     "indicacion": "1 tableta cada 12 horas" if "Metformina" in m else "1 tableta al día"})
        controlado = rng.random() < p_ctrl * 0.6
        mediciones.append({"folio": folio, "fecha": fecha_conf, "programa_id": "centros_rxii",
                           **_medicion(rng, enf, controlado, "diabetes" in enf)})
        for m in meds:
            rng.random()  # conserva la secuencia de las personas
            surtidos.append({"folio": folio, "fecha": fecha_conf, "medicamento": m, "dias": 30,
                             "completo": abasto.completo(clues, m, fecha_conf)})

        # Seguimiento mes a mes
        actual = fecha_conf
        ultima_hba1c = fecha_conf
        racha_asist = 0
        abandono = False
        while True:
            intervalo = 90 if controlado else 30
            proxima = actual + timedelta(days=intervalo + rng.randint(-3, 6))
            if proxima > hoy:
                if not abandono:
                    if rng.random() < 0.18:  # parte de las citas futuras ya quedó vencida sin reprogramar
                        break
                    futura = max(proxima, hoy)
                    if futura <= hoy + timedelta(days=21) and rng.random() < 0.35:
                        futura = hoy  # agenda del día de la demostración
                    if futura <= hoy + timedelta(days=14) or rng.random() < 0.5:
                        citas.append({"folio": folio, "fecha": futura, "hora": time(rng.randint(8, 13), rng.choice([0, 30])),
                                      "tipo": "control", "clues": clues, "estado": "programada"})
                break
            if rng.random() < h_aband * (intervalo / 30):
                abandono = True
                citas.append({"folio": folio, "fecha": proxima, "hora": time(9, 0), "tipo": "control",
                              "clues": clues, "estado": "perdida"})
                if (hoy - proxima).days > 60 and rng.random() < 0.3:
                    citas.append({"folio": folio, "fecha": hoy + timedelta(days=rng.randint(0, 6)),
                                  "hora": time(rng.randint(9, 13), 0), "tipo": "visita", "clues": clues,
                                  "estado": "programada"})
                break
            if rng.random() < p_asiste:
                racha_asist += 1
                citas.append({"folio": folio, "fecha": proxima, "hora": time(rng.randint(8, 13), rng.choice([0, 30])),
                              "tipo": "control", "clues": clues, "estado": "atendida"})
                consultas.append({"folio": folio, "fecha": proxima, "tipo": "control", "clues": clues})
                # Cadena de dos estados calibrada para ~40-55% en control (Basto-Abreu 2024; Campos-Nonato 2025)
                mejora = min(p_ctrl * CTRL_ENTRA + CTRL_RACHA * racha_asist, CTRL_TOPE)
                controlado = rng.random() < (mejora if not controlado else CTRL_PERMANECE + p_ctrl * 0.2)
                con_hba1c = "diabetes" in enf and (proxima - ultima_hba1c).days >= 150 and rng.random() < 0.6
                if con_hba1c:
                    ultima_hba1c = proxima
                otro = rng.random() < 0.15
                mediciones.append({"folio": folio, "fecha": proxima,
                                   "programa_id": rng.choice(["ferias", "caravanas", "medicos_hogar"]) if otro else "centros_rxii",
                                   **_medicion(rng, enf, controlado, con_hba1c)})
                for m in meds:
                    surtidos.append({"folio": folio, "fecha": proxima, "medicamento": m,
                                     "dias": 90 if controlado else 30,
                                     "completo": (rng.random(), abasto.completo(clues, m, proxima))[1]})
                actual = proxima
            else:
                racha_asist = 0
                citas.append({"folio": folio, "fecha": proxima, "hora": time(9, 0), "tipo": "control",
                              "clues": clues, "estado": "perdida"})
                actual = proxima - timedelta(days=intervalo - 14)  # se reprograma a las dos semanas

    return {
        "programas": [{"id": p[0], "nombre": p[1], "ambito": p[2]} for p in PROGRAMAS],
        "unidades": unidades, "ferias": ferias, "personas": personas, "condiciones": condiciones,
        "mediciones": mediciones, "consultas": consultas, "citas": citas, "tratamientos": tratamientos,
        "surtidos": surtidos, "consentimientos": consent,
    }
