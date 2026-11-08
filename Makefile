# Everything runs inside Docker. The host needs only Docker and make.

COMPOSE := docker compose
EVAL := $(COMPOSE) run --rm eval
RUN_ARGS = $(if $(CONFIG),--config $(CONFIG)) $(if $(YES),--yes) $(if $(NEW),--new) $(if $(RUN),--run-id $(RUN)) $(if $(FROM),--estimate-from $(FROM)) $(if $(JOBS),--jobs $(JOBS))

.PHONY: help up down build test validate models free-models quota summary dry-run pilot run psql shell zip

help:
	@echo "make up     start Postgres 16.15 and wait until healthy"
	@echo "make down   stop and remove containers (data is in RAM, so it is gone)"
	@echo "make build  rebuild the eval image (after editing requirements.txt)"
	@echo "make test   run pytest inside the eval container"
	@echo "make validate [TASK=t01_flash_sale]  references must pass, wrong variants must fail"
	@echo "make models [CONFIG=paid]  live IDs and prices of a model set (default CONFIG=free; no key)"
	@echo "make free-models  every zero-priced :free model in the live catalog"
	@echo "make quota   free-model requests used / left today (local counter + OpenRouter's)"
	@echo "make summary RUN=<run_id> [REGRADE=1]   write results/<run_id>/summary.md (REGRADE: re-grade from disk, no API)"
	@echo "make dry-run  whole pipeline with a mock model that returns the references (\$$0)"
	@echo "make pilot    1 trial per model and task; prints the estimate; add YES=1 to start"
	@echo "make run      5 trials (TRIALS=n to change); options: CONFIG=free|paid (default free) YES=1 NEW=1 RUN=<id> FROM=<pilot id> JOBS=<n>"
	@echo "             resumes only an unfinished run with the same tasks, models, trials; else refuses: RUN=<id> or NEW=1"
	@echo "make psql   open psql on the db container"
	@echo "make shell  bash inside the eval container"
	@echo "make zip    lastseat-eval.zip from HEAD (git archive), then checked: < 50 MB, README at root, no .env/keys/caches/videos"

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
	$(EVAL) python -m lastseat.runner models $(if $(CONFIG),--config $(CONFIG))

free-models:
	$(EVAL) python -m lastseat.runner models --list-free

quota:
	$(EVAL) python -m lastseat.runner quota $(if $(CONFIG),--config $(CONFIG))

summary: up
	$(EVAL) python -m lastseat.summary results/$(RUN) $(if $(REGRADE),--regrade)

dry-run: up
	$(EVAL) python -m lastseat.runner run --trials 1 --dry-run $(RUN_ARGS)

pilot: up
	$(EVAL) python -m lastseat.runner run --trials 1 $(RUN_ARGS)

run: up
	$(EVAL) python -m lastseat.runner run --trials $(or $(TRIALS),5) $(RUN_ARGS)

psql: up
	$(COMPOSE) exec db psql -U lastseat -d lastseat

shell: up
	$(EVAL) bash

# The zip is exactly the committed tree, so a dirty working tree is refused.
zip:
	$(if $(strip $(shell git status --porcelain)),$(error working tree has uncommitted changes; commit first, the zip is built from HEAD))
	git archive --format=zip -o lastseat-eval.zip HEAD
	$(EVAL) python -m lastseat.package lastseat-eval.zip
