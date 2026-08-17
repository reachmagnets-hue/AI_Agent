import os
import structlog
import httpx
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Try to import sib_api_v3_sdk for Brevo
try:
    import sib_api_v3_sdk
    from sib_api_v3_sdk.rest import ApiException
    BREVO_AVAILABLE = True
except ImportError:
    BREVO_AVAILABLE = False
    logger.warning("sib-api-v3-sdk not available. Brevo email sending will be mocked.")

# Try to import Twilio
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger.warning("twilio SDK not available. SMS sending will be mocked.")


import asyncio

SMTP_LOCK: Optional[asyncio.Lock] = None

async def send_smtp_email_direct(to_email: str, subject: str, html_content: str, lead_id: Optional[str] = None) -> bool:
    """Send standard email via secure SMTP client connection (Hostinger, Gmail, or Custom SMTP)"""
    global SMTP_LOCK
    if SMTP_LOCK is None:
        SMTP_LOCK = asyncio.Lock()

    settings = get_settings()
    host = os.getenv("SMTP_HOST") or settings.SMTP_HOST or "smtp.gmail.com"
    port = int(os.getenv("SMTP_PORT") or settings.SMTP_PORT or 587)
    user = os.getenv("SMTP_USER") or settings.SMTP_USER
    password = os.getenv("SMTP_PASSWORD") or settings.SMTP_PASSWORD

    if not user or not password:
        env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.env"))
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                for line in f:
                    line_s = line.strip()
                    if line_s.startswith("SMTP_USER="):
                        user = line_s.split("=", 1)[1].strip('"\'')
                    elif line_s.startswith("SMTP_PASSWORD="):
                        password = line_s.split("=", 1)[1].strip('"\'')

    sender = os.getenv("SENDER_EMAIL") or settings.SENDER_EMAIL or user or "reachmagnets@gmail.com"
    sender_name = os.getenv("SENDER_NAME") or settings.SENDER_NAME or "Reach Magnets"

    logger.info("Triggering SMTP email direct dispatch (waiting for queue lock)", to=to_email, host=host, port=port, user=user)

    if not user or not password:
        logger.error("🛑 CANNOT SEND REAL EMAIL: SMTP_USER or SMTP_PASSWORD is not set in .env! Please add SMTP_USER and SMTP_PASSWORD to apps/backend/.env to enable live outreach.")
        return False

    # Generate custom Message-ID
    import uuid
    from datetime import datetime, timezone
    msg_id = f"<{uuid.uuid4()}@reachmagnets.com>"

    # Inject tracking pixel and rewrite links if lead_id is provided
    if lead_id and settings.BASE_URL:
        base_url = settings.BASE_URL.rstrip("/")
        # Tracking open pixel
        pixel_url = f"{base_url}/api/v1/emails/track/open/{lead_id}"
        pixel_html = f'<img src="{pixel_url}" width="1" height="1" style="display:none !important;" />'
        if "</body>" in html_content:
            html_content = html_content.replace("</body>", f"{pixel_html}</body>")
        else:
            html_content += pixel_html

        # Tracking click link rewriter
        import re
        from urllib.parse import quote
        def repl(match):
            url = match.group(2)
            if url.startswith(("http://", "https://")) and "track/click" not in url:
                return f'{match.group(1)}="{base_url}/api/v1/emails/track/click/{lead_id}?url={quote(url)}"'
            return match.group(0)
        
        html_content = re.sub(r'(href)\s*=\s*["\']([^"\']+)["\']', repl, html_content)

    async with SMTP_LOCK:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{sender_name} <{sender}>"
            msg["To"] = to_email
            msg["Message-ID"] = msg_id

            msg.attach(MIMEText(html_content, "html"))

            def sync_send():
                if port == 465:
                    with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                        server.login(user, password)
                        server.sendmail(sender, to_email, msg.as_string())
                else:
                    with smtplib.SMTP(host, port, timeout=15) as server:
                        server.starttls()
                        server.login(user, password)
                        server.sendmail(sender, to_email, msg.as_string())

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, sync_send)
            logger.info("SMTP email dispatched successfully", to=to_email, message_id=msg_id)

            if lead_id:
                from app.core.database import SessionLocal, uuid_match
                from app.models.lead import Lead
                db = SessionLocal()
                try:
                    lead = db.query(Lead).filter(uuid_match(Lead.id, lead_id)).first()
                    if lead:
                        now_utc = datetime.now(timezone.utc)
                        lead.email_msg_id = msg_id  # type: ignore
                        lead.email_sent_at = now_utc  # type: ignore
                        if not lead.email_delivered_at:
                            lead.email_delivered_at = now_utc  # type: ignore
                        if lead.email_status not in ["opened", "clicked", "replied", "bounced", "blocked"]:
                            lead.email_status = "delivered"  # type: ignore
                        db.commit()
                except Exception as db_err:
                    logger.error("Failed to update lead message ID in database", error=str(db_err))
                finally:
                    db.close()

            return True
        except Exception as e:
            logger.error("Failed to send email via SMTP", error=str(e))
            await asyncio.sleep(3)
            return False


async def send_appointment_email(to_email: str, to_name: str, appointment_details: str) -> bool:
    """Send appointment confirmation details via SMTP"""
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #6C5DD3;">Reach Magnets - Appointment Scheduled 📅</h2>
            <p>Hello <strong>{to_name}</strong>,</p>
            <p>We are excited to confirm your upcoming appointment with Reach Magnets!</p>
            <div style="background-color: #f7f7f7; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <p style="margin: 0;"><strong>Details:</strong></p>
                <p style="margin: 5px 0 0 0;">{appointment_details}</p>
            </div>
            <p>If you need to reschedule or have any questions, feel free to reply directly to this email.</p>
            <br>
            <p>Best regards,</p>
            <p><strong>Reach Magnets Team</strong></p>
        </body>
    </html>
    """
    return await send_smtp_email_direct(to_email, "Your Reach Magnets Appointment Details", html_content)


async def send_appointment_sms(to_phone: str, to_name: str, appointment_details: str) -> bool:
    """Send appointment details SMS via Twilio"""
    settings = get_settings()
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_phone = settings.TWILIO_PHONE_NUMBER

    logger.info("Triggering appointment SMS", to_phone=to_phone, to_name=to_name)

    if not TWILIO_AVAILABLE or not account_sid or account_sid == "your_twilio_account_sid":
        logger.warning("Twilio SMS not configured. Mocking SMS delivery.")
        return True

    try:
        client = TwilioClient(account_sid, auth_token)
        message_body = (
            f"Hello {to_name}, your Reach Magnets appointment has been successfully scheduled! "
            f"Details: {appointment_details}. Reply to this text if you have questions."
        )
        
        message = client.messages.create(
            body=message_body,
            from_=from_phone,
            to=to_phone
        )
        logger.info("Twilio SMS sent successfully", message_sid=message.sid)
        return True
    except Exception as e:
        logger.error("Error sending Twilio SMS", error=str(e))
        return False


async def send_whatsapp_message(to_phone: str, to_name: str, message_text: str) -> bool:
    """Send WhatsApp message with click-to-chat options"""
    settings = get_settings()
    whatsapp_url = settings.WHATSAPP_API_URL
    token = settings.WHATSAPP_TOKEN

    logger.info("Triggering WhatsApp message", to_phone=to_phone, to_name=to_name)

    # Clean phone number (WhatsApp needs digits only, with country code)
    clean_phone = "".join(filter(str.isdigit, to_phone))
    if not clean_phone.startswith("+") and len(clean_phone) > 0:
        # Standard fallback for routing
        pass

    # Standard fallback link generation
    # For instant support, we can use wa.me links
    whatsapp_chat_link = f"https://wa.me/919999999999?text=Hi,%20I'm%20interested%20in%20Reach%20Magnets%20services!"

    if not whatsapp_url or not token or whatsapp_url == "your_whatsapp_api_url":
        logger.warning("WhatsApp API not configured. Mocking WhatsApp notification.")
        logger.info(f"Generated Click-to-Chat WhatsApp Link: {whatsapp_chat_link}")
        return True

    try:
        # Check if using Meta Cloud API or Evolution API by inspecting structure
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Meta Cloud API standard JSON payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {
                "preview_url": True,
                "body": f"Hello {to_name}, {message_text}\n\nWant to chat with our marketing specialists directly on WhatsApp? Click here: {whatsapp_chat_link}"
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(whatsapp_url, headers=headers, json=payload, timeout=10.0)
            if response.status_code in [200, 201]:
                logger.info("WhatsApp message sent successfully via API")
                return True
            else:
                logger.error("WhatsApp API returned error", status_code=response.status_code, body=response.text)
                return False
    except Exception as e:
        logger.error("Error sending WhatsApp message via API", error=str(e))
        return False


def render_outreach_email(to_name: str, business_name: Optional[str] = None, business_type: Optional[str] = None, step: int = 1) -> tuple[str, str]:
    """
    Render outreach email body and subject based on the lead's niche (business_type) and sequence step (1, 2, or 3).
    Returns (subject, html_content).
    """
    settings = get_settings()
    gmeet_link = getattr(settings, "GMEET_LINK", None)
    if gmeet_link and gmeet_link.strip():
        booking_url = gmeet_link
    else:
        booking_url = "https://calendar.google.com"
    
    biz_name_str = business_name.strip() if business_name else ""
    business_phrase = biz_name_str if biz_name_str else "your business"

    if step == 2:
        subject = f"Re: A humble perspective on {biz_name_str}'s local visibility gaps" if biz_name_str else "Following up on local search visibility"
        body_content = f"""
        <p style="margin-top: 0; margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">Hi {to_name},</p>
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">I wanted to quickly follow up on my note from a couple of days ago regarding local search visibility for {business_phrase}.</p>
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">I know you are busy managing daily shop operations, but I wanted to ensure you did not miss our offer for a completely free, no-pressure digital marketing & AI search visibility audit.</p>
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">It takes only 15 minutes to review your shop's visibility report. You can pick a time that works best for you here:</p>
        <p style="margin-bottom: 24px; font-size: 15px; font-family: sans-serif;">
            <a href="{booking_url}" style="color: #1a73e8; text-decoration: underline; font-weight: bold;">{booking_url}</a>
        </p>
        <p style="margin-bottom: 20px; font-size: 15px; color: #222222; font-family: sans-serif;">Looking forward to connecting!</p>
        <p style="margin-bottom: 0; font-size: 15px; color: #222222; font-family: sans-serif;">
            Best regards,<br>
            <strong>Reach Magnets Team</strong><br>
            <a href="https://reachmagnets.com" style="color: #1a73e8;">https://reachmagnets.com</a>
        </p>
        """
    elif step == 3:
        subject = f"Final follow-up regarding {biz_name_str}'s local search audit" if biz_name_str else "Final follow-up regarding local search audit"
        body_content = f"""
        <p style="margin-top: 0; margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">Hi {to_name},</p>
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">This is my final note regarding {business_phrase}'s local search visibility audit.</p>
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">We've helped local auto repair and service shops uncover hidden customer leads by optimizing their Google Maps rankings and AI assistant recommendations.</p>
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">If you would ever like to review your shop's free audit report, feel free to grab a time slot on my calendar whenever you're ready:</p>
        <p style="margin-bottom: 24px; font-size: 15px; font-family: sans-serif;">
            <a href="{booking_url}" style="color: #1a73e8; text-decoration: underline; font-weight: bold;">{booking_url}</a>
        </p>
        <p style="margin-bottom: 20px; font-size: 15px; color: #222222; font-family: sans-serif;">Wishing you and {business_phrase} continued growth and success!</p>
        <p style="margin-bottom: 0; font-size: 15px; color: #222222; font-family: sans-serif;">
            Best regards,<br>
            <strong>Reach Magnets Team</strong><br>
            <a href="https://reachmagnets.com" style="color: #1a73e8;">https://reachmagnets.com</a>
        </p>
        """
    else:
        subject = f"A humble perspective on {biz_name_str}'s local visibility gaps" if biz_name_str else "A humble perspective on your local visibility gaps"
        body_content = f"""
        <p style="margin-top: 0; margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">Hi {to_name},</p>
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">I was recently reviewing local search visibility for {business_phrase} and wanted to reach out regarding a few fixable gaps that might be costing you service bookings and customer visits.</p>
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">Many auto shops and dealerships miss out on customers because of simple things: slow mobile page speeds, low local map search rankings, or lack of recommendations from smart AI assistants (Generative Engine Optimization).</p>
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">We would love to put together a completely free, no-pressure digital marketing audit for you. Here is what we'll review:</p>
        <ul style="margin-bottom: 18px; padding-left: 20px; font-size: 15px; color: #222222; font-family: sans-serif; line-height: 1.5;">
            <li><strong>Local Map Rankings:</strong> Where you rank when customers search for direct repair and service keywords.</li>
            <li><strong>AI Search Visibility:</strong> What tools like ChatGPT and Gemini recommend when drivers ask for local auto service.</li>
            <li><strong>Actionable Fixes:</strong> Specific improvements to optimize your site speed and prevent booking drops.</li>
        </ul>
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">It only takes about 15 minutes to go over this together. You can pick a convenient time on my calendar here:</p>
        <p style="margin-bottom: 24px; font-size: 15px; font-family: sans-serif;">
            <a href="{booking_url}" style="color: #1a73e8; text-decoration: underline; font-weight: bold;">{booking_url}</a>
        </p>
        <p style="margin-bottom: 20px; font-size: 15px; color: #222222; font-family: sans-serif;">Looking forward to helping you uncover new visibility opportunities.</p>
        <p style="margin-bottom: 0; font-size: 15px; color: #222222; font-family: sans-serif;">
            Best regards,<br>
            <strong>Reach Magnets Team</strong><br>
            <a href="https://reachmagnets.com" style="color: #1a73e8;">https://reachmagnets.com</a>
        </p>
        """

    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
</head>
<body style="margin: 0; padding: 20px; background-color: #ffffff; font-family: sans-serif; color: #222222; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;">
    <div style="max-width: 600px; margin: 0 auto;">
        {body_content}
        <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 30px 0 15px 0;">
        <p style="font-size: 11px; color: #777777; font-family: sans-serif; line-height: 1.4; margin: 0;">
            &copy; 2026 Reach Magnets &bull; Digital Marketing Excellence<br>
            If you prefer not to receive helpful visibility audits, reply "stop" to unsubscribe.
        </p>
    </div>
</body>
</html>
"""
    return subject, full_html


async def generate_ai_personalized_email(
    to_name: str,
    business_name: Optional[str] = None,
    business_type: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    lead_id: Optional[str] = None,
    step: int = 1
) -> tuple[str, str]:
    """
    Generates a unique, hyper-personalized B2B cold outreach email using Gemini AI based on extracted lead metadata.
    Falls back to structured niche HTML templates if AI API is unavailable.
    """
    settings = get_settings()
    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    gmeet_link = getattr(settings, "GMEET_LINK", None)
    booking_url = gmeet_link.strip() if (gmeet_link and gmeet_link.strip()) else "https://calendar.google.com"

    biz_str = business_name.strip() if business_name else "your business"
    city_str = city.strip() if city else ""
    state_str = state.strip() if state else ""
    location_str = f"{city_str}, {state_str}".strip(", ") if (city_str or state_str) else "your local area"

    if api_key:
        try:
            import json
            prompt = f"""You are an elite B2B cold email copywriter for Reach Magnets (a premier digital growth agency).
Write a unique, non-template, human, highly persuasive B2B outreach email for this specific prospect.

PROSPECT METADATA:
- Contact Name: {to_name}
- Business Name: {biz_str}
- Industry / Niche: {business_type or 'Auto Body Shop'}
- Location: {location_str}
- Outreach Step: Step {step} of 3 ({'Initial Outreach' if step == 1 else '1st Follow-Up 48h later' if step == 2 else 'Final Follow-Up'})
- Booking Calendar URL: {booking_url}

REACH MAGNETS CORE SERVICES TO HIGHLIGHT:
1. Google Maps & GBP #1 Local Search Ranking (ranking at the top when drivers search for local auto repair/collision service).
2. Generative Engine Optimization (GEO): Ensuring AI search assistants (ChatGPT, Gemini, Perplexity) recommend {biz_str} when local drivers ask for recommendations.
3. Website Speed & Booking Conversion Fixes (converting website visitors into booked repair jobs).
4. Free 15-Minute No-Pressure Digital Marketing Audit & Strategy Session ({booking_url}).

STRICT RULES:
- Sounds 100% human, humble, concise, professional, and conversational.
- NO corporate jargon, NO fake fluff, NO 'Dear Sir/Madam'.
- Include an HTML call-to-action link to {booking_url}.
- Return ONLY valid JSON with two fields:
  {{"subject": "...", "body": "<html body content>"}}"""

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_mime_type": "application/json"}
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(raw_text)
                    subject = parsed.get("subject", "")
                    body_content = parsed.get("body", "")
                    if subject and body_content:
                        full_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="margin: 0; padding: 20px; background-color: #ffffff; font-family: sans-serif; color: #222222;">
    <div style="max-width: 600px; margin: 0 auto;">
        {body_content}
        <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 30px 0 15px 0;">
        <p style="font-size: 11px; color: #777777; font-family: sans-serif;">
            &copy; 2026 Reach Magnets &bull; Digital Marketing Excellence<br>
            If you prefer not to receive helpful visibility audits, reply "stop" to unsubscribe.
        </p>
    </div>
</body>
</html>"""
                        logger.info("Generated Gemini AI personalized email", lead=to_name, business=biz_str, step=step)
                        return subject, full_html
        except Exception as e:
            logger.warning("Gemini AI email generation fallback triggered", error=str(e))

    return render_outreach_email(to_name, business_name, business_type, step=step)


async def send_outreach_email(to_email: str, to_name: str, business_name: Optional[str] = None, business_type: Optional[str] = None, lead_id: Optional[str] = None, step: int = 1) -> bool:
    """Send initial approach or follow-up outreach email introducing services via SMTP using Gemini AI personalized rendering"""
    city = None
    state = None

    if lead_id:
        try:
            from app.core.database import SessionLocal, uuid_match
            from app.models.lead import Lead
            db = SessionLocal()
            lead = db.query(Lead).filter(uuid_match(Lead.id, lead_id)).first()
            if lead:
                city = getattr(lead, "city", None)
                state = getattr(lead, "state", None)
            db.close()
        except Exception:
            pass

    subject, html_content = await generate_ai_personalized_email(to_name, business_name, business_type, city=city, state=state, lead_id=lead_id, step=step)
    return await send_smtp_email_direct(to_email, subject, html_content, lead_id=lead_id)


async def send_outreach_sms(to_phone: str, to_name: str, business_name: Optional[str] = None) -> bool:
    """Send initial approach/outreach SMS introducing services via Twilio"""
    settings = get_settings()
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_phone = settings.TWILIO_PHONE_NUMBER

    logger.info("Triggering outreach SMS", to_phone=to_phone, to_name=to_name)

    if not TWILIO_AVAILABLE or not account_sid or account_sid == "your_twilio_account_sid":
        logger.warning("Twilio SMS not configured. Mocking outreach SMS delivery.")
        return True

    try:
        client = TwilioClient(account_sid, auth_token)
        biz_str = f" for {business_name}" if business_name else ""
        message_body = (
            f"Hi {to_name}! This is Ojas from Reach Magnets. "
            f"We help businesses{biz_str} get more customers online using SEO, Ads, and custom websites. "
            f"I'm giving you a quick call right now to offer a free 15-min digital marketing audit. Hope to speak soon!"
        )
        
        message = client.messages.create(
            body=message_body,
            from_=from_phone,
            to=to_phone
        )
        logger.info("Twilio outreach SMS sent successfully", message_sid=message.sid)
        return True
    except Exception as e:
        logger.error("Error sending Twilio outreach SMS", error=str(e))
        return False


async def send_twice_daily_sms_followups() -> bool:
    """Find all active interested leads, send them a follow-up SMS with calendar link, limit to max 2 times"""
    from app.core.database import SessionLocal
    from app.models.lead import Lead
    from app.services import sms_service
    from app.core.config import get_settings
    from datetime import datetime
    
    settings = get_settings()
    db = SessionLocal()
    try:
        # Get active leads that are interested
        interested_leads = db.query(Lead).filter(
            Lead.status == "interested",
            Lead.is_active == True,
            Lead.phone != None
        ).all()
        
        logger.info(f"Found {len(interested_leads)} interested leads for follow-up")
        
        for lead in interested_leads:
            # Prevent spamming: count how many system follow-ups have been sent
            notes = lead.internal_notes or ""
            follow_ups_sent = notes.count("[System] Follow-up SMS sent")
            
            if follow_ups_sent >= 2:
                logger.info(f"Lead {lead.id} already received 2 follow-ups. Skipping.")
                continue
                
            # Draft and send SMS
            booking_url = settings.GMEET_LINK or "https://calendar.google.com/calendar/u/0/appointments/schedules/AcZssZ35QI8Gc4MbVP5DQSfV6bJ7xeH746aG8NnJyxNR95p07BHpHKMY6guW7V5fgZRsIZCDGaaHQawv"
            message_body = (
                f"Hi {lead.full_name or 'there'}, this is Ojas from Reach Magnets. "
                f"Just wanted to follow up and share the link to schedule your free 15-minute digital growth audit: "
                f"{booking_url}. Select a time that works best for you!"
            )
            
            logger.info(f"Sending follow-up SMS to {lead.full_name} ({lead.phone})")
            success = await sms_service.send(str(lead.phone), message_body)
            
            if success:
                # Update notes to record follow-up
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                notes_addon = f"\n[{timestamp}] [System] Follow-up SMS sent."
                lead.internal_notes = notes + notes_addon  # type: ignore
                db.commit()
                
        return True
    except Exception as e:
        logger.error("Error running twice daily SMS followups", error=str(e))
        return False
    finally:
        db.close()


