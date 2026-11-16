<p align="center">
  <img src="design/brand/logo.svg" alt="Logo de Puente Salud" width="96" />
</p>

# Puente Salud

*"De cuántas personas se atendieron a cuántas llegaron al control."*

## Visión

Puente Salud apoya la continuidad de la atención de las personas con diabetes e hipertensión detectadas por los programas de salud de San Pedro Tlaquepaque, Jalisco. Ferias, Caravanas, Médicas y Médicos en tu Hogar, Salud Casa por Casa y los centros de salud operan con registros separados. Puente Salud los conecta sin reemplazarlos: un **Folio Único de Seguimiento** reconstruye el recorrido de cada persona, un **semáforo** explicable ordena a quién buscar primero y un **tablero de impacto** mide cuántas personas lleva cada programa al control.

## Objetivos del proyecto

1. Analizar, con una revisión multivocal, en qué etapas se pierden las personas y qué seguimiento funciona.
2. Integrar cinco conjuntos de datos oficiales (INEGI defunciones, Censo 2020, Marco Geoestadístico, CONEVAL y CLUES) para identificar las zonas con mayor necesidad y menor acceso.
3. Definir los datos mínimos del recorrido y las reglas del semáforo con base en la NOM-015-SSA2-2010 y la NOM-030-SSA2-2009.
4. Desarrollar un prototipo funcional con el recorrido, el semáforo y el tablero de impacto por programa.

## Sustento metodológico

- 📘 [`Investigación y revisión multivocal`](docs/investigacion.md): problema, evidencia, reglas del semáforo (Anexo D) y diseño (Anexo E).
- 🧭 [`Datos y fuentes`](docs/datos.md): perfil de los datasets, qué es real y qué es simulado, calibración y limitaciones.
- ✅ [`Requisitos y trazabilidad`](docs/requisitos-mvp.md): cada elemento del documento, con su pantalla, endpoint, prueba y estado.
- 🏗️ [`Decisiones de arquitectura`](docs/adr/): por qué está construido así.
- 🔗 [`Mapeo a HL7 FHIR R4`](docs/fhir-mapeo.md) · 🚀 [`Despliegue`](docs/despliegue.md) · 🎨 [`Paleta y contraste`](design/brand/paleta.md)

## Arquitectura

```
 web-ciudadania (Vite, :5173)      web-institucion (Vite, :5174)
             \                         /
              \   token en Authorization
               v                     v
            gateway (FastAPI, :8000)  ← único servicio público: login, roles, CORS
              /                    \      red privada + INTERNAL_TOKEN
   seguimiento (:8001)        territorio (:8002)
   folio, semáforo (Anexo D),  AGEB + Censo + CONEVAL, CLUES,
   indicadores (E.4), bitácora ferias, mortalidad INEGI
              \                    /
         PostgreSQL 16 + PostGIS (esquemas seguimiento | territorio)
```
Cada servicio sigue `routers → services → repositories`. Sin IA en el MVP: el semáforo es por reglas y el modelo de riesgo de abandono queda como trabajo futuro (ver [ADR 0001](docs/adr/0001-arquitectura.md)).

## Acceder al proyecto

1. Clonar los tres repositorios **en la misma carpeta** (el `docker-compose.yml` construye los frontends con `../`):

```
git clone https://github.com/Alejandrin08/puente-salud-backend.git
git clone https://github.com/Alejandrin08/puente-salud-web-ciudadania.git
git clone https://github.com/Alejandrin08/puente-salud-web-institucion.git
```

2. Crear el archivo de variables de entorno (cambia las contraseñas y secretos):

```
cd puente-salud-backend
cp .env.example .env
```

3. (Opcional) Regenerar los datos reales. Los seeds ya vienen en `db/seeds/real/`; solo hace falta si quieres reconstruirlos desde las fuentes:

```
python scripts/fetch_data.py            # descarga lo automático; los manuales se explican en data/datasets.json
make datos                              # geopandas: data/raw -> db/seeds/real
```

4. Levantar todo (base, carga de datos, servicios y frontends):

```
docker compose up --build
```

5. Abrir en el navegador:

| Servicio | URL |
|----------|-----|
| Ciudadanía (persona) | http://localhost:5173 |
| Institución (personal de salud y autoridad) | http://localhost:5174 |
| API (gateway) | http://localhost:8000/docs |

### Cuentas de demostración

| Vista | Acceso |
|---|---|
| Persona | folio `PS081368` (paso 2), `PS000877` (paso 4, fuera de meta), `PS119662` (en control) o `PS077861` (sin consentimiento); código `246810` |
| Personal de salud | `enfermeria.tateposco` / `demo-salud` · `medicina.lasjuntas` / `demo-salud` |
| Autoridad | `autoridad.rxii` / `demo-autoridad` |

Para reiniciar los datos: `make reset` (borra el volumen y vuelve a cargar).

## Pruebas

```
make test                                 # backend: unitarias + integración (levanta una PostGIS efímera)
cd ../puente-salud-web-ciudadania && npm test && npm run test:e2e
cd ../puente-salud-web-institucion && npm test && npm run test:e2e
```
Las pruebas extremo a extremo (Playwright + axe) corren contra el sistema levantado con `docker compose up`. La primera vez: `npx playwright install chromium`. Las e2e escriben en la base local (un desacuerdo y una medición de prueba): antes de una demostración, ejecuta `make reset` para volver a los datos limpios.

Último resultado (16 nov 2026, desde cero): backend 86 (territorio 17, seguimiento 57, gateway 12); ciudadanía 13 unitarias y 8 e2e; institución 16 unitarias y 4 e2e. Todo en verde, sin violaciones de accesibilidad graves ni críticas.

## Datos

| Real | Simulado (rotulado en la interfaz) |
|---|---|
| Defunciones INEGI 2023–2025, Censo 2020 por AGEB, Marco Geoestadístico, rezago CONEVAL, catálogo CLUES 2024 | 1,000 personas, folios, CURP, citas, mediciones, tratamientos, surtido, programas, horarios, ferias y ubicación de unidades (CLUES no trae coordenadas) |

Los datasets pesados se declaran como enlaces en `data/datasets.json` y no se suben a git. Detalle y limitaciones: [docs/datos.md](docs/datos.md).

## Estructura del repositorio

```
services/
  gateway/        sesión, roles y proxy
  seguimiento/    folio, semáforo, indicadores, bitácora
  territorio/     AGEB, unidades, ferias, mortalidad
db/
  init/           usuario de aplicación y PostGIS
  migrations/     001–004 (idempotentes)
  seeds/real/     derivados pequeños de fuentes oficiales
  seeds/simulated/ generador con semilla fija
scripts/          fetch_data.py, build_territorio.py, seed.py
data/             datasets.json (enlaces), raw/ y processed/ (ignorados)
docs/  design/    investigación, datos, ADR, despliegue, marca
```

## Equipo

<!-- PENDIENTE DEL EQUIPO: nombres de los expositores y del asesor (Anexo A de docs/investigacion.md). -->
Pendiente de completar por el equipo.
