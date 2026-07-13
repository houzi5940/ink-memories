"""线程安全的分析进度追踪"""

import threading
import time
from typing import Optional


class _Progress:
    """全局分析进度状态（单例模式，模块级变量）"""

    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._total = 0
        self._done = 0
        self._success = 0
        self._fail = 0
        self._current_file = ""
        self._phase = ""          # "scanning" | "analyzing" | "done" | ""
        self._started_at: Optional[float] = None

    # ── 写入 ──

    def reset(self, total: int = 0):
        with self._lock:
            self._running = True
            self._total = total
            self._done = 0
            self._success = 0
            self._fail = 0
            self._current_file = ""
            self._phase = "scanning" if total == 0 else "analyzing"
            self._started_at = time.time()

    def set_phase(self, phase: str):
        with self._lock:
            self._phase = phase

    def extend_total(self, n: int):
        """排空过程中有新任务加入时累加总数"""
        if n <= 0:
            return
        with self._lock:
            self._total += n

    def tick(self, filepath: str = "", success: bool = True):
        with self._lock:
            self._done += 1
            if success:
                self._success += 1
            else:
                self._fail += 1
            self._current_file = filepath

    def finish(self):
        with self._lock:
            self._running = False
            self._phase = "done"

    # ── 读取 ──

    def snapshot(self) -> dict:
        with self._lock:
            elapsed = round(time.time() - self._started_at, 1) if self._started_at else 0
            snap = {
                "running": self._running,
                "total": self._total,
                "done": self._done,
                "success": self._success,
                "fail": self._fail,
                "current_file": self._current_file,
                "phase": self._phase,
                "elapsed": elapsed,
            }
        # 附带队列实时统计（供前端展示“排队中 N 张”）；失败时不影响主体进度
        try:
            from backend import database
            stats = database.get_queue_stats()
            snap["pending"] = stats["pending"]
            snap["analyzing"] = stats["analyzing"]
        except Exception:
            snap["pending"] = 0
            snap["analyzing"] = 0
        return snap


# 模块级全局实例
_progress = _Progress()


def get_progress() -> dict:
    return _progress.snapshot()


def start_analysis(total: int = 0):
    _progress.reset(total)


def report_scanning():
    _progress.set_phase("scanning")


def report_analyzing():
    _progress.set_phase("analyzing")


def report_tick(filepath: str = "", success: bool = True):
    _progress.tick(filepath, success)


def report_done():
    _progress.finish()


def extend_total(n: int):
    _progress.extend_total(n)
