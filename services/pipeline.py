import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
import tldextract

from sqlalchemy.orm import sessionmaker

from ..models import TargetDomain, ScanJob, Candidate
from ..db import SessionLocal
from ..core.enrich import enrich_candidate
from ..core.screenshot import capture_screens
from ..core.similarity import compute_similarity
from ..core.classify import classify_candidate

logger = logging.getLogger(__name__)

SCAN_QUEUE: Optional[asyncio.Queue] = None
WORKERS: List[asyncio.Task] = []
QUEUED_TARGETS: set[int] = set()
SESSION_FACTORY: Optional[sessionmaker] = None

TUNNEL_HOSTS = [
    "ngrok.io", "trycloudflare.com", "loca.lt", "serveo.net",
    "pages.dev", "github.io", "cloudfront.net"
]

def ensure_pipeline_workers(session_factory: sessionmaker, concurrency: int = 1):
    global SCAN_QUEUE, WORKERS, SESSION_FACTORY
    if SCAN_QUEUE is not None:
        return
    SESSION_FACTORY = session_factory or SessionLocal
    SCAN_QUEUE = asyncio.Queue()
    WORKERS = [asyncio.create_task(_worker_loop(i)) for i in range(max(1, int(concurrency)))]
    logger.info("Pipeline workers started x%s", len(WORKERS))

def queue_scan(target_id: int):
    if SCAN_QUEUE is None:
        raise RuntimeError("Pipeline not initialized")
    if target_id in QUEUED_TARGETS:
        return
    QUEUED_TARGETS.add(target_id)
    SCAN_QUEUE.put_nowait(target_id)
    logger.info("Queued target %s", target_id)

async def _worker_loop(idx: int):
    while True:
        target_id = await SCAN_QUEUE.get()
        try:
            await asyncio.to_thread(_scan_target_sync, target_id)
        except Exception as e:
            logger.exception("Worker %s failed target %s: %s", idx, target_id, e)
        finally:
            QUEUED_TARGETS.discard(target_id)
            SCAN_QUEUE.task_done()

def _scan_target_sync(target_id: int):
    db = SESSION_FACTORY() if SESSION_FACTORY else SessionLocal()
    job: Optional[ScanJob] = None
    try:
        target: TargetDomain = db.query(TargetDomain).get(target_id)
        if not target or not target.is_verified or not target.is_active:
            return

        job = ScanJob(target_id=target.id, status="RUNNING")
        db.add(job)
        target.last_scan_started = datetime.utcnow()
        db.commit(); db.refresh(job)

        candidates = _discover_candidates(target.domain, target.brand)
        logger.info("Target %s discovery: %s candidates", target.domain, len(candidates))

        for cand in candidates:
            _process_candidate_sync(db, target, cand)

        job.status = "DONE"
        job.finished_at = datetime.utcnow()
        target.last_scan_finished = datetime.utcnow()
        db.commit()

    except Exception as e:
        logger.exception("scan_target_sync error: %s", e)
        if job:
            job.status = "FAILED"
            db.commit()
    finally:
        db.close()

def _discover_candidates(original_domain: str, brand: Optional[str]) -> List[Dict]:
    out: List[Dict] = []
    ext = tldextract.extract(original_domain)
    base_domain = ext.domain
    suffix = ext.suffix

    for cand in _gen_typos(base_domain)[:400]:
        fqdn = f"{cand}.{suffix}"
        ext2 = tldextract.extract(fqdn)
        out.append({
            "source": "permutation",
            "fqdn": fqdn,
            "tld": ext2.suffix,
            "registrable_domain": f"{ext2.domain}.{ext2.suffix}",
            "url": f"http://{fqdn}"
        })

    brand_part = (brand or base_domain).lower()
    for host in TUNNEL_HOSTS:
        fqdn = f"{brand_part}.{host}"
        ext2 = tldextract.extract(fqdn)
        out.append({
            "source": "tunnel_hint",
            "fqdn": fqdn,
            "tld": ext2.suffix,
            "registrable_domain": f"{ext2.domain}.{ext2.suffix}",
            "url": f"http://{fqdn}"
        })

    out = [c for c in out if c["fqdn"] != original_domain]
    seen = set(); dedup = []
    for c in out:
        if c["fqdn"] in seen: continue
        seen.add(c["fqdn"]); dedup.append(c)
    return dedup

def _process_candidate_sync(db, target: TargetDomain, cand: Dict):
    c = Candidate(
        target_id=target.id,
        source=cand.get("source","unknown"),
        fqdn=cand["fqdn"],
        url=cand.get("url") or f"http://{cand['fqdn']}",
        tld=cand.get("tld"),
        registrable_domain=cand.get("registrable_domain"),
        label="UNKNOWN",
    )
    db.add(c); db.commit(); db.refresh(c)

    meta = enrich_candidate(c.fqdn)
    c.metadata = meta
    db.commit()

    paths = capture_screens(target.homepage_url or f"http://{target.domain}", c.url, out_dir="screens")
    c.original_screenshot_path = paths.get("orig")
    c.screenshot_path = paths.get("cand")
    db.commit()

    sim = compute_similarity(paths.get("orig"), paths.get("cand"), cand_url=c.url)
    c.img_phash = sim.get("phash")
    c.img_sim = sim.get("img_sim")
    c.html_hash = sim.get("html_hash")
    c.html_sim = sim.get("html_sim")
    db.commit()

    label, score, reason = classify_candidate(target, c, meta, sim)
    c.label, c.score, c.reason = label, float(score or 0.0), reason
    db.commit()

# Direct submit from CT watcher
def submit_candidate(target_id: int, fqdn: str, source: str = "ctstream", url: Optional[str] = None):
    db = SESSION_FACTORY() if SESSION_FACTORY else SessionLocal()
    try:
        target = db.query(TargetDomain).get(target_id)
        if not target or not target.is_active or not target.is_verified:
            return
        cand = {"source": source, "fqdn": fqdn, "url": url or f"http://{fqdn}"}
        _process_candidate_sync(db, target, cand)
    except Exception as e:
        logger.exception("submit_candidate failed: %s", e)
    finally:
        db.close()

# Typos
QWERTY_ADJ = {
    "a":"qwsz", "s":"awedxz", "d":"serfxc", "f":"drtgcv", "g":"ftyhbv", "h":"gyujnb",
    "j":"huikmn", "k":"jiolm,", "l":"kop;.", "q":"was", "w":"qeas", "e":"wsdr",
    "r":"edft", "t":"rfgy", "y":"tghu", "u":"yjh", "i":"ujk", "o":"iklp", "p":"ol"
}
def _gen_typos(s: str):
    s = s.lower()
    var = set()
    for i in range(len(s)):
        var.add(s[:i]+s[i+1:])
    for i in range(len(s)-1):
        var.add(s[:i]+s[i+1]+s[i]+s[i+2:])
    for i,c in enumerate(s):
        for r in QWERTY_ADJ.get(c,""):
            var.add(s[:i]+r+s[i+1:])
    for i in range(len(s)+1):
        for c in "abcdefghijklmnopqrstuvwxyz":
            var.add(s[:i]+c+s[i:])
    if "-" not in s and len(s)>3:
        var.add(s[:len(s)//2]+"-"+s[len(s)//2:])
    return [v for v in var if 2 <= len(v) <= 32]