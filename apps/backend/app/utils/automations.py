import os
import structlog
import httpx
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


async def send_appointment_email(to_email: str, to_name: str, appointment_details: str) -> bool:
    """Send appointment confirmation details via Brevo Transactional Email"""
    settings = get_settings()
    api_key = settings.BREVO_API_KEY
    sender_email = settings.SENDER_EMAIL
    sender_name = settings.SENDER_NAME

    logger.info("Triggering appointment email", to_email=to_email, to_name=to_name)

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
