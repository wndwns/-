"""
牧融绿链 - MySQL 数据库连接层
============================================================================
提供:
  - 连接池管理 (PyMySQL + DBUtils)
  - 查询辅助函数
  - 数据库初始化 (建表 + 种子数据)
  - 无 MySQL 时自动回退到样例数据

环境变量 (可选):
  MYSQL_HOST     - 默认 127.0.0.1
  MYSQL_PORT     - 默认 3306
  MYSQL_USER     - 默认 root
  MYSQL_PASSWORD - 默认空
  MYSQL_DATABASE - 默认 yak_green_chain
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 尝试加载 MySQL 驱动
# ---------------------------------------------------------------------------

_HAS_MYSQL = False
_POOL: Any = None

try:
    import pymysql
    from dbutils.pooled_db import PooledDB

    _HAS_MYSQL = True
except ImportError:
    pymysql = None  # type: ignore
    PooledDB = None  # type: ignore


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parent


def _load_dotenv_file(path: Path = BACKEND_DIR.parent / ".env") -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv_file()

MYSQL_CONFIG: dict[str, Any] = {
    "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.environ.get("MYSQL_PORT", "3306")),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
    "database": os.environ.get("MYSQL_DATABASE", "yak_green_chain"),
    "charset": "utf8mb4",
}


# ---------------------------------------------------------------------------
# 连接池
# ---------------------------------------------------------------------------

def get_pool():
    """获取数据库连接池（懒初始化）。"""
    global _POOL
    if not _HAS_MYSQL:
        return None
    if _POOL is None:
        try:
            _POOL = PooledDB(
                creator=pymysql,
                maxconnections=10,
                mincached=2,
                maxcached=5,
                blocking=True,
                **MYSQL_CONFIG,
            )
        except Exception as exc:
            print(f"[db] MySQL 连接失败: {exc}", file=sys.stderr)
            return None
    return _POOL


def get_conn():
    """从连接池获取一个连接。"""
    pool = get_pool()
    if pool is None:
        return None
    return pool.connection()


# ---------------------------------------------------------------------------
# 查询辅助
# ---------------------------------------------------------------------------

def fetch_all(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    """执行查询并返回所有行（字典列表）。"""
    conn = get_conn()
    if conn is None:
        return []
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:  # type: ignore[union-attr]
            cur.execute(sql, params)
            return cur.fetchall()  # type: ignore[no-any-return]
    finally:
        conn.close()


def fetch_one(sql: str, params: tuple | None = None) -> dict[str, Any] | None:
    """执行查询并返回第一行。"""
    conn = get_conn()
    if conn is None:
        return None
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:  # type: ignore[union-attr]
            cur.execute(sql, params)
            return cur.fetchone()  # type: ignore[no-any-return]
    finally:
        conn.close()


def execute(sql: str, params: tuple | None = None) -> int:
    """执行写操作，返回影响行数。"""
    conn = get_conn()
    if conn is None:
        return 0
    try:
        with conn.cursor() as cur:
            rows = cur.execute(sql, params)
            conn.commit()
            return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_many(sql: str, params_list: list[tuple]) -> int:
    """批量执行写操作。"""
    conn = get_conn()
    if conn is None:
        return 0
    try:
        with conn.cursor() as cur:
            rows = cur.executemany(sql, params_list)
            conn.commit()
            return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 数据库初始化
# ---------------------------------------------------------------------------

def is_db_available() -> bool:
    """检测 MySQL 是否可用。"""
    return get_pool() is not None


def init_database() -> bool:
    """初始化数据库：建表 + 种子数据。

    先尝试连接已存在的库，若不存在则创建。
    """
    if not _HAS_MYSQL:
        print("[db] PyMySQL 未安装，使用样例数据模式")
        return False

    # 先尝试创建数据库
    try:
        conn = pymysql.connect(
            host=MYSQL_CONFIG["host"],
            port=MYSQL_CONFIG["port"],
            user=MYSQL_CONFIG["user"],
            password=MYSQL_CONFIG["password"],
            charset="utf8mb4",
        )
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_CONFIG['database']}` "
                "DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"[db] 创建数据库失败: {exc}", file=sys.stderr)
        return False

    # 检查连接池
    pool = get_pool()
    if pool is None:
        return False

    # 检查表是否已存在（通过查 regions 表）
    conn = get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES LIKE 'regions'")
            if cur.fetchone():
                conn.close()
                print("[db] 数据库已初始化，跳过建表")
                return True
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # 执行 schema
    schema_file = BACKEND_DIR / "schema.sql"
    if not schema_file.exists():
        print(f"[db] schema.sql 不存在: {schema_file}", file=sys.stderr)
        return False

    try:
        conn = get_conn()
        if conn is None:
            return False
        with conn.cursor() as cur:
            for statement in _split_sql(schema_file.read_text(encoding="utf-8")):
                stmt = statement.strip()
                if stmt and not stmt.startswith("--"):
                    cur.execute(stmt)
            conn.commit()
        conn.close()
        print("[db] 数据库表创建成功")
    except Exception as exc:
        print(f"[db] 建表失败: {exc}", file=sys.stderr)
        return False

    # 执行种子数据
    seed_file = BACKEND_DIR / "seed_data.sql"
    if seed_file.exists():
        try:
            conn = get_conn()
            if conn is None:
                return False
            with conn.cursor() as cur:
                for statement in _split_sql(seed_file.read_text(encoding="utf-8")):
                    stmt = statement.strip()
                    if stmt and not stmt.startswith("--"):
                        cur.execute(stmt)
                conn.commit()
            conn.close()
            print("[db] 种子数据写入成功")
        except Exception as exc:
            print(f"[db] 种子数据写入失败: {exc}", file=sys.stderr)

    return True


def _split_sql(text: str) -> list[str]:
    """按分号分割 SQL 语句，忽略注释。"""
    statements = []
    current: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("--") or stripped == "":
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current))
            current = []
    if current:
        statements.append("\n".join(current))
    return statements


def ensure_initialized() -> bool:
    """保证数据库已初始化（幂等）。"""
    if not _HAS_MYSQL:
        return False
    pool = get_pool()
    if pool is None:
        return False
    # 快速检查
    tables = fetch_all("SHOW TABLES LIKE 'regions'")
    if tables:
        return True
    return init_database()
