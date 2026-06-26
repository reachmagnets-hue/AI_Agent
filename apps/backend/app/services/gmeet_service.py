import structlog
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

async def book_slot(name: str, email: str, date: str, time: str) -> dict:
    """
    Returns the Google Meet / Google Calendar link for the meeting.
    Since this is a free Google Meet / Calendar setup, it returns the link
    without making complex API calls.
    """
    settings = get_settings()
    
    # Use user's configured Meet link or a fallback Meet homepage
    gmeet_link = getattr(settings, "GMEET_LINK", "https://meet.google.com")
    if gmeet_link is None or gmeet_link.strip() == "":
        gmeet_link = "https://meet.google.com"
        
    logger.info("Providing Google Meet link for booking request", name=name, email=email, date=date, time=time)
    
    return {
        "success": True,
        "date": date,
        "time": time,
        "link": gmeet_link
    }
