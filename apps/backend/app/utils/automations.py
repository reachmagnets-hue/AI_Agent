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

async def send_smtp_email_direct(to_email: str, subject: str, html_content: str) -> bool:
    """Send standard email via secure SMTP client connection"""
    global SMTP_LOCK
    if SMTP_LOCK is None:
        SMTP_LOCK = asyncio.Lock()

    settings = get_settings()
    host = settings.SMTP_HOST
    port = settings.SMTP_PORT
    user = settings.SMTP_USER
    password = settings.SMTP_PASSWORD
    sender = settings.SENDER_EMAIL or user or ""
    sender_name = settings.SENDER_NAME or "Reach Magnets"

    logger.info("Triggering SMTP email direct dispatch (waiting for queue lock)", to=to_email, host=host, port=port)

    if not user or not password:
        logger.warning("SMTP user or password not configured. Mocking SMTP email delivery.")
        logger.info(f"Mock SMTP Email payload:\nTo: {to_email}\nSubject: {subject}\nBody preview: {html_content[:200]}...")
        return True

    async with SMTP_LOCK:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{sender_name} <{sender}>"
            msg["To"] = to_email

            msg.attach(MIMEText(html_content, "html"))

            def sync_send():
                with smtplib.SMTP(host, port, timeout=10) as server:
                    server.starttls()
                    server.login(user, password)
                    server.sendmail(sender, to_email, msg.as_string())

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, sync_send)
            logger.info("SMTP email dispatched successfully", to=to_email)
            # Stagger emails by 45 seconds to prevent Gmail anti-bot suspension
            logger.info("Enforcing 45-second stagger delay before next SMTP dispatch...")
            await asyncio.sleep(45)
            return True
        except Exception as e:
            logger.error("Failed to send email via SMTP", error=str(e))
            # Minimal cool down sleep after error
            await asyncio.sleep(5)
            return False


async def send_appointment_email(to_email: str, to_name: str, appointment_details: str) -> bool:
    """Send appointment confirmation details via chosen Email Provider (Brevo or SMTP)"""
    settings = get_settings()
    sender_email = settings.SENDER_EMAIL
    sender_name = settings.SENDER_NAME

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
            <p>If you need to reschedule or have any questions, feel free to reply directly to this email or connect with us on WhatsApp.</p>
            <br>
            <p>Best regards,</p>
            <p><strong>Reach Magnets Team</strong></p>
        </body>
    </html>
    """

    if settings.EMAIL_PROVIDER == "smtp":
        return await send_smtp_email_direct(to_email, "Your Reach Magnets Appointment Details", html_content)

    api_key = settings.BREVO_API_KEY
    logger.info("Triggering Brevo appointment email", to_email=to_email, to_name=to_name)

    if not BREVO_AVAILABLE or not api_key or api_key == "your_brevo_api_key":
        logger.warning("Brevo email not configured. Mocking email delivery.")
        return True

    try:
        # Configure API key authorization
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
        
        sender = {"name": sender_name, "email": sender_email}
        to = [{"email": to_email, "name": to_name}]
        
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
                <p>If you need to reschedule or have any questions, feel free to reply directly to this email or connect with us on WhatsApp.</p>
                <br>
                <p>Best regards,</p>
                <p><strong>Reach Magnets Team</strong></p>
            </body>
        </html>
        """
        
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            sender=sender,
            to=to,
            subject="Your Reach Magnets Appointment Details",
            html_content=html_content
        )

        api_response = api_instance.send_transac_email(send_smtp_email)
        logger.info("Brevo email sent successfully", message_id=getattr(api_response, "message_id", "unknown"))
        return True
    except ApiException as e:
        logger.error("Exception when calling TransactionalEmailsApi->send_transac_email", error=str(e))
        return False
    except Exception as e:
        logger.error("Error sending Brevo email", error=str(e))
        return False


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


def render_outreach_email(to_name: str, business_name: Optional[str] = None, business_type: Optional[str] = None) -> tuple[str, str]:
    """
    Render outreach email body and subject based on the lead's niche (business_type).
    Returns (subject, html_content).
    """
    settings = get_settings()
    gmeet_link = getattr(settings, "GMEET_LINK", None)
    if gmeet_link and gmeet_link.strip():
        booking_url = gmeet_link
    else:
        booking_url = "https://calendar.google.com"
    
    biz_name_str = business_name.strip() if business_name else ""
    
    # Niche classification
    is_automotive = False
    if business_type:
        bt_lower = business_type.lower()
        auto_keywords = ["automotive", "car", "dealer", "repair", "auto", "mechanic", "tire", "garage", "collision", "service center"]
        if any(kw in bt_lower for kw in auto_keywords):
            is_automotive = True

    if is_automotive:
        subject = f"A humble perspective on {biz_name_str}'s local visibility gaps" if biz_name_str else "A humble perspective on your local visibility gaps"
        business_phrase = biz_name_str if biz_name_str else "your business"
        
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
    else:
        # General Niche template (Humble & human fallback)
        subject = f"A humble perspective on {biz_name_str}'s visibility gaps" if biz_name_str else "A humble perspective on your visibility gaps"
        business_phrase = biz_name_str if biz_name_str else "your business"
        
        body_content = f"""
        <p style="margin-top: 0; margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">Hi {to_name},</p>
        
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">I was recently reviewing search visibility for {business_phrase} and wanted to reach out regarding a few simple gaps in your online presence that might be costing you potential customers.</p>
        
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">We often see local businesses missing out because of a slow website, low local map search rankings, or missing search visibility on new AI assistant results (Generative Engine Optimization/GEO).</p>
        
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">We would love to put together a completely free, no-pressure digital marketing audit for you. Here is what we'll check:</p>
        
        <ul style="margin-bottom: 18px; padding-left: 20px; font-size: 15px; color: #222222; font-family: sans-serif; line-height: 1.5;">
            <li><strong>Visibility Audit:</strong> How your website and rankings are performing right now.</li>
            <li><strong>AI Search Assessment:</strong> Identifying missed search opportunities with AI recommendation engines.</li>
            <li><strong>Actionable Fixes:</strong> Specific speed and layout improvements to start seeing results faster.</li>
        </ul>
        
        <p style="margin-bottom: 14px; font-size: 15px; color: #222222; font-family: sans-serif;">It only takes about 15 minutes to review this together. You can pick a convenient time on my calendar here:</p>
        
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


async def send_outreach_email(to_email: str, to_name: str, business_name: Optional[str] = None, business_type: Optional[str] = None) -> bool:
    """Send initial approach/outreach email introducing services via chosen Email Provider (Brevo or SMTP)"""
    settings = get_settings()
    sender_email = settings.SENDER_EMAIL
    sender_name = settings.SENDER_NAME

    subject, html_content = render_outreach_email(to_name, business_name, business_type)

    if settings.EMAIL_PROVIDER == "smtp":
        return await send_smtp_email_direct(to_email, subject, html_content)

    api_key = settings.BREVO_API_KEY
    logger.info("Triggering Brevo outreach email", to_email=to_email, to_name=to_name)

    if not BREVO_AVAILABLE or not api_key or api_key == "your_brevo_api_key":
        logger.warning("Brevo email not configured. Mocking outreach email delivery.")
        return True

    try:
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
        
        sender = {"name": sender_name, "email": sender_email}
        to = [{"email": to_email, "name": to_name}]
        
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            sender=sender,
            to=to,
            subject=subject,
            html_content=html_content
        )

        api_response = api_instance.send_transac_email(send_smtp_email)
        logger.info("Brevo outreach email sent successfully", message_id=getattr(api_response, "message_id", "unknown"))
        return True
    except ApiException as e:
        logger.error("Exception when calling TransactionalEmailsApi->send_transac_email for outreach", error=str(e))
        return False
    except Exception as e:
        logger.error("Error sending Brevo outreach email", error=str(e))
        return False


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


