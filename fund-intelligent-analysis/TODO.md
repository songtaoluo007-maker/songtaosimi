# Project Tasks

> Last updated: 2026-05-27 13:58 +08:00
> Purpose: handoff markers for the Claude -> Codex optimization work. Keep new follow-up items here unless they belong in a more specific roadmap document.

## Current Handoff Status

- [x] [high] [frontend] Fixed `frontend/src/views/InvestmentPlan.vue` build-breaking attribute quotes. (completed: 2026-05-26)
- [x] [high] [backend] Registered new V3/P1 models in `backend/models/__init__.py` and Alembic env. (completed: 2026-05-26)
- [x] [critical] [migrations] Made early Alembic migrations idempotent with the app's `create_all()`-before-upgrade startup flow. (completed: 2026-05-26)
- [x] [high] [packaging] Added new V3/P1 modules to `scripts/fund_ai.spec` hidden imports. (completed: 2026-05-26)
- [x] [high] [packaging] Rebuilt `dist/基金智能分析.exe`; output size 424,430,523 bytes, timestamp 2026-05-26 23:25:48. (completed: 2026-05-26)
- [x] [high] [tests] Fixed auth middleware test isolation by binding middleware `SessionLocal` to the in-memory test DB. (completed: 2026-05-26)
- [x] [high] [frontend] Integrated P2.2 behavior-bias radar and decision-review table into `AdviceReview.vue`. (completed: 2026-05-27)
- [x] [medium] [backend] Reduced decision-review N+1 queries by batching AI advice and holding lookups. (completed: 2026-05-27)
- [x] [medium] [packaging] Added P2 fee/review modules to PyInstaller hidden imports. (completed: 2026-05-27)
- [x] [high] [ocr] Added P2.3 OCR snapshot diff preview, inferred trade creation, sync status reminder, and frontend confirmation flow. (completed: 2026-05-27)
- [x] [high] [toolbox] Stabilized P2.4 老基民工具箱: route/sidebar entry, package hidden imports, milestone fee-drop math, holiday weekend bridge, and service tests. (completed: 2026-05-27)

## High

- [ ] [high] [runtime] Run a GUI smoke test from `dist/基金智能分析.exe`: startup, login/setup, Dashboard, Holdings, Risk Exposure, Investment Plans, Settings user profile. (added: 2026-05-26)
- [ ] [high] [runtime] Validate live DB upgrade on a copied real database before broad use; Codex only validated a temporary fresh SQLite DB. (added: 2026-05-26)
- [ ] [high] [data] Create one real monthly investment plan and verify 90-day execution materialization plus `/api/investment-plans/{id}/reconcile`. (added: 2026-05-26)
- [ ] [high] [data] Run live AKShare sync for fund managers and top holdings, then verify manager alerts and overlap heatmap data against known funds. (added: 2026-05-26)
- [ ] [high] [ocr] Validate P2.3 with real 支付宝 / 天天基金 screenshots: preview diff, inferred trades, duplicate skip, and missing-holding warning. (added: 2026-05-27)
- [ ] [high] [toolbox] Validate P2.4 with real fee schedules and holdings: milestone alerts, same-company switch calculator, quarterly disclosure coverage, and holiday advice. (added: 2026-05-27)

## Medium

- [ ] [medium] [tests] Add endpoint-level tests for new V3 APIs: fund manager, investment plan, asset allocation, and user profile. (added: 2026-05-26)
- [ ] [medium] [tests] Add endpoint-level tests for P2 fee ledger and decision review APIs. (added: 2026-05-27)
- [ ] [medium] [tests] Add endpoint-level auth-covered tests for `/api/ocr/status`, `/api/ocr/diff-preview`, and `/api/ocr/confirm-snapshot`. (added: 2026-05-27)
- [ ] [medium] [tests] Add endpoint-level auth-covered tests for `/api/toolbox/*` routes. (added: 2026-05-27)
- [ ] [medium] [frontend] Investigate Vite chunk warnings for `element-plus` and `echarts` if desktop startup or memory becomes a problem. (added: 2026-05-26)
- [ ] [medium] [repo] Decide whether generated `build/fund_ai/*` artifacts should remain tracked, be ignored, or be excluded from review diffs. (added: 2026-05-26)

## Verification Snapshot

- `python -m pytest backend/tests/ -v` -> 54 passed.
- 2026-05-27 `python -m pytest backend/tests/ -v` -> 55 passed.
- 2026-05-27 P2.3 `python -m py_compile backend\api\ocr.py backend\services\ocr_reconcile_service_v3.py` -> passed.
- 2026-05-27 P2.3 `python -m pytest backend/tests/test_ocr_reconcile.py -v` -> 3 passed.
- 2026-05-27 P2.3 `python -m pytest backend/tests/ -v` -> 58 passed.
- 2026-05-27 P2.4 `python -m py_compile backend\api\senior_toolbox_v3.py backend\services\senior_toolbox_service_v3.py backend\scheduler\jobs.py backend\scheduler\setup.py` -> passed.
- 2026-05-27 P2.4 `python -m pytest backend/tests/test_senior_toolbox.py -v` -> 4 passed.
- 2026-05-27 P2.4 `python -m pytest backend/tests/ -v` -> 62 passed.
- Publish worktree `python -m pytest backend/tests/ -v` -> 54 passed.
- `npm run build` -> passed; only existing Vite chunk-size warnings.
- 2026-05-27 `npm run build` -> passed; only existing Vite chunk-size warnings.
- 2026-05-27 P2.3 `npm run build` -> passed; only existing Vite chunk-size warnings.
- 2026-05-27 P2.4 `npm run build` -> passed; only existing Vite chunk-size warnings.
- Publish worktree `npm run build` -> passed; same Vite chunk-size warnings.
- Temporary SQLite `init_db()` -> Alembic upgraded to `f5b3a64e29d8`.
- 2026-05-27 temporary SQLite `init_db()` -> Alembic upgraded to `h7e3f94c20da`.
- `pwsh -File scripts/build_desktop.ps1` -> succeeded and rebuilt `dist/基金智能分析.exe`.
- 2026-05-27 P2.3 `pwsh -File scripts/build_desktop.ps1` -> succeeded; rebuilt `dist/基金智能分析.exe` (424,548,364 bytes, LastWriteTime 2026-05-27 12:30:31).
- 2026-05-27 P2.4 `pwsh -File scripts/build_desktop.ps1` -> succeeded; rebuilt `dist/基金智能分析.exe` (424,601,455 bytes, LastWriteTime 2026-05-27 14:05:20).
- 2026-05-27 P2.3 `git diff --check` -> passed; Git only reported existing LF/CRLF conversion warnings.
- 2026-05-27 P2.4 `git diff --check` -> passed; Git only reported existing LF/CRLF conversion warnings.
