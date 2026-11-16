# Puente Salud · comandos del backend
PY ?= .venv/bin/python

.PHONY: venv datos test test-db test-down up down reset

venv:            ## entorno de desarrollo y pruebas
	python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

datos:           ## regenera db/seeds/real desde data/raw (requiere scripts/requirements-datos.txt)
	python3.12 -m venv .venv-datos && .venv-datos/bin/pip install -q -r scripts/requirements-datos.txt
	.venv-datos/bin/python scripts/build_territorio.py

test-db:         ## base efímera para pruebas de integración
	docker compose -f docker-compose.test.yml up -d --wait

test: test-db    ## unitarias + integración de los tres servicios
	cd services/territorio && ../../$(PY) -m pytest -q
	cd services/seguimiento && ../../$(PY) -m pytest -q
	cd services/gateway && ../../$(PY) -m pytest -q

test-down:
	docker compose -f docker-compose.test.yml down -v

up:              ## levanta todo (base, servicios, frontends)
	docker compose up --build -d

down:
	docker compose down

reset:           ## borra la base local y vuelve a cargar los datos
	docker compose down -v && docker compose up --build -d
