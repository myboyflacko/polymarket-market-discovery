.DEFAULT_GOAL := help

ARGS ?=
CLI_GOAL_ARGS := $(filter-out cli doppler-cli,$(MAKECMDGOALS))
CLI_RUN_ARGS := $(if $(ARGS),$(ARGS),$(CLI_GOAL_ARGS))
COMPOSE := docker compose
DOPPLER_COMPOSE := doppler run -- docker compose

.PHONY: help postgres up down cli logs ps build config \
	doppler-postgres doppler-up doppler-down doppler-cli doppler-logs \
	doppler-ps doppler-build doppler-config

help:
	@awk 'BEGIN {FS = ":.*## "; print "Targets:"} /^[a-zA-Z_-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

postgres: ## Start only the postgres service.
	$(COMPOSE) up -d postgres

up: ## Start all compose services in the background.
	$(COMPOSE) up -d

down: ## Stop and remove compose services.
	$(COMPOSE) down

cli: ## Run the CLI service. Usage: make cli ARGS="--help"
	$(COMPOSE) run --rm cli $(CLI_RUN_ARGS)

logs: ## Follow compose logs.
	$(COMPOSE) logs -f

ps: ## Show compose service status.
	$(COMPOSE) ps

build: ## Build compose images.
	$(COMPOSE) build

config: ## Print the resolved compose config.
	$(COMPOSE) config

doppler-postgres: ## Start only the postgres service with Doppler.
	$(DOPPLER_COMPOSE) up -d postgres

doppler-up: ## Start all compose services with Doppler.
	$(DOPPLER_COMPOSE) up -d

doppler-down: ## Stop and remove compose services with Doppler.
	$(DOPPLER_COMPOSE) down

doppler-cli: ## Run the CLI service with Doppler. Usage: make doppler-cli ARGS="--help"
	$(DOPPLER_COMPOSE) run --rm cli $(CLI_RUN_ARGS)

doppler-logs: ## Follow compose logs with Doppler.
	$(DOPPLER_COMPOSE) logs -f

doppler-ps: ## Show compose service status with Doppler.
	$(DOPPLER_COMPOSE) ps

doppler-build: ## Build compose images with Doppler.
	$(DOPPLER_COMPOSE) build

doppler-config: ## Print the resolved compose config with Doppler.
	$(DOPPLER_COMPOSE) config

%:
	@:
