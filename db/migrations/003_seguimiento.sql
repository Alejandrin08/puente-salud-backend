-- 003 · Seguimiento: Folio Único de Seguimiento y recorrido (datos simulados en el MVP)
-- Cada tabla corresponde a un recurso HL7 FHIR R4 (indicado al lado)

CREATE TABLE IF NOT EXISTS seguimiento.programa (            -- Organization
  id        text PRIMARY KEY,
  nombre    text NOT NULL,
  ambito    text NOT NULL,                                    -- piloto municipal | estatal | otra institución
  simulated boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS seguimiento.parametros_programa (  -- Anexo D.2, configurable por programa
  programa_id                text PRIMARY KEY REFERENCES seguimiento.programa(id),
  dias_confirmacion          integer NOT NULL DEFAULT 30,
  dias_perdida_confirmacion  integer NOT NULL DEFAULT 90,
  dias_control_sin_control   integer NOT NULL DEFAULT 30,
  dias_control_con_control   integer NOT NULL DEFAULT 90,
  dias_vencida_grave         integer NOT NULL DEFAULT 30,
  meses_abandono             integer NOT NULL DEFAULT 12
);

CREATE TABLE IF NOT EXISTS seguimiento.ageb_ref (             -- copia mínima de territorio para el semáforo
  cvegeo  varchar(13) PRIMARY KEY,
  rezago      text NOT NULL,
  pct_sinder  numeric(5,1),
  lat         double precision,
  lon         double precision
);

CREATE TABLE IF NOT EXISTS seguimiento.unidad_ref (
  clues        varchar(11) PRIMARY KEY,
  nombre       text NOT NULL,
  institucion  text NOT NULL,
  lat          double precision,
  lon          double precision
);

CREATE TABLE IF NOT EXISTS seguimiento.persona (              -- Patient + EpisodeOfCare (folio)
  folio               varchar(12) PRIMARY KEY,               -- Folio Único de Seguimiento
  curp_simulada       varchar(18) UNIQUE NOT NULL,
  nombre              text NOT NULL,
  apellidos           text NOT NULL,
  sexo                char(1) NOT NULL CHECK (sexo IN ('H','M')),
  fecha_nacimiento    date NOT NULL,
  cvegeo              varchar(13) NOT NULL REFERENCES seguimiento.ageb_ref(cvegeo),
  domicilio_lat       double precision NOT NULL,
  domicilio_lon       double precision NOT NULL,
  seguridad_social    text,                                  -- Coverage: NULL = sin afiliación
  programa_origen     text NOT NULL REFERENCES seguimiento.programa(id),
  unidad_clues        varchar(11) NOT NULL REFERENCES seguimiento.unidad_ref(clues),
  fecha_deteccion     date NOT NULL,
  dependencia_social  boolean NOT NULL DEFAULT false,
  red_apoyo           text,
  telefono_simulado   text,
  codigo_hash         text NOT NULL,                         -- código de acceso de demostración (sha256)
  simulated           boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS persona_unidad_idx ON seguimiento.persona (unidad_clues);

CREATE TABLE IF NOT EXISTS seguimiento.condicion (            -- Condition
  id                  serial PRIMARY KEY,
  folio               varchar(12) NOT NULL REFERENCES seguimiento.persona(folio) ON DELETE CASCADE,
  enfermedad          text NOT NULL CHECK (enfermedad IN ('diabetes','hipertension')),
  fecha_confirmacion  date,
  UNIQUE (folio, enfermedad)
);

CREATE TABLE IF NOT EXISTS seguimiento.medicion (             -- Observation
  id            serial PRIMARY KEY,
  folio         varchar(12) NOT NULL REFERENCES seguimiento.persona(folio) ON DELETE CASCADE,
  fecha         date NOT NULL,
  pas           integer CHECK (pas BETWEEN 50 AND 300),
  pad           integer CHECK (pad BETWEEN 30 AND 200),
  glucosa       integer CHECK (glucosa BETWEEN 20 AND 700),
  hba1c         numeric(4,1) CHECK (hba1c BETWEEN 3 AND 20),
  programa_id   text REFERENCES seguimiento.programa(id),
  registrado_por text NOT NULL DEFAULT 'simulador',
  simulated     boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS medicion_folio_idx ON seguimiento.medicion (folio, fecha);

CREATE TABLE IF NOT EXISTS seguimiento.consulta (             -- Encounter
  id     serial PRIMARY KEY,
  folio  varchar(12) NOT NULL REFERENCES seguimiento.persona(folio) ON DELETE CASCADE,
  fecha  date NOT NULL,
  tipo   text NOT NULL CHECK (tipo IN ('confirmacion','primera','control','visita')),
  clues  varchar(11) REFERENCES seguimiento.unidad_ref(clues)
);
CREATE INDEX IF NOT EXISTS consulta_folio_idx ON seguimiento.consulta (folio, fecha);

CREATE TABLE IF NOT EXISTS seguimiento.cita (                 -- Appointment
  id      serial PRIMARY KEY,
  folio   varchar(12) NOT NULL REFERENCES seguimiento.persona(folio) ON DELETE CASCADE,
  fecha   date NOT NULL,
  hora    time,
  tipo    text NOT NULL CHECK (tipo IN ('confirmacion','control','visita')),
  estado  text NOT NULL CHECK (estado IN ('programada','atendida','perdida')),
  clues   varchar(11) REFERENCES seguimiento.unidad_ref(clues)
);
CREATE INDEX IF NOT EXISTS cita_folio_idx ON seguimiento.cita (folio, fecha);
CREATE INDEX IF NOT EXISTS cita_fecha_idx ON seguimiento.cita (fecha);

CREATE TABLE IF NOT EXISTS seguimiento.tratamiento (          -- MedicationRequest
  id            serial PRIMARY KEY,
  folio         varchar(12) NOT NULL REFERENCES seguimiento.persona(folio) ON DELETE CASCADE,
  fecha_inicio  date NOT NULL,
  medicamento   text NOT NULL,
  indicacion    text NOT NULL
);

CREATE TABLE IF NOT EXISTS seguimiento.surtido (              -- MedicationDispense
  id           serial PRIMARY KEY,
  folio        varchar(12) NOT NULL REFERENCES seguimiento.persona(folio) ON DELETE CASCADE,
  fecha        date NOT NULL,
  medicamento  text NOT NULL,
  dias         integer NOT NULL,
  completo     boolean NOT NULL
);

CREATE TABLE IF NOT EXISTS seguimiento.consentimiento (       -- Consent
  folio     varchar(12) PRIMARY KEY REFERENCES seguimiento.persona(folio) ON DELETE CASCADE,
  aceptado  boolean NOT NULL,
  fecha     timestamptz NOT NULL DEFAULT now(),
  alcance   text NOT NULL DEFAULT 'Compartir el conjunto mínimo de datos entre programas de salud para dar seguimiento'
);

CREATE TABLE IF NOT EXISTS seguimiento.desacuerdo (
  id               serial PRIMARY KEY,
  folio            varchar(12) NOT NULL REFERENCES seguimiento.persona(folio) ON DELETE CASCADE,
  fecha            timestamptz NOT NULL DEFAULT now(),
  usuario          text NOT NULL,
  nivel_sugerido   text NOT NULL,
  nivel_propuesto  text NOT NULL CHECK (nivel_propuesto IN ('verde','amarillo','rojo','gris')),
  motivo           text NOT NULL
);

CREATE TABLE IF NOT EXISTS seguimiento.bitacora (             -- AuditEvent
  id       bigserial PRIMARY KEY,
  fecha    timestamptz NOT NULL DEFAULT now(),
  usuario  text NOT NULL,
  rol      text NOT NULL,
  accion   text NOT NULL,
  folio    varchar(12),
  detalle  jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS bitacora_folio_idx ON seguimiento.bitacora (folio, fecha DESC);
