# Project Tasks

> Last updated: 2026-05-26 23:31 +08:00
> Purpose: handoff markers for the Claude -> Codex optimization work. Keep new follow-up items here unless they belong in a more specific roadmap document.

## Current Handoff Status

- [x] [high] [frontend] Fixed `frontend/src/views/InvestmentPlan.vue` build-breaking attribute quotes. (completed: 2026-05-26)
- [x] [high] [backend] Registered new V3/P1 models in `backend/models/__init__.py` and Alembic env. (completed: 2026-05-26)
- [x] [critical] [migrations] Made early Alembic migrations idempotent with the app's `create_all()`-before-upgrade startup flow. (completed: 2026-05-26)
- [x] [high] [packaging] Added new V3/P1 modules to `scripts/fund_ai.spec` hidden imports. (completed: 2026-05-26)
- [x] [high] [packaging] Rebuilt `dist/基金智能分析.exe`; output size 424,430,523 bytes, timestamp 2026-05-26 23:25:48. (completed: 2026-05-26)
- [x] [high] [tests] Fixed auth middleware test isolation by binding middleware `SessionLocal` to the in-memory test DB. (completed: 2026-05-26)

## High

- [ ] [high] [runtime] Run a GUI smoke test from `dist/基金智能分析.exe`: startup, login/setup, Dashboard, Holdings, Risk Exposure, Investment Plans, Settings user profile. (added: 2026-05-26)
- [ ] [high] [runtime] Validate live DB upgrade on a copied real database before broad use; Codex only validated a temporary fresh SQLite DB. (added: 2026-05-26)
- [ ] [high] [data] Create one real monthly investment plan and verify 90-day execution materialization plus `/api/investment-plans/{id}/reconcile`. (added: 2026-05-26)
- [ ] [high] [data] Run live AKShare sync for fund managers and top holdings, then verify manager alerts and overlap heatmap data against known funds. (added: 2026-05-26)

## Medium

- [ ] [medium] [tests] Add endpoint-level tests for new V3 APIs: fund manager, investment plan, asset allocation, and user profile. (added: 2026-05-26)
- [ ] [medium] [frontend] Investigate Vite chunk warnings for `element-plus` and `echarts` if desktop startup or memory becomes a problem. (added: 2026-05-26)
- [ ] [medium] [repo] Decide whether generated `build/fund_ai/*` artifacts should remain tracked, be ignored, or be excluded from review diffs. (added: 2026-05-26)

## Verification Snapshot

- `python -m pytest backend/tests/ -v` -> 54 passed.
- Publish worktree `python -m pytest backend/tests/ -v` -> 54 passed.
- `npm run build` -> passed; only existing Vite chunk-size warnings.
- Publish worktree `npm run build` -> passed; same Vite chunk-size warnings.
- Temporary SQLite `init_db()` -> Alembic upgraded to `f5b3a64e29d8`.
- `pwsh -File scripts/build_desktop.ps1` -> succeeded and rebuilt `dist/基金智能分析.exe`.
