# phishguard/services/crt_poller.py
import os
import time
import threading
import logging
from typing import Iterable, Set

import requests
from sqlalchemy.orm import sessionmaker

from ..db import engine
from ..models import TargetDomain  # adjust if your model name differs
# from ..models import Candidate, ScanJob  # uncomment if you insert jobs here

log = logging.getLogger("phishguard.crt_poller")

USER_AGENT = "phishguard-crt-poller/1.0 (+https://yourdomain.example)"
DEFAULT_INTERVAL = int(os.getenv("CRTSH_POLL_SECONDS", "600"))  # 10 min
ENABLE = os.getenv("ENABLE_CRT_POLL", "0") == "1"

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def fetch_crtsh_for(root: str) -> Set[str]:
    """
    Query crt.sh for subdomains of `root` (example.com) and return discovered FQDNs.
    """
    url = "https://crt.sh/"
    # Pass params so requests URL-encodes % automatically (%.example.com)
    params = {"q": f"%.{root}", "output": "json"}
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("crt.sh query failed for %s: %s", root, e)
        return set()

    found = set()
    for row in data:
        names = (row.get("name_value") or "").splitlines()
        for name in names:
            d = name.strip().lower()
            if not d:
                continue
            # normalize
            if d.startswith("*."):
                d = d[2:]
            # keep only domain/subdomains of root
            if d == root or d.endswith("." + root):
                found.add(d)
    return found

def get_watchlist(session) -> Iterable[str]:
    """
    Read the roots you want to watch from DB (TargetDomain table).
    Adjust attribute name to your schema (e.g., .domain or .name).
    """
    # Example assumes TargetDomain has a column `domain`
    return [t.domain for t in session.query(TargetDomain).all()]

def process_discovered(session, domains: Set[str]) -> None:
    """
    TODO: Integrate with your pipeline.
    - Upsert candidates and/or create ScanJob entries.
    - Deduplicate against existing table to avoid re-creating the same jobs.
    """
    # Example (pseudo — adjust to your models/fields):
    # existing = {d for (d,) in session.query(Candidate.domain).all()}
    # for fqdn in sorted(domains - existing):
    #     session.add(Candidate(domain=fqdn, source="crtsh"))
    #     session.add(ScanJob(domain=fqdn, status="pending"))
    # session.commit()
    log.info("Discovered %d domains from crt.sh (implement persistence)", len(domains))

def _run_poller(stop_event: threading.Event, interval_seconds: int):
    session = SessionLocal()
    try:
        while not stop_event.is_set():
            try:
                roots = list(get_watchlist(session))
                all_found = set()
                for i, root in enumerate(roots):
                    if stop_event.is_set():
                        break
                    found = fetch_crtsh_for(root)
                    all_found |= found
                    # be polite to crt.sh if watching many roots
                    time.sleep(0.5)
                if all_found:
                    process_discovered(session, all_found)
                # wait until next poll or until stopped
                stop_event.wait(interval_seconds)
            except Exception as e:
                log.exception("crt.sh polling loop error: %s", e)
                # short pause before retry on unexpected error
                if stop_event.wait(10):
                    break
    finally:
        session.close()

def attach_crt_poller(app, interval_seconds: int = DEFAULT_INTERVAL, enabled: bool | None = None):
    enabled = (ENABLE if enabled is None else enabled)
    if not enabled:
        log.info("CRT poller disabled (ENABLE_CRT_POLL=0)")
        return

    stop_event = threading.Event()

    @app.on_event("startup")
    async def _start():
        app.state.crt_stop_event = stop_event
        t = threading.Thread(target=_run_poller, args=(stop_event, interval_seconds), daemon=True)
        t.start()
        app.state.crt_thread = t
        log.info("CRT poller started (interval=%ss)", interval_seconds)

    @app.on_event("shutdown")
    async def _stop():
        stop_event.set()
        t = getattr(app.state, "crt_thread", None)
        if t:
            t.join(timeout=5)
        log.info("CRT poller stopped")