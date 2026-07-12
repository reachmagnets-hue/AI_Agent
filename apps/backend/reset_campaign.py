import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.models.call import Call

def reset_campaign_two():
    db = SessionLocal()
    try:
        # Find campaign "2"
        campaign = db.query(Campaign).filter(Campaign.name == "2").first()
        if not campaign:
            print("Campaign '2' not found.")
            return

        print(f"Resetting Campaign: {campaign.name} (ID: {campaign.id})")
        
        # Reset campaign status to draft
        setattr(campaign, "status", "draft")
        setattr(campaign, "started_at", None)
        setattr(campaign, "completed_at", None)

        # Reset all associated leads to pending
        leads = db.query(Lead).filter(Lead.campaign_id == campaign.id).all()
        for lead in leads:
            setattr(lead, "status", "pending")
            setattr(lead, "call_attempts", 0)
            setattr(lead, "total_calls", 0)
            setattr(lead, "internal_notes", None)
            setattr(lead, "last_called_at", None)
            print(f"  Reset Lead: {lead.phone} back to pending.")

        # Delete old calls logs for this campaign to avoid confusion
        deleted_calls = db.query(Call).filter(Call.campaign_id == campaign.id).delete()
        print(f"  Deleted {deleted_calls} simulated call log records.")

        db.commit()
        print("\nCampaign successfully reset! It is now in 'draft' status with 2 pending leads, ready to start.")
        
    except Exception as e:
        print(f"Error resetting campaign: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_campaign_two()
