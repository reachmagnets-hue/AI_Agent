from fastapi import APIRouter, BackgroundTasks
import structlog
from app.services.email_inbox import sync_email_inbox

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/emails", tags=["emails"])

@router.post("/sync-inbox")
async def trigger_email_inbox_sync(background_tasks: BackgroundTasks):
    """
    Launch the AI Inbox Reviewer to securely connect to IMAP, scan unread emails, 
    and automatically extract meeting bookings for active leads.
    """
    async def run_sync():
        await sync_email_inbox()
        
    background_tasks.add_task(run_sync)
    return {"message": "Email Inbox AI Sync scheduled in the background."}
