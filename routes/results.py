from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List

from ..db import get_db
from ..models import Candidate, TargetDomain
from ..services.reporter import render_candidate_report_html  # import the new renderer

router = APIRouter(prefix="/results", tags=["results"])


@router.get("/{target_id}", response_model=List[dict])
def list_results(target_id: int, db: Session = Depends(get_db)):
    """Return all candidate entries belonging to one target."""
    t = db.query(TargetDomain).get(target_id)
    if not t:
        raise HTTPException(404, "target not found")

    q = (
        db.query(Candidate)
        .filter(Candidate.target_id == target_id)
        .order_by(Candidate.created_at.desc())
    )
    rows = q.all()
    out = []
    for c in rows:
        out.append(
            dict(
                id=c.id,
                fqdn=c.fqdn,
                url=c.url,
                label=c.label or "UNKNOWN",
                reason=c.reason or "",
                score=float(c.score or 0.0),
                img_sim=float(c.img_sim or 0.0),
                html_sim=float(c.html_sim or 0.0),
                screenshot_path=c.screenshot_path,
                original_screenshot_path=c.original_screenshot_path,
                metadata=c.metadata_json,  # ✅ renamed
            )
        )
    return out


# ---------------------------------------------------------------------
# 🔍  NEW:  individual candidate HTML report route
# ---------------------------------------------------------------------
@router.get("/candidates/{candidate_id}/html", response_class=HTMLResponse)
def candidate_report_html(candidate_id: int, db: Session = Depends(get_db)):
    """
    Return a single-candidate HTML report.
    Useful when a user wants a dedicated report per discovered domain.
    """
    c = db.query(Candidate).get(candidate_id)
    if not c:
        raise HTTPException(404, "Candidate not found")

    html = render_candidate_report_html(db, candidate_id)
    return HTMLResponse(content=html, status_code=200)


# ---------------------------------------------------------------------
# 🔍  OPTIONAL:  individual candidate PDF download
#               (requires  `pip install weasyprint`)
# ---------------------------------------------------------------------
try:
    from weasyprint import HTML
    from fastapi.responses import Response

    @router.get("/candidates/{candidate_id}/pdf")
    def candidate_report_pdf(candidate_id: int, db: Session = Depends(get_db)):
        """
        Generate and return a PDF version of the candidate report.
        """
        c = db.query(Candidate).get(candidate_id)
        if not c:
            raise HTTPException(404, "Candidate not found")

        html_str = render_candidate_report_html(db, candidate_id)
        pdf_bytes = HTML(string=html_str).write_pdf()
        filename = f"candidate_report_{c.fqdn}.pdf"

        return Response(
            pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

except Exception:
    # if WeasyPrint is not installed, safely skip the PDF endpoint
    pass