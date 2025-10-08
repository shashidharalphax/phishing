from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, Response
from sqlalchemy.orm import Session
from weasyprint import HTML

from ..db import get_db
from ..models import TargetDomain
from ..services.reporter import (
    render_target_report_html,
    render_candidate_report_html,
    save_target_report,
)

router = APIRouter(prefix="/reports", tags=["reports"])


# HTML report
@router.get("/targets/{target_id}/html", response_class=HTMLResponse)
def report_html(target_id: int, db: Session = Depends(get_db)):
    t = db.query(TargetDomain).get(target_id)
    if not t:
        raise HTTPException(404, "Target not found")
    html = render_target_report_html(db, target_id)
    return HTMLResponse(content=html, status_code=200)


# HTML file download
@router.get("/targets/{target_id}/download")
def report_download(target_id: int, db: Session = Depends(get_db)):
    t = db.query(TargetDomain).get(target_id)
    if not t:
        raise HTTPException(404, "Target not found")
    path = save_target_report(db, target_id)
    return FileResponse(path, media_type="text/html", filename=path.split("/")[-1])


# ✅ PDF with screenshots
@router.get("/targets/{target_id}/pdf")
def report_pdf(target_id: int, db: Session = Depends(get_db)):
    """Generate and return a PDF report including screenshots."""
    html_str = render_target_report_html(db, target_id)

    BASE_URL = "http://127.0.0.1:8000"  # must be accessible by WeasyPrint

    pdf_bytes = HTML(string=html_str, base_url=BASE_URL).write_pdf()
    filename = f"report_{target_id}.pdf"

    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# Candidate HTML report (optional)
@router.get("/candidates/{candidate_id}/html", response_class=HTMLResponse)
def candidate_html(candidate_id: int, db: Session = Depends(get_db)):
    html = render_candidate_report_html(db, candidate_id)
    return HTMLResponse(content=html, status_code=200)