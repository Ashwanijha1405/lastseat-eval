# Everything runs inside Docker. The host needs only Docker and make.
# Targets for later milestones (validate, pilot, run, report, zip) are added
# when the code behind them exists.

COMPOSE := docker compose
EVAL := $(COMPOSE) run --rm eval

.PHONY: help up down build test psql shell

help:
	@echo "make up     start Postgres 16.15 and wait until healthy"
	@echo "make down   stop and remove containers (data is in RAM, so it is gone)"
	@echo "make build  rebuild the eval image (after editing requirements.txt)"
	@echo "make test   run pytest inside the eval container"
	@echo "make psql   open psql on the db container"
	@echo "make shell  bash inside the eval container"

up:
	$(COMPOSE) up -d --wait db

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build eval

test: up
	$(EVAL) python -m pytest

psql: up
	$(COMPOSE) exec db psql -U lastseat -d lastseat

shell: up
	$(EVAL) bash
