from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
from datetime import datetime
import structlog

from app.core.database import get_db, SessionLocal
from app.models.lead import Lead
from app.models.campaign import Campaign
from app.services.linkedin_scraper import scrape_linkedin_leads
from app.services.linkedin_sender import send_linkedin_campaign
from app.utils.linkedin_generator import generate_linkedin_message
from app.services.linkedin_autopilot import run_linkedin_autopilot
from app.services.linkedin_inbox import sync_linkedin_inbox

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/linkedin", tags=["linkedin"])

@router.post("/search")
async def trigger_linkedin_search(
    background_tasks: BackgroundTasks,
    industry: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    campaign_id: Optional[str] = Query(None),
    location: Optional[str] = Query(None)
):
    """
    Trigger Playwright lead discovery search for target industry and location.
    Imports discovered prospects into target campaign.
    """
    if campaign_id:
        try:
            UUID(campaign_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid campaign ID UUID format")

    async def run_search_task():
        await scrape_linkedin_leads(industry=industry, limit=limit, campaign_id=campaign_id, location=location)
        
    background_tasks.add_task(run_search_task)
    return {"message": f"LinkedIn lead search for '{industry}' in '{location or 'Anywhere'}' has been scheduled.", "limit": limit}


@router.post("/generate-messages")
async def generate_linkedin_messages_campaign(
    campaign_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger Gemini message generation for all pending LinkedIn leads in a campaign.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    leads = db.query(Lead).filter(
        Lead.campaign_id == campaign_id,
        Lead.linkedin_url.isnot(None),
        Lead.linkedin_message.is_(None),
        Lead.is_active == True
    ).all()
    
    if not leads:
        return {"message": "No pending leads requiring LinkedIn message generation."}
        
    lead_data = [(lead.id, lead.full_name, lead.business_name, lead.business_type or "industry") for lead in leads]
    
    async def process_generation():
        logger.info("Starting bulk LinkedIn message generation", campaign_id=str(campaign_id), count=len(lead_data))
        for lid, name, biz, ind in lead_data:
            msg = await generate_linkedin_message(str(name or ""), str(biz or ""), str(ind or ""))
            
            task_db = SessionLocal()
            try:
                item = task_db.query(Lead).filter(Lead.id == lid).first()
                if item:
                    item.linkedin_message = msg  # type: ignore
                    task_db.commit()
            except Exception as e:
                logger.error("Error saving generated message", lead_id=str(lid), error=str(e))
            finally:
                task_db.close()
                
    background_tasks.add_task(process_generation)
    return {"message": f"Scheduled message generation for {len(leads)} leads in the background."}


@router.post("/start-campaign")
async def start_linkedin_campaign_run(
    campaign_id: UUID,
    background_tasks: BackgroundTasks,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Launch automated Playwright connection invitation & message queue.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    # Check if there are messages ready
    ready_count = db.query(Lead).filter(
        Lead.campaign_id == campaign_id,
        Lead.linkedin_url.isnot(None),
        Lead.linkedin_message.isnot(None),
        Lead.linkedin_sent_at.is_(None),
        Lead.is_active == True
    ).count()
    
    if ready_count == 0:
        raise HTTPException(status_code=400, detail="No leads with generated LinkedIn messages ready to send in this campaign.")
        
    background_tasks.add_task(send_linkedin_campaign, str(campaign_id), limit)
    
    return {"message": f"LinkedIn campaign outreach started. Dispatching to {min(ready_count, limit)} leads."}


@router.get("/stats")
def get_linkedin_campaign_stats(campaign_id: UUID, db: Session = Depends(get_db)):
    """
    Get statistical outreach metrics for a LinkedIn campaign.
    """
    total = db.query(Lead).filter(Lead.campaign_id == campaign_id, Lead.linkedin_url.isnot(None), Lead.is_active == True).count()
    scraped = db.query(Lead).filter(Lead.campaign_id == campaign_id, Lead.linkedin_url.isnot(None), Lead.source.like("linkedin_scraper%"), Lead.is_active == True).count()
    pending_generation = db.query(Lead).filter(Lead.campaign_id == campaign_id, Lead.linkedin_url.isnot(None), Lead.linkedin_message.is_(None), Lead.is_active == True).count()
    ready_to_send = db.query(Lead).filter(Lead.campaign_id == campaign_id, Lead.linkedin_url.isnot(None), Lead.linkedin_message.isnot(None), Lead.linkedin_sent_at.is_(None), Lead.is_active == True).count()
    sent = db.query(Lead).filter(Lead.campaign_id == campaign_id, Lead.linkedin_url.isnot(None), Lead.linkedin_sent_at.isnot(None), Lead.is_active == True).count()
    
    return {
        "total": total,
        "scraped": scraped,
        "pending_generation": pending_generation,
        "ready_to_send": ready_to_send,
        "sent": sent
    }


@router.post("/autopilot")
async def trigger_linkedin_autopilot(
    background_tasks: BackgroundTasks,
    industry: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    location: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Launch fully automated end-to-end autopilot outreach:
    1. Create a Campaign record
    2. Start sequential lead scraping, message drafting, and invitation delivery
    """
    # Create a new campaign
    campaign_name = f"Autopilot - {industry.capitalize()} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    if location:
        campaign_name = f"Autopilot - {industry.capitalize()} ({location}) - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
    campaign = Campaign(
        name=campaign_name,
        description=f"Automated end-to-end LinkedIn autopilot campaign for industry: {industry} in location: {location or 'Anywhere'}",
        status="active"
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    background_tasks.add_task(run_linkedin_autopilot, str(campaign.id), industry, limit, location)
    
    return {
        "message": f"LinkedIn Autopilot initiated for industry '{industry}' in '{location or 'Anywhere'}'.",
        "campaign_id": str(campaign.id),
        "campaign_name": campaign_name
    }


@router.post("/sync-inbox")
async def trigger_linkedin_inbox_sync(background_tasks: BackgroundTasks):
    """
    Launch the AI Inbox Reviewer to scan LinkedIn messages and automatically extract meeting bookings.
    """
    async def run_sync():
        await sync_linkedin_inbox()
        
    if background_tasks:
        background_tasks.add_task(run_sync)
        return {"message": "LinkedIn Inbox AI Sync scheduled in the background."}
    else:
        # Run synchronously if no background_tasks provided (for testing)
        result = await sync_linkedin_inbox()
        return result

