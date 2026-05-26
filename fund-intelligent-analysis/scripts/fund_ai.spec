# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置 — 基金智能分析 Windows 桌面应用
打包: python -m PyInstaller scripts/fund_ai.spec --clean --noconfirm
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

ROOT = Path.cwd()

# pkg_resources 需要 email / xml / html，必须显式收集所有子模块
_email_mods = collect_submodules('email')
_xml_mods = collect_submodules('xml')
_html_mods = collect_submodules('html')

# backend/ 作为 data 文件打包，PyInstaller 不分析其 import
# 必须显式收集 backend 代码依赖的所有子模块
_fastapi_mods = collect_submodules('fastapi')
_starlette_mods = collect_submodules('starlette')

a = Analysis(
    [str(ROOT / 'scripts' / 'desktop_app.py')],
    pathex=[str(ROOT)],
    binaries=collect_dynamic_libs('py_mini_racer'),
    datas=[
        (str(ROOT / 'frontend' / 'dist'), 'frontend/dist'),
        (str(ROOT / 'assets'), 'assets'),
        (str(ROOT / 'scripts' / 'run_backend.py'), 'scripts'),
        (str(ROOT / 'backend'), 'backend'),
        (str(ROOT / '.env.example'), '.'),
        (str(ROOT / 'requirements.txt'), '.'),
        (str(ROOT / 'data' / 'calendar.json'), 'data'),
    ] + collect_data_files('akshare') + collect_data_files('py_mini_racer'),
    hiddenimports=[
        # Web server
        'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
        'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
        'fastapi', 'starlette',
        # Database
        'sqlalchemy', 'alembic', 'alembic.config', 'alembic.command',
        # AI & config
        'pydantic', 'pydantic_settings', 'openai',
        # HTTP & data
        'httpx', 'httpcore', 'h11', 'requests',
        # Financial data
        'akshare', 'pandas',
        # Scheduling
        'apscheduler', 'apscheduler.schedulers.background', 'apscheduler.triggers.cron',
        # Time parsing
        'dateutil', 'dateutil.parser',
        # Logging
        'loguru',
        # OCR (rapidocr is the working fallback)
        'rapidocr_onnxruntime',
        # JS engine for AKShare
        'py_mini_racer',
        # GUI
        'webview', 'tkinter', 'tkinter.ttk', 'plistlib',
        # V2 新增模块
        'backend.models.ai_advice_review', 'backend.models.fund_tag',
        'backend.services.advice_review_service', 'backend.services.capital_flow_scorer',
        'backend.services.fund_tag_service', 'backend.services.news_impact_service',
        'backend.services.risk_exposure_service', 'backend.services.return_metrics_v3',
        'backend.models.portfolio_snapshot',
        'backend.api.advice_review', 'backend.api.risk_exposure', 'backend.api.holding_metrics_v3',
        # V3/P1 新增模块
        'backend.models.fund_manager', 'backend.models.fund_top_holding',
        'backend.models.investment_plan', 'backend.models.asset_allocation',
        'backend.services.fund_manager_service_v3', 'backend.services.fund_top_holdings_collector_v3',
        'backend.services.overlap_analyzer_v3', 'backend.services.investment_plan_service_v3',
        'backend.services.asset_allocation_service_v3',
        'backend.api.fund_manager_v3', 'backend.api.investment_plan_v3',
        'backend.api.asset_allocation_v3', 'backend.api.user_profile_v3',
    ] + _email_mods + _xml_mods + _html_mods + _fastapi_mods + _starlette_mods,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='基金智能分析',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'assets' / 'fund-ai.ico'),
)
