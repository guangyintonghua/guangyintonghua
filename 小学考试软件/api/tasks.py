import threading
import uuid
from typing import Callable

_tasks: dict[str, dict] = {}


def create_task() -> str:
    tid = uuid.uuid4().hex[:10]
    _tasks[tid] = {"status": "pending", "result": None, "error": None}
    return tid


def run_task(tid: str, fn: Callable, *args, **kwargs):
    _tasks[tid]["status"] = "running"

    def _worker():
        try:
            _tasks[tid]["result"] = fn(*args, **kwargs)
            _tasks[tid]["status"] = "done"
        except Exception as e:
            _tasks[tid]["error"] = str(e)
            _tasks[tid]["status"] = "error"

    threading.Thread(target=_worker, daemon=True).start()


def get_task(tid: str) -> dict:
    return _tasks.get(tid, {"status": "not_found", "result": None, "error": "任务不存在"})
