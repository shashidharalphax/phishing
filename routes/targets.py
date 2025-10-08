import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi import UploadFile, File
import io, csv

from ..db import get_db, SessionLocal
from ..models import TargetDomain
from ..services.pipeline import queue_scan, ensure_pipeline_workers

router = APIRouter(prefix="/targets", tags=["targets"])

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# -------------------------------------------------------------------
# Global controls
active_scan_task: asyncio.Task | None = None
stop_flag = asyncio.Event()
# -------------------------------------------------------------------

@router.get("/", response_model=list[dict])
def list_targets(db: Session = Depends(get_db)):
    rows = db.query(TargetDomain).order_by(TargetDomain.id.asc()).all()
    out = []
    for t in rows:
        status = "ORIGINAL (CSE)" if t.is_verified else "INCOMPLETE"
        out.append(dict(
            id=t.id, domain=t.domain, brand=t.brand,
            homepage_url=t.homepage_url,
            notes=t.notes, is_verified=t.is_verified, is_active=t.is_active,
            scan_interval_minutes=t.scan_interval_minutes, status=status
        ))
    return out


# -------------------------------------------------------------------
@router.post("/start", response_model=dict)
async def start_scanning(db: Session = Depends(get_db)):
    """Sequential scan with 5‑minute delay per target."""
    global active_scan_task, stop_flag
    if active_scan_task and not active_scan_task.done():
        raise HTTPException(400, "Scan already running")

    stop_flag.clear()
    ensure_pipeline_workers(SessionLocal, concurrency=2)

    targets = db.query(TargetDomain).filter(TargetDomain.is_verified == True).order_by(TargetDomain.id.asc()).all()
    if not targets:
        raise HTTPException(400, "No verified targets")

    logging.info(f"Starting sequential scan of {len(targets)} domains")

    async def sequential_runner():
    #"""Loop indefinitely until stop_flag is set."""
        cycle = 0
        while not stop_flag.is_set():
            cycle += 1
            logging.info(f"♻️  Starting scan cycle {cycle}")
            for idx, t in enumerate(targets, start=1):
                asyncio.current_task().set_name(t.domain)
                if stop_flag.is_set():
                    logging.info("Stop flag set, cancelling sequence")
                    break
                logging.info(f"[cycle {cycle}] [{idx}/{len(targets)}] Queuing scan for {t.domain}")
                queue_scan(t.id)
                await asyncio.sleep(300)   # 5 min per domain
         # optional pause between cycles
            logging.info("♻️  Completed one full cycle — starting again in 60 seconds")
            await asyncio.sleep(60)

    active_scan_task = asyncio.create_task(sequential_runner())
    return {"status": "started", "domains": len(targets)}
# -------------------------------------------------------------------


@router.post("/stop", response_model=dict)
async def stop_scanning():
    global active_scan_task, stop_flag
    stop_flag.set()
    if active_scan_task and not active_scan_task.done():
        active_scan_task.cancel()
    logging.info("Stopped sequential scanning")
    return {"status": "stopped"}


# -------------------------------------------------------------------
# 🔍 NEW: simple status endpoint for dashboard progress
@router.get("/status", response_model=dict)
async def scan_status():
    """Report current scanning progress for dashboard."""
    global active_scan_task, stop_flag
    running = bool(active_scan_task and not active_scan_task.done())
    current = None
    try:
        current = active_scan_task.get_name()
    except Exception:
        pass
    return {
        "running": running,
        "current_target": current or "Idle",
        "stopped": stop_flag.is_set()
    }
# -------------------------------------------------------------------


@router.post("/bulk", response_model=dict)
async def bulk_upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Handle CSV/XLSX bulk upload of target domains."""
    data = await file.read()
    text = data.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    count = 0

    for row in reader:
        domain = row.get("domain")
        if not domain:
            continue
        brand = row.get("brand", "")
        homepage = row.get("homepage_url", "")
        # avoid duplicates
        exists = db.query(TargetDomain).filter(TargetDomain.domain == domain).first()
        if exists:
            continue
        t = TargetDomain(
            domain=domain.strip().lower(),
            brand=brand.strip() or None,
            homepage_url=homepage.strip() or None,
            is_verified=True,
            is_active=True,
        )
        db.add(t)
        count += 1

    db.commit()
    return {"status": "ok", "inserted": count}
# -------------------------------------------------------------------