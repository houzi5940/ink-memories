"""SQLite 数据库操作"""

from __future__ import annotations

import sqlite3
import json
import threading
from contextlib import contextmanager

from backend import config

# 并发写锁：asyncio 多线程并发时确保同一时间只有一个线程写 SQLite
_write_lock = threading.Lock()


@contextmanager
def write_lock():
    """获取写锁，避免 sqlite3.OperationalError: database is locked"""
    _write_lock.acquire()
    try:
        yield
    finally:
        _write_lock.release()


def init_db():
    """初始化数据库，创建表结构"""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS photo_scores (
                path            TEXT PRIMARY KEY,
                caption         TEXT,
                type            TEXT,
                memory_score    REAL,
                beauty_score    REAL,
                reason          TEXT,
                side_caption    TEXT,
                width           INTEGER,
                height          INTEGER,
                orientation     TEXT,
                exif_datetime   TEXT,
                exif_make       TEXT,
                exif_model      TEXT,
                exif_iso        INTEGER,
                exif_exposure_time REAL,
                exif_f_number   REAL,
                exif_focal_length REAL,
                exif_gps_lat    REAL,
                exif_gps_lon    REAL,
                exif_gps_alt    REAL,
                exif_city       TEXT,
                exif_json       TEXT,
                raw_json        TEXT,
                perceptual_hash TEXT,
                tags            TEXT,  -- JSON 数组，如 ["旅行", "海边"]
                status          TEXT,  -- pending | analyzing | done | failed | skipped
                used_at         TEXT,
                analyzed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 兼容旧数据库：新增 perceptual_hash / tags / status 字段
        columns = {row[1] for row in conn.execute("PRAGMA table_info(photo_scores)").fetchall()}
        if "perceptual_hash" not in columns:
            conn.execute("ALTER TABLE photo_scores ADD COLUMN perceptual_hash TEXT")
        if "tags" not in columns:
            conn.execute("ALTER TABLE photo_scores ADD COLUMN tags TEXT")
        if "status" not in columns:
            conn.execute("ALTER TABLE photo_scores ADD COLUMN status TEXT")
            # 一次性回填：按现有 type 标记推断分析状态
            conn.execute("UPDATE photo_scores SET status = 'pending' WHERE type = '待分析'")
            conn.execute("UPDATE photo_scores SET status = 'failed'  WHERE type = '分析失败'")
            conn.execute("UPDATE photo_scores SET status = 'skipped' WHERE type = '跳过'")
            conn.execute("UPDATE photo_scores SET status = 'done' WHERE status IS NULL")

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_score
            ON photo_scores(memory_score DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_exif_datetime
            ON photo_scores(exif_datetime)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_status
            ON photo_scores(status)
        """)

        # 每日精选描述缓存
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_captions (
                photo_path  TEXT NOT NULL,
                date        TEXT NOT NULL,
                caption     TEXT NOT NULL,
                side_caption TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (photo_path, date)
            )
        """)

        # 每日精选照片缓存（一天内固定不变）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_selection (
                date        TEXT NOT NULL,
                path        TEXT NOT NULL,
                sort_order  INTEGER NOT NULL DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, path)
            )
        """)
        conn.commit()


@contextmanager
def get_conn():
    """获取数据库连接"""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_analyzed_paths():
    """获取已分析的照片路径集合"""
    with get_conn() as conn:
        rows = conn.execute("SELECT path FROM photo_scores").fetchall()
        return {row["path"] for row in rows}


def insert_photo(photo: dict):
    """插入一条照片分析记录（缺失的可选字段补 NULL）"""
    # 确保所有 SQL 占位字段都存在，避免绑定参数缺失报错
    defaults = {
        "caption": None, "side_caption": None, "reason": None,
        "type": None, "memory_score": None, "beauty_score": None,
        "width": None, "height": None, "orientation": None,
        "exif_datetime": None, "exif_make": None, "exif_model": None,
        "exif_iso": None, "exif_exposure_time": None, "exif_f_number": None,
        "exif_focal_length": None, "exif_gps_lat": None, "exif_gps_lon": None,
        "exif_gps_alt": None, "exif_city": None, "exif_json": "{}",
        "raw_json": "{}", "perceptual_hash": None, "tags": None,
    }
    record = {**defaults, **photo}
    # tags 以 list 传入时存为 JSON 字符串
    if isinstance(record.get("tags"), (list, tuple, set)):
        record["tags"] = json.dumps(list(record["tags"]), ensure_ascii=False)
    with write_lock():
        with get_conn() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO photo_scores
            (path, caption, type, memory_score, beauty_score, reason,
             side_caption, width, height, orientation,
             exif_datetime, exif_make, exif_model,
             exif_iso, exif_exposure_time, exif_f_number, exif_focal_length,
             exif_gps_lat, exif_gps_lon, exif_gps_alt, exif_city,
             exif_json, raw_json, perceptual_hash, tags, analyzed_at)
            VALUES
            (:path, :caption, :type, :memory_score, :beauty_score, :reason,
             :side_caption, :width, :height, :orientation,
             :exif_datetime, :exif_make, :exif_model,
             :exif_iso, :exif_exposure_time, :exif_f_number, :exif_focal_length,
             :exif_gps_lat, :exif_gps_lon, :exif_gps_alt, :exif_city,
             :exif_json, :raw_json, :perceptual_hash, :tags, CURRENT_TIMESTAMP)
        """, record)
            conn.commit()


def get_all_photo_hashes() -> list[dict]:
    """获取所有已记录感知哈希的照片（用于相似度比对）"""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT path, perceptual_hash, memory_score
            FROM photo_scores
            WHERE perceptual_hash IS NOT NULL
            """
        ).fetchall()
        return [dict(r) for r in rows]


def update_photo(path: str, updates: dict):
    """更新照片的评分/标签/旁白（仅更新非空字段；tags 传空列表可清空）"""
    allowed = {"memory_score", "beauty_score", "type", "side_caption", "caption", "reason", "perceptual_hash", "tags"}
    fields = {k: v for k, v in updates.items() if k in allowed and v is not None}

    # tags 以 list 传入时存为 JSON 字符串；空列表/空字符串表示清空标签
    if "tags" in fields:
        tags = fields["tags"]
        if isinstance(tags, (list, tuple, set)):
            fields["tags"] = json.dumps(list(tags), ensure_ascii=False) if tags else None
        elif isinstance(tags, str):
            fields["tags"] = tags.strip() or None
        else:
            fields["tags"] = None

    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [path]
    with write_lock():
        with get_conn() as conn:
            conn.execute(f"UPDATE photo_scores SET {set_clause} WHERE path = ?", values)
            conn.commit()


def get_photo_by_path(path: str) -> dict | None:
    """按路径获取单张照片"""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM photo_scores WHERE path = ?", (path,)).fetchone()
        return dict(row) if row else None


def get_photos_by_date(month_day: str):
    """按 MM-DD 查询历年同一天的照片"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM photo_scores
            WHERE substr(exif_datetime, 6, 5) = ?
            AND memory_score >= ?
            ORDER BY memory_score DESC
        """, (month_day, config.MEMORY_THRESHOLD)).fetchall()
        return [dict(r) for r in rows]


def get_top_photos(limit=5):
    """获取全库最高分照片（兜底）"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM photo_scores
            WHERE memory_score >= ?
            ORDER BY memory_score DESC
            LIMIT ?
        """, (config.MEMORY_THRESHOLD, limit)).fetchall()
        return [dict(r) for r in rows]


def get_all_photos(limit=None, offset=0, order_by="analyzed_at DESC", exclude_skipped=True, status=None):
    """获取所有照片

    Args:
        exclude_skipped: 为 True 时排除 status='skipped'（默认）
        status: 指定只返回某状态的照片（如 'skipped'），与 exclude_skipped 互斥
    """
    with get_conn() as conn:
        safe_orders = {"analyzed_at DESC", "analyzed_at ASC", "memory_score DESC",
                       "memory_score ASC", "beauty_score DESC", "beauty_score ASC",
                       "exif_datetime DESC", "exif_datetime ASC"}
        if order_by not in safe_orders:
            order_by = "analyzed_at DESC"
        if status:
            where = f"WHERE status = '{status}'"
        elif exclude_skipped:
            where = "WHERE status != 'skipped'"
        else:
            where = ""
        sql = f"SELECT * FROM photo_scores {where} ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit} OFFSET {offset}"
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]


def get_photo_count(exclude_skipped=True, status=None):
    """获取总照片数

    Args:
        exclude_skipped: 为 True 时排除 status='skipped'（默认）
        status: 指定只统计某状态的照片（如 'skipped'），与 exclude_skipped 互斥
    """
    with get_conn() as conn:
        if status:
            where = f"WHERE status = '{status}'"
        elif exclude_skipped:
            where = "WHERE status != 'skipped'"
        else:
            where = ""
        row = conn.execute(f"SELECT COUNT(*) as cnt FROM photo_scores {where}").fetchone()
        return row["cnt"]


def get_type_distribution():
    """获取照片类型分布"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT type, COUNT(*) as cnt, AVG(memory_score) as avg_score
            FROM photo_scores
            GROUP BY type
            ORDER BY cnt DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_tag_distribution():
    """获取手动标签分布（tags 字段为 JSON 数组）"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT tags FROM photo_scores WHERE tags IS NOT NULL AND tags != ''
        """).fetchall()
    counts = {}
    for row in rows:
        try:
            tags = json.loads(row["tags"])
            if isinstance(tags, list):
                for tag in tags:
                    tag = str(tag).strip()
                    if tag:
                        counts[tag] = counts.get(tag, 0) + 1
        except (json.JSONDecodeError, TypeError):
            continue
    return sorted([{"tag": k, "count": v} for k, v in counts.items()], key=lambda x: -x["count"])


def get_score_distribution():
    """获取评分分布"""
    buckets = [(0, 40), (40, 60), (60, 70), (70, 80), (80, 90), (90, 101)]
    result = []
    with get_conn() as conn:
        for low, high in buckets:
            row = conn.execute("""
                SELECT COUNT(*) as cnt FROM photo_scores
                WHERE memory_score >= ? AND memory_score < ?
            """, (low, high)).fetchone()
            result.append({
                "range": f"{low}-{high-1 if high <= 100 else 100}",
                "count": row["cnt"]
            })
    return result


def search_photos(keyword: str, limit=50):
    """按关键词搜索照片描述、类型和标签"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM photo_scores
            WHERE caption LIKE ? OR reason LIKE ? OR side_caption LIKE ? OR type LIKE ? OR tags LIKE ?
            ORDER BY memory_score DESC
            LIMIT ?
        """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit)).fetchall()
        return [dict(r) for r in rows]


# ============================================================
# 每日精选描述缓存
# ============================================================

def save_daily_caption(photo_path: str, date: str, caption: str, side_caption: str = None):
    """保存当日精选描述"""
    with write_lock():
        with get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO daily_captions (photo_path, date, caption, side_caption)
                VALUES (?, ?, ?, ?)
            """, (photo_path, date, caption, side_caption))
            conn.commit()


def get_daily_captions(date: str) -> dict:
    """获取某天的所有精选描述"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT photo_path, caption, side_caption FROM daily_captions WHERE date = ?",
            (date,)
        ).fetchall()
        return {row["photo_path"]: {"caption": row["caption"], "side_caption": row["side_caption"]}
                for row in rows}


def clear_daily_captions(date: str):
    """清除某天的精选描述（用于重新生成）"""
    with write_lock():
        with get_conn() as conn:
            conn.execute("DELETE FROM daily_captions WHERE date = ?", (date,))
            conn.commit()


# ============================================================
# 每日精选照片缓存（一天内固定不变）
# ============================================================

def save_daily_selection(date: str, photos: list[dict]):
    """保存今日精选的照片列表"""
    with write_lock():
        with get_conn() as conn:
            conn.execute("DELETE FROM daily_selection WHERE date = ?", (date,))
            for i, p in enumerate(photos):
                conn.execute(
                    "INSERT OR REPLACE INTO daily_selection (date, path, sort_order) VALUES (?, ?, ?)",
                    (date, p["path"], i),
                )
            conn.commit()


def get_daily_selection(date: str) -> list[str]:
    """获取今日精选的照片路径（按排序顺序）"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT path FROM daily_selection WHERE date = ? ORDER BY sort_order",
            (date,),
        ).fetchall()
        return [r["path"] for r in rows]


def clear_daily_selection(date: str):
    """清除今日精选缓存（用于每日轮换）"""
    with write_lock():
        with get_conn() as conn:
            conn.execute("DELETE FROM daily_selection WHERE date = ?", (date,))
            conn.execute("DELETE FROM daily_captions WHERE date = ?", (date,))
            conn.commit()


# ============================================================
# 人工审核 - 未评分照片查询
# ============================================================

def scan_unanalyzed_photos(limit: int = 20, offset: int = 0) -> list[dict]:
    """扫描 PHOTO_DIR，返回不在 photo_scores 中的照片路径（按 mtime 降序）"""
    import os
    from pathlib import Path
    from backend.config import PHOTO_DIR, SUPPORTED_EXTENSIONS, EXCLUDE_DIRS

    analyzed = get_analyzed_paths()
    photo_dir = Path(PHOTO_DIR)
    if not photo_dir.exists():
        return []

    candidates: list[tuple[str, float]] = []  # (path, mtime)

    for root, dirs, files in os.walk(photo_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            ext = Path(f).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            full_path = str(Path(root) / f)
            if full_path in analyzed:
                continue
            try:
                mtime = os.path.getmtime(full_path)
            except OSError:
                mtime = 0
            candidates.append((full_path, mtime))

    # 按修改时间降序（最新的优先展示）
    candidates.sort(key=lambda x: -x[1])
    total = len(candidates)
    page = candidates[offset : offset + limit]

    return [
        {
            "path": path,
            "date": "",  # 由前端展示时从 EXIF 获取
            "type": "",
        }
        for path, _ in page
    ]


def get_unanalyzed_count() -> int:
    """未评分照片总数"""
    import os
    from pathlib import Path
    from backend.config import PHOTO_DIR, SUPPORTED_EXTENSIONS, EXCLUDE_DIRS

    analyzed = get_analyzed_paths()
    photo_dir = Path(PHOTO_DIR)
    if not photo_dir.exists():
        return 0

    count = 0
    for root, dirs, files in os.walk(photo_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            ext = Path(f).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            full_path = str(Path(root) / f)
            if full_path not in analyzed:
                count += 1
    return count


def batch_skip_photos(paths: list[str]):
    """将未勾选的照片标记为跳过（插入 photo_scores，score=0）"""
    import json
    from backend.config import SUPPORTED_EXTENSIONS
    from pathlib import Path

    with write_lock():
        with get_conn() as conn:
            for path in paths:
                ext = Path(path).suffix.lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue
                conn.execute(
                    """INSERT OR IGNORE INTO photo_scores
                       (path, memory_score, beauty_score, type, reason, raw_json, status, analyzed_at)
                       VALUES (?, 0, 0, '跳过', '人工审核跳过', '{}', 'skipped', CURRENT_TIMESTAMP)""",
                    (path,),
                )
            conn.commit()


# ============================================================
# 分析任务队列（status: pending / analyzing / done / failed / skipped）
# ============================================================

def enqueue_pending(paths: list[str]) -> int:
    """将选中照片写入队列（status='pending'）。已在库的路径保持不动。

    返回实际新入队的数量。
    """
    from backend.config import SUPPORTED_EXTENSIONS
    from pathlib import Path

    count = 0
    with write_lock():
        with get_conn() as conn:
            for path in paths:
                if Path(path).suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                cur = conn.execute(
                    """INSERT OR IGNORE INTO photo_scores
                       (path, type, reason, raw_json, status, analyzed_at)
                       VALUES (?, '待分析', '等待分析', '{}', 'pending', CURRENT_TIMESTAMP)""",
                    (path,),
                )
                count += cur.rowcount
            conn.commit()
    return count


def requeue_paths(paths: list[str]):
    """强制将指定路径置回 pending（供单张重新分析；已入库的 done 照片重新排队）"""
    if not paths:
        return
    with write_lock():
        with get_conn() as conn:
            for path in paths:
                conn.execute(
                    "UPDATE photo_scores SET status = 'pending', type = '待分析', reason = '等待重新分析' WHERE path = ?",
                    (path,),
                )
            conn.commit()


def claim_pending_batch(limit: int) -> list[str]:
    """原子领取一批 pending 照片：选中后置为 analyzing，返回其路径列表。"""
    if limit <= 0:
        limit = 1
    with write_lock():
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT path FROM photo_scores WHERE status = 'pending' LIMIT ?",
                (limit,),
            ).fetchall()
            paths = [r["path"] for r in rows]
            if paths:
                placeholders = ",".join("?" for _ in paths)
                conn.execute(
                    f"UPDATE photo_scores SET status = 'analyzing' WHERE path IN ({placeholders})",
                    paths,
                )
                conn.commit()
            return paths


def mark_status(path: str, status: str):
    """更新单张照片的分析状态"""
    with write_lock():
        with get_conn() as conn:
            conn.execute("UPDATE photo_scores SET status = ? WHERE path = ?", (status, path))
            conn.commit()


def get_queue_stats() -> dict:
    """按 status 统计各状态数量"""
    stats = {"pending": 0, "analyzing": 0, "done": 0, "failed": 0, "skipped": 0}
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM photo_scores WHERE status IS NOT NULL GROUP BY status"
        ).fetchall()
    for row in rows:
        if row["status"] in stats:
            stats[row["status"]] = row["cnt"]
    return stats


def reset_stale_analyzing() -> int:
    """启动恢复：将上次中断遗留的 analyzing 重置为 pending，返回重置数量"""
    with write_lock():
        with get_conn() as conn:
            cur = conn.execute(
                "UPDATE photo_scores SET status = 'pending' WHERE status = 'analyzing'"
            )
            conn.commit()
            return cur.rowcount
