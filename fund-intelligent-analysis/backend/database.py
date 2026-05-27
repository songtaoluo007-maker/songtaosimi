import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from loguru import logger
from backend.config import settings
from backend.utils import sanitize_text


engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={
        "check_same_thread": False,  # SQLite需要
        "timeout": 30,  # SQLite 写入锁等待超时（秒）
    },
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

# 启用 WAL 模式以提升并发读写性能（失败不影响启动）
if settings.DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
        except Exception as e:
            logger.debug(f"WAL模式设置跳过（可能已启用或权限不足）: {e}")
        try:
            cursor.execute("PRAGMA busy_timeout=30000")
        except Exception as e:
            logger.debug(f"busy_timeout设置失败: {e}")
        cursor.close()

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
    """初始化数据库：创建表 + 运行迁移 + 清洗数据"""
    # 导入所有模型以确保它们被注册
    from backend.models import fund, holding, trade, market_snapshot, news, ai_advice, fund_group, user, capital_flow, ai_advice_review, fund_tag, portfolio_snapshot, fund_manager, fund_top_holding, investment_plan, asset_allocation, fund_fee, user_decision_review  # noqa: F401

    # create_all 处理全新部署（幂等：已有表不重复创建）
    Base.metadata.create_all(bind=engine)

    # alembic 处理已有数据库的增量迁移
    try:
        from alembic.config import Config
        from alembic import command

        _dir = os.path.dirname(os.path.abspath(__file__))
        alembic_cfg = Config(os.path.join(_dir, "alembic.ini"))
        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        logger.warning(f"Alembic迁移跳过（可能首次启动或路径问题）: {e}")

    # 清洗历史数据中的编码损坏
    with engine.begin() as conn:
        _clean_garbled_text(conn)


def _clean_garbled_text(conn):
    """清洗数据库中已存在的编码损坏数据——每次启动检查一次。"""
    import re
    surr_pattern = re.compile(r'[\ud800-\udfff]')
    for table, cols in [
        ("news", ["title", "content", "keyword"]),
        ("funds", ["fund_name"]),
        ("market_snapshots", ["name"]),
        ("ai_advices", ["overall_suggestion"]),
    ]:
        try:
            rows = conn.exec_driver_sql(
                f"SELECT id, {', '.join(cols)} FROM {table}"
            ).fetchall()
            updates = 0
            for row in rows:
                rid = row[0]
                for i, col in enumerate(cols):
                    val = row[i + 1] or ""
                    if surr_pattern.search(val):
                        clean = sanitize_text(val)
                        conn.exec_driver_sql(
                            f"UPDATE {table} SET {col} = ? WHERE id = ?",
                            (clean, rid),
                        )
                        updates += 1
            if updates:
                logger.info(f"清洗 {table} 表 {updates} 处编码损坏")
        except Exception as e:
            logger.debug(f"清洗 {table} 表时跳过: {e}")
