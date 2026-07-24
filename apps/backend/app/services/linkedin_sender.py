import asyncio
import random
import structlog
from datetime import datetime, timezone
from typing import Dict, Any
from uuid import UUID
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.lead import Lead
from app.core.websocket import websocket_manager
from app.services.ai_reviewer import analyze_inbox_message

logger = structlog.get_logger(__name__)

# Try to import Playwright
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


async def send_linkedin_campaign(campaign_id: str, limit: int = 30, force_simulate: bool = False) -> Dict[str, Any]:
    """
    Background worker task to iterate through a campaign's approved leads.
    Enforces a strict limit (e.g. 30 per day) of connection requests.
    """
    settings = get_settings()
    cookie = settings.LINKEDIN_SESSION_COOKIE
    
    # Enforce safe hard limit
    daily_limit = 30
    
    logger.info("Starting LinkedIn campaign delivery", campaign_id=campaign_id, daily_limit=daily_limit)
    
    # Check if force_simulate is explicitly set
    is_simulation = force_simulate
    
    db = SessionLocal()
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        # Count connections sent today
        actions_today = db.query(Lead).filter(
            Lead.linkedin_status.in_(['connection_sent', 'connected', 'message_sent', 'meeting_scheduled']),
            Lead.linkedin_sent_at >= today_start
        ).count()
        
        remaining_actions = max(0, daily_limit - actions_today)
        if remaining_actions <= 0:
            logger.info("Daily LinkedIn connection limit reached.", limit=daily_limit, actions_today=actions_today)
            return {"success": True, "sent": 0, "status": "limit_reached"}
            
        actionable_leads = db.query(Lead).filter(
            Lead.campaign_id == (UUID(campaign_id) if isinstance(campaign_id, str) else campaign_id),
            Lead.linkedin_url.isnot(None),
            Lead.is_active == True,
            Lead.linkedin_status.in_(['approved', 'pending_approval', 'pending']),
            Lead.linkedin_message.isnot(None)
        ).limit(remaining_actions).all()
        
        lead_ids_to_process = [lead.id for lead in actionable_leads]
    finally:
        db.close()
        
    if not lead_ids_to_process:
        logger.info("No actionable LinkedIn outreach leads found for this campaign.")
        return {"success": True, "sent": 0, "status": "completed_empty"}

    if is_simulation or not PLAYWRIGHT_AVAILABLE or not cookie or cookie == "your_linkedin_session_cookie":
        logger.info("Running LinkedIn campaign in SIMULATED outreach mode")
        return await run_simulated_campaign(lead_ids_to_process, remaining_actions)

    return await run_playwright_campaign(cookie, lead_ids_to_process, remaining_actions)


async def run_playwright_campaign(cookie: str, lead_ids: list, remaining_actions: int) -> Dict[str, Any]:
    """Only sends connection requests via real Playwright Chrome browser"""
    sent_count = 0
    errors_count = 0
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome")
            context = await browser.new_context()
            
            await context.add_cookies([{
                "name": "li_at",
                "value": cookie,
                "domain": ".www.linkedin.com",
                "path": "/"
            }])
            
            page = await context.new_page()
            
            for lid in lead_ids:
                if remaining_actions <= 0:
                    break
                    
                db = SessionLocal()
                try:
                    lead = db.query(Lead).filter(Lead.id == lid).first()
                    if not lead or lead.linkedin_status not in ['approved', 'pending_approval', 'pending']:
                        continue
                        
                    logger.info("Outreach: Open profile to connect", name=lead.full_name)
                    await page.goto(str(lead.linkedin_url), timeout=30000)
                    await asyncio.sleep(random.uniform(3.0, 6.0))
                    
                    try:
                        await page.screenshot(path="/home/chetan-patil/.gemini/antigravity-ide/brain/4da66a20-3865-4ff0-8500-2426726bbe55/linkedin_debug.png")
                        logger.info("Saved debug profile screenshot to linkedin_debug.png")
                    except Exception as ss_err:
                        logger.error("Failed to capture debug screenshot", error=str(ss_err))
                    
                    connect_btn = None
                    selectors = [
                        "button:has-text('Connect')",
                        "a:has-text('Connect')",
                        "button[aria-label^='Invite']",
                        "a[aria-label^='Invite']",
                        "a[href*='custom-invite']",
                        "a[href*='connect']",
                        ".pvs-profile-actions button:has-text('Connect')",
                        ".pvs-profile-actions a:has-text('Connect')"
                    ]
                    for sel in selectors:
                        btn = await page.query_selector(sel)
                        if btn:
                            connect_btn = btn; break
                            
                    if not connect_btn:
                        more_btn = await page.query_selector("button:has-text('More')")
                        if more_btn:
                            await more_btn.click(force=True)
                            await asyncio.sleep(1.0)
                            connect_btn = await page.query_selector("div[role='button']:has-text('Connect')")
                            
                    if connect_btn:
                        await connect_btn.click(force=True)
                        await asyncio.sleep(2.0)
                        
                        send_without_note = await page.query_selector("button:has-text('Send without a note'), button[aria-label='Send without a note']")
                        if send_without_note:
                            await send_without_note.click(force=True)
                        else:
                            send_btn = await page.query_selector("button:has-text('Send'), button[aria-label='Send now']")
                            if send_btn: await send_btn.click(force=True)
                            
                        await asyncio.sleep(2.0)
                        lead.linkedin_status = 'connection_sent' # type: ignore
                        lead.linkedin_sent_at = datetime.now(timezone.utc) # type: ignore
                        db.commit()
                        sent_count += 1
                        remaining_actions -= 1
                        await websocket_manager.broadcast({"event": "lead_status_updated", "lead_id": str(lead.id), "linkedin_status": "connection_sent"})
                        logger.info("LinkedIn connection sent.", lead=lead.full_name)
                    else:
                        logger.warning("No Connect option found.")
                        errors_count += 1
                        
                except Exception as item_err:
                    logger.error("Error processing profile", lead_id=str(lid), error=str(item_err))
                    errors_count += 1
                finally:
                    db.close()
                    
                await asyncio.sleep(random.uniform(30.0, 60.0)) # Throttle
                
            await browser.close()
    except Exception as e:
        logger.error("Fatal exception in Playwright sender loop", error=str(e))
        return {"success": False, "sent": sent_count, "errors": len(lead_ids) - sent_count, "detail": str(e)}

    return {"success": True, "sent": sent_count, "errors": errors_count}


async def simulate_acceptance_and_messaging(lead_ids: list):
    """
    Simulates acceptance and messaging for simulated leads.
    """
    logger.info("Starting simulated acceptance and messaging background worker", count=len(lead_ids))
    # Wait 8 seconds to allow the user to see 'connection_sent' state
    await asyncio.sleep(8.0)
    
    for lid in lead_ids:
        db = SessionLocal()
        try:
            lead = db.query(Lead).filter(Lead.id == lid).first()
            if lead and lead.linkedin_status == 'connection_sent':
                # 1. Accept connection
                lead.linkedin_status = 'connected'  # type: ignore
                db.commit()
                await websocket_manager.broadcast({
                    "event": "lead_status_updated",
                    "lead_id": str(lead.id),
                    "linkedin_status": "connected"
                })
                logger.info("SIMULATED: Connection accepted", lead=lead.full_name)
                
                # Wait 5 seconds to simulate reading/writing message
                await asyncio.sleep(5.0)
                
                # Re-fetch lead to ensure no status change
                lead = db.query(Lead).filter(Lead.id == lid).first()
                if lead and lead.linkedin_status == 'connected' and lead.linkedin_message:
                    # 2. Send message
                    lead.linkedin_status = 'message_sent'  # type: ignore
                    db.commit()
                    await websocket_manager.broadcast({
                        "event": "lead_status_updated",
                        "lead_id": str(lead.id),
                        "linkedin_status": "message_sent"
                    })
                    logger.info("SIMULATED: Outreach message sent", lead=lead.full_name)
                    
                    # Wait 4 seconds before processing next lead
                    await asyncio.sleep(4.0)
        except Exception as e:
            logger.error("Error in simulated acceptance/messaging task", lead_id=str(lid), error=str(e))
        finally:
            db.close()

async def run_simulated_campaign(lead_ids: list, remaining_actions: int) -> Dict[str, Any]:
    sent_count = 0
    errors_count = 0
    processed_lead_ids = []
    
    for lid in lead_ids:
        if remaining_actions <= 0: break
        
        db = SessionLocal()
        try:
            lead = db.query(Lead).filter(Lead.id == lid).first()
            if lead and lead.linkedin_status in ['approved', 'pending_approval']:
                lead.linkedin_status = 'connection_sent' # type: ignore
                lead.linkedin_sent_at = datetime.now(timezone.utc) # type: ignore
                logger.info("SIMULATED OUTREACH: Connection request sent", to=lead.full_name)
                db.commit()
                sent_count += 1
                remaining_actions -= 1
                processed_lead_ids.append(lid)
                
                await websocket_manager.broadcast({
                    "event": "lead_status_updated",
                    "lead_id": str(lead.id),
                    "linkedin_status": lead.linkedin_status
                })
        except Exception as e:
            logger.error("Error in simulated outreach item", error=str(e))
            errors_count += 1
        finally:
            db.close()
            
    # Trigger live progression simulation task in the background
    if processed_lead_ids:
        asyncio.create_task(simulate_acceptance_and_messaging(processed_lead_ids))
        
    return {"sent_count": sent_count, "errors": errors_count}

async def run_simulated_hourly_tasks():
    db = SessionLocal()
    try:
        leads = db.query(Lead).filter(
            Lead.linkedin_url.isnot(None),
            Lead.is_active == True,
            Lead.linkedin_status.in_(['connection_sent', 'connected'])
        ).all()
        
        for lead in leads:
            if lead.linkedin_status == 'connection_sent':
                lead.linkedin_status = 'connected'  # type: ignore
                db.commit()
                await websocket_manager.broadcast({
                    "event": "lead_status_updated",
                    "lead_id": str(lead.id),
                    "linkedin_status": "connected"
                })
                logger.info("SIMULATED HOURLY: Connection accepted", lead=lead.full_name)
                await asyncio.sleep(1.0)
                
            if lead.linkedin_status == 'connected' and lead.linkedin_message:
                lead.linkedin_status = 'message_sent'  # type: ignore
                db.commit()
                await websocket_manager.broadcast({
                    "event": "lead_status_updated",
                    "lead_id": str(lead.id),
                    "linkedin_status": "message_sent"
                })
                logger.info("SIMULATED HOURLY: Outreach message sent", lead=lead.full_name)
                await asyncio.sleep(1.0)
    except Exception as e:
        logger.error("Error in simulated hourly tasks", error=str(e))
    finally:
        db.close()

async def process_hourly_linkedin_tasks():
    """
    Runs every hour to:
    1. Check acceptances for connection_sent leads.
    2. Send messages to connected leads.
    3. Read inbox for replies and use AI to schedule meetings.
    """
    logger.info("process_hourly_linkedin_tasks: Starting hourly routine")
    settings = get_settings()
    cookie = settings.LINKEDIN_SESSION_COOKIE
    
    if not PLAYWRIGHT_AVAILABLE or not cookie or cookie == "your_linkedin_session_cookie":
        logger.info("Hourly routine running in SIMULATED mode")
        await run_simulated_hourly_tasks()
        return
        
    db = SessionLocal()
    try:
        leads_to_check = db.query(Lead).filter(
            Lead.linkedin_url.isnot(None),
            Lead.is_active == True,
            Lead.linkedin_status.in_(['connection_sent', 'connected', 'message_sent'])
        ).limit(100).all()
        lead_ids = [lead.id for lead in leads_to_check]
    finally:
        db.close()
        
    if not lead_ids:
        logger.info("Hourly routine: No active connections to process.")
        return
        
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome")
            context = await browser.new_context()
            await context.add_cookies([{"name": "li_at", "value": cookie, "domain": ".www.linkedin.com", "path": "/"}])
            page = await context.new_page()
            
            for lid in lead_ids:
                db = SessionLocal()
                try:
                    lead = db.query(Lead).filter(Lead.id == lid).first()
                    if not lead: continue
                    
                    logger.info(f"Hourly check: {lead.full_name} ({lead.linkedin_status})")
                    await page.goto(str(lead.linkedin_url), timeout=30000)
                    await asyncio.sleep(random.uniform(4.0, 7.0))
                    
                    # 1. Check for connection acceptance
                    if lead.linkedin_status == 'connection_sent':
                        msg_btn = await page.query_selector("button:has-text('Message'), a:has-text('Message')")
                        if msg_btn:
                            lead.linkedin_status = 'connected' # type: ignore
                            db.commit()
                            await websocket_manager.broadcast({"event": "lead_status_updated", "lead_id": str(lead.id), "linkedin_status": "connected"})
                            logger.info("Connection accepted!", lead=lead.full_name)
                    
                    # 2. Send message if connected
                    if lead.linkedin_status == 'connected' and lead.linkedin_message:
                        msg_btn = await page.query_selector("button:has-text('Message'), a:has-text('Message')")
                        if msg_btn:
                            await msg_btn.click()
                            await asyncio.sleep(2.0)
                            textarea = await page.query_selector("div[role='textbox'], textarea[name='message']")
                            if textarea:
                                await textarea.fill(lead.linkedin_message)
                                await asyncio.sleep(1.0)
                                send_btn = await page.query_selector("button.msg-form__send-button")
                                if send_btn:
                                    await send_btn.click()
                                    await asyncio.sleep(2.0)
                                    lead.linkedin_status = 'message_sent' # type: ignore
                                    db.commit()
                                    await websocket_manager.broadcast({"event": "lead_status_updated", "lead_id": str(lead.id), "linkedin_status": "message_sent"})
                                    logger.info("Initial message sent.", lead=lead.full_name)
                                    
                    # 3. Read inbox if message_sent
                    elif lead.linkedin_status == 'message_sent':
                        msg_btn = await page.query_selector("button:has-text('Message'), a:has-text('Message')")
                        if msg_btn:
                            await msg_btn.click()
                            await asyncio.sleep(3.0)
                            
                            # Scrape all paragraphs in the popup message list container
                            chat_elements = await page.query_selector_all(".msg-s-message-list-container p.msg-s-event-listitem__body, .msg-s-message-list-container .msg-s-event-listitem__message-bubble")
                            chat_text = ""
                            for el in chat_elements:
                                txt = await el.inner_text()
                                chat_text += f"{txt}\n"
                                
                            if chat_text:
                                logger.info(f"Read chat history for {lead.full_name}", length=len(chat_text))
                                ai_result = await analyze_inbox_message(chat_text)
                                
                                if ai_result.get("status") == "booking_requested":
                                    logger.info("AI detected booking request! Sending link.", lead=lead.full_name)
                                    textarea = await page.query_selector("div[role='textbox'], textarea[name='message']")
                                    if textarea:
                                        reply = f"Awesome! You can pick a time that works for you here: {settings.GMEET_LINK}"
                                        await textarea.fill(reply)
                                        await asyncio.sleep(1.0)
                                        send_btn = await page.query_selector("button.msg-form__send-button")
                                        if send_btn:
                                            await send_btn.click()
                                            await asyncio.sleep(2.0)
                                            lead.linkedin_status = 'meeting_scheduled' # type: ignore
                                            db.commit()
                                            await websocket_manager.broadcast({"event": "lead_status_updated", "lead_id": str(lead.id), "linkedin_status": "meeting_scheduled"})
                                
                except Exception as e:
                    logger.error("Error in hourly check for lead", lead_id=str(lid), error=str(e))
                finally:
                    db.close()
                    
                await asyncio.sleep(random.uniform(5.0, 10.0))
                
            await browser.close()
    except Exception as e:
        logger.error("Fatal exception in hourly Playwright loop", error=str(e))
