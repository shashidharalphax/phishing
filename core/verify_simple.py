from .enrich import enrich_candidate
from ..config import VERIFY_MIN_AGE_DAYS

PARKING_NS_HINTS = ["sedoparking", "afternic", "bodis", "parking", "dan.com", "parkingcrew"]

def _age_days(meta) -> int:
    try:
        events = meta.get("rdap", {}).get("events", [])
        for e in events:
            if "registration" in e.get("eventAction","").lower() or "creation" in e.get("eventAction","").lower():
                from datetime import datetime, timezone
                dt = datetime.fromisoformat(e["eventDate"].replace("Z","+00:00"))
                return max(0, (datetime.now(timezone.utc) - dt).days)
    except Exception:
        pass
    return 0

def _is_parked(meta) -> bool:
    ns = [x.lower() for x in meta.get("dns",{}).get("NS",[])]
    return any(any(h in n for h in PARKING_NS_HINTS) for n in ns)

def verify_simple(domain: str) -> bool:
    meta = enrich_candidate(domain)
    resolves = bool(meta.get("dns",{}).get("A") or meta.get("dns",{}).get("AAAA"))
    age_ok = _age_days(meta) >= VERIFY_MIN_AGE_DAYS
    not_parked = not _is_parked(meta)
    return bool(resolves and age_ok and not_parked)