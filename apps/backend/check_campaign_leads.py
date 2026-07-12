import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.campaign import Campaign
from app.models.lead import Lead

def check_db():
    db = SessionLocal()
    try:
        campaigns = db.query(Campaign).all()
        print(f"Total campaigns: {len(campaigns)}")
        for c in campaigns:
            leads = db.query(Lead).filter(Lead.campaign_id == c.id).all()
            pending = sum(1 for l in leads if l.status == "pending")
            calling = sum(1 for l in leads if l.status == "calling")
            failed = sum(1 for l in leads if l.status == "failed")
            completed = sum(1 for l in leads if l.status == "completed")
            print(f"Campaign: {c.name} (ID: {c.id})")
            print(f"  Status: {c.status}")
            print(f"  Total Leads: {len(leads)}")
            print(f"    Pending  : {pending}")
            print(f"    Calling  : {calling}")
            print(f"    Failed   : {failed}")
            print(f"    Completed: {completed}")
            for l in leads:
                print(f"      Lead: {l.full_name} | Phone: {l.phone} | Status: {l.status} | Notes: {l.internal_notes}")
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
