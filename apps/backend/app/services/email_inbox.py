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

def extract_failed_recipient_from_bounce(msg: email.message.Message, body: str) -> str | None:
    """Extracts the failed recipient's email address from a bounce report or bounce body"""
    import re
    # 1. Check X-Failed-Recipients header
    failed = msg.get("X-Failed-Recipients")
    if failed:
        if "<" in failed and ">" in failed:
            return failed.split("<")[1].split(">")[0].strip().rstrip(".").lower()
        return failed.strip().rstrip(".").lower()
    
    # 2. Check delivery-status multipart reports
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "message/delivery-status":
                try:
                    payload = part.get_payload()
                    if isinstance(payload, list) and len(payload) > 0:
                        sub_msg = payload[0]
                        if isinstance(sub_msg, email.message.Message):
                            final_rec = sub_msg.get("Final-Recipient")
                            if final_rec and ";" in final_rec:
                                return final_rec.split(";")[-1].strip().rstrip(".").lower()
                except Exception:
                    pass

    # 3. Match explicit delivery failure phrases
    delivery_patterns = [
        r"wasn't delivered to\s+([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
        r"delivering your message to\s+([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
        r"failed to deliver to\s+([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
        r"<([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)>:\s*recipient",
        r"to:\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
    ]
    for pattern in delivery_patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            found_email = match.group(1).rstrip(".").lower()
            if "reachmagnets" not in found_email and "mailer-daemon" not in found_email:
                return found_email

    # 4. Fallback to scanning body via regex
    emails_in_body = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', body)
    if emails_in_body:
        filtered = [e.rstrip(".").lower() for e in emails_in_body if not any(x in e.lower() for x in ["mailer-daemon", "postmaster", "reachmagnets", "sentry.io", "2x.webp", "godaddy.com", "schema.org"])]
        if filtered:
            return filtered[0]
    return None

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
    Connects to IMAP securely, fetches UNSEEN emails & bounce notifications,
    and updates lead statuses in database.
    """
    settings = get_settings()
    server = settings.IMAP_SERVER or (settings.SMTP_HOST.replace("smtp", "imap") if settings.SMTP_HOST else "imap.gmail.com")
    user = settings.IMAP_USER or settings.SMTP_USER or settings.SENDER_EMAIL
    password = settings.IMAP_PASSWORD or settings.SMTP_PASSWORD
    
    if not server or not user or not password:
        logger.warning("IMAP configuration is missing. Cannot sync email inbox.")
        return {"status": "error", "message": "IMAP Configuration Missing"}

    db = SessionLocal()
    scraped_threads = 0
    bookings_found = 0
    bounces_found = 0
    ignored_emails = 0
    
    try:
        # Connect to IMAP server securely
        mail = imaplib.IMAP4_SSL(server)
        mail.login(user, password)
        mail.select("inbox")
        
        # 1. SCAN FOR BOUNCES ACROSS INBOX
        bounce_queries = ['FROM "mailer-daemon"', 'FROM "postmaster"', 'SUBJECT "Delivery Status Notification"', 'SUBJECT "Address not found"']
        bounce_ids = set()
        for bq in bounce_queries:
            st, msgs = mail.search(None, bq)
            if st == "OK" and msgs[0]:
                bounce_ids.update(msgs[0].split())
                
        for b_id in list(bounce_ids)[:50]:
            st, msg_data = mail.fetch(b_id, "(RFC822)")
            if st != "OK": continue
            for resp in msg_data:
                if isinstance(resp, tuple):
                    b_msg = email.message_from_bytes(resp[1])
                    b_body = clean_email_body(b_msg)
                    failed_rec = extract_failed_recipient_from_bounce(b_msg, b_body)
                    if failed_rec:
                        lead = db.query(Lead).filter(Lead.email.ilike(f"%{failed_rec}%"), Lead.is_active == True).first()
                        if lead and lead.email_status != "bounced":
                            logger.info("Detected email bounce for lead via IMAP", lead=lead.full_name, email=failed_rec)
                            lead.email_status = "bounced"  # type: ignore
                            lead.email_bounced_at = datetime.utcnow()  # type: ignore
                            lead.internal_notes = f"{lead.internal_notes or ''}\n[IMAP Bounce Scanner] Email bounced back from recipient address: {failed_rec}"  # type: ignore
                            db.commit()
                            bounces_found += 1
        
        # 2. SEARCH FOR UNREAD REPLIES
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            mail.logout()
            return {"status": "success", "bounces_found": bounces_found, "threads_reviewed": scraped_threads, "bookings_found": bookings_found}
            
        email_ids = messages[0].split()
        
        for e_id in email_ids[:20]: # Process up to 20 unread emails at a time
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
                    
                    # Skip bounce messages already processed
                    is_bounce = any(pattern in sender_email for pattern in ["mailer-daemon", "postmaster", "bounce"])
                    if is_bounce:
                        ignored_emails += 1
                        continue

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
