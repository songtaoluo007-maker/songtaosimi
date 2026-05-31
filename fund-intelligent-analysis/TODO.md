# Project Tasks

> Last updated: 2026-05-31 19:59 +08:00
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
- [x] [medium] [tests] Added endpoint-level test suites for V3/P2 APIs: investment-plan, fund-manager, asset-allocation, user-profile, fund-fees, decision-review, OCR snapshot, toolbox. (completed: 2026-05-27)
- [x] [medium] [tests] Patched conftest with rate-limit bypass + shared `register_and_login` helper; full suite now 153 passed (was 62). (completed: 2026-05-27)
- [x] [high] [runtime] Fixed desktop/API smoke-test regressions found on copied real DB: static assets no longer count toward API rate limit, and XIRR now normalizes mixed `date` / `datetime` cash-flow dates. (completed: 2026-05-31)
- [x] [high] [packaging] Rebuilt `dist/基金智能分析.exe`; output size 424,684,570 bytes, timestamp 2026-05-31 15:01:27. (completed: 2026-05-31)
- [x] [high] [runtime] GUI smoke test from the rebuilt EXE passed: login, Dashboard, Holdings, Risk Exposure, Investment Plans, Settings user profile, Toolbox, OCR Import; report `data/validation/gui_smoke_20260531_150222.json`. (completed: 2026-05-31)
- [x] [medium] [branding] Replaced the desktop/frontend brand icon with the user-selected second blue-white candlestick version; regenerated PNG sizes 16/24/32/48/64/128/192/256/512 and multi-size ICO. (completed: 2026-05-31)

## High

- [x] [high] [runtime] Run a GUI smoke test from `dist/基金智能分析.exe`: startup, login/setup, Dashboard, Holdings, Risk Exposure, Investment Plans, Settings user profile. (added: 2026-05-26, completed: 2026-05-31)
- [x] [high] [runtime] Validate live DB upgrade on a copied real database before broad use; copied DB `data/validation/fund_quant_validation_20260530_112919.db` upgraded successfully. (added: 2026-05-26, completed: 2026-05-31)
- [x] [high] [data] Create one real monthly investment plan on copied real DB and verify 90-day execution materialization plus `/api/investment-plans/{id}/reconcile` service path; generated 3 monthly rows and reconciled 1 validation trade. (added: 2026-05-26, completed: 2026-05-31)
- [x] [high] [data] Run live AKShare / Eastmoney sync on copied real DB: fund managers checked 22/22 with 24 medium new-manager alerts; top holdings checked 22/22, success 21, source returned no data for `015283`; report `data/validation/live_sync_all_holdings_20260531_150449.json`. (added: 2026-05-26, completed: 2026-05-31)
- [ ] [blocked] [ocr] Validate P2.3 OCR recognition with fresh real 支付宝 / 天天基金 screenshots. No local account screenshots exist under `data/ocr_temp` or repo image paths; service-level diff/duplicate/missing-holding flow passed on copied real holdings in `data/validation/remaining_plan_validation_20260530_112919.json`. (added: 2026-05-27)
- [ ] [blocked] [toolbox] Enter or sync real fee schedules for active holdings before relying on P2.4 fee outputs. Source DB has 0 `fund_fee_schedules`; toolbox algorithm path passed on copied real holdings with temporary validation schedules, but real fee-rate business acceptance still needs actual fee data. (added: 2026-05-27)

## Medium

- [x] [medium] [tests] Endpoint-level tests for V3 APIs (fund manager, investment plan, asset allocation, user profile). (added: 2026-05-26, completed: 2026-05-27)
- [x] [medium] [tests] Endpoint-level tests for P2 fee ledger and decision review APIs. (added: 2026-05-27, completed: 2026-05-27)
- [x] [medium] [tests] Endpoint-level auth-covered tests for `/api/ocr/status`, `/api/ocr/diff-preview`, and `/api/ocr/confirm-snapshot`. (added: 2026-05-27, completed: 2026-05-27)
- [x] [medium] [tests] Endpoint-level auth-covered tests for `/api/toolbox/*` routes. (added: 2026-05-27, completed: 2026-05-27)
- [x] [medium] [frontend] Investigate Vite chunk warnings for `element-plus` and `echarts`; current local-desktop budget accepts the measured vendor chunks, and `chunkSizeWarningLimit` is set to 1000 KB so builds only warn on unexpected growth. (added: 2026-05-26, completed: 2026-05-31)
- [x] [medium] [repo] Decide whether generated `build/fund_ai/*` artifacts should remain tracked, be ignored, or be excluded from review diffs; keep `build/` ignored and exclude generated PyInstaller intermediates from review diffs. (added: 2026-05-26, completed: 2026-05-31)

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
- 2026-05-27 endpoint-tests `python -m pytest backend/tests/ -v` -> 153 passed (62 → 153, +91 new endpoint tests across investment-plan / fund-manager / asset-allocation / user-profile / fund-fees / decision-review / ocr / toolbox).
- 2026-05-31 `python -m pytest backend/tests/test_return_metrics.py backend/tests/test_rate_limit_middleware.py -v` -> 5 passed.
- 2026-05-31 copied real DB validation -> upgrade passed; investment-plan materialization/reconcile passed; OCR diff duplicate-skip/missing-holding service path passed; toolbox path passed with temporary validation fee schedules; live sync managers 22/22 and top holdings 21/22.
- 2026-05-31 `npm run build` -> passed; previous large chunk warnings for `element-plus` / `echarts` suppressed by measured desktop budget, only static/dynamic import notices remain.
- 2026-05-31 `pwsh -File scripts/build_desktop.ps1` -> succeeded; rebuilt `dist/基金智能分析.exe` (424,684,570 bytes, LastWriteTime 2026-05-31 15:01:27).
- 2026-05-31 rebuilt EXE GUI smoke -> passed; login + Dashboard + Holdings + Risk Exposure + Investment Plans + Settings user profile + Toolbox + OCR Import, no 429/500/page errors.
- 2026-05-31 branding `python scripts/generate_brand_assets.py` -> succeeded; regenerated icon assets from `assets/fund-ai-source.png`.
- 2026-05-31 branding `npm run build` (frontend) -> passed; only existing Vite static/dynamic import notices.
- 2026-05-31 branding `pwsh -File scripts/build_desktop.ps1` -> succeeded after stopping two running old EXE processes that locked the target; rebuilt `dist/基金智能分析.exe` (425,711,512 bytes, LastWriteTime 2026-05-31 20:11:58).
