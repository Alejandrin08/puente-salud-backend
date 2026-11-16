#!/bin/sh
# Se ejecuta una sola vez al crear el volumen de PostgreSQL (docker-entrypoint-initdb.d).
# Crea PostGIS y el usuario de la aplicación con permisos limitados (no superusuario).
set -e
: "${APP_DB_USER:?Define APP_DB_USER}"
: "${APP_DB_PASSWORD:?Define APP_DB_PASSWORD}"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE EXTENSION IF NOT EXISTS postgis;
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${APP_DB_USER}') THEN
    CREATE ROLE ${APP_DB_USER} LOGIN PASSWORD '${APP_DB_PASSWORD}' NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
END \$\$;
GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${APP_DB_USER};
SQL
