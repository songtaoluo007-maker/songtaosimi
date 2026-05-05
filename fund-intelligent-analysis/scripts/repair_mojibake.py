import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "fund_quant.db"
MARKERS = ("æ", "ç", "è", "é", "å", "ä", "ï¼", "ã")


def looks_broken(value: str) -> bool:
    return isinstance(value, str) and any(marker in value for marker in MARKERS)


def repair(value: str) -> str:
    if not looks_broken(value):
        return value
    try:
        fixed = value.encode("latin1").decode("utf-8")
        return fixed if fixed else value
    except Exception:
        return value


def repair_table(conn, table: str, columns: list[str]):
    rows = conn.execute(f"SELECT id, {', '.join(columns)} FROM {table}").fetchall()
    for row in rows:
        row_id = row[0]
        updates = {}
        for idx, column in enumerate(columns, start=1):
            original = row[idx]
            fixed = repair(original)
            if fixed != original:
                updates[column] = fixed
        if updates:
            set_sql = ", ".join([f"{column}=?" for column in updates])
            conn.execute(
                f"UPDATE {table} SET {set_sql} WHERE id=?",
                [*updates.values(), row_id],
            )


def main():
    if not DB.exists():
        return
    conn = sqlite3.connect(DB)
    try:
        repair_table(conn, "funds", ["fund_name", "fund_type", "manager", "company"])
        repair_table(conn, "market_snapshots", ["name", "snapshot_type"])
        repair_table(conn, "news", ["title", "content", "source", "keyword"])
        repair_table(conn, "ai_advices", ["market_summary", "portfolio_snapshot", "advice_content", "reasoning", "overall_suggestion"])
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
