.PHONY: help up down restart status logs logs-api logs-frontend test clean

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Stop other projects' containers, then start this one
	@docker ps -q --filter label=com.docker.compose.project | xargs -r docker stop
	docker compose up -d
	@echo "→ API ready at http://localhost:8000/docs"
	@echo "→ Frontend ready at http://localhost:5173"

build:   ## rebuild images
	@docker ps -q --filter label=com.docker.compose.project | xargs -r docker stop
	docker compose up -d --build
	@echo "→ API ready at http://localhost:8000/docs"
	@echo "→ Frontend ready at http://localhost:5173"

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

logs-frontend: ## View live logs from the frontend container
	docker compose logs -f frontend

test: ## Run backend unit/integration tests
	cd backend && poetry run pytest

clean: ## Stop containers and remove volumes
	docker compose down -v

shell:
	docker compose exec api sh