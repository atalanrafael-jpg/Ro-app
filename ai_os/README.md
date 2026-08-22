# RAFAEL AI OS Runtime Foundation

This package defines the execution contract for the universal RAFAEL AI OS control plane.

## Lifecycle

`INBOX -> PLAN -> ROUTE -> EXECUTE -> QA -> VERIFY -> EVIDENCE -> UPDATE -> NEXT`

A task cannot become `DONE` without evidence. Failed verification requires:

`STOP -> CORRECT -> REVERIFY`

## Safety

- Production mutations remain disabled by default.
- Credentials are referenced by environment variable names; secrets are never stored here.
- External model/provider integrations are adapters, not assumptions.
- Autonomous execution must remain behind explicit permission/approval gates.
- Every execution should emit a machine-readable result and evidence reference.

## Language routing

- TypeScript: web, app, API, integrations
- Python: automation, AI, data
- SQL: data and database operations
- Shell: CI/CD and infrastructure
- Rust/Go: only when a measured technical requirement justifies them
