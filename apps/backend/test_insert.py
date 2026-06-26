from app.core.database import SessionLocal
from app.models.lead import Lead
import uuid

db = SessionLocal()
try:
    lead = Lead(
        full_name="Test Name",
        business_name="Test Business",
        business_type="Automotive",
        phone="+1234567890",
        city="Test City",
        state="TS",
        linkedin_url="https://linkedin.com/in/test",
        source="linkedin_scraper_simulated",
        status="pending"
    )
    db.add(lead)
    db.flush()
    db.commit()
    print("Success, ID:", lead.id)
except Exception as e:
    print("Error:", repr(e))
finally:
    db.close()
