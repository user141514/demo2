# demo2 Architecture

## Goals

This project is now organized around a simple layered structure so future work can evolve without pushing more logic into route handlers or one-off helpers.

The refactor keeps the existing runtime behavior and API paths, while introducing clearer boundaries between:

- HTTP entry points
- application services
- shared runtime/core utilities
- persistence
- scoring engines and adapters

## Current Structure

```text
scoring_app/
  app_factory.py          # application assembly
  blueprints/             # HTTP routes grouped by domain
  core/                   # shared runtime and transport helpers
  services/               # business/application logic
  repository.py           # persistence access
  scoring.py              # scoring engine orchestration
  live_scoring.py         # external model adapter
  rules.py                # scoring rules and metadata
  pdf_extract.py          # PDF text extraction
  markdown_export.py      # export formatting
  utils.py                # low-level utilities
```

## Layer Responsibilities

### 1. `app_factory.py`

Only responsible for composing the application:

- create `Flask` app
- load config
- bootstrap storage/database
- register request hooks
- register blueprints

No business logic should be added here.

### 2. `blueprints/`

Route handlers should stay thin.

They are responsible for:

- mapping HTTP requests to service calls
- reading request body / query / form data
- translating service errors to HTTP responses
- returning JSON or download responses

They should not contain:

- scoring rules
- password hashing logic
- email delivery logic
- direct database SQL
- complex validation branches

### 3. `services/`

This is the main application layer.

- `auth_service.py`: registration, login, password reset, session creation
- `mail_service.py`: password reset delivery strategy
- `score_service.py`: score submission flow, history/detail/export orchestration

New business workflows should be added here first, then exposed through blueprints.

### 4. `core/`

Shared runtime helpers used across domains:

- app configuration
- bootstrap/init
- auth session context
- JSON / file response helpers
- shared error types

If logic is generic and not domain-specific, it belongs here instead of `services/`.

### 5. `repository.py`

Persistence boundary for SQLite access.

Rules:

- keep raw SQL here
- keep return shapes stable and predictable
- do not call Flask request globals from repository code
- do not put HTTP response logic here

If storage grows more complex later, this file can be split by aggregate (`users`, `sessions`, `scores`) without changing upper layers.

## Refactoring Rules Going Forward

### Add a new API

1. Add or extend a service function.
2. Add route wiring in the relevant blueprint.
3. Add tests against the route contract.
4. Only update template/front-end after the service contract is stable.

### Add a new storage field

1. Update schema bootstrap in `repository.py`.
2. Update repository read/write functions.
3. Update service-level data mapping.
4. Add regression tests for old/new records.

### Add a new scoring mode or provider

1. Keep provider-specific code behind `live_scoring.py` or a dedicated adapter module.
2. Keep `scoring.py` as the orchestration layer that chooses between strategies.
3. Avoid leaking provider response formats into route handlers or front-end code.

## Known Remaining Coupling

- `static/app.js` is still a single front-end runtime file. It is behaviorally stable, but it remains the next large candidate for modularization.
- `repository.py` still groups all SQL in one module. The boundary is clean enough now, but eventually it should split into domain-specific repositories if features continue to grow.

## Recommended Next Steps

- split `static/app.js` into `auth`, `history`, `score-submit`, `render`, and `http` modules
- add service-level tests around score submission validation and export behavior
- introduce typed request/response DTOs for service boundaries if the API expands
- centralize user-facing messages if copy complexity continues to grow
