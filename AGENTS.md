# AGENTS.md

## Project overview

This repo is a multi-agent trip planning system built around a FastAPI backend, a CrewAI worker, and a Shiny frontend. The app accepts a city/date range, sends the job to RabbitMQ, and the worker uses Ollama-backed agents to fetch weather and attraction data before writing results back to RustFS and storing task state in Postgres.

See [README.md](README.md) for the feature overview and [justfile](justfile) for the repo formatting/lint commands.

## Key directories

- [backend/](backend/): FastAPI API, environment config, and API tests.
- [worker/](worker/): RabbitMQ consumer, CrewAI orchestration, and task execution logic.
- [frontend/](frontend/): Shiny UI and config for the browser experience.
- [tests/](tests/): end-to-end integration tests using Docker containers.
- [ollama/](ollama/): local Ollama image setup.

## Useful conventions

- Prefer small, local changes that match the existing module structure instead of introducing new app frameworks.
- Keep configuration values centralized in the appconfig modules under each service rather than scattering environment usage.
- The backend and worker both rely on environment variables loaded from Docker Compose or local `.env` files; any config change usually needs to be mirrored in the compose files and service code.
- The worker's orchestration is defined in [worker/recieve.py](worker/recieve.py); the API entrypoints live in [backend/app.py](backend/app.py). Follow those service boundaries when adding features.
- Docker is the primary integration environment; many repo-level checks are effectively container or service-based.

## Development workflow

- Format and lint from the repo root with:
  - `just format`
  - `just lint`
- Python tests live in [backend/tests/test_api.py](backend/tests/test_api.py) and [tests/test_e2e.py](tests/test_e2e.py); use pytest for targeted validation when working on a specific service.
- For runtime behavior, prefer the existing Docker Compose setup and service wiring instead of ad hoc local scripts.

## Architectural boundaries

- [backend/app.py](backend/app.py): accepts trip requests, validates dates/city, writes task rows to Postgres, and publishes tasks to RabbitMQ.
- [worker/recieve.py](worker/recieve.py): consumes queued messages, updates task state, creates the CrewAI crew, writes output to RustFS, and persists worker updates.
- [frontend/app.py](frontend/app.py): provides the user-facing Shiny interface and calls the backend API.

## When editing this repo

- Keep API contracts stable unless the related tests are updated in the same change.
- Match the existing naming and model conventions for task IDs, config keys, and queue names.
- For Docker or service changes, verify the corresponding compose files and environment variable mappings before finishing the patch.
- Do not add broad refactors or new abstractions unless they are required to solve the specific issue at hand.

## Practical reminders

- The current repo expects local model access via Ollama and service dependencies such as Postgres, RabbitMQ, and RustFS.
- The task lifecycle is driven by task state transitions (`submitted`, `running`, `done`) in the database and by result retrieval from RustFS.
- If a change affects the API contract or task flow, update the relevant tests and the service configuration together.
