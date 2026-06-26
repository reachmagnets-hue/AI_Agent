import asyncio
import structlog
from datetime import datetime
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.lead import Lead
from app.models.appointment import Appointment
from app.services.ai_reviewer import analyze_inbox_message
from app.core.websocket import websocket_manager

logger = structlog.get_logger(__name__)

async def sync_linkedin_inbox():
    """
    Connects to LinkedIn Messaging using the session cookie,
    reads the recent conversation threads, and passes them to the AI Reviewer.
    If a meeting is booked, it automatically links it to the CRM.
    """
    settings = get_settings()
    cookie = settings.LINKEDIN_SESSION_COOKIE
    
    if not cookie or cookie == "your_linkedin_session_cookie" or len(cookie) < 50:
        logger.warning("Invalid or missing LINKEDIN_SESSION_COOKIE. Cannot sync inbox.")
        return {"status": "error", "message": "Invalid LinkedIn Session Cookie."}
        
    db = SessionLocal()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome")
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            await context.add_cookies([{
                "name": "li_at",
                "value": cookie,
                "domain": ".www.linkedin.com",
                "path": "/"
            }])
            
            page = await context.new_page()
            logger.info("Navigating to LinkedIn Messaging Inbox...")
            await page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded", timeout=30000)
            
            # Wait for the inbox list to load
            try:
                await page.wait_for_selector(".msg-conversation-listitem", timeout=15000)
            except Exception:
                logger.error("Failed to load LinkedIn messaging. Cookie may be expired or account restricted.")
                await browser.close()
                return {"status": "error", "message": "Failed to load LinkedIn Inbox. Cookie may be expired."}
                
            # Scrape the top 5 recent conversations
            threads = await page.query_selector_all(".msg-conversation-listitem")
            scraped_threads = 0
            bookings_found = 0
            
            for thread in threads[:5]:
                try:
                    # Click to open thread
                    await thread.click()
                    await asyncio.sleep(2) # Wait for thread to load
                    
                    # Get prospect name
                    name_elem = await page.query_selector(".msg-thread__name")
                    if not name_elem:
                        continue
                    prospect_name = (await name_elem.inner_text()).strip()
                    
                    # Scrape conversation history in this thread
                    messages = await page.query_selector_all(".msg-s-event-listitem__body")
                    chat_history = ""
                    for msg in messages[-5:]: # Get last 5 messages in thread
                        text = await msg.inner_text()
                        chat_history += f"{text.strip()}\n---\n"
                        
                    if not chat_history:
                        continue
                        
                    scraped_threads += 1
                    logger.info("Analyzing LinkedIn thread", prospect=prospect_name)
                    
                    # Analyze with Gemini
                    outcome = await analyze_inbox_message(chat_history)
                    
                    # Find matching Lead in CRM that WE HAVE ACTIVELY CONTACTED
                    lead = db.query(Lead).filter(
                        Lead.full_name.ilike(f"%{prospect_name}%"),
                        Lead.linkedin_sent_at.isnot(None),
                        Lead.is_active == True
                    ).first()
                    
                    if not lead:
                        logger.info("Ignoring thread: Sender is not a contacted lead in our CRM", prospect=prospect_name)
                        continue
                        
                    # Process Outcome
                    if outcome["classification"] == "meeting_booked":
                        # Check if appointment already exists to prevent duplicates
                        existing_appt = db.query(Appointment).filter(Appointment.lead_id == lead.id).first()
                        if not existing_appt:
                            date_str = outcome.get("meeting_date") or datetime.now().strftime("%Y-%m-%d")
                            time_str = outcome.get("meeting_time") or "12:00 PM"
                            
                            appt = Appointment(
                                lead_id=lead.id,
                                title=f"Discovery Call - {lead.full_name}",
                                meeting_date=date_str,
                                meeting_time=time_str,
                                timezone=outcome.get("meeting_timezone") or "EST",
                                status="scheduled"
                            )
                            db.add(appt)
                            lead.status = "meeting_booked"
                            lead.internal_notes = f"{lead.internal_notes or ''}\n[AI Inbox Review] Prospect booked meeting via LinkedIn for {date_str} at {time_str}. Summary: {outcome['summary']}"
                            
                            bookings_found += 1
                            logger.info("Booking created from LinkedIn Inbox!", lead_id=str(lead.id))
                            
                            # Notify UI
                            await websocket_manager.broadcast({
                                "event": "appointment_booked",
                                "lead_id": str(lead.id),
                                "prospect_name": lead.full_name,
                                "date": date_str,
                                "time": time_str
                            })
                            
                    elif outcome["classification"] in ["interested", "not_interested"]:
                        if lead.status not in ["meeting_booked", "interested"]:
                            lead.status = outcome["classification"]
                            lead.internal_notes = f"{lead.internal_notes or ''}\n[AI Inbox Review] Prospect replied on LinkedIn. Classified as {outcome['classification']}. Summary: {outcome['summary']}"
                            
                    db.commit()
                    
                except Exception as ex:
                    logger.error("Error processing a LinkedIn thread", error=str(ex))
                    continue
            
            await browser.close()
            return {"status": "success", "threads_reviewed": scraped_threads, "bookings_found": bookings_found}
            
    except Exception as e:
        logger.error("LinkedIn Inbox Sync failed", error=str(e))
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
