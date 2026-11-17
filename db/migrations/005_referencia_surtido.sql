-- 005 · Referencia real de surtido de recetas (ISSSTE, datos.gob.mx, CC-BY 4.0)
CREATE TABLE IF NOT EXISTS territorio.referencia_surtido (
  periodo        varchar(7) NOT NULL,          -- AAAA-MM
  ambito         text NOT NULL CHECK (ambito IN ('nacional','estatal','unidad')),
  nombre         text NOT NULL,
  clues          varchar(11),
  unidades       integer NOT NULL,
  recetas        integer NOT NULL,
  completas_pct  numeric(5,1) NOT NULL,
  parciales_pct  numeric(5,1) NOT NULL,
  negadas_pct    numeric(5,1) NOT NULL,
  PRIMARY KEY (periodo, ambito, nombre)
);
