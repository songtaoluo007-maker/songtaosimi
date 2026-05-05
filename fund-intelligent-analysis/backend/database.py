from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import settings


engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},  # SQLite需要
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库，创建所有表"""
    # 导入所有模型以确保它们被注册
    from backend.models import fund, holding, trade, market_snapshot, news, ai_advice, fund_group  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns():
    """为本地SQLite做轻量字段补齐，避免已有数据库升级后缺列。"""
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    columns = {
        "market_view": "VARCHAR(20) DEFAULT 'neutral'",
        "overall_suggestion": "TEXT DEFAULT ''",
        "risk_level": "VARCHAR(20) DEFAULT 'medium'",
        "data_quality": "JSON DEFAULT '{}'",
    }
    with engine.begin() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(ai_advices)").fetchall()}
        for name, ddl in columns.items():
            if name not in existing:
                conn.exec_driver_sql(f"ALTER TABLE ai_advices ADD COLUMN {name} {ddl}")

        holding_columns = {
            "daily_pnl": "NUMERIC(16,2) DEFAULT 0",
            "daily_pnl_ratio": "NUMERIC(8,4) DEFAULT 0",
            "daily_pnl_date": "DATE",
        }
        existing_holdings = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(holdings)").fetchall()}
        for name, ddl in holding_columns.items():
            if name not in existing_holdings:
                conn.exec_driver_sql(f"ALTER TABLE holdings ADD COLUMN {name} {ddl}")

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS fund_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(80) NOT NULL UNIQUE,
                description VARCHAR(300) DEFAULT '',
                color VARCHAR(20) DEFAULT '#2f6fef',
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS fund_group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                fund_code VARCHAR(6) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(group_id, fund_code)
            )
            """
        )
