# phishguard/services/reporter.py
import os
import json
import logging
from datetime import datetime
from urllib.parse import quote
from sqlalchemy.orm import Session
from ..models import TargetDomain, Candidate

# ----------------------------------------------------------------------
# Directory setup
# ----------------------------------------------------------------------
REPORTS_DIR = os.path.join(os.getcwd(), "phishguard", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# Base URL used for <img src="..."> in both HTML and PDF
BASE_URL = "http://127.0.0.1:8000"

STYLE = '''
body{font-family:Arial,Helvetica,sans-serif;margin:20px;}
.card{border:1px solid #ddd;border-radius:8px;padding:12px;margin-bottom:16px;}
h1,h2{margin:0 0 12px 0;}
img{max-width:48%;border:1px solid #ccc;border-radius:4px;margin:3px;}
table{width:100%;border-collapse:collapse;margin-top:8px;}
td,th{border:1px solid #eee;padding:6px;text-align:left;}
.badge{display:inline-block;padding:2px 6px;border-radius:4px;background:#eee;margin-left:8px;}
'''

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def _badge(lbl):
    lbl = (lbl or "UNKNOWN").upper()
    if lbl.startswith("IDENTIFIED"):
        color = "red"
    elif lbl == "CLEAN":
        color = "green"
    else:
        color = "amber"
    return f'<span class="badge {color}">{lbl}</span>'


def _safe_meta(metadata, key):
    try:
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if isinstance(metadata, dict):
            return metadata.get(key)
        if hasattr(metadata, key):
            return getattr(metadata, key)
    except Exception:
        return None
    return None


def _image_tag(local_path: str, label: str) -> str:
    """
    Return an <img> tag usable in both the browser and PDF.
    Works even if the stored path is relative or absolute.
    """
    from urllib.parse import quote

    # directory where images really exist
    SCREEN_DIR = "/home/admincit/etherX/Phishing_detection/Backend/phishguard/phishguard/screens"

    if not local_path:
        return f"<p><b>{label}:</b> (no image)</p>"

    # always extract only the filename: orig_http_*.png / cand_http_*.png
    filename = os.path.basename(local_path)
    abs_path = os.path.join(SCREEN_DIR, filename)

    # check existence, then build proper web URL
    if os.path.isfile(abs_path):
        web_url = f"{BASE_URL}/screens/{quote(filename)}"
        return (
            f"<p><b>{label}:</b><br>"
            f"<img src='{web_url}' "
            f"style='max-width:45%;border:1px solid #ccc;margin:3px;'/></p>"
        )

    # if not found, show placeholder text
    return f"<p><b>{label}:</b> (image not found: {filename})</p>"


# ----------------------------------------------------------------------
# Target report
# ----------------------------------------------------------------------
def render_target_report_html(db: Session, target_id: int) -> str:
    t = db.query(TargetDomain).get(target_id)
    if not t:
        return "<h1>Target Not Found</h1>"

    rows = (
        db.query(Candidate)
        .filter(Candidate.target_id == target_id)
        .order_by(Candidate.score.desc().nullslast())
        .all()
    )

    parts = [
        f"<html><head><meta charset='utf-8'><style>{STYLE}</style></head><body>",
        f"<h1>Phishing Detection Report — {t.domain}</h1>",
        f"<p><small>Generated: {datetime.utcnow().isoformat()}Z</small></p>",
    ]

    for c in rows:
        parts.append('<div class="card">')
        parts.append(
            f"<h2>{c.fqdn} {_badge(c.label)} &nbsp; score={round(c.score or 0,2)}</h2>"
        )
        
        # ---------- Screenshots (absolute URLs) ----------
        parts.append(_image_tag(c.original_screenshot_path, "Original"))
        parts.append(_image_tag(c.screenshot_path, "Candidate"))
        # ---------- Data table ----------
        parts.append("<table>")
        for k, v in {
            "URL": c.url,
            "Reason": c.reason,
            "Image Similarity": round(c.img_sim or 0, 3),
            "HTML Similarity": round(c.html_sim or 0, 3),
            "pHash": c.img_phash,
            "HTML Hash": c.html_hash,
            "DNS": _safe_meta(c.metadata, "dns"),
            "IPs": _safe_meta(c.metadata, "ips"),
            "ASN": _safe_meta(c.metadata, "asn"),
            "RDAP": _safe_meta(c.metadata, "rdap"),
        }.items():
            parts.append(f"<tr><th>{k}</th><td><code>{v}</code></td></tr>")
        parts.append("</table></div>")

    parts.append("</body></html>")
    return "".join(parts)


# ----------------------------------------------------------------------
# Save target report to file
# ----------------------------------------------------------------------
def save_target_report(db: Session, target_id: int) -> str:
    t = db.query(TargetDomain).get(target_id)
    if not t:
        raise ValueError("Target not found")

    folder = os.path.join(REPORTS_DIR, t.domain)
    os.makedirs(folder, exist_ok=True)

    path = os.path.join(folder, f"report_{t.domain}.html")
    html = render_target_report_html(db, target_id)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    logging.info(f"Report saved at {path}")
    return path


# ----------------------------------------------------------------------
# Candidate report (single domain)
# ----------------------------------------------------------------------
def render_candidate_report_html(db: Session, candidate_id: int) -> str:
    c = db.query(Candidate).get(candidate_id)
    if not c:
        return "<h1>Candidate Not Found</h1>"

    t = db.query(TargetDomain).get(c.target_id)
    title = f"Phishing Analysis Report — {c.fqdn}"

    parts = [
        f"<html><head><meta charset='utf-8'><style>{STYLE}</style></head><body>",
        f"<h1>{title}</h1>",
        f"<p><small>Generated UTC: {datetime.utcnow().isoformat()}Z</small></p>",
        f"<h2>Parent Target: {t.domain}</h2>",
        f"<h2>{c.fqdn} {_badge(c.label)}  score={round(c.score or 0,2)}</h2>",
    ]

    parts.append(_image_tag(c.original_screenshot_path, "Original"))
    parts.append(_image_tag(c.screenshot_path, "Candidate"))

    parts.append("<table>")
    for k, v in {
        "URL": c.url,
        "Reason": c.reason,
        "Image Similarity": round(c.img_sim or 0,3),
        "HTML Similarity": round(c.html_sim or 0,3),
        "pHash": c.img_phash,
        "HTML Hash": c.html_hash,
        "DNS": _safe_meta(c.metadata, "dns"),
        "IPs": _safe_meta(c.metadata, "ips"),
        "ASN": _safe_meta(c.metadata, "asn"),
        "RDAP": _safe_meta(c.metadata, "rdap"),
    }.items():
        parts.append(f"<tr><th>{k}</th><td><code>{v}</code></td></tr>")
    parts.append("</table></body></html>")

    return "".join(parts)