# MARSEL CURRENT STATE — 2026-08-15

## Verified live state
- Repository: `atalanrafael-jpg/Ro-app`.
- Hardening changes are isolated on a Codex branch; production `main` is not modified by this step.
- Latest verified RO App read-only audit evidence: API v2 access succeeded with zero access failures and zero hard issues.
- Latest verified entity counts: Products 1,721; Services 727; Orders 4,389; total 6,837.
- `ROAPP_API_KEY` exists in GitHub Actions and was used successfully by the latest live audit. The secret value must never be exposed.
- Production write requests remain disabled.

## Current unresolved items
1. Complete API/entity coverage is not established; seven entities remain unverified/blocked by the current canonical audit.
2. Eleven product-code collision groups require review. They are not deletion candidates without identity/business verification.
3. A complete production backup/restore test is not yet proven.
4. Gmail OAuth implementation exists in the repository, but live authorization and mailbox access are not verified.
5. Official RO App MCP availability is documented, but direct authorization in the current ChatGPT environment is not verified.
6. Historical subscription-expired 403 evidence is superseded by current successful live API evidence and must not be treated as an active blocker.

## Scope separation
Business requirements may include production, sales, repair, stock, metal, stones, and cost accounting. Production configuration must be reported separately from historical/project requirements and must never be inferred from them.

## Operating rule
Use `docs/MARSEL-CONTROL-PROTOCOL.md` for every subsequent task. Each task must finish with fresh verification before the next task begins.
