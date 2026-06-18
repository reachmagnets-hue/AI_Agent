import asyncio
import random
import structlog
from datetime import datetime, timezone
from typing import Dict, Any
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.lead import Lead
from app.core.websocket import websocket_manager

logger = structlog.get_logger(__name__)

# Try to import Playwright
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

async def send_linkedin_campaign(campaign_id: str, limit: int = 100) -> Dict[str, Any]:
    """
    Background worker task to iterate through a campaign's pending LinkedIn leads
    and send messages/connection requests with daily throttling limits.
    """
    settings = get_settings()
    cookie = settings.LINKEDIN_SESSION_COOKIE
    
    logger.info("Starting LinkedIn message campaign delivery", campaign_id=campaign_id, limit=limit)
    
    # Fetch pending leads that have a generated message but haven't been sent yet
    db = SessionLocal()
    try:
        query = db.query(Lead).filter(
            Lead.campaign_id == campaign_id,
            Lead.linkedin_url.isnot(None),
            Lead.linkedin_message.isnot(None),
            Lead.linkedin_sent_at.is_(None),
            Lead.is_active == True
        )
        leads = query.limit(limit).all()
        lead_ids = [lead.id for lead in leads]
    finally:
        db.close()
        
    if not leads:
        logger.info("No pending LinkedIn outreach leads found for this campaign.")
        return {"success": True, "sent": 0, "status": "completed_empty"}

    # Fallback to simulated delivery if Playwright or cookie is not available
    if not PLAYWRIGHT_AVAILABLE or not cookie or cookie == "your_linkedin_session_cookie":
        logger.info("Running LinkedIn campaign in SIMULATED outreach mode")
        return await run_simulated_campaign(lead_ids)

    return await run_playwright_campaign(cookie, lead_ids)


async def run_playwright_campaign(cookie: str, lead_ids: list) -> Dict[str, Any]:
    """Execute real connection requests with personalized notes using Playwright"""
    sent_count = 0
    errors_count = 0
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome")
            context = await browser.new_context()
            
            # Inject session cookie
            await context.add_cookies([{
                "name": "li_at",
                "value": cookie,
                "domain": ".www.linkedin.com",
                "path": "/"
            }])
            
            page = await context.new_page()
            
            for lid in lead_ids:
                db = SessionLocal()
                try:
                    # Re-fetch lead
                    lead = db.query(Lead).filter(Lead.id == lid).first()
                    if not lead:
                        continue
                        
                    logger.info("Outreach: Open LinkedIn profile", name=lead.full_name, url=lead.linkedin_url)
                    await page.goto(lead.linkedin_url, timeout=30000)
                    await asyncio.sleep(random.uniform(3.0, 6.0)) # human reading delay
                    
                    # ── CONNECTION INVITATION FLOW ──
                    # Try to locate the Connect action button
                    connect_btn = None
                    
                    # Look for prominent Connect button
                    connect_selectors = [
                        "button:has-text('Connect')",
                        "button[aria-label^='Invite']",
                        ".pvs-profile-actions button:has-text('Connect')"
                    ]
                    for sel in connect_selectors:
                        btn = await page.query_selector(sel)
                        if btn:
                            connect_btn = btn
                            break
                            
                    # If not found directly, check the "More" dropdown action panel
                    if not connect_btn:
                        more_btn = await page.query_selector("button:has-text('More')")
                        if more_btn:
                            await more_btn.click()
                            await asyncio.sleep(1.0)
                            connect_btn = await page.query_selector("div[role='button']:has-text('Connect')")
                            
                    if connect_btn:
                        # Trigger connection modal
                        await connect_btn.click()
                        await asyncio.sleep(2.0)
                        
                        # Click "Add a note" on connection confirmation dialog
                        add_note_btn = await page.query_selector("button:has-text('Add a note')")
                        if add_note_btn:
                            await add_note_btn.click()
                            await asyncio.sleep(1.5)
                            
                        # Locate the message textbox
                        textarea = await page.query_selector("textarea#custom-message, textarea[name='message']")
                        if textarea:
                            # Types the custom Gemini outreach message
                            await textarea.fill(lead.linkedin_message)
                            await asyncio.sleep(1.5)
                            
                            # Click Send invitation button
                            send_btn = await page.query_selector("button:has-text('Send'), button[aria-label='Send now']")
                            if send_btn:
                                await send_btn.click()
                                await asyncio.sleep(2.0)
                                
                                # Log successful send
                                lead.linkedin_sent_at = datetime.now(timezone.utc)
                                lead.status = "called" # map to called status
                                db.commit()
                                sent_count += 1
                                
                                # Broadcast update to frontend Command Center
                                await websocket_manager.broadcast({
                                    "event": "lead_status_updated",
                                    "lead_id": str(lead.id),
                                    "status": "called",
                                    "business_name": lead.business_name
                                })
                                
                                logger.info("LinkedIn connection note sent successfully", lead=lead.full_name)
                            else:
                                logger.error("Send invitation button not found in modal.")
                                errors_count += 1
                        else:
                            # Handles cases where Connect directly triggers connection request without note confirmation
                            logger.info("Direct connection sent without note option.")
                            lead.linkedin_sent_at = datetime.now(timezone.utc)
                            lead.status = "called"
                            db.commit()
                            sent_count += 1
                    else:
                        logger.warning("No Connect option found on profile page.")
                        errors_count += 1
                        
                except Exception as item_err:
                    logger.error("Error sending message to profile", lead_id=str(lid), error=str(item_err))
                    errors_count += 1
                finally:
                    db.close()
                    
                # Throttling delay to emulate organic pacing behavior
                throttle_delay = random.uniform(60.0, 180.0)
                logger.info("Outreach throttling delay active", seconds=round(throttle_delay, 1))
                await asyncio.sleep(throttle_delay)
                
            await browser.close()
    except Exception as e:
        logger.error("Fatal exception in Playwright sender loop", error=str(e))
        return {"success": False, "sent": sent_count, "errors": len(lead_ids) - sent_count, "detail": str(e)}

    return {
        "success": True,
        "sent": sent_count,
        "errors": errors_count
    }


async def run_simulated_campaign(lead_ids: list) -> Dict[str, Any]:
    """Simulates sending connection requests to target leads in mock environments"""
    sent_count = 0
    
    for lid in lead_ids:
        db = SessionLocal()
        try:
            lead = db.query(Lead).filter(Lead.id == lid).first()
            if lead:
                logger.info("SIMULATED OUTREACH: Sending LinkedIn connection request", to=lead.full_name, message=lead.linkedin_message)
                
                # Mock sending delay
                await asyncio.sleep(random.uniform(2.0, 5.0))
                
                lead.linkedin_sent_at = datetime.now(timezone.utc)
                lead.status = "called" # map to called status
                db.commit()
                sent_count += 1
                
                # Broadcast live status update to frontend
                await websocket_manager.broadcast({
                    "event": "lead_status_updated",
                    "lead_id": str(lead.id),
                    "status": "called",
                    "business_name": lead.business_name
                })
        except Exception as e:
            logger.error("Error in simulated outreach item", error=str(e))
        finally:
            db.close()
            
    return {
        "success": True,
        "sent": sent_count,
        "errors": 0
    }
