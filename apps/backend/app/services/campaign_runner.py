import asyncio
import structlog
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import Any, cast
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.campaign import Campaign
from app.models.lead import Lead

logger = structlog.get_logger(__name__)

# Keep track of campaigns currently running their dialer loops in memory to avoid duplicate tasks
RUNNING_CAMPAIGNS = set()

def is_within_allowed_run_windows() -> bool:
    """
    Checks if current local time in India (IST, UTC+5:30) falls within the allowed windows:
    - 8:00 PM - 10:00 PM (20:00 to 22:00)
    - 12:00 AM - 1:00 AM (00:00 to 01:00)
    - 3:00 AM - 4:00 AM (03:00 to 04:00)
    """
    from app.core.config import get_settings
    settings = get_settings()
    if settings.BYPASS_TIME_GATING:
        return True

    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(timezone.utc).astimezone(ist_tz)
    
    hour = now_ist.hour
    minute = now_ist.minute
    
    # Check Window 1: 8:00 PM - 10:00 PM (20:00 - 22:00)
    if 20 <= hour < 22:
        return True
        
    # Check Window 2: 12:00 AM - 1:00 AM (00:00 - 01:00)
    if hour == 0:
        return True
        
    # Check Window 3: 3:00 AM - 4:00 AM (03:00 - 04:00)
    if hour == 3:
        return True
        
    return False

async def run_active_campaigns():
    """
    Scans for active campaigns and spawns a dialer loop for them if not already running,
    provided we are within allowed calling windows.
    """
    if not is_within_allowed_run_windows():
        logger.debug("Currently outside campaign running windows. Skipping active campaigns check.")
        return

    db = SessionLocal()
    try:
        active_campaigns = db.query(Campaign).filter(Campaign.status == "active").all()
        for campaign in active_campaigns:
            if campaign.id not in RUNNING_CAMPAIGNS:
                logger.info("Found active campaign to run", campaign_id=str(campaign.id), name=campaign.name)
                asyncio.create_task(run_campaign_dialer_loop(cast(Any, campaign.id)))
    except Exception as e:
        logger.error("Error checking active campaigns in background runner", error=str(e))
    finally:
        db.close()

async def run_campaign_dialer_loop(campaign_id: UUID):
    """
    Sequentially processes pending leads for an active campaign, making outbound calls.
    Respects rate limits, calling hours, and automatically handles pause/completion states.
    """
    if campaign_id in RUNNING_CAMPAIGNS:
        return
        
    RUNNING_CAMPAIGNS.add(campaign_id)
    logger.info("Dialer loop started for campaign", campaign_id=str(campaign_id))
    
    try:
        from app.services.retell_service import RetellService
        from app.routers.campaigns import make_single_call_sqlalchemy
        
        retell_service = RetellService()
        
        while True:
            # Check calling windows
            if not is_within_allowed_run_windows():
                logger.info("Exiting campaign dialer loop: outside allowed calling windows", campaign_id=str(campaign_id))
                break
                
            db = SessionLocal()
            lead_id = None
            try:
                campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
                if not campaign or campaign.status != "active":
                    logger.info("Exiting campaign dialer loop: campaign is no longer active", campaign_id=str(campaign_id))
                    break
                    
                # Pull next pending lead
                lead = db.query(Lead).filter(
                    Lead.campaign_id == campaign_id,
                    Lead.status == "pending",
                    Lead.is_dnc == False,
                    Lead.is_active == True
                ).order_by(Lead.created_at).first()
                
                if not lead:
                    logger.info("No more pending leads found. Campaign completed.", campaign_id=str(campaign_id))
                    setattr(campaign, "status", "completed")
                    setattr(campaign, "completed_at", datetime.now(timezone.utc))
                    db.commit()
                    break
                    
                lead_id = cast(Any, lead.id)
            except Exception as e:
                logger.error("Error inside campaign dialer loop db query", campaign_id=str(campaign_id), error=str(e))
                break
            finally:
                db.close()
                
            # Check if this is an email-only campaign based on campaign name
            is_email_only = False
            db_check = SessionLocal()
            try:
                camp_check = db_check.query(Campaign).filter(Campaign.id == campaign_id).first()
                if camp_check and camp_check.name:
                    name_lower = camp_check.name.lower()
                    if "email" in name_lower or "e mail" in name_lower:
                        is_email_only = True
            except Exception as check_err:
                logger.error("Error checking campaign type", error=str(check_err))
            finally:
                db_check.close()

            if is_email_only:
                logger.info("Processing email-only campaign lead", campaign_id=str(campaign_id), lead_id=str(lead_id))
                db_update = SessionLocal()
                try:
                    db_item = db_update.query(Lead).filter(Lead.id == lead_id).first()
                    if db_item:
                        if db_item.email:
                            from app.utils.automations import send_outreach_email
                            # Update lead status to calling/sending to prevent double execution
                            db_item.status = "calling"
                            db_update.commit()
                            
                            # Send email
                            success = await send_outreach_email(
                                to_email=str(db_item.email),
                                to_name=db_item.full_name or "there",
                                business_name=db_item.business_name,
                                business_type=db_item.business_type,
                                lead_id=str(db_item.id)
                            )
                            
                            # Re-fetch item to update status
                            db_item = db_update.query(Lead).filter(Lead.id == lead_id).first()
                            if db_item:
                                db_item.status = "called" if success else "failed"
                                db_update.commit()
                            logger.info("Email outreach complete for lead", lead_id=str(lead_id), success=success)
                        else:
                            db_item.status = "failed"
                            db_item.internal_notes = "Skipped: Lead has no email address."
                            db_update.commit()
                            logger.warning("Lead skipped: no email", lead_id=str(lead_id))
                except Exception as update_err:
                    logger.error("Error processing email campaign lead", lead_id=str(lead_id), error=str(update_err))
                finally:
                    db_update.close()
                
                # Small delay to keep event loop alive and stagger sends
                await asyncio.sleep(1.0)
            else:
                # Place outbound call
                logger.info("Placing outbound call for lead", campaign_id=str(campaign_id), lead_id=str(lead_id))
                await make_single_call_sqlalchemy(lead_id, campaign_id, retell_service)
                
                # Rate limit cooldown (1.5 seconds)
                await asyncio.sleep(1.5)
            
    except Exception as e:
        logger.error("Error in campaign dialer loop executor", campaign_id=str(campaign_id), error=str(e))
    finally:
        RUNNING_CAMPAIGNS.discard(campaign_id)
        logger.info("Dialer loop stopped for campaign", campaign_id=str(campaign_id))

def start_campaign_dialer(campaign_id: UUID):
    """Convenience trigger to immediately spin up the campaign dialer loop"""
    asyncio.create_task(run_campaign_dialer_loop(campaign_id))
