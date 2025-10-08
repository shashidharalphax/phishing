import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import sessionmaker

from ..db import SessionLocal
from ..models import TargetDomain
from .pipeline import ensure_pipeline_workers, queue_scan

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self, session_factory: sessionmaker, tick_seconds: int = 30, max_concurrency: int = 2):
        self.session_factory = session_factory or SessionLocal
        self.tick_seconds = tick_seconds
        self.max_concurrency = max_concurrency
        self._task: Optional[asyncio.Task] = None
        self._stopped = asyncio.Event()
        self._started = False

    async def start(self):
        if self._started:
            return
        self._started = True
        ensure_pipeline_workers(self.session_factory, concurrency=self.max_concurrency)
        self._stopped.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started (tick=%ss, concurrency=%s)", self.tick_seconds, self.max_concurrency)

    async def stop(self):
        self._stopped.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
        logger.info("Scheduler stopped")

    async def _run_loop(self):
        while not self._stopped.is_set():
            try:
                self._tick_once()
            except Exception as e:
                logger.exception("Scheduler tick error: %s", e)
            await asyncio.sleep(self.tick_seconds)

    def _tick_once(self):
        db = self.session_factory()
        try:
            now = datetime.utcnow()
            targets = (
                db.query(TargetDomain)
                .filter(TargetDomain.is_active == True)
                .filter(TargetDomain.is_verified == True)
                .all()
            )
            for t in targets:
                interval = timedelta(minutes=t.scan_interval_minutes or 15)
                due = (t.last_scan_started is None) or ((now - t.last_scan_started) >= interval)
                if due:
                    queue_scan(t.id)
        finally:
            db.close()

_scheduler_singleton: Optional[Scheduler] = None
def attach_scheduler(app, session_factory: sessionmaker = None,
                     tick_seconds: int = 30, max_concurrency: int = 2):
    """Attach a scheduler but do NOT start it automatically."""
    global _scheduler_singleton
    _scheduler_singleton = Scheduler(session_factory or SessionLocal,
                                     tick_seconds=tick_seconds,
                                     max_concurrency=max_concurrency)
    # we'll start/stop explicitly from routes
    return _scheduler_singleton
def queue_scan(target_id: int):
    from .pipeline import queue_scan as _q
    _q(target_id)

def ensure_pipeline_workers(session_factory: sessionmaker, concurrency: int = 2):
    from .pipeline import ensure_pipeline_workers as _e
    _e(session_factory or SessionLocal, concurrency=concurrency)