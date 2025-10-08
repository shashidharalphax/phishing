from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from .db import Base, engine
from .routes import targets, results, reports
from .services.scheduler import attach_scheduler
from .services.ctwatcher import attach_ctwatcher
from .services.crt_poller import attach_crt_poller
from .config import SCHEDULER_TICK_SECONDS, WORKER_CONCURRENCY

# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

app = FastAPI(title="PhishGuard", version="0.1.0")

# ---------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------
app.include_router(targets.router)
app.include_router(results.router)
app.include_router(reports.router)

# ---------------------------------------------------------------------
#  ✅  Mount /screens FIRST (before “/”)
# ---------------------------------------------------------------------
SCREEN_DIR = "/home/admincit/etherX/Phishing_detection/Backend/phishguard/phishguard/screens"
print("✅ [DEBUG] Mounting /screens from:", SCREEN_DIR)
app.mount("/screens", StaticFiles(directory=os.path.abspath(SCREEN_DIR)), name="screens")

# ---------------------------------------------------------------------
#  Root static UI MOUNTED AFTER /screens
# ---------------------------------------------------------------------
STATIC_UI = os.path.join(os.path.dirname(__file__), "static")
print("✅ [DEBUG] Mounting / from:", STATIC_UI)
app.mount("/", StaticFiles(directory=STATIC_UI, html=True), name="static")

# ---------------------------------------------------------------------
# Background services
# ---------------------------------------------------------------------
attach_scheduler(
    app,
    session_factory=None,
    tick_seconds=SCHEDULER_TICK_SECONDS,
    max_concurrency=WORKER_CONCURRENCY,
)
attach_crt_poller(app)