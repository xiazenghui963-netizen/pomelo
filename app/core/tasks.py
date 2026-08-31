import asyncio
import logging

from ..config import settings
from ..services.jobs import run_job

logger = logging.getLogger(__name__)

_queue: asyncio.Queue[int] = asyncio.Queue()
_workers: list[asyncio.Task] = []


async def _worker(_idx: int):
    while True:
        task_id = await _queue.get()
        try:
            await asyncio.to_thread(run_job, task_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("async task %s failed: %s", task_id, exc)
        finally:
            _queue.task_done()


def start_workers():
    for i in range(settings.task_workers):
        _workers.append(asyncio.create_task(_worker(i)))


def shutdown_workers():
    for w in _workers:
        w.cancel()


def enqueue(task_id: int):
    _queue.put_nowait(task_id)