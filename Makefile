.PHONY: help up down restart status logs logs-api test clean

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Start all Docker containers in background
	docker compose up -d --build
	@echo "→ API ready at http://localhost:8000/docs"

down: ## Stop all Docker containers
	docker compose down

restart: ## Restart all Docker containers
	docker compose restart

status: ## Check status of running containers
	docker compose ps

logs: ## View live logs from all containers
	docker compose logs -f

logs-api: ## View live logs from the API container
	docker compose logs -f api

logs-postgres: ## View live logs from the postgres container
	docker compose logs -f postgres

test: ## Run backend unit/integration tests
	cd backend && poetry run pytest

clean: ## Stop containers and remove volumes
	docker compose down -v
