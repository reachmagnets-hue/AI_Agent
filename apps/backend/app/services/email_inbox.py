import imaplib
import email
import structlog
from email.header import decode_header
from datetime import datetime
from bs4 import BeautifulSoup
from sqlalchemy import or_

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.lead import Lead
from app.models.appointment import Appointment
from app.services.ai_reviewer import analyze_inbox_message
from app.core.websocket import websocket_manager

logger = structlog.get_logger(__name__)

def extract_email_address(from_header: str) -> str:
    """Extracts just the email address from a 'Name <email@domain.com>' string"""
    if "<" in from_header and ">" in from_header:
        return from_header.split("<")[1].split(">")[0].strip().lower()
    return from_header.strip().lower()

def clean_email_body(msg: email.message.Message) -> str:
    """Extracts plain text from an email message"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body = payload.decode()
                    break
                except Exception:
                    pass
            elif content_type == "text/html" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        html_content = payload.decode()
                        body = BeautifulSoup(html_content, "html.parser").get_text(separator="\n")
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                body = payload.decode()
                if msg.get_content_type() == "text/html":
                    body = BeautifulSoup(body, "html.parser").get_text(separator="\n")
        except Exception:
            pass
    return body.strip()

async def sync_email_inbox():
    """
    Connects to IMAP securely, fetches UNSEEN emails, and STRICTLY filters by 
    whether the sender is a Lead we have actively contacted.
    """
    settings = get_settings()
    server = settings.IMAP_SERVER
    user = settings.IMAP_USER
    password = settings.IMAP_PASSWORD
    
    if not server or not user or not password:
        logger.warning("IMAP configuration is missing. Cannot sync email inbox.")
        return {"status": "error", "message": "IMAP Configuration Missing"}

    db = SessionLocal()
    scraped_threads = 0
    bookings_found = 0
    ignored_emails = 0
    
    try:
        # Connect to IMAP server securely
        mail = imaplib.IMAP4_SSL(server)
        mail.login(user, password)
        mail.select("inbox")
        
        # Search for all unread emails
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            mail.logout()
            return {"status": "error", "message": "Failed to search inbox."}
            
        email_ids = messages[0].split()
        
        for e_id in email_ids[:15]: # Process up to 15 unread emails at a time
            # Fetch the email
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            if status != "OK":
                continue
                
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Extract Sender Email
                    from_header = msg.get("From", "")
                    sender_email = extract_email_address(from_header)
                    
                    # ---- STRICT FILTERING ----
                    # Only process this email if it matches an ACTIVE lead that we HAVE CONTACTED
                    # Contacted implies email_sent_at is not null, or status implies we reached out
                    lead = db.query(Lead).filter(
                        Lead.email.ilike(f"%{sender_email}%"),
                        Lead.is_active == True,
                        or_(
                            Lead.status.in_(["meeting_booked", "interested", "follow_up", "not_interested", "voicemail", "no_answer"]),
                            Lead.total_calls > 0,
                            Lead.email_sent_at.isnot(None)
                        )
                    ).first()
                    
                    if not lead:
                        logger.info("Ignoring email: Sender is not a contacted lead", email=sender_email)
                        ignored_emails += 1
                        continue
                        
                    # Extract Subject and Body
                    subject, encoding = decode_header(msg.get("Subject", ""))[0]
                    if isinstance(subject, bytes):
                        try:
                            subject = subject.decode(encoding or "utf-8")
                        except Exception:
                            subject = subject.decode("utf-8", "ignore")
                            
                    body = clean_email_body(msg)
                    chat_history = f"Subject: {subject}\n\nProspect Email Body:\n{body}"
                    
                    scraped_threads += 1
                    logger.info("Analyzing Email thread", lead=lead.full_name, email=sender_email)
                    
                    # Analyze with Gemini
                    outcome = await analyze_inbox_message(chat_history)
                    
                    # Process Outcome
                    if outcome["classification"] == "meeting_booked":
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
                            lead.status = "meeting_booked"  # type: ignore
                            lead.internal_notes = f"{lead.internal_notes or ''}\n[AI Email Review] Prospect booked meeting via Email for {date_str} at {time_str}. Summary: {outcome['summary']}"  # type: ignore
                            
                            bookings_found += 1
                            logger.info("Booking created from Email Inbox!", lead_id=str(lead.id))
                            
                            await websocket_manager.broadcast({
                                "event": "appointment_booked",
                                "lead_id": str(lead.id),
                                "prospect_name": lead.full_name,
                                "date": date_str,
                                "time": time_str
                            })
                            
                    elif outcome["classification"] in ["interested", "not_interested"]:
                        if lead.status not in ["meeting_booked", "interested"]:
                            lead.status = str(outcome["classification"])  # type: ignore
                            lead.internal_notes = f"{lead.internal_notes or ''}\n[AI Email Review] Prospect replied via Email. Classified as {outcome['classification']}. Summary: {outcome['summary']}"  # type: ignore
                            
                    db.commit()
                    
        # Logout
        mail.close()
        mail.logout()
        return {
            "status": "success", 
            "threads_reviewed": scraped_threads, 
            "ignored_emails": ignored_emails,
            "bookings_found": bookings_found
        }
            
    except Exception as e:
        logger.error("Email Inbox Sync failed", error=str(e))
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
