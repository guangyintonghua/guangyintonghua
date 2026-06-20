"""
任务队列：持久化到 JSON，支持断点续传、暂停、取消、重试。
"""
import json
import time
from pathlib import Path
from loguru import logger
from models.product import Product, TaskStatus


_STATE_FILE = Path('data') / 'task_state.json'


class TaskQueue:
    def __init__(self, products: list[Product], state_file: Path = _STATE_FILE):
        self._state_file = state_file
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._paused    = False
        self._cancelled = False

        # 恢复已有状态（断点续传）
        saved = self._load_state()
        if saved:
            self._restore(products, saved)
            done = sum(1 for p in products if p.status == TaskStatus.DONE)
            logger.info(f"断点续传：已完成 {done}/{len(products)} 个商品")
        self._products = products

    # ── 迭代接口 ───────────────────────────────────────────────────────────

    def pending(self) -> list[Product]:
        return [p for p in self._products
                if p.status in (TaskStatus.PENDING, TaskStatus.FAILED)]

    def __iter__(self):
        for p in self._products:
            if p.status in (TaskStatus.PENDING, TaskStatus.FAILED):
                yield p

    # ── 控制 ───────────────────────────────────────────────────────────────

    def pause(self):
        self._paused = True
        logger.info("任务已暂停")

    def resume(self):
        self._paused = False
        logger.info("任务已恢复")

    def cancel(self):
        self._cancelled = True
        logger.info("任务已取消")

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    # ── 状态持久化 ─────────────────────────────────────────────────────────

    def save_state(self):
        state = {
            p.seq: {
                'status':  p.status.name,
                'item_id': p.item_id,
                'error':   p.error,
            }
            for p in self._products
        }
        self._state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8'
        )

    def _load_state(self) -> dict | None:
        if not self._state_file.exists():
            return None
        try:
            return json.loads(self._state_file.read_text(encoding='utf-8'))
        except Exception:
            return None

    def _restore(self, products: list[Product], saved: dict):
        for p in products:
            if p.seq in saved:
                s = saved[p.seq]
                try:
                    p.status  = TaskStatus[s['status']]
                    p.item_id = s.get('item_id', '')
                    p.error   = s.get('error', '')
                except KeyError:
                    pass

    # ── 统计 ───────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        total   = len(self._products)
        done    = sum(1 for p in self._products if p.status == TaskStatus.DONE)
        failed  = sum(1 for p in self._products if p.status == TaskStatus.FAILED)
        pending = sum(1 for p in self._products if p.status == TaskStatus.PENDING)
        return {'total': total, 'done': done, 'failed': failed, 'pending': pending}
