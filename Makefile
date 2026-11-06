# Everything runs inside Docker. The host needs only Docker and make.
# Targets for later milestones (report, zip) are added when the code behind
# them exists.

COMPOSE := docker compose
EVAL := $(COMPOSE) run --rm eval
RUN_ARGS = $(if $(YES),--yes) $(if $(RUN),--run-id $(RUN)) $(if $(FROM),--estimate-from $(FROM)) $(if $(JOBS),--jobs $(JOBS))

.PHONY: help up down build test validate models dry-run pilot run psql shell

help:
	@echo "make up     start Postgres 16.15 and wait until healthy"
	@echo "make down   stop and remove containers (data is in RAM, so it is gone)"
	@echo "make build  rebuild the eval image (after editing requirements.txt)"
	@echo "make test   run pytest inside the eval container"
	@echo "make validate [TASK=t01_flash_sale]  references must pass, wrong variants must fail"
	@echo "make models   live OpenRouter IDs and prices for config/models.yaml (free, no key)"
	@echo "make dry-run  whole pipeline with a mock model that returns the references (\$$0)"
	@echo "make pilot    1 trial per model and task; prints the estimate; add YES=1 to start"
	@echo "make run      5 trials; options: YES=1 RUN=<id to resume> FROM=<pilot id> JOBS=<n>"
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

validate: up
	$(EVAL) python -m lastseat.validate $(if $(TASK),--task $(TASK))

models:
	$(EVAL) python -m lastseat.runner models

dry-run: up
	$(EVAL) python -m lastseat.runner run --trials 1 --dry-run $(RUN_ARGS)

pilot: up
	$(EVAL) python -m lastseat.runner run --trials 1 $(RUN_ARGS)

run: up
	$(EVAL) python -m lastseat.runner run --trials 5 $(RUN_ARGS)

psql: up
	$(COMPOSE) exec db psql -U lastseat -d lastseat

shell: up
	$(EVAL) bash
