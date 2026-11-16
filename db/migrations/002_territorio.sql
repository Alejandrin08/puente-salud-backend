-- 002 · Territorio: datos públicos y agregados (sin personas)

CREATE TABLE IF NOT EXISTS territorio.ageb (
  cvegeo          varchar(13) PRIMARY KEY,
  cve_loc         varchar(4)  NOT NULL,
  cve_ageb        varchar(4)  NOT NULL,
  nom_loc         text,
  pobtot          integer,
  p_18ymas        integer,
  p_60ymas        integer,
  psinder         integer,
  pder_ss         integer,
  pcon_disc       integer,
  psinder_18_est  integer,      -- estimación proporcional (no existe en el Censo)
  pct_sinder      numeric(5,1),
  rezago          text NOT NULL DEFAULT 'Sin dato',
  geom            geometry(MultiPolygon, 4326) NOT NULL,
  centro_lat      double precision,
  centro_lon      double precision
);
CREATE INDEX IF NOT EXISTS ageb_geom_idx ON territorio.ageb USING gist (geom);

CREATE TABLE IF NOT EXISTS territorio.unidad (
  clues              varchar(11) PRIMARY KEY,
  nombre             text NOT NULL,
  institucion        text NOT NULL,
  tipo               text,
  tipologia          text,
  localidad          text,
  estatus            text,
  publica            boolean NOT NULL,
  urgencias          boolean NOT NULL DEFAULT false,
  asigna_folios      boolean NOT NULL DEFAULT false,
  -- Ubicación: CLUES no trae coordenadas; se asigna a una AGEB con semilla fija
  cvegeo             varchar(13) REFERENCES territorio.ageb(cvegeo),
  lat                double precision,
  lon                double precision,
  ubicacion_simulada boolean NOT NULL DEFAULT true,
  -- Horarios y servicios: simulados
  horario            text,
  servicios          text[] NOT NULL DEFAULT '{}',
  telefono           text,
  datos_simulados    boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS territorio.feria (
  id          serial PRIMARY KEY,
  nombre      text NOT NULL,
  programa    text NOT NULL,
  fecha       date NOT NULL,
  horario     text NOT NULL,
  lugar       text NOT NULL,
  cvegeo      varchar(13) REFERENCES territorio.ageb(cvegeo),
  lat         double precision NOT NULL,
  lon         double precision NOT NULL,
  servicios   text[] NOT NULL DEFAULT '{}',
  simulated   boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS territorio.mortalidad (
  anio           integer NOT NULL,
  causa          text    NOT NULL CHECK (causa IN ('diabetes','hipertension','total')),
  sexo           text    NOT NULL CHECK (sexo IN ('total','hombre','mujer')),
  defunciones    integer NOT NULL,
  poblacion_ref  integer NOT NULL,
  tasa_100k      numeric(6,1),
  PRIMARY KEY (anio, causa, sexo)
);
