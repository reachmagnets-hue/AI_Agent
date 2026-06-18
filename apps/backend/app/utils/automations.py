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


async def send_smtp_email_direct(to_email: str, subject: str, html_content: str) -> bool:
    """Send standard email via secure SMTP client connection"""
    settings = get_settings()
    host = settings.SMTP_HOST
    port = settings.SMTP_PORT
    user = settings.SMTP_USER
    password = settings.SMTP_PASSWORD
    sender = settings.SENDER_EMAIL or user
    sender_name = settings.SENDER_NAME or "Reach Magnets"

    logger.info("Triggering SMTP email direct dispatch", to=to_email, host=host, port=port)

    if not user or not password:
        logger.warning("SMTP user or password not configured. Mocking SMTP email delivery.")
        logger.info(f"Mock SMTP Email payload:\nTo: {to_email}\nSubject: {subject}\nBody preview: {html_content[:200]}...")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{sender_name} <{sender}>"
        msg["To"] = to_email

        msg.attach(MIMEText(html_content, "html"))

        import asyncio
        def sync_send():
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.starttls()
                server.login(user, password)
                server.sendmail(sender, to_email, msg.as_string())

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, sync_send)
        logger.info("SMTP email dispatched successfully", to=to_email)
        return True
    except Exception as e:
        logger.error("Failed to send email via SMTP", error=str(e))
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
        logger.info("Brevo email sent successfully", message_id=api_response.message_id)
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


async def send_outreach_email(to_email: str, to_name: str, business_name: Optional[str] = None) -> bool:
    """Send initial approach/outreach email introducing services via chosen Email Provider (Brevo or SMTP)"""
    settings = get_settings()
    sender_email = settings.SENDER_EMAIL
    sender_name = settings.SENDER_NAME

    biz_str = f" for {business_name}" if business_name else ""
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 8px;">
            <div style="text-align: center; margin-bottom: 20px;">
                <h1 style="color: #6C5DD3; margin: 0;">Reach Magnets</h1>
                <p style="color: #777; font-size: 14px; margin: 5px 0 0 0;">Digital Marketing & Customer Acquisition Specialists</p>
            </div>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            <p>Hello <strong>{to_name}</strong>,</p>
            <p>I hope you're having a productive day!</p>
            <p>I am reaching out from <strong>Reach Magnets</strong>{biz_str}. We specialize in helping local businesses scale their online presence, attract high-value prospects, and grow their revenue.</p>
            <p>Here is a quick overview of what we do:</p>
            <ul style="padding-left: 20px; color: #555;">
                <li style="margin-bottom: 8px;"><strong>Google Ads & PPC:</strong> Get found instantly by customers searching for your services.</li>
                <li style="margin-bottom: 8px;"><strong>Search Engine Optimization (SEO):</strong> Climb to the top page of Google search results organically.</li>
                <li style="margin-bottom: 8px;"><strong>Social Media Marketing:</strong> Engage your audience and build a loyal customer base.</li>
                <li style="margin-bottom: 8px;"><strong>Premium Web Development:</strong> Fast, responsive websites optimized for high conversion.</li>
                <li style="margin-bottom: 8px;"><strong>CRM & Automation Setup:</strong> Streamline your sales process and automatically follow up with leads.</li>
            </ul>
            <p>We would love to offer you a <strong>15-Minute Free Marketing Audit</strong> of your current online presence to show you exactly where you might be losing customers to competitors.</p>
            <p>Our sales representative, <strong>Sarah</strong>, will be giving you a call shortly to chat about this. Alternatively, if you'd like to schedule a time right now, please let us know!</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #777; text-align: center; margin: 0;">
                Reach Magnets Team &bull; <a href="mailto:team@reachmagnets.com" style="color: #6C5DD3; text-decoration: none;">team@reachmagnets.com</a>
            </p>
        </body>
    </html>
    """

    if settings.EMAIL_PROVIDER == "smtp":
        return await send_smtp_email_direct(to_email, "Boost your customer acquisition with Reach Magnets 🚀", html_content)

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
            subject="Boost your customer acquisition with Reach Magnets 🚀",
            html_content=html_content
        )

        api_response = api_instance.send_transac_email(send_smtp_email)
        logger.info("Brevo outreach email sent successfully", message_id=api_response.message_id)
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
            f"Hi {to_name}! This is Sarah from Reach Magnets. "
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

