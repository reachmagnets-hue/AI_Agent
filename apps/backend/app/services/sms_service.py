import structlog
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

async def send(to_phone: str, message_text: str) -> bool:
    """Send custom SMS via Twilio Client"""
    settings = get_settings()
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_phone = settings.TWILIO_PHONE_NUMBER

    logger.info("Sending SMS via Twilio", to_phone=to_phone)

    if not TWILIO_AVAILABLE or not account_sid or account_sid == "your_twilio_account_sid" or "ACxxxx" in account_sid:
        logger.warning("Twilio SMS not configured or placeholder detected. Mocking SMS delivery.", body=message_text)
        return True

    try:
        client = TwilioClient(account_sid, auth_token)
        msg = client.messages.create(
            body=message_text,
            from_=from_phone,
            to=to_phone
        )
        logger.info("SMS sent successfully via Twilio", message_sid=msg.sid)
        return True
    except Exception as e:
        logger.error("Error sending SMS via Twilio", error=str(e))
        return False
