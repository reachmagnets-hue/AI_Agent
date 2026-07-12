import structlog
from app.utils.automations import send_appointment_email
from app.core.database import SessionLocal
from app.models.lead import Lead

logger = structlog.get_logger(__name__)

async def send_meeting_confirmation(prospect_name: str, prospect_phone: str, meeting_dt: str, services: str, lead_id: str = None):
    """
    Looks up lead's email address if lead_id is provided.
    Does NOT send emails to team@reachmagnets.com (only sends to actual prospects).
    """
    to_email = None
    if lead_id:
        db = SessionLocal()
        try:
            import uuid
            lead_uuid = uuid.UUID(lead_id) if isinstance(lead_id, str) else lead_id
            lead = db.query(Lead).filter(Lead.id == lead_uuid).first()
            if lead and lead.email:
                to_email = lead.email
        except Exception as e:
            logger.error("Error looking up lead email for confirmation", error=str(e))
        finally:
            db.close()
            
    if not to_email or to_email == "team@reachmagnets.com" or "reachmagnets" in to_email.lower():
        logger.info("Skipping email confirmation: No valid prospect email available and team emails are disabled.")
        return
        
    details = f"Discovery Call scheduled on {meeting_dt}.\nServices interested: {services}.\nCallback Phone: {prospect_phone}."
    await send_appointment_email(to_email, prospect_name, details)
