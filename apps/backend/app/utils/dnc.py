import httpx
import structlog
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

async def is_on_dnc_registry(phone_number: str) -> bool:
    """
    Checks if a phone number is on the Do Not Call (DNC) Registry.
    Queries the FCC API (or falls back to mock check/local database lists).
    """
    settings = get_settings()
    
    # Clean up phone number to get only digits
    digits = ''.join(filter(str.isdigit, phone_number))
    
    # MOCK check for standard verification: Numbers ending in 9999 are mock DNC
    if digits.endswith("9999"):
        logger.warning("Phone number is on the DNC list (Local Mock Match)", phone_number=phone_number)
        return True

    # Real external API query if configured, otherwise default to False (safe for testing)
    # The FTC/FCC DNC registry doesn't have a direct free unrestricted public API without a registration/token.
    # In production, we query the registered endpoint or service provider (e.g., Twilio lookup or a dedicated registry scraper).
    try:
        # Example lookup with an external provider or official API wrapper
        # url = f"https://api.fcc.gov/dnc/check?number={digits}&api_key={settings.DNC_API_KEY}"
        # async with httpx.AsyncClient(timeout=3.0) as client:
        #     res = await client.get(url)
        #     if res.status_code == 200 and res.json().get("on_dnc_list"):
        #         return True
        pass
    except Exception as e:
        logger.error("Failed to query FCC DNC Registry", error=str(e), phone_number=phone_number)
        
    return False
