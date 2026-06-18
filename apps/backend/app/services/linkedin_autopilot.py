import asyncio
import structlog
from uuid import UUID
from datetime import datetime

from app.core.database import SessionLocal
from app.models.lead import Lead
from app.models.campaign import Campaign
from app.services.linkedin_scraper import scrape_linkedin_leads
from app.services.linkedin_sender import send_linkedin_campaign
from app.utils.linkedin_generator import generate_linkedin_message
from app.core.websocket import websocket_manager

logger = structlog.get_logger(__name__)

async def run_linkedin_autopilot(campaign_id: str, industry: str, limit: int):
    """
    Unified background task to:
    1. Scrape leads for the target industry and assign them to the campaign.
    2. Generate personalized LinkedIn messages using Gemini 2.5 Flash.
    3. Send connection invitations using Playwright.
    """
    logger.info("Starting LinkedIn Autopilot run", campaign_id=campaign_id, industry=industry, limit=limit)
    
    # Broadcast start of scraping
    await websocket_manager.broadcast({
        "event": "autopilot_status",
        "campaign_id": campaign_id,
        "stage": "scraping",
        "message": f"Starting lead discovery for '{industry}'..."
    })

    # Step 1: Scrape leads
    try:
        scrape_res = await scrape_linkedin_leads(industry=industry, limit=limit, campaign_id=campaign_id)
        scraped_count = scrape_res.get("scraped", 0)
        logger.info("Autopilot Step 1 complete: Scraped leads", campaign_id=campaign_id, count=scraped_count)
        
        await websocket_manager.broadcast({
            "event": "autopilot_status",
            "campaign_id": campaign_id,
            "stage": "generating_messages",
            "message": f"Discovered {scraped_count} leads. Starting AI message generation..."
        })
    except Exception as e:
        logger.error("Autopilot Step 1 failed", campaign_id=campaign_id, error=str(e))
        await websocket_manager.broadcast({
            "event": "autopilot_status",
            "campaign_id": campaign_id,
            "stage": "failed",
            "message": f"Autopilot failed during scraping: {str(e)}"
        })
        _update_campaign_status(campaign_id, "paused")
        return

    # Step 2: Message Generation
    try:
        db = SessionLocal()
        try:
            leads = db.query(Lead).filter(
                Lead.campaign_id == UUID(campaign_id),
                Lead.linkedin_url.isnot(None),
                Lead.linkedin_message.is_(None),
                Lead.is_active == True
            ).all()
            lead_data = [(lead.id, lead.full_name, lead.business_name, lead.business_type or industry) for lead in leads]
        finally:
            db.close()
            
        logger.info("Autopilot: Generating messages for leads", campaign_id=campaign_id, count=len(lead_data))
        
        for idx, (lid, name, biz, ind) in enumerate(lead_data):
            msg = await generate_linkedin_message(name, biz, ind)
            
            task_db = SessionLocal()
            try:
                item = task_db.query(Lead).filter(Lead.id == lid).first()
                if item:
                    item.linkedin_message = msg
                    task_db.commit()
            except Exception as e:
                logger.error("Error saving generated message", lead_id=str(lid), error=str(e))
            finally:
                task_db.close()
                
            await websocket_manager.broadcast({
                "event": "autopilot_status",
                "campaign_id": campaign_id,
                "stage": "generating_messages",
                "message": f"Generated message {idx + 1}/{len(lead_data)} for {name or 'prospect'}..."
            })
            
        logger.info("Autopilot Step 2 complete: Generated messages", campaign_id=campaign_id)
        await websocket_manager.broadcast({
            "event": "autopilot_status",
            "campaign_id": campaign_id,
            "stage": "sending",
            "message": "AI message drafts completed. Starting Playwright connection delivery..."
        })
    except Exception as e:
        logger.error("Autopilot Step 2 failed", campaign_id=campaign_id, error=str(e))
        await websocket_manager.broadcast({
            "event": "autopilot_status",
            "campaign_id": campaign_id,
            "stage": "failed",
            "message": f"Autopilot failed during message generation: {str(e)}"
        })
        _update_campaign_status(campaign_id, "paused")
        return

    # Step 3: Run outreach campaign
    try:
        outreach_res = await send_linkedin_campaign(campaign_id, limit)
        sent_count = outreach_res.get("sent", 0)
        logger.info("Autopilot Step 3 complete: Sent invitations", campaign_id=campaign_id, count=sent_count)
        
        _update_campaign_status(campaign_id, "completed")
        
        await websocket_manager.broadcast({
            "event": "autopilot_status",
            "campaign_id": campaign_id,
            "stage": "completed",
            "message": f"Autopilot run finished successfully! Sent {sent_count} invitations."
        })
    except Exception as e:
        logger.error("Autopilot Step 3 failed", campaign_id=campaign_id, error=str(e))
        await websocket_manager.broadcast({
            "event": "autopilot_status",
            "campaign_id": campaign_id,
            "stage": "failed",
            "message": f"Autopilot failed during outreach: {str(e)}"
        })
        _update_campaign_status(campaign_id, "paused")

def _update_campaign_status(campaign_id: str, status: str):
    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter(Campaign.id == UUID(campaign_id)).first()
        if campaign:
            campaign.status = status
            if status == "completed":
                campaign.completed_at = datetime.now()
            db.commit()
    except Exception as e:
        logger.error("Failed to update campaign status during autopilot", campaign_id=campaign_id, error=str(e))
    finally:
        db.close()
