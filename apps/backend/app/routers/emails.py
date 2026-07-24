from fastapi import APIRouter, BackgroundTasks, Depends, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import structlog
from datetime import datetime, timezone
from uuid import UUID

from app.core.database import get_db
from app.models.lead import Lead
from app.services.email_inbox import sync_email_inbox

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/emails", tags=["emails"])

# 1x1 transparent pixel GIF bytes
GIF_1X1 = b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b"

@router.post("/sync-inbox")
def trigger_email_inbox_sync(background_tasks: BackgroundTasks):
    """
    Launch the AI Inbox Reviewer to securely connect to IMAP, scan unread emails, 
    and automatically extract meeting bookings for active leads.
    """
    async def run_sync():
        await sync_email_inbox()
        
    background_tasks.add_task(run_sync)
    return {"message": "Email Inbox AI Sync scheduled in the background."}

@router.get("/track/open/{lead_id}")
def track_email_open(lead_id: UUID, db: Session = Depends(get_db)):
    """Tracking pixel endpoint returned as a transparent 1x1 pixel image"""
    logger.info("Email open tracked", lead_id=str(lead_id))
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead:
        now_utc = datetime.now(timezone.utc)
        # Don't downgrade status if already clicked or replied
        if lead.email_status not in ["clicked", "replied", "bounced", "blocked"]:
            lead.email_status = "opened"  # type: ignore
        if not lead.email_opened_at:
            lead.email_opened_at = now_utc  # type: ignore
        lead.updated_at = now_utc  # type: ignore
        db.commit()
    
    return Response(content=GIF_1X1, media_type="image/gif")

@router.get("/track/click/{lead_id}")
def track_email_click(lead_id: UUID, url: str, db: Session = Depends(get_db)):
    """Redirect link tracker endpoint"""
    logger.info("Email click tracked", lead_id=str(lead_id), redirect_url=url)
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead:
        now_utc = datetime.now(timezone.utc)
        if lead.email_status not in ["replied", "bounced", "blocked"]:
            lead.email_status = "clicked"  # type: ignore
        if not lead.email_clicked_at:
            lead.email_clicked_at = now_utc  # type: ignore
        lead.updated_at = now_utc  # type: ignore
        db.commit()

    return RedirectResponse(url=url)

