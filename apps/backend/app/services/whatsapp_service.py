import httpx
import structlog
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

async def send(to_phone: str, message_text: str) -> bool:
    """Send WhatsApp message using Evolution API"""
    settings = get_settings()
    api_url = settings.EVOLUTION_API_URL
    api_key = settings.EVOLUTION_API_KEY
    instance = settings.EVOLUTION_INSTANCE

    logger.info("Sending WhatsApp message via Evolution API", to_phone=to_phone)

    # Clean phone number: Evolution API wants digits only
    clean_phone = "".join(filter(str.isdigit, to_phone))

    if not api_url or "localhost:8080" in api_url or not api_key or api_key == "your-secret-key":
        logger.warning("Evolution API not configured or placeholder detected. Mocking WhatsApp delivery.", body=message_text)
        return True

    try:
        url = f"{api_url}/message/sendText/{instance}"
        headers = {
            "apikey": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "number": clean_phone,
            "text": message_text
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code in [200, 201]:
                logger.info("WhatsApp message sent successfully via Evolution API")
                return True
            else:
                logger.error("Evolution API returned error", status_code=res.status_code, body=res.text)
                return False
    except Exception as e:
        logger.error("Error sending WhatsApp message via Evolution API", error=str(e))
        return False
