-- 004 · Permisos del usuario de la aplicación (sin DDL, sin superusuario).
-- El nombre del rol llega como variable de psql: -v app_user=...
GRANT USAGE ON SCHEMA territorio, seguimiento TO :"app_user";
GRANT SELECT ON ALL TABLES IN SCHEMA territorio TO :"app_user";
GRANT SELECT ON ALL TABLES IN SCHEMA seguimiento TO :"app_user";
GRANT INSERT, UPDATE ON seguimiento.medicion, seguimiento.consentimiento, seguimiento.desacuerdo,
                         seguimiento.bitacora, seguimiento.consulta, seguimiento.cita TO :"app_user";
GRANT USAGE ON ALL SEQUENCES IN SCHEMA seguimiento TO :"app_user";
